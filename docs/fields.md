# Fields and widgets

Every field of the model becomes a widget:

| Type | Widget |
|---|---|
| `str` | Text input |
| `int`, `float`, `Decimal` | Number input |
| `bool` | Checkbox |
| `date`, `datetime`, `time` | Native date and time inputs |
| `SecretStr` | Password input, never echoed back |
| `UploadedFile`, `FileUpload` | [File input](uploads.md) |
| `Literal[...]`, `Enum` | Select |
| `list[Literal[...]]`, `list[Enum]` | Multi-select |
| A nested `BaseModel` | Fieldset |
| `list[X]` | Repeatable rows |

`X | None` makes a field optional. Required fields get the `required`
attribute, labels are linked to their inputs, and defaults and submitted
values are filled in.

## Choosing another widget

You can pick a widget in the model:

```python
bio: str = Field(..., json_schema_extra={"widget": "textarea"})
```

or, without touching the model, in a [UI schema](ui-schema.md) with
`ui:widget`. The names are `text`, `textarea`, `password`, `email`, `radio`,
`select`, `date`, `datetime`, `datetime-local`, `time`, `checkbox` and `file`.

## Nested models and lists

Nesting is encoded in field names as dot paths, such as `users.0.name`, and
folded back into dicts and lists before validation. Indices may have gaps, so
deleting a middle row still parses. Pydantic's error locations flatten to the
same paths, which puts each error at the right nested input.

List fields get add and remove buttons. A hidden `<template>` holds a blank
row and a small script clones it, with no server round-trip. The script is
only included when a form contains a list.

## Selects and radio groups

`Literal[...]` and `Enum` fields render as a `<select>` with a blank first
option, so nothing is preselected by accident. To show them as radio buttons,
use `ui:widget`, or register the widget for the field:

```python
FormRenderer(custom_widgets={"salutation": RadioFieldRenderer})
```

## Choices that depend on the request

Build the schema in `get_schema(request)`. It runs for both rendering and
validation, so a manipulated POST can't submit an option this request wasn't
offered:

```python
def get_schema(self, request):
    flavors = available_flavors(request)   # database, permissions, tenant ...
    return create_model("FlavorForm", __base__=BaseForm,
                        flavor=(t.Literal[flavors], Field(...)))
```

## Custom widgets

Register a renderer by type or by dot path:

```python
FormRenderer(
    widgets={TypeHint(str): MyStringRenderer},    # by type
    custom_widgets={"name": MyNameRenderer},      # by dot path
)
```

A widget receives `(name, field_info, field_type, value, errors)` and returns
`markupsafe.Markup`. It must render an input under its `name`, or the field is
never submitted. Extending a built-in renderer is the easiest way to get this
right, and a new widget can be one line of Python plus a template:

```python
class StarsRenderer(IntFieldRenderer):
    template = "stars.pt"     # found through FormRenderer(templates=[...])
```

See [Changing the markup](templates.md) for how templates are found.
