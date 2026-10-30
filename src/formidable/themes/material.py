"""Materialize CSS (Material Design) theme plugin.

Materialize is structurally demanding: labels float over their inputs
and must follow them in the markup, so most templates are overridden.
"""

from pathlib import Path

from beartype.door import TypeHint

from formidable.renderers import IntFieldRenderer, StringFieldRenderer
from formidable.themes import Theme


class MaterialStringRenderer(StringFieldRenderer):
    """Text inputs: `.input-field` wrapper, label *after* the input;
    a floating label over a prefilled value needs `.active`."""

    template = "formidable/input_floating.pt"


class MaterialIntRenderer(IntFieldRenderer):
    template = "formidable/input_floating.pt"


MATERIAL = Theme(
    input="validate",
    # Materialize selects normally need JS init; browser-default skips it
    select="browser-default",
    checkbox="filled-in",
    unit="helper-text",
    invalid="invalid",
    error="helper-text red-text",
    hint="helper-text",
    legend="flow-text",
    button="btn waves-effect waves-light",
    row_button="btn-flat",
    container="container",
    summary="card-panel red lighten-4",
    status="card-panel green lighten-4",
    templates=(str(Path(__file__).parent / "material_templates"),),
    widgets={
        TypeHint(str): MaterialStringRenderer,
        TypeHint(int): MaterialIntRenderer,
    },
    stylesheets=(
        "https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css",
    ),
    scripts=(
        "https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js",
    ),
)
