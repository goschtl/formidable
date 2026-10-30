import datetime
import enum
import typing as t
from pathlib import Path
from fanstatic import Fanstatic, Library, Resource, get_library_registry
from js.jquery import jquery
from autoroutes import Routes as Autoroutes
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response
from pydantic import BaseModel, Field, create_model, model_validator
from pydantic_core import PydanticCustomError
from formidable.fields import UploadedFile
from formidable.views import Form, trigger
from formidable.renderers import FormRenderer, RadioFieldRenderer, StringFieldRenderer
from formidable import i18n, themes
from formidable.themes import page
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.themes.material import MATERIAL
from formidable.ui import load_ui
from ex_forms.LD_000_0V1100.model import LD_000_0V1100Model


themes.use(MATERIAL)  # the site-wide default
i18n.use(
    {
        **i18n.GERMAN,
        # application-defined error types translate the same way
        "nickname_required": "Wenn Sie den Bedingungen zustimmen, "
        "ist ein Spitzname erforderlich.",
    }
)

routes = Autoroutes()


class CustomFieldRenderer(StringFieldRenderer):
    """A custom widget must still render an input named `name`,
    otherwise the field is never submitted and validation always fails."""

    template = "custom_input.pt"


class User(BaseModel):
    id: int
    name: str = "Jane Doe"


class Salutation(enum.Enum):
    mr = "mr"
    mrs = "mrs"
    other = "other"


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    salutation: Salutation = Field(..., title="Salutation")
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")
    birthday: datetime.date | None = Field(None, title="Birthday")
    bio: str | None = Field(None, title="Bio", json_schema_extra={"widget": "textarea"})
    interests: list[t.Literal["sports", "music", "tech"]] = Field(
        default_factory=list, title="Interests"
    )
    avatar: UploadedFile | None = Field(None, title="Avatar")
    users: list[User] = Field(default_factory=list, title="Users")

    @model_validator(mode="after")
    def nickname_required_when_agreeing(self):
        if self.agree and not self.nickname:
            raise PydanticCustomError(
                "nickname_required",
                "When agreeing to the terms, a nickname is required.",
                {"field": "nickname"},
            )
        return self


def available_flavors(request) -> tuple[str, ...]:
    """A selection source that depends on the request — in real life a
    database query, the logged-in user's permissions, the tenant, ..."""
    flavors = ("vanilla", "chocolate", "strawberry")
    if "premium" in request.args:
        flavors += ("pistachio", "black truffle")
    return flavors


class Index(Form):
    def get_schema(self, request):
        # deform's "deferred" pattern: bind the schema to the request.
        # Validation then only accepts exactly these choices.
        flavors = available_flavors(request)
        return create_model(
            "RequestExampleForm",
            __base__=ExampleForm,
            flavor=(t.Literal[flavors], Field("vanilla", title="Flavor")),
        )

    def get_renderer(self, request):
        return FormRenderer(
            theme=self.get_theme(request),
            templates=[Path(__file__).parent / "ex_templates"],
            custom_widgets={
                "name": CustomFieldRenderer,
                # same choice source as the select, radio markup
                "salutation": RadioFieldRenderer,
            },
        )

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="formidable demo"),
            mimetype="text/html",
        )

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ExampleForm instance, not a raw dict.
        breakpoint()
        print(data)
        headers = {"Location": request.url}
        return Response(request.url, status=302, headers=headers)


class MaterialIndex(Index):
    theme = MATERIAL  # per-view override of the site default


# --- Explicit field rendering with an own template ---
class FeedbackForm(BaseModel):
    salutation: Salutation = Field(..., title="Salutation")
    name: str = Field(..., title="Name")
    email: str = Field(..., title="E-Mail")
    nickname: str | None = Field(None, title="Nickname")


FEEDBACK_TEMPLATE = """<form {attrs}>
  {form_errors}
  <div class="row">
    <div class="col-6">
      {salutation}
      {name}
    </div>
    <div class="col-6">
      {email}
      {nickname}
    </div>
  </div>
  {buttons}
</form>
{scripts}"""


class Feedback(Form):
    def get_schema(self, request):
        return FeedbackForm

    def get_form(self, request, values=None, errors=None):
        # explicit, template-driven rendering: place each field yourself
        bound = self.bind(request, values, errors)
        return FEEDBACK_TEMPLATE.format(
            attrs=bound.attrs,
            form_errors=bound.form_errors(),
            salutation=bound["salutation"],
            name=bound["name"],
            email=bound["email"],
            nickname=bound["nickname"],
            buttons=bound.buttons(),
            scripts=bound.scripts(),
        )

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="own template"),
            mimetype="text/html",
        )

    @trigger(name="send", title="Send", validate=True)
    def send(self, request, data):
        return Response(f"Danke, {data.name}!", mimetype="text/plain")


# --- A generated model plus a UI schema, with conditional fields ---

EX_FORMS = Path(__file__).parent / "ex_forms"
LD_000_0V1100_UI = load_ui(EX_FORMS / "LD_000_0V1100" / "ui_schema.json")


# A copy of nva.dynamic_form_elements' script, so the example runs on its own
library = Library("formidable_example", "ex_forms/static")
get_library_registry().add(library)
conditional_fields = Resource(library, "conditionalfield.js", depends=[jquery])


class Rueckfrage(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return LD_000_0V1100Model

    def get_renderer(self, request):
        return FormRenderer(theme=self.get_theme(request), ui=LD_000_0V1100_UI)

    def render_response(self, html_form, request):
        conditional_fields.need()  # adds the script and jQuery to the page
        return Response(
            page(html_form, self.get_theme(request),
                 title=LD_000_0V1100Model.__doc__.splitlines()[0]),
            mimetype="text/html",
        )

    @trigger(name="send", title="Absenden", validate=True)
    def send(self, request, data):
        return Response(data.model_dump_json(indent=2), mimetype="text/plain")


# URL routing rules
routes.add("/", endpoint=Index())
routes.add("/rueckfrage", endpoint=Rueckfrage())
routes.add("/material", endpoint=MaterialIndex())
routes.add("/custom", endpoint=Feedback())


class LimitedRequest(Request):
    max_content_length = 2 * 1024 * 1024  # uploads beyond 2 MiB get a 413


# Main WSGI application
def wsgi_app(environ, start_response):
    request = LimitedRequest(environ)
    if matched := routes.match(request.path):
        (route, params) = matched
        if route is not None:
            try:
                response = route["endpoint"](request)
            except HTTPException as exc:
                # e.g. 413 when an upload exceeds max_content_length
                response = exc
            return response(environ, start_response)

    response = Response("404 Not Found", status=404)
    return response(environ, start_response)


# Injects needed resources into pages and serves them
application = Fanstatic(wsgi_app)


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("0.0.0.0", 8000, application, use_debugger=True, use_reloader=True)
