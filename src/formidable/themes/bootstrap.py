"""Bootstrap 5 theme plugin."""

from beartype.door import TypeHint
from dominate.tags import div, label, input_, span

from formidable.renderers import BoolFieldRenderer, classes, field_title
from formidable.themes import Theme


class BootstrapBoolRenderer(BoolFieldRenderer):
    """Bootstrap checkboxes need their own structure: a `.form-check`
    wrapper with the label *after* the input."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        field = div(
            input_(**self.attributes(name, value, invalid=bool(error))),
            label(field_title(field_info, name),
                  html_for=f"field-{name}", cls="form-check-label"),
            cls="mb-3 form-check",
        )
        if error:
            field.add(span(error, cls=classes("field-error", self.theme.error)))
        return field


BOOTSTRAP = Theme(
    wrapper="mb-3",
    label="form-label",
    input="form-control",
    checkbox="form-check-input",
    invalid="is-invalid",
    error="invalid-feedback d-block",
    hint="form-text",
    fieldset="border rounded p-3 mb-3",
    legend="fs-5 w-auto",
    button="btn btn-primary me-2",
    row_button="btn btn-outline-secondary btn-sm",
    container="container py-4",
    widgets={TypeHint(bool): BootstrapBoolRenderer},
    stylesheets=(
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    ),
)
