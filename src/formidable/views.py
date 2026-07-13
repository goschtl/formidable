import typing as t
from inspect import unwrap, getmembers, isroutine
from pydantic import BaseModel, ValidationError
from dominate.tags import button
from werkzeug.wrappers import Response
from formidable.data import unflatten, normalize
from formidable.renderers import FormRenderer


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

    def get_renderer(self, request):
        return FormRenderer()

    def get_data(self, request) -> dict[str, t.Any]:
        """Extract and normalize submitted form data.

        Strips the trigger marker, unflattens dot-path names
        (``users.0.name``) into nested dicts and lists, maps absent
        checkboxes to False and drops empty submissions for optional
        fields so their defaults apply.
        """
        flat = request.form.to_dict()
        flat.pop(self.button_name, None)
        for key, storage in request.files.items():
            # an empty file input submits a part with no filename: treat
            # it as absent so defaults apply
            if storage.filename:
                flat[key] = storage
        data = unflatten(flat)
        return normalize(self.get_schema(request), data)

    def get_form(self, request, values=None, errors=None):
        schema = self.get_schema(request)
        renderer = self.get_renderer(request)
        html_form = renderer(schema, values=values, errors=errors)
        for name, btn in self.buttons.items():
            html_form.add(button(
                btn.title,
                name=self.button_name,
                value=name,
            ))
        return html_form

    def GET(self, request):
        html_form = self.get_form(request)
        return Response(html_form.render(), mimetype="text/html")

    def POST(self, request):
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
            errors: dict[str, str] = {}
            for error in exc.errors():
                loc = ".".join(str(part) for part in error["loc"])
                errors.setdefault(loc, error["msg"])
            html_form = self.get_form(request, values=data, errors=errors)
            return Response(html_form.render(), mimetype="text/html")

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
        return endpoint(request)
