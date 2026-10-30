# Read-only views

Show the answers as text instead of controls, for a "please check" page, a
confirmation, or a record someone may only look at.

```python
class Claim(Form):
    @trigger(name="send", title="Send", validate=True)
    def send(self, request, data):
        save(data)
        return Response(self.get_readonly(request, data), mimetype="text/html")
```

Without a view, ask the renderer. `values` can be a dict or a validated model:

```python
FormRenderer(ui=ui)(ClaimForm, values=claim, readonly=True)
```

With buttons, the result is a `<form>` holding them and the CSRF token. Without
any, it's a plain `<div class="form-readonly">`, and no scripts are included.

## What each field shows

| Field | Shows |
|---|---|
| Text, numbers | The value, followed by `ui:unit` |
| Long text | The value, keeping its line breaks |
| Checkbox | Yes or No |
| Dates and times | Formatted by `ui_date_format` and `ui_datetime_format` |
| Select, radio | The option's label, not its value |
| Multi-select | The labels, separated by commas |
| Password | Dots, never the value |
| File | Its file name |
| Background upload | Whatever `upload_label` returns, otherwise the id |
| Nested model, list | A fieldset with the fields inside |
| Empty | A dash |

## Conditions

Fields hidden by [conditions](conditions.md) stay hidden. There's no browser
script here, so the server evaluates the conditions with the same rules, using
`formidable.conditions.is_visible`.

## Background uploads

An upload's id means nothing to a reader, so tell the renderer how to name it.
Only reveal names of files that belong to this user:

```python
FormRenderer(upload_url="/upload",
             upload_label=lambda upload_id: uploads.label(request, upload_id))
```

## Your own widgets and layout

A custom widget gets this for free. To change what it shows, override `display`:

```python
class StarsRenderer(IntFieldRenderer):
    def display(self, value, field_type):
        return "★" * int(value) if value else None
```

For a whole different appearance, override `render_readonly`, or copy
`formidable/readonly.pt` as described in [Changing the markup](templates.md).

Placing fields yourself also works:

```python
form = self.configured_renderer(request).bind(ClaimForm, values=data, readonly=True)
```
