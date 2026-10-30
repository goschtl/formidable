import hmac
import secrets
import typing as t
from inspect import unwrap, getmembers, isroutine
from pydantic import BaseModel, ValidationError
from werkzeug.wrappers import Response
from formidable import i18n, themes
from formidable.data import unflatten, normalize
from formidable.renderers import CSRF_FIELD, FormRenderer


class Button(t.NamedTuple):
    type: str
    name: str
    title: str
    action: t.Callable
    validate: bool


class annotation:
    name: t.ClassVar[str] = "__annotations__"

    def __init__(self, **values):
        self.annotation = values

    @staticmethod
    def discriminator(component) -> Exception | None:
        if not isroutine(component):
            return TypeError(f"{component!r} is not a routine.")
        if component.__name__.startswith("_"):
            return NameError(f"{component!r} has a private name.")
        return None

    @classmethod
    def predicate(cls, component):
        if cls.discriminator(component) is not None:
            return False
        return True

    @classmethod
    def find(cls, obj_or_module):
        members = getmembers(obj_or_module, predicate=cls.predicate)
        for name, func in members:
            canonical = unwrap(func)
            if annotations := getattr(canonical, cls.name, False):
                yield annotations, func

    def __call__(self, func):
        canonical = unwrap(func)
        if error := self.discriminator(canonical):
            raise error
        setattr(canonical, self.name, self.annotation)
        return func


class trigger(annotation):
    name = "__form_trigger__"

    def __init__(self, name: str, title: str,
                 order: int = 0, validate: bool = False):
        super().__init__(name=name, title=title, order=order, validate=validate)


class Form:

    button_name: t.ClassVar[str] = "__trigger__"
    methods: t.ClassVar[tuple[str, ...]] = ("GET", "POST")
    theme: t.ClassVar[themes.Theme | None] = None  # None: site default
    error_messages: t.ClassVar[i18n.Catalog | None] = None  # None: site default
    # CSRF protection (double-submit cookie). Disable per view with
    # `csrf = False` when the hosting framework brings its own.
    csrf: t.ClassVar[bool] = True
    csrf_field: t.ClassVar[str] = CSRF_FIELD
    csrf_cookie: t.ClassVar[str] = "formidable-csrf"

    def __init__(self):
        triggers = sorted(
            tuple(trigger.find(self)),
            key=lambda x: (x[0]["order"], x[0]["name"])
        )
        self.buttons = {
            ann["name"]: Button(
                type=self.button_name,
                name=ann["name"],
                title=ann["title"],
                action=func,
                validate=ann.get("validate", False),
            )
            for ann, func in triggers
        }

    def get_schema(self, request) -> type[BaseModel]:
        raise NotImplementedError()

    def get_theme(self, request) -> themes.Theme:
        """The view's own theme, or the one registered via themes.use()."""
        if self.theme is not None:
            return self.theme
        return themes.current()

    def get_messages(self, request) -> i18n.Catalog:
        """The view's own catalog, or the one registered via i18n.use().

        Override to pick a catalog per request (e.g. Accept-Language).
        """
        if self.error_messages is not None:
            return self.error_messages
        return i18n.current()

    def get_renderer(self, request):
        return FormRenderer(theme=self.get_theme(request))

    def get_fields(self, request) -> t.Collection[str] | None:
        """The top-level fields to show; None for all of them."""
        return None

    def get_hidden(self, request) -> t.Mapping[str, t.Any] | None:
        """Values to carry along in hidden inputs."""
        return None

    def get_buttons(self, request) -> t.Iterable[Button]:
        return self.buttons.values()

    def configured_renderer(self, request) -> FormRenderer:
        renderer = self.get_renderer(request)
        renderer.messages = self.get_messages(request)
        return renderer

    def get_csrf_token(self, request) -> str | None:
        """The request's CSRF token: the cookie's, or a fresh one.

        Cached in the WSGI environ so form rendering and the
        Set-Cookie in __call__ agree within one request.
        """
        if not self.csrf:
            return None
        token = request.environ.get("formidable.csrf_token")
        if not token:
            token = request.cookies.get(self.csrf_cookie) \
                or secrets.token_urlsafe(32)
            request.environ["formidable.csrf_token"] = token
        return token

    def check_csrf(self, request) -> bool:
        cookie = request.cookies.get(self.csrf_cookie)
        submitted = request.form.get(self.csrf_field)
        return bool(cookie and submitted
                    and hmac.compare_digest(cookie, submitted))

    def get_data(self, request) -> dict[str, t.Any]:
        """Extract and normalize submitted form data.

        Strips the trigger marker, unflattens dot-path names
        (``users.0.name``) into nested dicts and lists, maps absent
        checkboxes to False and drops empty submissions so optional
        fields fall back to their defaults and required ones fail as
        "missing".
        """
        flat = {}
        for key, submitted in request.form.lists():
            if key in (self.button_name, self.csrf_field):
                continue
            # repeated keys (multi-selects, checkbox groups) stay lists
            flat[key] = submitted[0] if len(submitted) == 1 else submitted
        for key, storages in request.files.lists():
            # an empty file input submits a part with no filename: treat
            # it as absent so defaults apply
            chosen = [storage for storage in storages if storage.filename]
            if chosen:
                flat[key] = chosen[0] if len(chosen) == 1 else chosen
        data = unflatten(flat)
        return normalize(self.get_schema(request), data)

    def get_form(self, request, values=None, errors=None):
        schema = self.get_schema(request)
        renderer = self.configured_renderer(request)
        return renderer(schema, values=values, errors=errors,
                        buttons=self.get_buttons(request),
                        csrf_token=self.get_csrf_token(request),
                        only=self.get_fields(request),
                        hidden=self.get_hidden(request))

    def bind(self, request, values=None, errors=None):
        """A BoundForm for explicit field rendering in own templates.

        Typically used from an overridden get_form(), which may return
        the template output as a plain string.
        """
        renderer = self.configured_renderer(request)
        return renderer.bind(self.get_schema(request), values=values,
                             errors=errors, buttons=self.get_buttons(request),
                             csrf_token=self.get_csrf_token(request),
                             only=self.get_fields(request),
                             hidden=self.get_hidden(request))

    def get_readonly(self, request, values, buttons=()):
        """The values as text, for a summary or a confirmation page."""
        renderer = self.configured_renderer(request)
        return renderer(self.get_schema(request), values=values, readonly=True,
                        buttons=buttons,
                        csrf_token=self.get_csrf_token(request) if buttons else None)

    def render_response(self, html_form, request) -> Response:
        """Hook: wrap the rendered form in a full page if desired."""
        return Response(str(html_form), mimetype="text/html")

    def GET(self, request):
        return self.render_response(self.get_form(request), request)

    def POST(self, request):
        if self.csrf and not self.check_csrf(request):
            return Response("Invalid CSRF token.", status=403)
        # A trigger value may carry an argument: `remove_user:1`.
        name, _, arg = (request.form.get(self.button_name) or "").partition(":")
        btn = self.buttons.get(name) if name else None
        if btn is None:
            return Response("Unknown form action.", status=400)
        data = self.get_data(request)
        try:
            # A validating trigger receives the schema instance,
            # any other trigger the raw (normalized) data tree.
            if btn.validate:
                payload = self.get_schema(request)(**data)
            else:
                payload = data
            if arg:
                return btn.action(request, payload, arg)
            return btn.action(request, payload)
        except ValidationError as exc:
            errors = self.errors_of(exc, request)
            html_form = self.get_form(request, values=data, errors=errors)
            return self.render_response(html_form, request)

    def errors_of(self, exc: ValidationError, request) -> dict[str, str]:
        """Translated messages by dot path; "" for the form as a whole."""
        errors: dict[str, str] = {}
        messages = self.get_messages(request)
        for error in exc.errors():
            # a cross-field validator can bind its error to a field
            # by raising PydanticCustomError with {"field": "<path>"};
            # otherwise a model-level error renders at the form top
            ctx = error.get("ctx") or {}
            loc = ctx.get("field") or ".".join(
                str(part) for part in error["loc"])
            errors.setdefault(loc, i18n.translate(error, messages))
        return errors

    def __call__(self, request):
        if request.method not in self.methods:
            return Response(
                "Method Not Allowed",
                status=405,
                headers={"Allow": ", ".join(self.methods)},
            )
        endpoint = getattr(self, request.method, None)
        if endpoint is None:
            return Response(
                "Method Not Allowed",
                status=405,
                headers={"Allow": ", ".join(self.methods)},
            )
        response = endpoint(request)
        if self.csrf and isinstance(response, Response):
            token = self.get_csrf_token(request)
            if token and request.cookies.get(self.csrf_cookie) != token:
                response.set_cookie(
                    self.csrf_cookie, token,
                    httponly=True, samesite="Lax")
        return response
