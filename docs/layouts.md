# Your own form layout

By default the renderer emits the fields one after the other. To arrange them
yourself, bind the form and place each piece in a template.

## In a view

Override `get_form` and pass the bound form to your template:

```python
from pathlib import Path
from formidable.renderers import render_template

TEMPLATES = Path(__file__).parent / "templates"


class Claim(Form):
    def get_schema(self, request):
        return ClaimForm

    def get_form(self, request, values=None, errors=None):
        return render_template(
            "claim.pt", dirs=(str(TEMPLATES),),
            form=self.bind(request, values, errors))
```

Validation errors go through `get_form` as well, so the same template shows
them, with no further code.

## The template

```html
<form tal:attributes="form.attributes">
  ${form.form_errors()}

  <div class="row">
    <div class="col-md-6">${form['name']}</div>
    <div class="col-md-6">${form['email']}</div>
  </div>

  <h2>Address</h2>
  <div class="row">
    <div class="col-md-12">${form['address.street']}</div>
    <div class="col-md-4">${form['address.zip']}</div>
    <div class="col-md-8">${form['address.city']}</div>
  </div>

  ${form.buttons()}
</form>
${form.scripts()}
```

The `/custom` route in `ex.py` works like this.

`render_template` uses formidable's own settings, so `novalidate` and
`required` render correctly. If you use your own `PageTemplateLoader`, pass it
`boolean_attributes=HTML5_BOOLEAN_ATTRIBUTES` from `chameleon_rs.template`.

## What a bound form offers

| | |
|---|---|
| `form['name']` | The whole field: label, input, error, description and help |
| `form['address.city']` | A field inside a nested model |
| `form['users.0.name']` | A field inside a list row |
| `form['address']` | The whole fieldset of a nested model |
| `form['name'].title` | The field's title, honouring `ui:title` |
| `form['name'].name` | The field's dot path |
| `form.attributes` | The `<form>` attributes, for `tal:attributes` |
| `form.attrs` | The same as text, for Jinja2 or f-strings |
| `form.form_errors()` | The [summary of all errors](accessibility.md), with model-level errors |
| `form.error('name')` | The bare error message of a field |
| `form.errors` | All error messages, by dot path |
| `form.buttons()` | The buttons and the CSRF token |
| `form.csrf()` | Only the CSRF token, if you write your own buttons |
| `form.scripts()` | The scripts and styles the form needs |

Looping over `form` gives the top-level fields in model order:

```html
<div tal:repeat="field form" class="col-md-6">${field}</div>
```

## Things to watch out for

!!! warning "Place every field"
    A field you leave out isn't submitted. If it's required, validation fails,
    so the form can never be sent. `form.form_errors()` still names the field,
    which is why every layout should include it.

!!! warning "Keep `form.scripts()`"
    List rows, conditions, masks and background uploads all need it.

- **Place a nested field or its fieldset, not both.** `form['address']` already
  contains `form['address.city']`, and the name would be submitted twice.
- **List rows you place yourself are fixed.** `form['users.0.name']` renders
  that row, but only `form['users']` has the add and remove buttons.
- **Don't name a template variable `attrs`.** Chameleon reserves it.
- **`<form ${form.attrs}>` doesn't work in Chameleon**, because an expression
  can't stand where an attribute belongs. Use `tal:attributes="form.attributes"`.

## Other template engines

Fields implement `__html__`, so Jinja2 doesn't escape them. Jinja2 and plain
f-strings can write `form.attrs` directly into the tag:

```python
f"""<form {form.attrs}>
  {form.form_errors()}
  <div class="left">{form["name"]}</div>
  {form.buttons()}
</form>
{form.scripts()}"""
```
