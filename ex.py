from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import NotFound
from pydantic import BaseModel, Field
from formidable.form import setup_container
from formidable.renderers import FormRenderer


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


container = setup_container()
form_renderer: FormRenderer = container.get(FormRenderer)


# URL routing rules
url_map = Map(
    [
        Rule("/", endpoint="index"),
        Rule("/hello", endpoint="hello"),
    ]
)


TT = """ <html> <head> </head> <body> %s </body> </html>"""


def index():
    html_form = form_renderer.render(ExampleForm)
    return Response(TT % html_form.render(), mimetype="text/html")


def hello():
    return Response("Hello from /hello 👋", mimetype="text/plain")


# Main WSGI application
def wsgi_app(environ, start_response):
    request = Request(environ)
    adapter = url_map.bind_to_environ(environ)

    try:
        endpoint, values = adapter.match()
        if endpoint == "index":
            response = index()
        elif endpoint == "hello":
            response = hello()
    except NotFound:
        response = Response("404 Not Found", status=404)

    return response(environ, start_response)


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("localhost", 8000, wsgi_app, use_debugger=True, use_reloader=True)
