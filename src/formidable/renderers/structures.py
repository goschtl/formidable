"""Structural widgets: nested models and repeatable list rows."""

import typing as t
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from formidable.renderers.base import (
    IFieldRenderer, default_value, field_title)


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
      document.dispatchEvent(new CustomEvent("formidable:rows"));
      return;
    }
    var rm = ev.target.closest(".formidable-remove-row");
    if (rm) {
      rm.closest(".field-list-item").remove();
      document.dispatchEvent(new CustomEvent("formidable:rows"));
    }
    // no reindexing needed: the server accepts sparse indices
  });
})();
"""


class ModelFieldRenderer(IFieldRenderer):
    """Renders a nested BaseModel as a fieldset, one widget per field."""

    template = "formidable/model.pt"

    def render(self, name, field_info, field_type, value=None, errors=None):
        # recursion stays in Python: widget dispatch needs the types
        fields = [
            self.renderer.render_field(
                f"{name}.{sub_name}", sub_field,
                value=self.subvalue(value, sub_name, sub_field),
                errors=errors,
            )
            for sub_name, sub_field in field_type.model_fields.items()
        ]
        return self.render_template(
            self.template,
            title=field_title(field_info, name),
            fields=fields,
            error=(errors or {}).get(name),
            wrapper_attrs=self.ui.attributes_without_conditions,
        )

    @staticmethod
    def subvalue(container, key, model_field):
        if isinstance(container, BaseModel):
            return getattr(container, key)
        if isinstance(container, dict) and key in container:
            return container[key]
        return default_value(model_field)


class ListFieldRenderer(IFieldRenderer):
    """Renders `list[X]` as a fieldset of indexed sub-widgets with
    client-side add/remove row buttons (a <template> holds the blank row)."""

    template = "formidable/list.pt"
    item_template: t.ClassVar[str] = "formidable/list_item.pt"

    def render(self, name, field_info, field_type, value=None, errors=None):
        title = field_title(field_info, name)
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str

        def item_row(index, num, item):
            item_info = FieldInfo.from_annotation(item_annotation)
            item_info.title = f"{title} #{num}"
            return self.render_template(
                self.item_template,
                index=index,
                field=self.renderer.render_field(
                    f"{name}.{index}", item_info, value=item, errors=errors),
            )

        rows = [item_row(index, index + 1, item)
                for index, item in enumerate(value or [])]
        if self.renderer is not None:
            self.renderer.needs_script = True
        return self.render_template(
            self.template,
            title=title,
            rows=rows,
            blank_row=item_row(INDEX_PLACEHOLDER, NUM_PLACEHOLDER, None),
            error=(errors or {}).get(name),
            wrapper_attrs=self.ui.attributes_without_conditions,
        )
