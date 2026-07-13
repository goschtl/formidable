import typing as t
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from dominate.tags import form, label, input_, div, span, fieldset, legend
from beartype.door import TypeHint, UnionTypeHint


OPTIONAL = TypeHint(None)

TRUTHY = frozenset(("true", "on", "1", "yes", True))


def resolve(annotation) -> tuple[TypeHint, bool]:
    """Unwrap `X | None` annotations into (hint, optional)."""
    hint = TypeHint(annotation)
    if isinstance(hint, UnionTypeHint):
        first = next(x for x in hint if x != OPTIONAL)
        optional = OPTIONAL in hint
        return first, optional
    return hint, False


def field_title(field_info: FieldInfo, name: str) -> str:
    """Explicit title, or the last segment of the dot path."""
    return field_info.title or name.rsplit(".", 1)[-1]


def default_value(model_field: FieldInfo) -> t.Any:
    default = model_field.get_default(call_default_factory=True)
    return None if default is PydanticUndefined else default


# --- Interface for all field renderers ---
class IFieldRenderer:

    def __init__(self, optional: bool, renderer: "FormRenderer | None" = None):
        self.optional = optional
        self.renderer = renderer

    def render(self,
               name: str,
               field_info: FieldInfo,
               field_type: type,
               value: t.Any = None,
               errors: dict[str, str] | None = None):
        """Render the field at dot path `name`.

        `errors` maps full dot paths to messages; a renderer picks its
        own message via `errors.get(name)`.
        """
        raise NotImplementedError


# --- Renderer implementations ---
class InputFieldRenderer(IFieldRenderer):

    input_type: t.ClassVar[str] = "text"

    def attributes(self, name: str, value: t.Any) -> dict:
        attrs = {"type": self.input_type, "name": name, "id": f"field-{name}"}
        if not self.optional:
            attrs["required"] = True
        if value is not None:
            attrs["value"] = str(value)
        return attrs

    def render(self, name, field_info, field_type, value=None, errors=None):
        field = div(
            label(field_title(field_info, name), html_for=f"field-{name}"),
            input_(**self.attributes(name, value)),
        )
        if error := (errors or {}).get(name):
            field.add(span(error, cls="field-error"))
        return field


class StringFieldRenderer(InputFieldRenderer):
    input_type = "text"


class IntFieldRenderer(InputFieldRenderer):
    input_type = "number"


class BoolFieldRenderer(InputFieldRenderer):
    input_type = "checkbox"

    def attributes(self, name, value):
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
        return attrs


class ModelFieldRenderer(IFieldRenderer):
    """Renders a nested BaseModel as a fieldset, one widget per field."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        fs = fieldset(legend(field_title(field_info, name)), cls="field-model")
        for sub_name, sub_field in field_type.model_fields.items():
            fs.add(self.renderer.render_field(
                f"{name}.{sub_name}", sub_field,
                value=self.subvalue(value, sub_name, sub_field),
                errors=errors,
            ))
        if error := (errors or {}).get(name):
            fs.add(span(error, cls="field-error"))
        return fs

    @staticmethod
    def subvalue(container, key, model_field):
        if isinstance(container, BaseModel):
            return getattr(container, key)
        if isinstance(container, dict) and key in container:
            return container[key]
        return default_value(model_field)


class ListFieldRenderer(IFieldRenderer):
    """Renders `list[X]` as a fieldset of indexed sub-widgets."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        title = field_title(field_info, name)
        fs = fieldset(legend(title), cls="field-list")
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str
        for index, item in enumerate(value or []):
            item_info = FieldInfo.from_annotation(item_annotation)
            item_info.title = f"{title} #{index + 1}"
            fs.add(self.renderer.render_field(
                f"{name}.{index}", item_info,
                value=item, errors=errors,
            ))
        if error := (errors or {}).get(name):
            fs.add(span(error, cls="field-error"))
        return fs


BASIC_WIDGETS = {
    TypeHint(str): StringFieldRenderer,
    TypeHint(int): IntFieldRenderer,
    TypeHint(bool): BoolFieldRenderer,
}


class FormRenderer:

    def __init__(self,
                 widgets: dict[TypeHint, type[IFieldRenderer]] | None = None,
                 custom_widgets: dict[str, type[IFieldRenderer]] | None = None):
        self.widgets = {**BASIC_WIDGETS, **(widgets or {})}
        self.custom_widgets = {**(custom_widgets or {})}

    def dispatch(self, name: str, token: TypeHint) -> type[IFieldRenderer] | None:
        """Pick a widget: by dot path first, then type, then structure."""
        if name in self.custom_widgets:
            return self.custom_widgets[name]
        if widget := self.widgets.get(token):
            return widget
        hint = token.hint
        if t.get_origin(hint) is list:
            return ListFieldRenderer
        if isinstance(hint, type) and issubclass(hint, BaseModel):
            return ModelFieldRenderer
        return None

    def render_field(self,
                     name: str,
                     model_field: FieldInfo,
                     value: t.Any = None,
                     errors: dict[str, str] | None = None):
        token, optional = resolve(model_field.annotation)
        widget = self.dispatch(name, token)
        if widget is None:
            return div(f"⚠ No renderer for type: {model_field.annotation}")
        renderer: IFieldRenderer = widget(optional, self)
        return renderer.render(
            name, model_field, token.hint, value=value, errors=errors)

    def __call__(self,
                 model_cls: type[BaseModel],
                 values: dict[str, t.Any] | None = None,
                 errors: dict[str, str] | None = None):
        values = values or {}
        errors = errors or {}
        f = form(method="post")
        for name, model_field in model_cls.model_fields.items():
            if name in values:
                value = values[name]
            else:
                value = default_value(model_field)
            f.add(self.render_field(name, model_field, value=value, errors=errors))
        return f
