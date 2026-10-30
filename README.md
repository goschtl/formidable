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
every element, template and widget overrides, asset URLs. Bootstrap 5 and
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
returns markup (`markupsafe.Markup`). It must render an input under its
`name` — extending a built-in renderer is the easiest way to stay
correct.

### Templates

All markup lives in [Chameleon](https://chameleon.readthedocs.io) page
templates, rendered by [chameleon-rs](https://mkennedy.codes/docs/chameleon-rs/),
under `src/formidable/templates/formidable/`:

```html
<div class="${classes(theme.wrapper)}">
  <label class="${classes(theme.label)}" for="field-${name}">${title}</label>
  <input class="${css}" id="field-${name}" name="${name}" required="${required}"
         step="${step}" type="${input_type}" value="${value}">
  ${render_partial('formidable/error.pt', error=error, theme=theme)}
</div>
```

To change the markup, copy a template and keep its relative path. Own
templates beat the theme's, which beat the built-ins:

```python
FormRenderer(templates=["myapp/templates"])     # myapp/templates/formidable/input.pt
Theme(templates=("mytheme/templates",))         # the same, as part of a theme
```

A renderer picks its template by name, so a new widget can be a single
line of Python plus a template:

```python
class StarsRenderer(IntFieldRenderer):
    template = "stars.pt"                       # myapp/templates/stars.pt
```

Values are HTML-escaped, except for `Markup` (rendered fields and
partials). Avoid `structure:` for anything a user can influence. Empty
attributes (`None`) disappear, `required`, `checked` and friends are
boolean attributes, and `classes(...)` merges class names, skipping
empty ones. A template sees the variables its renderer passes plus
`theme`; a partial only what is handed to it.

formidable never calls `chameleon_rs.configure()`, that setting belongs
to your application. Two consequences if you do use it: a
`formidable/...` file in your `template_folder` overrides the partial of
the same name, and `partial_search="registered"` is not supported, as it
hides formidable's own partials.

### UI schemas and conditional fields

A `ui_schema.json` adds presentation to a model without touching it:
titles, descriptions, help texts, placeholders, units, masks, widgets,
option labels, attributes and conditions, by dot path (`users.items.street` for list rows).

```python
from formidable.ui import load_ui

FormRenderer(ui=load_ui("ui_schema.json"))
```

Conditions render as `data-conditions`, and the form includes a small,
dependency-free script that shows and hides those fields. It clears and
disables what is hidden, so browsers don't submit it. All operators are
supported: `equals`, `not_equals`, `contains`, `not_contains`,
`starts_with`, `ends_with`, `greater_than`, `less_than`, `greater_equal`,
`less_equal`, `empty`, `not_empty`, `in`, `not_in`, as well as
`data-conditional-options` and `data-not-required` in own templates.

The browser only decides what is visible, so conditional requirements
still belong in a model validator. See `/rueckfrage` in `ex.py`.

`ui:attributes` go on the input, select or textarea, and on the fieldset
of nested models and lists. `data-conditions`, `data-condition-logic`,
`data-conditional-options` and `data-not-required` go on the element
around the field, where the script reads them. An attribute replaces a
value the template already sets, so `class` replaces the theme's classes.

`ui:unit` shows a unit next to the input, `ui:help` a help text below it.
File inputs take `ui:multiple` (use `list[UploadedFile]` in the model, or
`list[str]` with an upload URL, see below) and
`ui:accept`, which only filters the browser's file dialog: check the
content type on the server if it matters. `ui:mask`
(`{"mask": "99-9999", "mask_placeholder": "#"}`, with `9` a digit, `a` a
letter, `*` either) formats input while typing, and only applies together
with a `ui:widget`, as in deform. Validate the value in the model as well.

### Uploading files on their own

Normally files travel with the form, and are lost when validation fails.
With an upload URL, a file field whose model holds references (`str`,
`list[str]`) sends each file there as soon as it is chosen, with progress,
drag and drop and removal of single files, through the bundled
[FilePond](https://pqina.nl/filepond/). The form then submits only the ids,
and earlier uploads come back after a validation error. Fields declared as
`UploadedFile` or `FileUpload` stay in the form.

```python
class Claim(BaseModel):
    belege: list[str] = Field(..., title="Belege")

FormRenderer(
    ui=parse_ui({"belege": {"ui:widget": "file", "ui:multiple": True}}),
    upload_url="/upload",
    upload_options=i18n.UPLOAD_GERMAN,  # any further FilePond options
)
```

Storing the files is up to the application. The URL has to handle:

| Request | Purpose | Response |
|---|---|---|
| `POST` | store the file, a multipart part named like the field | the id, as plain text |
| `DELETE` | remove a file, the id is the request body | empty |
| `GET ?id=` | give a file back | the file, its name in `Content-Disposition` |

The form's CSRF token arrives in an `X-CSRF-Token` header. The ids are
user input like any other: generate them on the server and check on submit
that they belong to the user, or anyone could claim someone else's file.
Check size and type on the server too, and remove files no form was
submitted for. `Uploads` in `ex.py` is a small example, at `/upload-demo`.

`data-max-file-size` in `ui:attributes` limits the size in the browser, as
`ui:accept` does the type (mime types only, not extensions). A form using
this needs JavaScript, and carries FilePond inline, about 140 KB.

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
cd tests/js && npm install && npm test     # the browser scripts
```

CI runs both on Python 3.12 and 3.13 (GitHub Actions).

Requires Python ≥ 3.12. Built on Pydantic v2, chameleon-rs, beartype and
werkzeug.
