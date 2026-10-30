# Views and buttons

A view subclasses `formidable.views.Form`. `GET` renders the form and `POST`
handles a submit.

## Buttons

Buttons are methods, marked with `@trigger`:

```python
@trigger(name="save", title="Save", validate=True, order=0)
def save(self, request, data): ...

@trigger(name="draft", title="Save draft", order=1)
def draft(self, request, data): ...
```

With `validate=True`, the action receives the validated model instance, and
validation errors re-render the form automatically. Without it, the action
gets the raw, normalized data, which suits buttons that work on incomplete
input.

A button value can carry an argument: `value="remove:3"` calls
`action(request, data, "3")`.

## Hooks

Override these methods to change how a view behaves:

| Hook | Purpose |
|---|---|
| `get_schema(request)` | The model |
| `get_renderer(request)` | Widgets, theme, UI schema, upload URL, `novalidate` |
| `get_theme(request)` | Theme selection; falls back to `themes.use()` |
| `get_messages(request)` | Error messages; falls back to `i18n.use()` |
| `get_form(request, values, errors)` | The assembled form; override for [your own layout](layouts.md) |
| `get_readonly(request, values, buttons)` | The values [as text](readonly.md) |
| `get_fields(request)` | Which top-level fields to show; all by default |
| `get_buttons(request)` | Which buttons to show; all by default |
| `bind(request, values, errors)` | A bound form, for [your own layout](layouts.md) |
| `render_response(html_form, request)` | The page around the form |
| `get_csrf_token(request)` | Where the CSRF token comes from |

## The renderer

`get_renderer` returns a `FormRenderer`, which takes:

| Argument | Purpose |
|---|---|
| `theme` | The [theme](themes.md); defaults to the site-wide one |
| `ui` | A [UI schema](ui-schema.md) |
| `widgets` | Widgets by type |
| `custom_widgets` | Widgets by dot path |
| `templates` | Folders with [template overrides](templates.md) |
| `novalidate` | `True` by default; `False` turns browser validation back on |
| `upload_url` | Where [background uploads](uploads.md) go |
| `upload_options` | Further FilePond options |
| `upload_label` | The name a [read-only view](readonly.md) shows for an upload id |
| `messages` | Interface texts; `Form` views set this from `get_messages` |

## CSRF protection

CSRF protection is on by default and uses the double-submit cookie pattern. A
hidden `__csrf__` field must match the `formidable-csrf` cookie (HttpOnly,
SameSite=Lax), and a mismatch gets a 403. It needs no session storage.

Set `csrf = False` on a view if your framework already protects it. A
[hand-written form](layouts.md) gets the token from `form.buttons()`.
