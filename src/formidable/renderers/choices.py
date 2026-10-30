"""Choice widgets: select, radio group, multi-select.

All three share the same choice sources — `Literal[...]` args or
`enum.Enum` members — and Pydantic validates the submitted value
against those same choices, so a manipulated POST cannot smuggle in
an unknown option.
"""

import enum
import typing as t
from formidable.renderers.base import IFieldRenderer, classes, field_title


class Option(t.NamedTuple):
    value: str
    title: str
    selected: bool = False


class SelectFieldRenderer(IFieldRenderer):
    """Renders `Literal[...]` and `enum.Enum` fields as a <select>."""

    template = "formidable/select.pt"

    def choices(self, field_type) -> list[tuple[str, str]]:
        if self.ui.options:
            return [(str(option.value), option.label)
                    for option in self.ui.options]
        if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
            return [(str(member.value), member.name.replace("_", " ").title())
                    for member in field_type]
        return [(str(v), str(v)) for v in t.get_args(field_type)]

    def display(self, value, field_type):
        if isinstance(value, enum.Enum):
            value = value.value
        if value is None or value == "":
            return None
        return dict(self.choices(field_type)).get(str(value), str(value))

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        if isinstance(value, enum.Enum):
            value = value.value
        current = None if value is None else str(value)

        options = []
        # a blank option so nothing is preselected silently; an empty
        # submission is dropped by normalization ("missing" / default)
        if self.optional or current is None:
            options.append(Option("", ""))
        options.extend(Option(choice, title, choice == current)
                       for choice, title in self.choices(field_type))
        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            options=options,
            multiple=False,
            required=not self.optional,
            css=classes(theme.select, theme.invalid if error else ""),
        )


class RadioFieldRenderer(SelectFieldRenderer):
    """The same choice sources as SelectFieldRenderer, rendered as a
    radio group.

    Not dispatched automatically — selects are the default for choice
    fields; opt in per field via `custom_widgets={"field": RadioFieldRenderer}`,
    per type via `widgets`, or in the schema via
    `json_schema_extra={"widget": "radio"}`.
    """

    template = "formidable/radio.pt"

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        error = (errors or {}).get(name)
        if isinstance(value, enum.Enum):
            value = value.value
        current = None if value is None else str(value)

        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            options=[Option(choice, title, choice == current)
                     for choice, title in self.choices(field_type)],
            required=not self.optional,
            css=classes(theme.checkbox, theme.invalid if error else ""),
        )


class MultiSelectFieldRenderer(SelectFieldRenderer):
    """Renders `list[Literal[...]]` / `list[Enum]` as a multi-select.

    The browser submits one repeated key per selection; the form layer
    folds those back into a list before validation.
    """

    def display(self, value, field_type):
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str
        items = value if isinstance(value, list) else [value] if value else []
        return ", ".join(filter(None, (
            super(MultiSelectFieldRenderer, self).display(item, item_annotation)
            for item in items))) or None

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

        return self.render_template(
            self.template,
            name=name,
            title=field_title(field_info, name),
            error=error,
            options=[Option(choice, title, choice in current)
                     for choice, title in self.choices(item_annotation)],
            multiple=True,
            required=field_info.is_required(),
            css=classes(theme.select, theme.invalid if error else ""),
        )
