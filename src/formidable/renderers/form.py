"""The form renderer: widget registries, dispatch, whole-form and
bound (template-driven) rendering."""

import copy
import datetime
import typing as t
from decimal import Decimal
from os import PathLike

from beartype.door import TypeHint
from markupsafe import Markup
from pydantic import BaseModel, SecretStr
from pydantic.fields import FieldInfo
from werkzeug.datastructures import FileStorage

from formidable import i18n
from formidable.conditions import is_visible
from formidable.renderers.base import (
    CONDITIONS_SCRIPT,
    CSRF_FIELD,
    MASK_SCRIPT,
    UPLOAD_SCRIPTS,
    UPLOAD_STYLE,
    IFieldRenderer,
    field_title,
    field_value,
    is_choice,
    render_template,
    resolve,
    widget_hint,
)
from formidable.renderers.choices import (
    MultiSelectFieldRenderer,
    RadioFieldRenderer,
    SelectFieldRenderer,
)
from formidable.renderers.inputs import (
    AsyncFileFieldRenderer,
    BoolFieldRenderer,
    DateFieldRenderer,
    DateTimeFieldRenderer,
    EmailFieldRenderer,
    FileFieldRenderer,
    FloatFieldRenderer,
    IntFieldRenderer,
    PasswordFieldRenderer,
    StringFieldRenderer,
    TextareaFieldRenderer,
    TimeFieldRenderer,
)
from formidable.renderers.structures import (
    LIST_SCRIPT,
    ListFieldRenderer,
    ModelFieldRenderer,
)
from formidable.themes import Theme, current
from formidable.ui import NO_UI, UIField, ui_path

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


class ErrorItem(t.NamedTuple):
    path: str
    title: str
    message: str


def as_values(values: t.Any) -> dict[str, t.Any]:
    """Values as a dict, also from a validated model instance."""
    if isinstance(values, BaseModel):
        return {name: getattr(values, name) for name in type(values).model_fields}
    return values or {}


class FormRenderer:

    def __init__(self,
                 widgets: dict[TypeHint, type[IFieldRenderer]] | None = None,
                 custom_widgets: dict[str, type[IFieldRenderer]] | None = None,
                 theme: Theme | None = None,
                 novalidate: bool = True,
                 templates: t.Iterable[str | PathLike] = (),
                 ui: t.Mapping[str, UIField] | None = None,
                 upload_url: str | None = None,
                 upload_options: t.Mapping[str, t.Any] | None = None,
                 upload_label: t.Callable[[str], str] | None = None,
                 messages: i18n.Catalog | None = None):
        if theme is None:
            theme = current()  # the theme registered site-wide
        # explicit `widgets` beat the theme's, which beat the defaults
        self.widgets = {**BASIC_WIDGETS, **dict(theme.widgets), **(widgets or {})}
        self.custom_widgets = {**(custom_widgets or {})}
        self.theme = theme
        # own templates beat the theme's, which beat the built-ins
        self.template_dirs = (*map(str, templates), *theme.templates)
        self.ui = ui or {}
        # where file widgets holding references upload to, see dispatch()
        self.upload_url = upload_url
        self.upload_options = upload_options
        # what a read-only view shows for an upload id: its file name
        self.upload_label = upload_label
        self.messages = messages  # interface texts, None: the site-wide ones
        # Server-side validation is the source of truth: `novalidate`
        # stops the browser from blocking submits, while the `required`
        # attributes stay in the markup for accessibility and styling.
        self.novalidate = novalidate
        self.needs_script = False
        self.needs_multipart = False
        self.needs_uploads = False
        self.readonly = False
        self.values: t.Any = {}  # what the conditions of read-only fields see
        self.titles: dict[str, str] = {}

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
        is_group = hint_name == "checkbox" and ui.options
        if hint_name and not is_group and (named := NAMED_WIDGETS.get(hint_name)):
            if named is FileFieldRenderer and self.uploads_apart(token):
                return AsyncFileFieldRenderer
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

    def uploads_apart(self, token: TypeHint) -> bool:
        """Whether a file field gets uploaded on its own. The model decides:
        `list[UploadedFile]` wants the files, `list[str]` only references."""
        hint = token.hint
        if t.get_origin(hint) is list and (args := t.get_args(hint)):
            hint = resolve(args[0])[0].hint
        return bool(self.upload_url) and hint not in (FileStorage, bytes)

    def render_template(self, template: str, /, **context) -> Markup:
        return render_template(template, dirs=self.template_dirs,
                               theme=self.theme, **context)

    def render_button(self, btn) -> Markup:
        return self.render_template(
            "formidable/button.pt",
            name=btn.type, value=btn.name, title=btn.title)

    def text(self, key: str, default: str, **values) -> str:
        return i18n.text(key, default, self.messages, **values)

    def error_item(self, path: str, message: str) -> ErrorItem:
        """An entry of the error summary. An error on `tags.0` may belong to
        a widget for all of `tags`: it links to the closest field there is."""
        target = path
        while target not in self.titles and "." in target:
            target = target.rsplit(".", 1)[0]
        title = self.titles.get(target, path.rsplit(".", 1)[-1])
        return ErrorItem(target, title, message)

    def render_form_errors(self, errors: dict[str, str]) -> Markup | None:
        """All errors in one place, linking to their fields. Model-level
        errors (cross-field validators) have no field to attach to and
        only show here."""
        if not errors:
            return None
        return self.render_template(
            "formidable/form_errors.pt",
            heading=self.text("ui_error_summary",
                              "Please correct the following:"),
            error=errors.get(""),
            items=[self.error_item(path, message)
                   for path, message in errors.items() if path])

    def render_hidden(self, hidden: t.Mapping[str, t.Any] | None) -> list[Markup]:
        """Values for the conditions of a form showing only some fields."""
        return [
            self.render_template("formidable/csrf.pt", name=name, value=item)
            for name, value in (hidden or {}).items()
            for item in (value if isinstance(value, list) else [value])]

    def render_scripts(self) -> Markup | None:
        """The scripts this form needs, or None."""
        if self.readonly:
            return None
        scripts = []
        if self.needs_script:
            scripts.append(LIST_SCRIPT)
        if any(ui.needs_conditions_script for ui in self.ui.values()):
            scripts.append(CONDITIONS_SCRIPT)
        if any(ui.active_mask for ui in self.ui.values()):
            scripts.append(MASK_SCRIPT)
        if self.needs_uploads:
            scripts.extend(UPLOAD_SCRIPTS)
        if not scripts:
            return None
        parts = [self.render_template("formidable/script.pt", code=code)
                 for code in scripts]
        if self.needs_uploads:
            parts.insert(0, self.render_template(
                "formidable/style.pt", code=UPLOAD_STYLE))
        return Markup("\n").join(parts)

    def bind(self,
             model_cls: type[BaseModel],
             values: dict[str, t.Any] | None = None,
             errors: dict[str, str] | None = None,
             buttons: t.Iterable = (),
             csrf_token: str | None = None,
             readonly: bool = False,
             only: t.Collection[str] | None = None,
             hidden: t.Mapping[str, t.Any] | None = None) -> "BoundForm":
        """Bind a schema for explicit, template-driven field rendering."""
        return BoundForm(self, model_cls, values=values, errors=errors,
                         buttons=buttons, csrf_token=csrf_token,
                         readonly=readonly, only=only, hidden=hidden)

    def render_field(self,
                     name: str,
                     model_field: FieldInfo,
                     value: t.Any = None,
                     errors: dict[str, str] | None = None):
        token, optional = resolve(model_field.annotation)
        path = ui_path(name)
        ui = self.ui.get(path, NO_UI)
        if self.readonly and not is_visible(name, self.ui, self.values):
            return Markup("")
        widget = self.dispatch(name, token, model_field, ui)
        if widget is None:
            return self.render_template(
                "formidable/unknown.pt", annotation=model_field.annotation)
        # list rows number their own titles
        if ui.title and not path.endswith(".items"):
            model_field = copy.copy(model_field)
            model_field.title = ui.title
        self.titles[name] = field_title(model_field, name)
        renderer: IFieldRenderer = widget(
            optional, self, ui=ui,
            description=ui.description or model_field.description)
        if self.readonly:
            return renderer.render_readonly(
                name, model_field, token.hint, value=value)
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
                 csrf_token: str | None = None,
                 readonly: bool = False,
                 only: t.Collection[str] | None = None,
                 hidden: t.Mapping[str, t.Any] | None = None) -> Markup:
        """The whole form. `readonly` shows the values as text instead of
        controls, and `only` limits it to these top-level fields."""
        values = as_values(values)
        errors = errors or {}
        self.needs_script = False
        self.needs_multipart = False
        self.needs_uploads = False
        self.readonly = readonly
        self.values = values
        self.titles = {}
        # fields first: they decide on the enctype and the row script
        fields = [
            self.render_field(
                name, model_field,
                value=field_value(name, model_field, values), errors=errors)
            for name, model_field in model_cls.model_fields.items()
            if only is None or name in only
        ]
        buttons = tuple(buttons)
        if readonly and not buttons:
            return self.render_template(
                "formidable/form_readonly.pt", fields=fields)
        tokens = [self.csrf_input(csrf_token)] if csrf_token else []
        tokens.extend(self.render_hidden(hidden))
        return self.render_template(
            "formidable/form.pt",
            enctype="multipart/form-data" if self.needs_multipart else None,
            novalidate=self.novalidate,
            csrf=Markup("\n").join(tokens) if tokens else None,
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

        form = renderer.bind(Schema, values=v, errors=e, buttons=btns)

        <form tal:attributes="form.attributes">
          ${form.form_errors()}
          <div class="left">${form['name']}</div>
          <div class="right">${form['address.city']}</div>
          ${form.buttons()}
        </form>
        ${form.scripts()}

    Fields are looked up by dot path, so parts of nested models and list
    rows can go anywhere as well. All fields are rendered eagerly at bind
    time so `attributes` already knows whether the form needs
    `enctype="multipart/form-data"` and whether `scripts()` has anything
    to contribute.
    """

    def __init__(self, renderer: FormRenderer, model_cls: type[BaseModel],
                 values=None, errors=None, buttons: t.Iterable = (),
                 csrf_token: str | None = None, readonly: bool = False,
                 only: t.Collection[str] | None = None,
                 hidden: t.Mapping[str, t.Any] | None = None):
        self.renderer = renderer
        self.model_cls = model_cls
        self.values = as_values(values)
        self.errors = errors or {}
        self._buttons = tuple(buttons)
        self.csrf_token = csrf_token
        self.hidden = hidden
        renderer.readonly = readonly
        renderer.values = self.values
        renderer.titles = {}
        renderer.needs_script = False
        renderer.needs_multipart = False
        renderer.needs_uploads = False
        self._fields: dict[str, BoundField] = {}
        self._nested: dict[str, BoundField] = {}
        for name, model_field in model_cls.model_fields.items():
            if only is not None and name not in only:
                continue
            value = field_value(name, model_field, self.values)
            self._fields[name] = self._render(name, model_field, value)
        self.needs_multipart = renderer.needs_multipart
        self.needs_script = renderer.needs_script
        self.needs_uploads = renderer.needs_uploads

    def _render(self, name: str, model_field: FieldInfo, value) -> BoundField:
        html = self.renderer.render_field(
            name, model_field, value=value, errors=self.errors)
        ui = self.renderer.ui.get(ui_path(name), NO_UI)
        title = ui.title or field_title(model_field, name)
        return BoundField(name, title, html)

    def _resolve(self, path: str) -> tuple[FieldInfo, t.Any]:
        """The field at a dot path below the top level, and its value."""
        first, *rest = path.split(".")
        schema = self.model_cls
        if first not in schema.model_fields:
            raise self._unknown(path, schema)
        model_field = schema.model_fields[first]
        value = field_value(first, model_field, self.values)
        for part in rest:
            hint = resolve(model_field.annotation)[0].hint
            if isinstance(hint, type) and issubclass(hint, BaseModel):
                if part not in hint.model_fields:
                    raise self._unknown(path, hint)
                model_field = hint.model_fields[part]
                value = ModelFieldRenderer.subvalue(value, part, model_field)
            elif t.get_origin(hint) is list and part.isdigit():
                index = int(part)
                title = field_title(model_field, first)
                model_field = FieldInfo.from_annotation(t.get_args(hint)[0])
                model_field.title = f"{title} #{index + 1}"
                value = value[index] if value and index < len(value) else None
            else:
                raise KeyError(f"{self.model_cls.__name__} has no field "
                               f"{path!r}: nothing below {part!r}")
        return model_field, value

    def _unknown(self, path: str, schema: type[BaseModel]) -> KeyError:
        return KeyError(f"{schema.__name__} has no field {path!r}; "
                        f"available: {', '.join(schema.model_fields)}")

    def __getitem__(self, name: str) -> BoundField:
        if name in self._fields:
            return self._fields[name]
        if name not in self._nested:
            self._nested[name] = self._render(name, *self._resolve(name))
        return self._nested[name]

    field = __getitem__

    def __contains__(self, name: str) -> bool:
        return name in self._fields

    def __iter__(self) -> t.Iterator[BoundField]:
        return iter(self._fields.values())

    @property
    def attributes(self) -> dict[str, str]:
        """The attributes of a hand-written <form> tag, as Chameleon's
        `tal:attributes` takes them."""
        attributes = {"method": "post"}
        if self.needs_multipart:
            attributes["enctype"] = "multipart/form-data"
        if self.renderer.novalidate:
            attributes["novalidate"] = "novalidate"
        if self.renderer.theme.form:
            attributes["class"] = self.renderer.theme.form
        return attributes

    @property
    def attrs(self) -> Markup:
        """The same as text, for templates that can write into a tag:
        Jinja2 or f-strings, but not Chameleon."""
        return Markup(" ").join(
            Markup(name) if name == value
            else Markup('{}="{}"').format(name, value)
            for name, value in self.attributes.items())

    def form_errors(self) -> Markup:
        """All errors, linking to their fields, or empty. A field you did
        not place shows its message here as well."""
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
        parts.extend(self.renderer.render_hidden(self.hidden))
        parts.extend(self.renderer.render_button(btn) for btn in self._buttons)
        return Markup("\n").join(parts)

    def scripts(self) -> Markup:
        """The row and conditions scripts, when the form needs them."""
        self.renderer.needs_script = self.needs_script
        self.renderer.needs_uploads = self.needs_uploads
        return self.renderer.render_scripts() or Markup("")
