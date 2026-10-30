"""Scalar widgets: text, number, temporal, password, textarea, file."""

import typing as t
from dominate.tags import label, input_, div, span, textarea
from formidable.renderers.base import (
    IFieldRenderer, TRUTHY, classes, field_title)


class InputFieldRenderer(IFieldRenderer):

    input_type: t.ClassVar[str] = "text"

    def format_value(self, value: t.Any) -> t.Any:
        return value

    def attributes(self, name: str, value: t.Any, invalid: bool = False) -> dict:
        attrs = {"type": self.input_type, "name": name, "id": f"field-{name}"}
        if not self.optional:
            attrs["required"] = True
        if value is not None:
            attrs["value"] = str(self.format_value(value))
        if css := classes(self.theme.input, self.theme.invalid if invalid else ""):
            attrs["cls"] = css
        return attrs

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        label_attrs = {"html_for": f"field-{name}"}
        if theme.label:
            label_attrs["cls"] = theme.label
        wrapper_attrs = {"cls": theme.wrapper} if theme.wrapper else {}
        field = div(
            label(field_title(field_info, name), **label_attrs),
            input_(**self.attributes(name, value, invalid=bool(error))),
            **wrapper_attrs,
        )
        if error:
            field.add(span(error, cls=classes("field-error", theme.error)))
        return field


class StringFieldRenderer(InputFieldRenderer):
    input_type = "text"


class EmailFieldRenderer(InputFieldRenderer):
    input_type = "email"


class IntFieldRenderer(InputFieldRenderer):
    input_type = "number"


class FloatFieldRenderer(InputFieldRenderer):
    input_type = "number"

    def attributes(self, name, value, invalid=False):
        attrs = super().attributes(name, value, invalid=invalid)
        attrs.setdefault("step", "any")
        return attrs


class DateFieldRenderer(InputFieldRenderer):
    input_type = "date"

    def format_value(self, value):
        return value.isoformat() if hasattr(value, "isoformat") else value


class DateTimeFieldRenderer(InputFieldRenderer):
    input_type = "datetime-local"

    def format_value(self, value):
        if hasattr(value, "isoformat"):
            return value.isoformat(timespec="minutes")
        return value


class TimeFieldRenderer(DateTimeFieldRenderer):
    input_type = "time"


class PasswordFieldRenderer(InputFieldRenderer):
    input_type = "password"

    def attributes(self, name, value, invalid=False):
        # secrets are never echoed back into the HTML
        return super().attributes(name, None, invalid=invalid)


class TextareaFieldRenderer(InputFieldRenderer):

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        attrs = {"name": name, "id": f"field-{name}"}
        if not self.optional:
            attrs["required"] = True
        if css := classes(theme.input, theme.invalid if error else ""):
            attrs["cls"] = css
        label_attrs = {"html_for": f"field-{name}"}
        if theme.label:
            label_attrs["cls"] = theme.label
        wrapper_attrs = {"cls": theme.wrapper} if theme.wrapper else {}
        field = div(
            label(field_title(field_info, name), **label_attrs),
            textarea("" if value is None else str(value), **attrs),
            **wrapper_attrs,
        )
        if error:
            field.add(span(error, cls=classes("field-error", theme.error)))
        return field


class BoolFieldRenderer(InputFieldRenderer):
    input_type = "checkbox"

    def attributes(self, name, value, invalid=False):
        # A checkbox is never marked `required`: an unchecked box submits
        # nothing, which the form layer normalizes to False.
        attrs = {
            "type": self.input_type,
            "name": name,
            "id": f"field-{name}",
            "value": "true",
        }
        if value in TRUTHY:
            attrs["checked"] = True
        if css := classes(self.theme.checkbox, self.theme.invalid if invalid else ""):
            attrs["cls"] = css
        return attrs


class FileFieldRenderer(InputFieldRenderer):
    input_type = "file"

    def attributes(self, name, value, invalid=False):
        # Browsers forbid prefilling file inputs, so never emit a value.
        return super().attributes(name, None, invalid=invalid)

    def render(self, name, field_info, field_type, value=None, errors=None):
        field = super().render(name, field_info, field_type,
                               value=None, errors=errors)
        if value:
            field.add(span(
                "Previous upload was discarded — please choose the file again.",
                cls=classes("field-hint", self.theme.hint)))
        if self.renderer is not None:
            self.renderer.needs_multipart = True
        return field
