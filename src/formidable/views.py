import typing as t
from collections.abc import MutableMapping
from inspect import unwrap, getmembers, isroutine
from pydantic import BaseModel, ValidationError
from dominate.tags import button
from werkzeug.wrappers import Request, Response
from formidable.renderers import FormRenderer


class Button(t.NamedTuple):
    type: str
    name: str
    title: str
    action: t.Callable


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

    def __init__(self, name: str, title: str, order: int = 0):
        super().__init__(name=name, title=title, order=order)


class Form:

    button_name: t.ClassVar[str] = "__trigger__"

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
                action=func
            )
            for ann, func in triggers
        }

    def get_schema(self, request) -> BaseModel:
        raise NotImplementedError()

    def get_renderer(self, request):
        return FormRenderer()

    def get_form(self, request):
        schema = self.get_schema(request)
        renderer = self.get_renderer(request)
        html_form = renderer(schema)
        for name, trigger in self.buttons.items():
            html_form.add(button(
                trigger.title,
                name=self.button_name,
                value=name,
            ))
        return html_form

    def GET(self, request):
        html_form = self.get_form(request)
        return Response(html_form.render(), mimetype="text/html")

    def POST(self, request):
        data = request.form.to_dict()
        if trigger := data.get(self.button_name):
            if endpoint := self.buttons.get(trigger):
                try:
                    return endpoint.action(request, data)
                except ValidationError as exc:
                    html_form = self.get_form(request)
                    return Response(
                        html_form.render(), mimetype="text/html")
        raise NotImplementedError('Action not found')

    def __call__(self, request):
        if endpoint := getattr(self, request.method):
            return endpoint(request)
        raise NotImplementedError("Unknow method.")
