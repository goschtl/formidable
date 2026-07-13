import typing as t
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from dominate.tags import (
    form, label, input_, div, span, fieldset, legend, button, script, html_tag)
from dominate.util import raw
from beartype.door import TypeHint, UnionTypeHint
from werkzeug.datastructures import FileStorage


class template(html_tag):
    """The HTML5 <template> tag, missing from dominate."""


OPTIONAL = TypeHint(None)

TRUTHY = frozenset(("true", "on", "1", "yes", True))


def resolve(annotation) -> tuple[TypeHint, bool]:
    """Unwrap `X | None` and `Annotated[X, ...]` annotations into
    (hint, optional)."""
    hint = TypeHint(annotation)
    optional = False
    if isinstance(hint, UnionTypeHint):
        optional = OPTIONAL in hint
        hint = next(x for x in hint if x != OPTIONAL)
    if getattr(hint.hint, "__metadata__", None) is not None:
        hint = TypeHint(hint.hint.__origin__)
    return hint, optional


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


class FileFieldRenderer(InputFieldRenderer):
    input_type = "file"

    def attributes(self, name, value):
        # Browsers forbid prefilling file inputs, so never emit a value.
        return super().attributes(name, None)

    def render(self, name, field_info, field_type, value=None, errors=None):
        field = super().render(name, field_info, field_type,
                               value=None, errors=errors)
        if value:
            field.add(span(
                "Previous upload was discarded — please choose the file again.",
                cls="field-hint"))
        if self.renderer is not None:
            self.renderer.needs_multipart = True
        return field


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


INDEX_PLACEHOLDER = "__index__"
NUM_PLACEHOLDER = "__num__"

LIST_SCRIPT = """
(function () {
  if (window.__formidable_rows) return;
  window.__formidable_rows = true;
  document.addEventListener("click", function (ev) {
    var add = ev.target.closest(".formidable-add-row");
    if (add) {
      var fs = add.closest(".field-list");
      var tpl = fs.querySelector(":scope > template");
      var items = fs.querySelector(":scope > .field-list-items");
      var next = 0;
      items.querySelectorAll(":scope > .field-list-item").forEach(function (el) {
        var i = parseInt(el.dataset.index, 10);
        if (!isNaN(i) && i >= next) next = i + 1;
      });
      var html = tpl.innerHTML
        .replaceAll("__index__", next)
        .replaceAll("__num__", next + 1);
      items.insertAdjacentHTML("beforeend", html);
      return;
    }
    var rm = ev.target.closest(".formidable-remove-row");
    if (rm) rm.closest(".field-list-item").remove();
    // no reindexing needed: the server accepts sparse indices
  });
})();
"""


class ListFieldRenderer(IFieldRenderer):
    """Renders `list[X]` as a fieldset of indexed sub-widgets with
    client-side add/remove row buttons (a <template> holds the blank row)."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        title = field_title(field_info, name)
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str

        def item_row(index, num, item):
            item_info = FieldInfo.from_annotation(item_annotation)
            item_info.title = f"{title} #{num}"
            return div(
                self.renderer.render_field(
                    f"{name}.{index}", item_info, value=item, errors=errors),
                button("Remove", type="button", cls="formidable-remove-row"),
                cls="field-list-item",
                data_index=str(index),
            )

        items = div(cls="field-list-items")
        for index, item in enumerate(value or []):
            items.add(item_row(index, index + 1, item))

        fs = fieldset(
            legend(title),
            items,
            template(item_row(INDEX_PLACEHOLDER, NUM_PLACEHOLDER, None)),
            button("Add", type="button", cls="formidable-add-row"),
            cls="field-list",
        )
        if error := (errors or {}).get(name):
            fs.add(span(error, cls="field-error"))
        if self.renderer is not None:
            self.renderer.needs_script = True
        return fs


BASIC_WIDGETS = {
    TypeHint(str): StringFieldRenderer,
    TypeHint(int): IntFieldRenderer,
    TypeHint(bool): BoolFieldRenderer,
    TypeHint(bytes): FileFieldRenderer,
    TypeHint(FileStorage): FileFieldRenderer,
}


class FormRenderer:

    def __init__(self,
                 widgets: dict[TypeHint, type[IFieldRenderer]] | None = None,
                 custom_widgets: dict[str, type[IFieldRenderer]] | None = None):
        self.widgets = {**BASIC_WIDGETS, **(widgets or {})}
        self.custom_widgets = {**(custom_widgets or {})}
        self.needs_script = False
        self.needs_multipart = False

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
        self.needs_script = False
        self.needs_multipart = False
        f = form(method="post")
        for name, model_field in model_cls.model_fields.items():
            if name in values:
                value = values[name]
            else:
                value = default_value(model_field)
            f.add(self.render_field(name, model_field, value=value, errors=errors))
        if self.needs_multipart:
            f["enctype"] = "multipart/form-data"
        if self.needs_script:
            f.add(script(raw(LIST_SCRIPT)))
        return f
