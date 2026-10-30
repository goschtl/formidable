# UI schemas

A `ui_schema.json` adds presentation to a model without touching it. It maps
dot paths to `ui:*` entries, with `items` standing in for list rows:

```json
{
  "kosten": {"ui:unit": "EUR", "ui:help": "Bitte Belege beifügen."},
  "users.items.street": {"ui:title": "Straße"}
}
```

```python
from formidable.ui import load_ui, parse_ui

FormRenderer(ui=load_ui("ui_schema.json"))
FormRenderer(ui=parse_ui({"kosten": {"ui:unit": "EUR"}}))   # or from a dict
```

A UI schema decides how a field looks, never whether its value is valid. That
stays with the model. Unknown keys are ignored.

## Keys

| Key | Purpose |
|---|---|
| `ui:title` | Replaces the field's title |
| `ui:description` | Replaces the field's description |
| `ui:placeholder` | The input's placeholder |
| `ui:widget` | [Another widget](fields.md#choosing-another-widget) |
| `ui:options` | Choices with labels, as a list of `{"value": ..., "label": ...}` |
| `ui:help` | A help text below the field, escaped |
| `ui:unit` | A unit next to the input |
| `ui:mask` | Formats input while typing, see below |
| `ui:multiple` | Lets a file input take several files |
| `ui:accept` | Filters the file dialog, as a list of mime types |
| `ui:attributes` | Any further attributes, see below |
| `ui:conditions` | [Shows and hides the field](conditions.md) |
| `ui:condition_logic` | `or` (the default) or `and` |

## Attributes

`ui:attributes` go on the input, select or textarea, and on the fieldset of
nested models and lists. An attribute replaces a value the template already
sets, so `class` replaces the theme's classes.

`data-conditions`, `data-condition-logic`, `data-conditional-options` and
`data-not-required` go on the element around the field, where the conditions
script reads them.

## Masks

```json
{"nummer": {"ui:widget": "text",
            "ui:mask": {"mask": "99-9999", "mask_placeholder": "#"}}}
```

`9` stands for a digit, `a` for a letter and `*` for either; anything else is
inserted as it is. The mask also becomes the placeholder, here `##-####`.

!!! warning "A mask needs a `ui:widget`"
    Without a `ui:widget`, the mask is ignored, as it is in deform.

A mask only helps while typing, so validate the value in the model as well.
An incomplete value stays in the field and the model rejects it on submit.

## Files

`ui:multiple` needs a list in the model, and `ui:accept` is only a filter that
users can bypass, so check content types on the server if they matter. See
[File uploads](uploads.md).
