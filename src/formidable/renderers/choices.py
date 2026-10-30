"""Choice widgets: select, radio group, multi-select.

All three share the same choice sources — `Literal[...]` args or
`enum.Enum` members — and Pydantic validates the submitted value
against those same choices, so a manipulated POST cannot smuggle in
an unknown option.
"""

import enum
import typing as t
from dominate.tags import label, input_, div, span, fieldset, legend, select, option
from formidable.renderers.base import IFieldRenderer, classes, field_title


class SelectFieldRenderer(IFieldRenderer):
    """Renders `Literal[...]` and `enum.Enum` fields as a <select>."""

    def choices(self, field_type) -> list[tuple[str, str]]:
        if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
            return [(str(member.value), member.name.replace("_", " ").title())
                    for member in field_type]
        return [(str(v), str(v)) for v in t.get_args(field_type)]

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        if isinstance(value, enum.Enum):
            value = value.value
        current = None if value is None else str(value)

        attrs = {"name": name, "id": f"field-{name}"}
        if not self.optional:
            attrs["required"] = True
        if css := classes(theme.select, theme.invalid if error else ""):
            attrs["cls"] = css
        widget = select(**attrs)
        # a blank option so nothing is preselected silently; an empty
        # submission is dropped by normalization ("missing" / default)
        if self.optional or current is None:
            widget.add(option("", value=""))
        for choice, title in self.choices(field_type):
            option_attrs = {"value": choice}
            if choice == current:
                option_attrs["selected"] = True
            widget.add(option(title, **option_attrs))

        label_attrs = {"html_for": f"field-{name}"}
        if theme.label:
            label_attrs["cls"] = theme.label
        wrapper_attrs = {"cls": theme.wrapper} if theme.wrapper else {}
        field = div(
            label(field_title(field_info, name), **label_attrs),
            widget,
            **wrapper_attrs,
        )
        if error:
            field.add(span(error, cls=classes("field-error", theme.error)))
        return field


class RadioFieldRenderer(SelectFieldRenderer):
    """The same choice sources as SelectFieldRenderer, rendered as a
    radio group.

    Not dispatched automatically — selects are the default for choice
    fields; opt in per field via `custom_widgets={"field": RadioFieldRenderer}`,
    per type via `widgets`, or in the schema via
    `json_schema_extra={"widget": "radio"}`.
    """

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        if isinstance(value, enum.Enum):
            value = value.value
        current = None if value is None else str(value)

        legend_attrs = {"cls": theme.legend} if theme.legend else {}
        group = fieldset(
            legend(field_title(field_info, name), **legend_attrs),
            cls=classes("field-radiogroup", theme.fieldset))
        for index, (choice, title) in enumerate(self.choices(field_type)):
            attrs = {
                "type": "radio",
                "name": name,
                "value": choice,
                "id": f"field-{name}-{index}",
            }
            if not self.optional:
                attrs["required"] = True
            if choice == current:
                attrs["checked"] = True
            if css := classes(theme.checkbox, theme.invalid if error else ""):
                attrs["cls"] = css
            group.add(div(
                input_(**attrs),
                label(title, html_for=f"field-{name}-{index}"),
                cls="field-radio-option",
            ))
        if error:
            group.add(span(error, cls=classes("field-error", theme.error)))
        return group


class MultiSelectFieldRenderer(SelectFieldRenderer):
    """Renders `list[Literal[...]]` / `list[Enum]` as a multi-select.

    The browser submits one repeated key per selection; the form layer
    folds those back into a list before validation.
    """

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        errors = errors or {}
        # one widget represents the whole list: item errors
        # ("interests.0") surface here as well
        error = errors.get(name) or next(
            (msg for key, msg in errors.items()
             if key.startswith(f"{name}.")), None)
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str
        current = set()
        for item in (value or []):
            if isinstance(item, enum.Enum):
                item = item.value
            current.add(str(item))

        attrs = {"name": name, "id": f"field-{name}", "multiple": True}
        if field_info.is_required():
            attrs["required"] = True
        if css := classes(theme.select, theme.invalid if error else ""):
            attrs["cls"] = css
        widget = select(**attrs)
        for choice, title in self.choices(item_annotation):
            option_attrs = {"value": choice}
            if choice in current:
                option_attrs["selected"] = True
            widget.add(option(title, **option_attrs))

        label_attrs = {"html_for": f"field-{name}"}
        if theme.label:
            label_attrs["cls"] = theme.label
        wrapper_attrs = {"cls": theme.wrapper} if theme.wrapper else {}
        field = div(
            label(field_title(field_info, name), **label_attrs),
            widget,
            **wrapper_attrs,
        )
        if error:
            field.add(span(error, cls=classes("field-error", theme.error)))
        return field
