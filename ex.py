from autoroutes import Routes as Autoroutes
from werkzeug.wrappers import Request, Response
from pydantic import BaseModel, Field
from formidable.views import Form, trigger


routes = Autoroutes()


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


class Index(Form):

    def get_schema(self, request):
        return ExampleForm

    @trigger(name="save", title="Save")
    def save(self, request, data):
        result = self.get_schema(request)(**data)
        headers = {
            'Location': request.url
        }
        print(result)
        return Response(request.url, status=302, headers=headers)


# URL routing rules
routes.add("/", endpoint=Index())


# Main WSGI application
def wsgi_app(environ, start_response):
    request = Request(environ)
    if matched := routes.match(request.path):
        (route, params) = matched
        response = route['endpoint'](request)
    else:
        response = Response("404 Not Found", status=404)
    return response(environ, start_response)


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("0.0.0.0", 8000, wsgi_app, use_debugger=True, use_reloader=True)
