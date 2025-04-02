from typing import get_origin, get_args, Union
from pydantic import BaseModel, Field
from dominate.tags import form, label, input_, div, button
from wired import ServiceContainer


# --- Interface for all field renderers ---
class IFieldRenderer:
    def render(self, name: str, field_info: Field, field_type: type):
        raise NotImplementedError


# --- Custom tokens (you cannot use str, int, etc. directly) ---
class StringToken:
    pass


class IntToken:
    pass


class BoolToken:
    pass


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


# --- Map from Python types to our safe service tokens ---
type_token_map = {
    str: StringToken,
    int: IntToken,
    bool: BoolToken,
}


# --- Util: resolve Optional/Union[T, None] to T, and get token ---
def resolve_token(annotation):
    origin = get_origin(annotation)
    if origin is Union:
        # Extract first non-None type
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if args:
            annotation = args[0]
    return type_token_map.get(annotation)


# --- Form Renderer using wired injection ---
class FormRenderer:
    def __init__(self, container: ServiceContainer):
        self.container = container

    def render(self, model_cls: type[BaseModel]):
        f = form(action="/submit", method="post")

        for name, model_field in model_cls.model_fields.items():
            annotation = model_field.annotation
            field_info = model_field
            field_title = field_info.title or name

            token = resolve_token(annotation)

            if token:
                renderer: IFieldRenderer = self.container.get(token)
                f.add(renderer.render(name, field_info, annotation))
            else:
                f.add(div(f"⚠ No renderer for type: {annotation}"))

        f.add(button("Submit", type="submit"))
        return f
