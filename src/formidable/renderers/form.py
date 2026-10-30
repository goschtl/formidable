"""The form renderer: widget registries, dispatch, whole-form and
bound (template-driven) rendering."""

import copy
import datetime
import typing as t
from decimal import Decimal
from os import PathLike
from pydantic import BaseModel, SecretStr
from pydantic.fields import FieldInfo
from beartype.door import TypeHint
from markupsafe import Markup
from werkzeug.datastructures import FileStorage
from formidable.themes import Theme, current
from formidable.ui import NO_UI, UIField, ui_path
from formidable.renderers.base import (
    CONDITIONS_SCRIPT, CSRF_FIELD, IFieldRenderer, field_title, field_value,
    is_choice, render_template, resolve, widget_hint)
from formidable.renderers.inputs import (
    BoolFieldRenderer, DateFieldRenderer, DateTimeFieldRenderer,
    EmailFieldRenderer, FileFieldRenderer, FloatFieldRenderer,
    IntFieldRenderer, PasswordFieldRenderer, StringFieldRenderer,
    TextareaFieldRenderer, TimeFieldRenderer)
from formidable.renderers.choices import (
    MultiSelectFieldRenderer, RadioFieldRenderer, SelectFieldRenderer)
from formidable.renderers.structures import (
    LIST_SCRIPT, ListFieldRenderer, ModelFieldRenderer)


BASIC_WIDGETS = {
    TypeHint(str): StringFieldRenderer,
    TypeHint(int): IntFieldRenderer,
    TypeHint(float): FloatFieldRenderer,
    TypeHint(Decimal): FloatFieldRenderer,
    TypeHint(bool): BoolFieldRenderer,
    TypeHint(bytes): FileFieldRenderer,
    TypeHint(FileStorage): FileFieldRenderer,
    TypeHint(datetime.date): DateFieldRenderer,
    TypeHint(datetime.datetime): DateTimeFieldRenderer,
    TypeHint(datetime.time): TimeFieldRenderer,
    TypeHint(SecretStr): PasswordFieldRenderer,
}

# widgets selectable per field from the schema, without code:
#   Field(..., json_schema_extra={"widget": "textarea"})
NAMED_WIDGETS = {
    "textarea": TextareaFieldRenderer,
    "password": PasswordFieldRenderer,
    "email": EmailFieldRenderer,
    "radio": RadioFieldRenderer,
    "select": SelectFieldRenderer,
    "text": StringFieldRenderer,
    "date": DateFieldRenderer,
    "datetime": DateTimeFieldRenderer,
    "datetime-local": DateTimeFieldRenderer,
    "time": TimeFieldRenderer,
    "checkbox": BoolFieldRenderer,
    "file": FileFieldRenderer,
}


class FormRenderer:

    def __init__(self,
                 widgets: dict[TypeHint, type[IFieldRenderer]] | None = None,
                 custom_widgets: dict[str, type[IFieldRenderer]] | None = None,
                 theme: Theme | None = None,
                 novalidate: bool = True,
                 templates: t.Iterable[str | PathLike] = (),
                 ui: t.Mapping[str, UIField] | None = None):
        if theme is None:
            theme = current()  # the theme registered site-wide
        # explicit `widgets` beat the theme's, which beat the defaults
        self.widgets = {**BASIC_WIDGETS, **dict(theme.widgets), **(widgets or {})}
        self.custom_widgets = {**(custom_widgets or {})}
        self.theme = theme
        # own templates beat the theme's, which beat the built-ins
        self.template_dirs = (*map(str, templates), *theme.templates)
        self.ui = ui or {}
        # Server-side validation is the source of truth: `novalidate`
        # stops the browser from blocking submits, while the `required`
        # attributes stay in the markup for accessibility and styling.
        self.novalidate = novalidate
        self.needs_script = False
        self.needs_multipart = False

    def dispatch(self, name: str, token: TypeHint,
                 model_field: FieldInfo | None = None,
                 ui: UIField = NO_UI) -> type[IFieldRenderer] | None:
        """Pick a widget: dot path, UI schema, schema hint, type, then
        structure."""
        if name in self.custom_widgets:
            return self.custom_widgets[name]
        hint_name = ui.widget
        if hint_name is None and model_field is not None:
            hint_name = widget_hint(model_field)
        # a checkbox with options is a group: left to the type dispatch
        if hint_name and not (hint_name == "checkbox" and ui.options):
            if named := NAMED_WIDGETS.get(hint_name):
                return named
        if widget := self.widgets.get(token):
            return widget
        hint = token.hint
        if is_choice(hint):
            return SelectFieldRenderer
        if t.get_origin(hint) is list:
            args = t.get_args(hint)
            if args and is_choice(resolve(args[0])[0].hint):
                return MultiSelectFieldRenderer
            return ListFieldRenderer
        if isinstance(hint, type) and issubclass(hint, BaseModel):
            return ModelFieldRenderer
        return None

    def render_template(self, template: str, /, **context) -> Markup:
        return render_template(template, dirs=self.template_dirs,
                               theme=self.theme, **context)

    def render_button(self, btn) -> Markup:
        return self.render_template(
            "formidable/button.pt",
            name=btn.type, value=btn.name, title=btn.title)

    def render_form_errors(self, errors: dict[str, str]) -> Markup | None:
        """Model-level errors (cross-field validators) have no field to
        attach to; they render in their own block."""
        if form_error := errors.get(""):
            return self.render_template(
                "formidable/form_errors.pt", error=form_error)
        return None

    def render_scripts(self) -> Markup | None:
        """The scripts this form needs, or None."""
        scripts = []
        if self.needs_script:
            scripts.append(LIST_SCRIPT)
        if any(ui.conditions for ui in self.ui.values()):
            scripts.append(CONDITIONS_SCRIPT)
        if not scripts:
            return None
        return Markup("\n").join(
            self.render_template("formidable/script.pt", code=code)
            for code in scripts)

    def bind(self,
             model_cls: type[BaseModel],
             values: dict[str, t.Any] | None = None,
             errors: dict[str, str] | None = None,
             buttons: t.Iterable = (),
             csrf_token: str | None = None) -> "BoundForm":
        """Bind a schema for explicit, template-driven field rendering."""
        return BoundForm(self, model_cls, values=values, errors=errors,
                         buttons=buttons, csrf_token=csrf_token)

    def render_field(self,
                     name: str,
                     model_field: FieldInfo,
                     value: t.Any = None,
                     errors: dict[str, str] | None = None):
        token, optional = resolve(model_field.annotation)
        path = ui_path(name)
        ui = self.ui.get(path, NO_UI)
        widget = self.dispatch(name, token, model_field, ui)
        if widget is None:
            return self.render_template(
                "formidable/unknown.pt", annotation=model_field.annotation)
        # list rows number their own titles
        if ui.title and not path.endswith(".items"):
            model_field = copy.copy(model_field)
            model_field.title = ui.title
        renderer: IFieldRenderer = widget(
            optional, self, ui=ui,
            description=ui.description or model_field.description)
        return renderer.render(
            name, model_field, token.hint, value=value, errors=errors)

    def csrf_input(self, csrf_token: str) -> Markup:
        return self.render_template(
            "formidable/csrf.pt", name=CSRF_FIELD, value=csrf_token)

    def __call__(self,
                 model_cls: type[BaseModel],
                 values: dict[str, t.Any] | None = None,
                 errors: dict[str, str] | None = None,
                 buttons: t.Iterable = (),
                 csrf_token: str | None = None) -> Markup:
        values = values or {}
        errors = errors or {}
        self.needs_script = False
        self.needs_multipart = False
        # fields first: they decide on the enctype and the row script
        fields = [
            self.render_field(
                name, model_field,
                value=field_value(name, model_field, values), errors=errors)
            for name, model_field in model_cls.model_fields.items()
        ]
        return self.render_template(
            "formidable/form.pt",
            enctype="multipart/form-data" if self.needs_multipart else None,
            novalidate=self.novalidate,
            csrf=self.csrf_input(csrf_token) if csrf_token else None,
            form_errors=self.render_form_errors(errors),
            fields=fields,
            buttons=[self.render_button(btn) for btn in buttons],
            script=self.render_scripts(),
        )


class BoundField:
    """One rendered field of a BoundForm.

    Safe for direct interpolation: template engines honoring the
    `__html__` protocol (Jinja2, Chameleon) will not escape it.
    """

    def __init__(self, name: str, title: str, html: str):
        self.name = name
        self.title = title
        self._html = html

    def __html__(self) -> str:
        return self._html

    def __str__(self) -> str:
        return self._html


class BoundForm:
    """A schema bound to values and errors for explicit rendering.

    Instead of letting FormRenderer emit the whole <form>, place the
    pieces yourself in any template::

        bound = renderer.bind(Schema, values=v, errors=e, buttons=btns)

        <form {{ bound.attrs }}>
          {{ bound.form_errors() }}
          <div class="left">{{ bound["name"] }}</div>
          <div class="right">{{ bound["age"] }}</div>
          {{ bound.buttons() }}
        </form>
        {{ bound.scripts() }}

    All fields are rendered eagerly at bind time so `attrs` already
    knows whether the form needs `enctype="multipart/form-data"` and
    whether `scripts()` has anything to contribute.
    """

    def __init__(self, renderer: FormRenderer, model_cls: type[BaseModel],
                 values=None, errors=None, buttons: t.Iterable = (),
                 csrf_token: str | None = None):
        self.renderer = renderer
        self.model_cls = model_cls
        self.values = values or {}
        self.errors = errors or {}
        self._buttons = tuple(buttons)
        self.csrf_token = csrf_token
        renderer.needs_script = False
        renderer.needs_multipart = False
        self._fields: dict[str, BoundField] = {}
        for name, model_field in model_cls.model_fields.items():
            value = field_value(name, model_field, self.values)
            html = renderer.render_field(
                name, model_field, value=value, errors=self.errors)
            self._fields[name] = BoundField(
                name, field_title(model_field, name), html)
        self.needs_multipart = renderer.needs_multipart
        self.needs_script = renderer.needs_script

    def __getitem__(self, name: str) -> BoundField:
        try:
            return self._fields[name]
        except KeyError:
            raise KeyError(
                f"{self.model_cls.__name__} has no field {name!r}; "
                f"available: {', '.join(self._fields)}") from None

    field = __getitem__

    def __iter__(self) -> t.Iterator[BoundField]:
        return iter(self._fields.values())

    @property
    def attrs(self) -> Markup:
        """Attributes for a hand-written <form> tag."""
        parts = ['method="post"']
        if self.needs_multipart:
            parts.append('enctype="multipart/form-data"')
        if self.renderer.novalidate:
            parts.append("novalidate")
        if self.renderer.theme.form:
            parts.append(f'class="{self.renderer.theme.form}"')
        return Markup(" ".join(parts))

    def form_errors(self) -> Markup:
        """The model-level error block, or empty."""
        return self.renderer.render_form_errors(self.errors) or Markup("")

    def error(self, name: str) -> str:
        """The raw error message for a field path, or empty."""
        return self.errors.get(name, "")

    def csrf(self) -> Markup:
        """The hidden CSRF input, or empty. Included in buttons()."""
        if self.csrf_token:
            return self.renderer.csrf_input(self.csrf_token)
        return Markup("")

    def buttons(self) -> Markup:
        """The form's trigger buttons (plus the CSRF token), themed."""
        parts = [self.csrf()] if self.csrf_token else []
        parts.extend(self.renderer.render_button(btn) for btn in self._buttons)
        return Markup("\n").join(parts)

    def scripts(self) -> Markup:
        """The row and conditions scripts, when the form needs them."""
        self.renderer.needs_script = self.needs_script
        return self.renderer.render_scripts() or Markup("")
