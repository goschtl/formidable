# formidable

Generate HTML forms from [Pydantic](https://docs.pydantic.dev/) models —
rendering, parsing, validation, themes and i18n, with the model as the
single source of truth.

```python
from pydantic import BaseModel, Field
from werkzeug.wrappers import Response
from formidable.views import Form, trigger


class ContactForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


class Contact(Form):
    def get_schema(self, request):
        return ContactForm

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ContactForm instance
        return Response("thanks!", status=302,
                        headers={"Location": request.url})
```

`GET` renders the form; `POST` parses, validates and dispatches to the
pressed button's action. On validation errors the form re-renders with
the submitted values and per-field error messages.

See `ex.py` for a runnable demo (`uv run python ex.py`, then
<http://localhost:8000/> for Bootstrap and `/material` for Material).

## Features

### Schema-driven rendering

Every field of the model becomes a widget: `str` → text input,
`int`/`float`/`Decimal` → number input, `bool` → checkbox,
`date`/`datetime`/`time` → native picker inputs, `SecretStr` →
password (never echoed back), `bytes`/file types → file input,
`Literal[...]`/`Enum` → select, `list[Literal/Enum]` → multi-select,
nested `BaseModel` → fieldset, `list[X]` → repeatable rows.
`X | None` unions mark a field optional; required fields get the
`required` attribute, labels are linked via `for`/`id`, defaults and
submitted values are prefilled.

Cosmetic widget choices live in the schema, no code needed:

```python
bio: str = Field(..., json_schema_extra={"widget": "textarea"})
# also: "password", "email", "radio", "select"
```

### Server-side validation only

Forms render with `novalidate`: the browser never blocks a submit, and
Pydantic is the single validator (`FormRenderer(novalidate=False)`
turns browser validation back on). HTML form quirks are normalized
before validation:

* unchecked checkboxes become `False`,
* empty submissions are dropped — optional fields fall back to their
  defaults, required ones fail as *missing* ("Field required") instead
  of an unparsable empty string.

### Nested models and lists

Nesting is encoded in field names as dot paths (`users.0.name`) and
folded back into dicts/lists before validation. Indices may be sparse —
deleting a middle row still parses. Pydantic error locations flatten to
the same paths, so errors land on the exact nested input for free.

List fields render with client-side add/remove row buttons: a hidden
`<template>` holds a blank row and ~25 lines of dependency-free JS
(injected only when a form contains a list) clone it on demand. No
server round-trip, no reindexing.

### Buttons as triggers

Form buttons are methods, discovered and ordered automatically:

```python
@trigger(name="save", title="Save", validate=True, order=0)
def save(self, request, data): ...
```

With `validate=True` the action receives the validated model instance
and validation errors re-render the form centrally. Without it, the
action gets the raw (normalized) data tree — for buttons that operate
on incomplete input. A trigger value may carry an argument
(`value="remove:3"` calls `action(request, data, "3")`).

### File uploads

Two field types in `formidable.fields`:

* `UploadedFile` — the werkzeug `FileStorage` itself: a file-like
  `.stream` (spooled to disk for large uploads), `.filename`,
  `.content_type`, `.save(path)`. Prefer this for anything sizeable.
* `FileUpload` — the content eagerly read into `bytes`, for small blobs.

`enctype="multipart/form-data"` is added automatically when a form
contains a file widget. Empty file inputs count as "not submitted";
nested uploads (`docs.0.data`) work through the same dot paths. File
inputs never echo a value back; if validation fails elsewhere, the user
is told to re-select the file.

### Selects, radios and request-bound choices

`Literal[...]` and `enum.Enum` fields render as a `<select>` (with a
blank option so nothing is preselected silently). Radio groups use the
same choice sources — opt in per field:

```python
FormRenderer(custom_widgets={"salutation": RadioFieldRenderer})
```

For choices that depend on the request (deform's "deferred" pattern),
build the schema in `get_schema(request)` — it is called for rendering
*and* validation, so a manipulated POST cannot smuggle in an option the
request wasn't offered:

```python
def get_schema(self, request):
    flavors = available_flavors(request)   # DB, permissions, tenant ...
    return create_model("BoundForm", __base__=BaseForm,
                        flavor=(t.Literal[flavors], Field(...)))
```

### CSRF protection

On by default, using the double-submit cookie pattern: a hidden
`__csrf__` field must match the `formidable-csrf` cookie (HttpOnly,
SameSite=Lax), compared in constant time; mismatch or absence is a 403.
No session infrastructure required. Disable per view with
`csrf = False` when the hosting framework brings its own protection;
`get_csrf_token(request)` is the override point for custom token
sources.

### Error handling

Pydantic errors are routed by dot path to the exact widget: message
span plus an `invalid` class on the input. Model-level errors from
cross-field validators render at the top of the form — or bind
themselves to a field:

```python
@model_validator(mode="after")
def nickname_required_when_agreeing(self):
    if self.agree and not self.nickname:
        raise PydanticCustomError(
            "nickname_required",
            "When agreeing to the terms, a nickname is required.",
            {"field": "nickname"})   # <- renders at the nickname widget
    return self
```

### Themes as plugins

A `Theme` bundles everything a CSS framework needs: class names for
every element, structural widget overrides, asset URLs. Bootstrap 5 and
Materialize ship as plugins; a new theme is a ~30-line module.

```python
from formidable import themes
from formidable.themes.bootstrap import BOOTSTRAP

themes.use(BOOTSTRAP)                  # site-wide default, once at startup

class Admin(Form):
    theme = MATERIAL                   # per-view override

def get_theme(self, request): ...      # per-request (multi-tenant) hook
```

`page(html_form, theme, title=...)` wraps a form in a full HTML page
with the theme's stylesheets and scripts. Unthemed output is clean,
class-stable HTML you can style yourself.

### Translated error messages

Pydantic identifies errors by stable `type` strings; a catalog maps
them to templates with `{placeholders}` filled from the error context.
A German catalog ships in `formidable.i18n.GERMAN`; unknown types fall
back to Pydantic's English. Custom `PydanticCustomError` types
translate the same way.

```python
from formidable import i18n

i18n.use({**i18n.GERMAN, "nickname_required": "..."})  # site-wide
class Kontakt(Form):
    error_messages = {...}             # per-view
def get_messages(self, request): ...   # per-request (Accept-Language)
```

### Own templates: explicit field rendering

Instead of letting the renderer emit the whole `<form>`, bind the
schema and place each piece yourself — in Jinja2, Chameleon or plain
f-strings (fields implement `__html__`, so template engines don't
escape them):

```python
bound = self.bind(request, values, errors)   # in a Form view

f"""<form {bound.attrs}>
  {bound.form_errors()}
  <div class="left">{bound["name"]}</div>
  <div class="right">{bound["age"]}</div>
  {bound.buttons()}
</form>
{bound.scripts()}"""
```

`bound.attrs` already knows whether the form needs `enctype` or the
row script (fields are rendered at bind time), iteration yields the
fields in schema order, and `bound.error("name")` exposes raw messages
for fully custom error display. Override `get_form()` to return the
template output and the validation-error re-render automatically flows
through the same template — see the `/custom` route in `ex.py`.

### Custom widgets

Register per type or per field:

```python
FormRenderer(
    widgets={TypeHint(str): MyStringRenderer},        # by type
    custom_widgets={"name": MyNameRenderer},          # by dot path
)
```

A widget receives `(name, field_info, field_type, value, errors)` and
must render an input under its `name` — extending a built-in renderer
is the easiest way to stay correct.

## The hooks at a glance

| Hook | Purpose |
|---|---|
| `get_schema(request)` | the model — fields, validation, dynamic/request-bound forms |
| `@trigger(...)` methods | buttons and their actions |
| `get_renderer(request)` | widgets, theme, novalidate |
| `get_theme(request)` | theme selection (falls back to `themes.use()`) |
| `get_messages(request)` | error-message catalog (falls back to `i18n.use()`) |
| `get_form(request, ...)` | the assembled form — override for own templates |
| `bind(request, values, errors)` | a BoundForm for explicit field rendering |
| `render_response(html_form, request)` | page shell around the form |

## Development

```bash
uv sync
uv run pytest
uvx ruff check src/ tests/ ex.py
```

CI runs both on Python 3.12 and 3.13 (GitHub Actions).

Requires Python ≥ 3.12. Built on Pydantic v2, dominate, beartype and
werkzeug.
