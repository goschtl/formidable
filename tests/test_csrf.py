import re

from pydantic import BaseModel
from werkzeug.test import Client
from werkzeug.wrappers import Request, Response

from formidable.views import Form, trigger


class Schema(BaseModel):
    name: str


class Index(Form):
    def get_schema(self, request):
        return Schema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(f"saved {data.name}", mimetype="text/plain")


def wsgi_app(environ, start_response):
    return Index()(Request(environ))(environ, start_response)


def get_token(html: str) -> str:
    return re.search(
        r'name="__csrf__" type="hidden" value="([^"]+)"', html).group(1)


def test_get_sets_cookie_and_renders_hidden_token():
    client = Client(wsgi_app)
    response = client.get("/")
    html = response.get_data(as_text=True)
    token = get_token(html)
    cookie = response.headers.get("Set-Cookie", "")
    assert "formidable-csrf" in cookie
    assert token in cookie
    assert "HttpOnly" in cookie


def test_post_with_matching_token_passes():
    client = Client(wsgi_app)  # the Client keeps cookies, like a browser
    token = get_token(client.get("/").get_data(as_text=True))
    response = client.post("/", data={
        "__trigger__": "save", "name": "CK", "__csrf__": token})
    assert response.get_data(as_text=True) == "saved CK"


def test_post_without_token_is_403():
    client = Client(wsgi_app)
    client.get("/")
    response = client.post("/", data={"__trigger__": "save", "name": "CK"})
    assert response.status_code == 403


def test_post_with_wrong_token_is_403():
    client = Client(wsgi_app)
    client.get("/")
    response = client.post("/", data={
        "__trigger__": "save", "name": "CK", "__csrf__": "forged"})
    assert response.status_code == 403


def test_post_without_cookie_is_403():
    client = Client(wsgi_app)  # no prior GET: no cookie
    response = client.post("/", data={
        "__trigger__": "save", "name": "CK", "__csrf__": "anything"})
    assert response.status_code == 403


def test_token_is_stripped_from_data():
    class Echo(Index):
        @trigger(name="peek", title="Peek")
        def peek(self, request, data):
            return Response(str(sorted(data)), mimetype="text/plain")

    def app(environ, start_response):
        return Echo()(Request(environ))(environ, start_response)

    client = Client(app)
    token = get_token(client.get("/").get_data(as_text=True))
    response = client.post("/", data={
        "__trigger__": "peek", "name": "CK", "__csrf__": token})
    assert response.get_data(as_text=True) == "['name']"


def test_csrf_disabled_per_view():
    class Open(Index):
        csrf = False

    def app(environ, start_response):
        return Open()(Request(environ))(environ, start_response)

    client = Client(app)
    response = client.post("/", data={"__trigger__": "save", "name": "CK"})
    assert response.get_data(as_text=True) == "saved CK"
    assert "Set-Cookie" not in client.get("/").headers
