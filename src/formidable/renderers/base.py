"""Type resolution, shared helpers and the field renderer interface."""

import enum
import typing as t
from functools import lru_cache
from pathlib import Path

from beartype.door import TypeHint, UnionTypeHint
from chameleon_rs import PageTemplateLoader
from chameleon_rs.template import HTML5_BOOLEAN_ATTRIBUTES
from markupsafe import Markup
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from formidable import i18n
from formidable.themes import DEFAULT, Theme
from formidable.ui import NO_UI, UIField

OPTIONAL = TypeHint(None)

TRUTHY = frozenset(("true", "on", "1", "yes", True))

CSRF_FIELD = "__csrf__"

TEMPLATES = Path(__file__).parent.parent / "templates"

STATIC = Path(__file__).parent.parent / "static"
CONDITIONS_SCRIPT = (STATIC / "conditions.js").read_text(encoding="utf-8")
MASK_SCRIPT = (STATIC / "mask.js").read_text(encoding="utf-8")
UPLOAD_SCRIPTS = tuple(
    (STATIC / path).read_text(encoding="utf-8") for path in (
        "filepond/filepond.min.js",
        "filepond/filepond-plugin-file-validate-type.min.js",
        "filepond/filepond-plugin-file-validate-size.min.js",
        "upload.js",
    ))
UPLOAD_STYLE = (STATIC / "filepond/filepond.min.css").read_text(encoding="utf-8")


def classes(*parts: str) -> str | None:
    """Merge functional and theme class names, skipping empty ones.

    None when nothing is left: templates then drop the attribute."""
    return " ".join(part for part in parts if part) or None


@lru_cache
def loader(dirs: tuple[str, ...]) -> PageTemplateLoader:
    """A template loader searching `dirs`, then the built-in templates.

    Deliberately no `chameleon_rs.configure()`: that setting is
    process-wide and belongs to the host application.
    """
    return PageTemplateLoader(
        [*dirs, str(TEMPLATES)],
        boolean_attributes=HTML5_BOOLEAN_ATTRIBUTES,
        extra_builtins={"classes": classes},
        strict_tags=True,
    )


def render_template(template: str, /, dirs: tuple[str, ...] = (),
                    **context) -> Markup:
    return Markup(loader(dirs)[template](**context).strip())


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


def field_value(name: str, model_field: FieldInfo, values: dict) -> t.Any:
    """The submitted value for a field, or its schema default."""
    if name in values:
        return values[name]
    return default_value(model_field)


def widget_hint(model_field: FieldInfo) -> str | None:
    """A widget name declared in the schema:
    Field(..., json_schema_extra={"widget": "textarea"})."""
    extra = model_field.json_schema_extra
    if isinstance(extra, dict):
        return extra.get("widget")
    return None


def is_choice(hint) -> bool:
    if t.get_origin(hint) is t.Literal:
        return True
    return isinstance(hint, type) and issubclass(hint, enum.Enum)


class IFieldRenderer:
    """Interface for all field renderers."""

    template: t.ClassVar[str] = ""
    multiline: t.ClassVar[bool] = False  # read-only text keeps line breaks

    def __init__(self, optional: bool, renderer=None,
                 ui: UIField = NO_UI, description: str | None = None):
        self.optional = optional
        self.renderer = renderer  # the owning FormRenderer, if any
        self.ui = ui              # the field's UI schema entry
        self.description = description

    @property
    def theme(self) -> Theme:
        return self.renderer.theme if self.renderer is not None else DEFAULT

    def render_template(self, template: str, /, **context) -> Markup:
        context = {
            "conditions": self.ui.conditions_json,
            "description": self.description,
            "placeholder": self.ui.placeholder or (
                self.ui.active_mask.hint if self.ui.active_mask else None),
            "unit": self.ui.unit,
            "help": self.ui.help,
            "multiple": self.ui.multiple,
            "accept": self.ui.accept_value,
            "wrapper_attrs": self.ui.wrapper_attributes,
            "control_attrs": self.ui.control_attributes,
            **context,
        }
        name = context.get("name")
        context.setdefault("described_by", " ".join(
            f"field-{name}-{part}"
            for part in ("error", "description", "help", "hint")
            if context.get(part)) or None)
        context.setdefault("invalid", "true" if context.get("error") else None)
        if self.renderer is not None:
            return self.renderer.render_template(template, **context)
        return render_template(template, theme=DEFAULT, **context)

    def text(self, key: str, default: str, **values) -> str:
        messages = self.renderer.messages if self.renderer is not None else None
        return i18n.text(key, default, messages, **values)

    def display(self, value: t.Any, field_type: type) -> str | None:
        """The value as read-only text, None when there is nothing to show."""
        if value is None or value == "" or value == []:
            return None
        return str(value)

    def render_readonly(self, name: str, field_info: FieldInfo,
                        field_type: type, value: t.Any = None) -> Markup:
        """Render the field's value as text instead of a control."""
        return self.render_template(
            "formidable/readonly.pt",
            name=name,
            title=field_title(field_info, name),
            text=self.display(value, field_type),
            multiline=self.multiline,
        )

    def render(self,
               name: str,
               field_info: FieldInfo,
               field_type: type,
               value: t.Any = None,
               errors: dict[str, str] | None = None) -> Markup:
        """Render the field at dot path `name`, returning its markup.

        `errors` maps full dot paths to messages; a renderer picks its
        own message via `errors.get(name)`.
        """
        raise NotImplementedError
