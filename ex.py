from autoroutes import Routes as Autoroutes
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response
from pydantic import BaseModel, Field
from formidable.fields import UploadedFile
from formidable.views import Form, trigger
from formidable.renderers import StringFieldRenderer
from dominate.tags import div


routes = Autoroutes()


class CustomFieldRenderer(StringFieldRenderer):
    """A custom widget must still render an input named `name`,
    otherwise the field is never submitted and validation always fails."""

    def render(self, name, field_info, field_type, value=None, errors=None):
        field = super().render(name, field_info, field_type,
                               value=value, errors=errors)
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


class Index(Form):
    def get_schema(self, request):
        return ExampleForm

    def get_renderer(self, request):
        renderer = super().get_renderer(request)
        renderer.custom_widgets = {"name": CustomFieldRenderer}
        return renderer

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ExampleForm instance, not a raw dict.
        breakpoint()
        print(data)
        headers = {"Location": request.url}
        return Response(request.url, status=302, headers=headers)


# URL routing rules
routes.add("/", endpoint=Index())


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
