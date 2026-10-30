# Accessibility

Forms work with a keyboard and a screen reader without any extra code.

## Errors

When a form comes back with errors, a summary appears above it. It lists each
problem and links to its field, and it receives the focus, so screen reader
users hear about the problem right away and keyboard users can jump to it.

```html
<div autofocus="autofocus" class="form-errors" role="alert" tabindex="-1">
  <p class="form-errors-title">Please correct the following:</p>
  <ul>
    <li><a href="#field-name">Name: Field required</a></li>
  </ul>
</div>
```

Model-level errors appear in the same box. Its heading is the `ui_error_summary`
entry of the [catalog](translations.md), and themes style it through
`Theme.summary`.

## Fields

Each input points at the texts that belong to it:

```html
<input aria-describedby="field-name-error field-name-description"
       aria-invalid="true" id="field-name" name="name" required="required" type="text">
<span class="field-error" id="field-name-error">Field required</span>
<small class="field-description" id="field-name-description">Your full name</small>
```

- `aria-invalid` appears only when the field has an error.
- `aria-describedby` lists the error, description, help and hint that exist.
- Groups of radio buttons, nested models and lists are a `fieldset` with a
  `legend`, and carry `aria-describedby` on the `fieldset`.
- Labels are linked to their inputs through `for` and `id`.

## In your own templates

Templates receive `described_by` and `invalid`. A template that overrides a
built-in one should use them, and hand `name` to the partials so the ids exist:

```html
<input aria-describedby="${described_by}" aria-invalid="${invalid}"
       id="field-${name}" name="${name}" type="text">
${render_partial('formidable/error.pt', error=error, name=name, theme=theme)}
```

Older overrides without `name` keep working, but their error has no id for
`aria-describedby` to point at.

## The page language

Screen readers need the language of a page to pronounce it correctly, so tell
`page()`:

```python
page(html_form, theme, title="Unfallmeldung", lang="de")
```

## What this doesn't cover

These attributes are the foundation, not a certificate. Nobody has tested the
forms with a screen reader or audited them against BITV or WCAG. Check your
theme's colours as well, and remember that the "Add" and "Remove" buttons of
list rows are not yet translated.

The upload widget has its own interface from FilePond. The error and help texts
are linked to the group around it, not to its file input.
