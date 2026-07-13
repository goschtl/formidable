"""Materialize CSS (Material Design) theme plugin.

Materialize is structurally demanding: labels float over their inputs
and must follow them in the markup, so most widgets are overridden.
"""

from beartype.door import TypeHint
from dominate.tags import div, label, input_, span, p
from werkzeug.datastructures import FileStorage

from formidable.renderers import (
    BoolFieldRenderer,
    FileFieldRenderer,
    InputFieldRenderer,
    classes,
    field_title,
)
from formidable.themes import Theme


class MaterialInputRenderer(InputFieldRenderer):
    """Text-like inputs: `.input-field` wrapper, label *after* the
    input; a floating label over a prefilled value needs `.active`."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        label_attrs = {"html_for": f"field-{name}"}
        if value is not None:
            label_attrs["cls"] = "active"
        field = div(
            input_(**self.attributes(name, value, invalid=bool(error))),
            label(field_title(field_info, name), **label_attrs),
            cls="input-field",
        )
        if error:
            field.add(span(error, cls=classes("field-error", self.theme.error)))
        return field


class MaterialStringRenderer(MaterialInputRenderer):
    input_type = "text"


class MaterialIntRenderer(MaterialInputRenderer):
    input_type = "number"


class MaterialBoolRenderer(BoolFieldRenderer):
    """Checkboxes: the label wraps the input plus a text span."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        field = p(label(
            input_(**self.attributes(name, value, invalid=bool(error))),
            span(field_title(field_info, name)),
        ))
        if error:
            field.add(span(error, cls=classes("field-error", self.theme.error)))
        return field


class MaterialFileRenderer(FileFieldRenderer):
    """File inputs: a button holding the real input, next to a
    decorative text field Materialize fills with the chosen path."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        field = div(
            div(span(field_title(field_info, name)),
                input_(**self.attributes(name, None, invalid=bool(error))),
                cls="btn"),
            div(input_(cls="file-path validate", type="text"),
                cls="file-path-wrapper"),
            cls="file-field input-field",
        )
        if error:
            field.add(span(error, cls=classes("field-error", self.theme.error)))
        if value:
            field.add(span(
                "Previous upload was discarded — please choose the file again.",
                cls=classes("field-hint", self.theme.hint)))
        if self.renderer is not None:
            self.renderer.needs_multipart = True
        return field


MATERIAL = Theme(
    input="validate",
    checkbox="filled-in",
    invalid="invalid",
    error="helper-text red-text",
    hint="helper-text",
    legend="flow-text",
    button="btn waves-effect waves-light",
    row_button="btn-flat",
    container="container",
    widgets={
        TypeHint(str): MaterialStringRenderer,
        TypeHint(int): MaterialIntRenderer,
        TypeHint(bool): MaterialBoolRenderer,
        TypeHint(bytes): MaterialFileRenderer,
        TypeHint(FileStorage): MaterialFileRenderer,
    },
    stylesheets=(
        "https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css",
    ),
    scripts=(
        "https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js",
    ),
)
