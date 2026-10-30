"""Scalar widgets: text, number, temporal, password, textarea, file."""

import json
import typing as t
from formidable.renderers.base import (
    IFieldRenderer, TRUTHY, classes, field_title)


class InputFieldRenderer(IFieldRenderer):

    template = "formidable/input.pt"
    input_type: t.ClassVar[str] = "text"

    def format_value(self, value: t.Any) -> t.Any:
        return value

    def attributes(self, name: str, value: t.Any, invalid: bool = False) -> dict:
        """The template variables describing the input."""
        return {
            "input_type": self.input_type,
            "required": not self.optional,
            "step": None,
            "value": None if value is None else str(self.format_value(value)),
            "css": classes(self.theme.input,
                           self.theme.invalid if invalid else ""),
        }

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            **self.attributes(name, value, invalid=bool(error)),
        )


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
        attrs["step"] = "any"
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

    template = "formidable/textarea.pt"

    def attributes(self, name, value, invalid=False):
        attrs = super().attributes(name, value, invalid=invalid)
        attrs["value"] = "" if value is None else str(value)
        return attrs


class BoolFieldRenderer(InputFieldRenderer):
    template = "formidable/bool.pt"
    input_type = "checkbox"

    def attributes(self, name, value, invalid=False):
        # A checkbox is never marked `required`: an unchecked box submits
        # nothing, which the form layer normalizes to False.
        return {
            "value": "true",
            "checked": value in TRUTHY,
            "css": classes(self.theme.checkbox,
                           self.theme.invalid if invalid else ""),
        }


class FileFieldRenderer(InputFieldRenderer):
    template = "formidable/file.pt"
    input_type = "file"

    def attributes(self, name, value, invalid=False):
        # Browsers forbid prefilling file inputs, so never emit a value.
        return super().attributes(name, None, invalid=invalid)

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        if self.renderer is not None:
            self.renderer.needs_multipart = True
        hint = ("Previous upload was discarded — please choose the file again."
                if value else None)
        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            hint=hint,
            **self.attributes(name, None, invalid=bool(error)),
        )


class AsyncFileFieldRenderer(InputFieldRenderer):
    """Uploads each file on its own through FilePond. The field's value
    is what the upload URL answered: one id, or a list of them."""

    template = "formidable/file_async.pt"
    input_type = "file"

    def render(self, name, field_info, field_type, value=None, errors=None):
        error = (errors or {}).get(name)
        self.renderer.needs_uploads = True
        if not isinstance(value, list):
            value = [value] if value else []
        options = self.renderer.upload_options
        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            required=not self.optional,
            upload_url=self.renderer.upload_url,
            upload_files=json.dumps(value) if value else None,
            upload_options=json.dumps(options) if options else None,
        )
