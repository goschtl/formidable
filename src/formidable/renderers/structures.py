"""Structural widgets: nested models and repeatable list rows."""

import typing as t
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from dominate.tags import div, span, fieldset, legend, button, html_tag
from formidable.renderers.base import (
    IFieldRenderer, classes, default_value, field_title)


class template(html_tag):
    """The HTML5 <template> tag, missing from dominate."""


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


class ModelFieldRenderer(IFieldRenderer):
    """Renders a nested BaseModel as a fieldset, one widget per field."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        legend_attrs = {"cls": theme.legend} if theme.legend else {}
        fs = fieldset(
            legend(field_title(field_info, name), **legend_attrs),
            cls=classes("field-model", theme.fieldset))
        for sub_name, sub_field in field_type.model_fields.items():
            fs.add(self.renderer.render_field(
                f"{name}.{sub_name}", sub_field,
                value=self.subvalue(value, sub_name, sub_field),
                errors=errors,
            ))
        if error := (errors or {}).get(name):
            fs.add(span(error, cls=classes("field-error", theme.error)))
        return fs

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

    def render(self, name, field_info, field_type, value=None, errors=None):
        theme = self.theme
        title = field_title(field_info, name)
        args = t.get_args(field_type)
        item_annotation = args[0] if args else str

        def item_row(index, num, item):
            item_info = FieldInfo.from_annotation(item_annotation)
            item_info.title = f"{title} #{num}"
            return div(
                self.renderer.render_field(
                    f"{name}.{index}", item_info, value=item, errors=errors),
                button("Remove", type="button",
                       cls=classes("formidable-remove-row", theme.row_button)),
                cls="field-list-item",
                data_index=str(index),
            )

        items = div(cls="field-list-items")
        for index, item in enumerate(value or []):
            items.add(item_row(index, index + 1, item))

        legend_attrs = {"cls": theme.legend} if theme.legend else {}
        fs = fieldset(
            legend(title, **legend_attrs),
            items,
            template(item_row(INDEX_PLACEHOLDER, NUM_PLACEHOLDER, None)),
            button("Add", type="button",
                   cls=classes("formidable-add-row", theme.row_button)),
            cls=classes("field-list", theme.fieldset),
        )
        if error := (errors or {}).get(name):
            fs.add(span(error, cls=classes("field-error", theme.error)))
        if self.renderer is not None:
            self.renderer.needs_script = True
        return fs
