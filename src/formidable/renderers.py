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


# --- Form Renderer using wired injection ---
class FormRenderer:

    def __init__(self):
        self.widgets = {
            TypeHint(str): StringFieldRenderer,
            TypeHint(int): IntFieldRenderer,
            TypeHint(bool): BoolFieldRenderer,
        }

    def resolve(annotation):
        hint = TypeHint(annotation)
        if isinstance(hint, UnionTypeHint):
            first = next(x for x in hint if x is not OPTIONAL)
            optional = OPTIONAL in hint
            return first, optional
        return hint, False

    def render(self, model_cls: type[BaseModel]):
        f = form(method="post")

        for name, model_field in model_cls.model_fields.items():
            annotation = model_field.annotation
            field_info = model_field
            field_title = field_info.title or name

            token, optional = self.resolve(annotation)
            widget = self.widgets.get(token)
            if widget:
                renderer: IFieldRenderer = widget(optional)
                f.add(renderer.render(name, field_info, annotation))
            else:
                f.add(div(f"⚠ No renderer for type: {annotation}"))
        return f
