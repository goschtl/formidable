"""Type resolution, shared helpers and the field renderer interface."""

import enum
import typing as t
from functools import lru_cache
from pathlib import Path
from chameleon_rs import PageTemplateLoader
from chameleon_rs.template import HTML5_BOOLEAN_ATTRIBUTES
from markupsafe import Markup
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from beartype.door import TypeHint, UnionTypeHint
from formidable.themes import Theme, DEFAULT
from formidable.ui import NO_UI, UIField


OPTIONAL = TypeHint(None)

TRUTHY = frozenset(("true", "on", "1", "yes", True))

CSRF_FIELD = "__csrf__"

TEMPLATES = Path(__file__).parent.parent / "templates"


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
            "placeholder": self.ui.placeholder,
            **context,
        }
        if self.renderer is not None:
            return self.renderer.render_template(template, **context)
        return render_template(template, theme=DEFAULT, **context)

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
