"""Bootstrap 5 theme plugin."""

from pathlib import Path

from formidable.themes import Theme


BOOTSTRAP = Theme(
    wrapper="mb-3",
    label="form-label",
    input="form-control",
    select="form-select",
    checkbox="form-check-input",
    input_group="input-group",
    unit="input-group-text",
    invalid="is-invalid",
    error="invalid-feedback d-block",
    hint="form-text",
    fieldset="border rounded p-3 mb-3",
    legend="fs-5 w-auto",
    button="btn btn-primary me-2",
    row_button="btn btn-outline-secondary btn-sm",
    container="container py-4",
    # checkboxes need a `.form-check` wrapper, the label after the input
    templates=(str(Path(__file__).parent / "bootstrap_templates"),),
    stylesheets=(
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    ),
)
