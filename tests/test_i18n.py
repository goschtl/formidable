import typing as t

from pydantic import BaseModel, Field
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable import i18n
from formidable.views import Form, trigger


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age", ge=18)


class Index(Form):
    csrf = False

    def get_schema(self, request):
        return Schema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):  # pragma: no cover
        return Response("ok")


def post(data):
    builder = EnvironBuilder(method="POST", data={"__trigger__": "save", **data})
    return Index()(Request(builder.get_environ())).get_data(as_text=True)


def test_translate_known_type():
    error = {"type": "missing", "msg": "Field required", "loc": ("name",)}
    assert i18n.translate(error, i18n.GERMAN) == "Pflichtfeld."


def test_translate_formats_context():
    error = {"type": "greater_than_equal", "msg": "...",
             "ctx": {"ge": 18}, "loc": ("age",)}
    assert i18n.translate(error, i18n.GERMAN) == \
        "Der Wert muss mindestens 18 betragen."


def test_translate_unknown_type_falls_back():
    error = {"type": "some_exotic_error", "msg": "Original message"}
    assert i18n.translate(error, i18n.GERMAN) == "Original message"


def test_untranslated_form_uses_pydantic_messages():
    html = post({"age": "5"})
    assert "Field required" in html


def test_site_wide_catalog_translates_form_errors():
    previous = i18n.use(i18n.GERMAN)
    try:
        html = post({"age": "5"})
        assert "Pflichtfeld." in html
        assert "Der Wert muss mindestens 18 betragen." in html
        assert "Field required" not in html
    finally:
        i18n.use(previous)


def test_view_level_catalog_overrides_site_default():
    class FrenchIndex(Index):
        error_messages: t.ClassVar = {"missing": "Champ obligatoire."}

    previous = i18n.use(i18n.GERMAN)
    try:
        builder = EnvironBuilder(method="POST", data={"__trigger__": "save"})
        html = FrenchIndex()(
            Request(builder.get_environ())).get_data(as_text=True)
        assert "Champ obligatoire." in html
        assert "Pflichtfeld." not in html
    finally:
        i18n.use(previous)
