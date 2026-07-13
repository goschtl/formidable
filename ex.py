from autoroutes import Routes as Autoroutes
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from formidable.fields import UploadedFile
from formidable.views import Form, trigger
from formidable.renderers import FormRenderer, StringFieldRenderer
from formidable import i18n, themes
from formidable.themes import page
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.themes.material import MATERIAL


themes.use(BOOTSTRAP)  # the site-wide default
i18n.use({
    **i18n.GERMAN,
    # application-defined error types translate the same way
    "nickname_required": "Wenn Sie den Bedingungen zustimmen, "
                         "ist ein Spitzname erforderlich.",
})
from dominate.tags import div


routes = Autoroutes()


class CustomFieldRenderer(StringFieldRenderer):
    """A custom widget must still render an input named `name`,
    otherwise the field is never submitted and validation always fails."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        field = super().render(name, field_info, field_type, value=value, errors=errors)
        field.add(div("I am a custom widget.", cls="custom-hint"))
        return field


class User(BaseModel):
    id: int
    name: str = "Jane Doe"


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")
    avatar: UploadedFile | None = Field(None, title="Avatar")
    users: list[User] = Field(default_factory=list, title="Users")

    @model_validator(mode="after")
    def nickname_required_when_agreeing(self):
        if self.agree and not self.nickname:
            raise PydanticCustomError(
                "nickname_required",
                "When agreeing to the terms, a nickname is required.",
                {"field": "nickname"})
        return self


class Index(Form):
    def get_schema(self, request):
        return ExampleForm

    def get_renderer(self, request):
        return FormRenderer(
            theme=self.get_theme(request),
            custom_widgets={"name": CustomFieldRenderer},
        )

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="formidable demo"),
            mimetype="text/html")

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ExampleForm instance, not a raw dict.
        breakpoint()
        print(data)
        headers = {"Location": request.url}
        return Response(request.url, status=302, headers=headers)


class MaterialIndex(Index):
    theme = MATERIAL  # per-view override of the site default


# URL routing rules
routes.add("/", endpoint=Index())
routes.add("/material", endpoint=MaterialIndex())


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


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("0.0.0.0", 8000, wsgi_app, use_debugger=True, use_reloader=True)
