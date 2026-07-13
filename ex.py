from autoroutes import Routes as Autoroutes
from werkzeug.wrappers import Request, Response
from pydantic import BaseModel, Field
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

    @trigger(name="add_user", title="Add user", order=1)
    def add_user(self, request, data):
        data.setdefault("users", []).append({})
        html_form = self.get_form(request, values=data)
        return Response(html_form.render(), mimetype="text/html")

    @trigger(name="remove_user", title="Remove last user", order=2)
    def remove_user(self, request, data):
        if users := data.get("users"):
            users.pop()
        html_form = self.get_form(request, values=data)
        return Response(html_form.render(), mimetype="text/html")


# URL routing rules
routes.add("/", endpoint=Index())


# Main WSGI application
def wsgi_app(environ, start_response):
    request = Request(environ)
    if matched := routes.match(request.path):
        (route, params) = matched
        if route is not None:
            response = route["endpoint"](request)
            return response(environ, start_response)

    response = Response("404 Not Found", status=404)
    return response(environ, start_response)


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("0.0.0.0", 8000, wsgi_app, use_debugger=True, use_reloader=True)
