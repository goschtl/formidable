import datetime
import typing as t
from decimal import Decimal

from pydantic import BaseModel, Field, SecretStr
from werkzeug.datastructures import MultiDict
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.renderers import FormRenderer
from formidable.views import Form, trigger


def render(model, **kw):
    return FormRenderer()(model, **kw).render()


def test_float_and_decimal_render_number_step_any():
    class Money(BaseModel):
        price: float = Field(..., title="Price")
        total: Decimal = Field(..., title="Total")

    html = render(Money)
    assert ('<input id="field-price" name="price" required="required" '
            'step="any" type="number">') in html
    assert 'id="field-total"' in html and html.count('step="any"') == 2


def test_temporal_widgets_and_value_formatting():
    class When(BaseModel):
        day: datetime.date = Field(..., title="Day")
        at: datetime.datetime | None = Field(None, title="At")
        alarm: datetime.time | None = Field(None, title="Alarm")

    html = render(When, values={
        "day": datetime.date(2026, 7, 14),
        "at": datetime.datetime(2026, 7, 14, 9, 30),
        "alarm": datetime.time(7, 15),
    })
    assert 'type="date"' in html and 'value="2026-07-14"' in html
    assert 'type="datetime-local"' in html and 'value="2026-07-14T09:30"' in html
    assert 'type="time"' in html and 'value="07:15"' in html
    # submitted strings round-trip untouched
    html = render(When, values={"day": "2026-01-01"})
    assert 'value="2026-01-01"' in html


def test_secretstr_renders_password_and_never_echoes():
    class Login(BaseModel):
        password: SecretStr = Field(..., title="Password")

    html = render(Login, values={"password": "hunter2"})
    assert 'type="password"' in html
    assert "hunter2" not in html


def test_widget_hints_from_schema():
    class Post(BaseModel):
        body: str = Field(..., title="Body",
                          json_schema_extra={"widget": "textarea"})
        email: str = Field(..., title="E-Mail",
                           json_schema_extra={"widget": "email"})
        color: t.Literal["red", "green"] = Field(
            ..., title="Color", json_schema_extra={"widget": "radio"})

    html = render(Post, values={"body": "hello <world>"})
    assert ('<textarea id="field-body" name="body" required="required">'
            'hello &lt;world&gt;</textarea>') in html
    assert 'type="email"' in html
    assert '<fieldset class="field-radiogroup">' in html


class Prefs(BaseModel):
    name: str
    interests: list[t.Literal["sports", "music", "tech"]] = Field(
        default_factory=list, title="Interests")


def test_multiselect_renders_and_marks_selected():
    html = render(Prefs, values={"interests": ["music", "tech"]})
    assert ('<select id="field-interests" multiple="multiple" '
            'name="interests">') in html
    assert '<option value="sports">sports</option>' in html
    assert '<option selected="selected" value="music">music</option>' in html
    assert '<option selected="selected" value="tech">tech</option>' in html


class PrefsIndex(Form):
    csrf = False

    def get_schema(self, request):
        return Prefs

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(",".join(data.interests) or "-", mimetype="text/plain")


def post(data):
    builder = EnvironBuilder(method="POST", data=data)
    return PrefsIndex()(Request(builder.get_environ()))


def test_multiselect_repeated_keys_become_a_list():
    builder = EnvironBuilder(method="POST", data=MultiDict([
        ("__trigger__", "save"), ("name", "CK"),
        ("interests", "music"), ("interests", "tech"),
    ]))
    response = PrefsIndex()(Request(builder.get_environ()))
    assert response.get_data(as_text=True) == "music,tech"


def test_multiselect_single_selection_still_validates():
    response = post({"__trigger__": "save", "name": "CK",
                     "interests": "sports"})
    assert response.get_data(as_text=True) == "sports"


def test_multiselect_nothing_selected_uses_default():
    response = post({"__trigger__": "save", "name": "CK"})
    assert response.get_data(as_text=True) == "-"


def test_multiselect_rejects_unknown_choice():
    response = post({"__trigger__": "save", "name": "CK",
                     "interests": "gardening"})
    assert 'class="field-error"' in response.get_data(as_text=True)
