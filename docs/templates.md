# Changing the markup

All markup lives in [Chameleon](https://chameleon.readthedocs.io) page
templates, rendered by chameleon-rs, under
`src/formidable/templates/formidable/`:

```html
<div class="${classes(theme.wrapper)}">
  <label class="${classes(theme.label)}" for="field-${name}">${title}</label>
  <input class="${css}" id="field-${name}" name="${name}" required="${required}"
         step="${step}" type="${input_type}" value="${value}">
  ${render_partial('formidable/error.pt', error=error, theme=theme)}
</div>
```

To arrange whole fields rather than change their markup, see
[Your own form layout](layouts.md).

## Overriding a template

Copy a template and keep its relative path. Your templates beat the theme's,
which beat the built-in ones:

```python
FormRenderer(templates=["myapp/templates"])   # myapp/templates/formidable/input.pt
Theme(templates=("mytheme/templates",))       # the same, as part of a theme
```

## Writing templates

- Values are HTML-escaped, except for `Markup` such as rendered fields and
  partials. Avoid `structure:` for anything a user can influence.
- Attributes set to `None` disappear. `required`, `checked` and similar are
  boolean attributes.
- `classes(...)` merges class names and skips empty ones.
- A template sees the variables its renderer passes, plus `theme`. A partial
  only sees what is handed to it.
- `attrs` is reserved by Chameleon. The built-in templates use `wrapper_attrs`
  and `control_attrs` for `ui:attributes`.

## If your application configures Chameleon

formidable never calls `chameleon_rs.configure()`, because that setting belongs
to your application. If you use it:

- A `formidable/...` file in your `template_folder` overrides the partial of
  the same name.
- `partial_search="registered"` isn't supported, because it hides formidable's
  own partials.
