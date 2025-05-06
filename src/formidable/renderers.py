from pydantic import BaseModel, Field
from dominate.tags import form, label, input_, div, button
from beartype.door import TypeHint, UnionTypeHint


# --- Interface for all field renderers ---
class IFieldRenderer:

    def __init__(self, optional: bool):
        self.optional = optional

    def render(self, name: str, field_info: Field, field_type: type):
        raise NotImplementedError


# --- Renderer implementations ---
class StringFieldRenderer(IFieldRenderer):
    def render(self, name, field_info, field_type):
        return div(label(field_info.title or name), input_(type="text", name=name))


class IntFieldRenderer(IFieldRenderer):
    def render(self, name, field_info, field_type):
        return div(label(field_info.title or name), input_(type="number", name=name))


class BoolFieldRenderer(IFieldRenderer):
    def render(self, name, field_info, field_type):
        return div(label(field_info.title or name), input_(type="checkbox", name=name))


OPTIONAL = TypeHint(None)
BASIC_WIDGETS = {
    TypeHint(str): StringFieldRenderer,
    TypeHint(int): IntFieldRenderer,
    TypeHint(bool): BoolFieldRenderer,
}



# --- Form Renderer using wired injection ---
class FormRenderer:

    widgets: dict[TypeHint, IFieldRenderer] = {**BASIC_WIDGETS}
    custom_widgets: dict[str, IFieldRenderer] | None = None

    def __init__(self,
                 widgets: dict[TypeHint, IFieldRenderer] | None = None,
                 custom_widgets: dict[str, IFieldRenderer] | None = None):
        if widgets:
            self.widgets.update(widgets)
        if custom_widgets:
            self.custom_widgets = custom_widgets

    def resolve(self, annotation):
        hint = TypeHint(annotation)
        if isinstance(hint, UnionTypeHint):
            first = next(x for x in hint if x is not OPTIONAL)
            optional = OPTIONAL in hint
            return first, optional
        return hint, False

    def __call__(self, model_cls: type[BaseModel]):
        f = form(method="post")

        for name, model_field in model_cls.model_fields.items():
            annotation = model_field.annotation
            field_info = model_field
            field_title = field_info.title or name
            token, optional = self.resolve(annotation)

            if self.custom_widgets and name in self.custom_widgets:
                widget = self.custom_widgets.get(name)
            else:
                widget = self.widgets.get(token)

            if widget is not None:
                renderer: IFieldRenderer = widget(optional)
                f.add(renderer.render(name, field_info, annotation))
            else:
                f.add(div(f"⚠ No renderer for type: {annotation}"))
        return f
