import datetime
import enum
import typing as t
from io import BytesIO

import pytest
from pydantic import BaseModel, Field, SecretStr
from werkzeug.datastructures import FileStorage

from formidable import i18n
from formidable.conditions import check, is_visible
from formidable.fields import UploadedFile
from formidable.renderers import FormRenderer
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.ui import parse_ui
from formidable.views import Form, trigger


class Color(enum.Enum):
    red = "r"


class Address(BaseModel):
    city: str = Field(..., title="City")


class Schema(BaseModel):
    name: str = Field(..., title="Name")
    bio: str | None = Field(None, title="Bio", json_schema_extra={"widget": "textarea"})
    age: int | None = Field(None, title="Age")
    agree: bool = Field(False, title="Agree")
    day: datetime.date | None = Field(None, title="Day")
    moment: datetime.datetime | None = Field(None, title="Moment")
    at: datetime.time | None = Field(None, title="At")
    secret: SecretStr | None = Field(None, title="Secret")
    color: Color | None = Field(None, title="Color")
    size: t.Literal["s", "m"] | None = Field(None, title="Size")
    many: list[t.Literal["a", "b"]] = Field(default_factory=list, title="Many")
    address: Address | None = Field(None, title="Address")
    rows: list[Address] = Field(default_factory=list, title="Rows")
    doc: UploadedFile | None = Field(None, title="Doc")


def read(values, **options):
    return str(FormRenderer(**options)(Schema, values=values, readonly=True))


def test_no_controls_and_no_scripts():
    html = read({"name": "A", "rows": [{"city": "x"}]})
    for tag in ("<input", "<select", "<textarea", "<form", "<button", "<script",
                "<template"):
        assert tag not in html
    assert 'class="form-readonly"' in html


def test_title_and_value():
    html = read({"name": "<A>"})
    assert "<strong>Name</strong>" in html
    assert "&lt;A&gt;" in html


def test_empty_values_show_a_dash():
    assert ">—</div>" in read({"name": ""})


@pytest.mark.parametrize("values, expected", [
    ({"agree": "true"}, ">Yes<"),
    ({"agree": True}, ">Yes<"),
    ({"agree": "false"}, ">No<"),
    ({"day": "2026-10-30"}, ">2026-10-30<"),
    ({"day": datetime.date(2026, 10, 30)}, ">2026-10-30<"),
    ({"day": "not a date"}, ">not a date<"),
    ({"moment": "2026-10-30T12:30"}, ">2026-10-30 12:30<"),
    ({"at": datetime.time(12, 30)}, ">12:30<"),
    ({"at": "12:30"}, ">12:30<"),
    ({"color": Color.red}, ">Red<"),
    ({"color": "r"}, ">Red<"),
    ({"size": "m"}, ">m<"),
    ({"many": ["a", "b"]}, ">a, b<"),
    ({"address": {"city": "Bonn"}}, ">Bonn<"),
    ({"rows": [{"city": "Köln"}, {"city": "Bonn"}]}, ">Bonn<"),
    ({"doc": FileStorage(BytesIO(b"x"), filename="a.pdf")}, ">a.pdf<"),
])
def test_values_read_well(values, expected):
    assert expected in read(values)


def test_secrets_stay_secret():
    html = read({"secret": SecretStr("hunter2")})
    assert "hunter2" not in html
    assert "••••••" in html


def test_textarea_keeps_line_breaks():
    assert "white-space: pre-line" in read({"bio": "a\nb"})
    plain = str(FormRenderer()(Address, values={"city": "a"}, readonly=True))
    assert "white-space" not in plain


def test_interface_text_is_translated():
    html = read({"agree": True, "day": "2026-10-30"}, messages=i18n.GERMAN)
    assert ">Ja<" in html
    assert ">30.10.2026<" in html


def test_labels_and_units_from_the_ui_schema():
    ui = parse_ui({"age": {"ui:unit": "Jahre", "ui:title": "Alter"},
                   "size": {"ui:options": [{"value": "m", "label": "Medium"}]}})
    html = read({"age": 3, "size": "m"}, ui=ui)
    assert "<strong>Alter</strong>" in html
    assert "3 Jahre" in html
    assert ">Medium<" in html


def test_upload_label():
    class Refs(BaseModel):
        files: list[str] = Field(default_factory=list)

    ui = parse_ui({"files": {"ui:widget": "file"}})
    html = str(FormRenderer(ui=ui, upload_url="/u", upload_label=str.upper)(
        Refs, values={"files": ["a", "b"]}, readonly=True))
    assert ">A, B<" in html


def test_a_model_instance_works():
    html = str(FormRenderer()(Address, values=Address(city="Bonn"), readonly=True))
    assert ">Bonn<" in html


def test_bound_form_places_read_only_fields():
    form = FormRenderer().bind(
        Schema, values={"address": {"city": "Bonn"}}, readonly=True)
    assert "<input" not in str(form["address.city"])
    assert "Bonn" in str(form["address.city"])
    assert str(form.scripts()) == ""


def test_theme_applies():
    html = str(FormRenderer(theme=BOOTSTRAP)(Schema, values={}, readonly=True))
    assert "form-label" in html
    assert "<strong>Name</strong>" in html


def test_buttons_make_it_a_form():
    class View(Form):
        def get_schema(self, request):
            return Address

        @trigger(name="ok", title="OK")
        def ok(self, request, data):  # pragma: no cover
            ...

    view = View()
    html = str(FormRenderer()(Address, values={"city": "x"}, readonly=True,
                              buttons=view.buttons.values(), csrf_token="t"))
    assert "<form" in html and 'value="ok"' in html and 'name="__csrf__"' in html
    assert 'name="city"' not in html


# --- hidden by a condition ---


def conditional(condition, logic="or"):
    return parse_ui({"body": {"ui:conditions": [condition],
                              "ui:condition_logic": logic}})


class Cond(BaseModel):
    answer: str | None = None
    body: str | None = Field(None, title="Body")


def test_hidden_fields_do_not_show():
    ui = conditional({"field": "answer", "operator": "equals", "value": "b"})
    args = {"ui": ui}
    html = str(FormRenderer(**args)(Cond, values={"answer": "a", "body": "x"},
                                    readonly=True))
    assert "Body" not in html
    html = str(FormRenderer(**args)(Cond, values={"answer": "b", "body": "x"},
                                    readonly=True))
    assert "Body" in html


# follows the operators in static/conditions.js
@pytest.mark.parametrize("operator, actual, expected, result", [
    ("equals", "a", "a", True),
    ("equals", "a", "b", False),
    ("equals", ["a", "b"], "b", True),
    ("not_equals", "a", "b", True),
    ("not_equals", ["a", "b"], "b", False),
    ("contains", "hello", "ell", True),
    ("contains", "", "x", False),
    ("not_contains", "hello", "x", True),
    ("not_contains", "", "x", True),
    ("starts_with", "hello", "he", True),
    ("ends_with", "hello", "lo", True),
    ("ends_with", "", "lo", False),
    ("greater_than", "5", "3", True),
    ("greater_than", "", "3", False),
    ("less_than", "2", "3", True),
    ("greater_equal", "3", "3", True),
    ("less_equal", "3", "3", True),
    ("empty", "  ", None, True),
    ("empty", [], None, True),
    ("not_empty", "a", None, True),
    ("in", "a", ["a", "b"], True),
    ("in", "c", ["a", "b"], False),
    ("in", "a", "a", False),
    ("not_in", "c", ["a", "b"], True),
    ("not_in", "a", "a", True),
    ("nonsense", "a", "a", False),
])
def test_operators(operator, actual, expected, result):
    assert check(operator, actual, expected) is result


def test_a_condition_on_a_hidden_field_fails():
    ui = parse_ui({
        "b": {"ui:conditions": [{"field": "a", "operator": "equals", "value": "1"}]},
        "c": {"ui:conditions": [{"field": "b", "operator": "not_empty"}]},
    })
    assert not is_visible("c", ui, {"a": "2", "b": "stale"})
    assert is_visible("c", ui, {"a": "1", "b": "x"})


def test_a_cycle_ends():
    ui = parse_ui({
        "a": {"ui:conditions": [{"field": "b", "operator": "not_empty"}]},
        "b": {"ui:conditions": [{"field": "a", "operator": "not_empty"}]},
    })
    assert is_visible("a", ui, {"a": "1", "b": "1"})


def test_logic_and_attribute_formats():
    both = [{"field": "a", "operator": "equals", "value": "1"},
            {"field": "b", "operator": "equals", "value": "1"}]
    values = {"a": "1", "b": "2"}
    assert is_visible("x", parse_ui({"x": {"ui:conditions": both}}), values)
    assert not is_visible("x", parse_ui({"x": {
        "ui:conditions": both, "ui:condition_logic": "and"}}), values)
    single = parse_ui({"x": {"ui:attributes": {
        "data-conditions": "{'field': 'a', 'operator': 'equals', 'value': '2'}"}}})
    assert not is_visible("x", single, values)


def test_a_condition_looks_at_its_own_row_first():
    ui = parse_ui({"rows.items.b": {"ui:conditions": [
        {"field": "rows.items.a", "operator": "equals", "value": "1"}]}})
    values = {"rows": [{"a": "1"}, {"a": "2"}]}
    assert is_visible("rows.0.b", ui, values)
    assert not is_visible("rows.1.b", ui, values)


def test_checkbox_answers():
    ui = parse_ui({"x": {"ui:conditions": [
        {"field": "a", "operator": "equals", "value": "true"}]}})
    assert is_visible("x", ui, {"a": True})
    assert is_visible("x", ui, {"a": "true"})
    assert not is_visible("x", ui, {"a": False})
    assert not is_visible("x", ui, {"a": "false"})
