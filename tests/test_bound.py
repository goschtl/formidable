import pytest
from pydantic import BaseModel, Field
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.fields import UploadedFile
from formidable.renderers import FormRenderer, render_template
from formidable.themes import Theme
from formidable.ui import parse_ui
from formidable.views import Form, trigger


class User(BaseModel):
    id: int


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    agree: bool = Field(..., title="I agree")


def test_bound_field_access_and_iteration():
    bound = FormRenderer().bind(Schema)
    assert 'name="name"' in str(bound["name"])
    assert bound["name"].title == "Your Name"
    assert [f.name for f in bound] == ["name", "agree"]
    # __html__ marks output as safe for Jinja2/Chameleon
    assert bound["name"].__html__() == str(bound["name"])


def test_unknown_field_lists_alternatives():
    try:
        FormRenderer().bind(Schema)["nope"]
    except KeyError as exc:
        assert "name, agree" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_attrs_reflect_form_needs():
    assert str(FormRenderer().bind(Schema).attrs) == 'method="post" novalidate'

    class WithFile(BaseModel):
        doc: UploadedFile

    assert 'enctype="multipart/form-data"' in str(FormRenderer().bind(WithFile).attrs)

    themed = FormRenderer(theme=Theme(form="my-form"), novalidate=False)
    assert str(themed.bind(Schema).attrs) == 'method="post" class="my-form"'


def test_values_and_errors_round_trip():
    bound = FormRenderer().bind(
        Schema, values={"name": "Jane"}, errors={"name": "Bad", "": "Nope"})
    assert 'value="Jane"' in str(bound["name"])
    assert '<span class="field-error" id="field-name-error">Bad</span>' in str(bound["name"])
    assert bound.error("name") == "Bad"
    assert 'class="form-errors"' in str(bound.form_errors())


def test_scripts_only_for_list_forms():
    class WithList(BaseModel):
        users: list[User] = Field(default_factory=list)

    assert "__formidable_rows" in str(FormRenderer().bind(WithList).scripts())
    assert str(FormRenderer().bind(Schema).scripts()) == ""


TEMPLATE = """<form {attrs}>
{form_errors}<div class="left">{name}</div><div class="right">{agree}</div>
{buttons}
</form>"""


class TemplateIndex(Form):
    csrf = False

    def get_schema(self, request):
        return Schema

    def get_form(self, request, values=None, errors=None):
        bound = self.bind(request, values, errors)
        return TEMPLATE.format(
            attrs=bound.attrs, form_errors=bound.form_errors(),
            name=bound["name"], agree=bound["agree"],
            buttons=bound.buttons())

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response("saved", mimetype="text/plain")


def make_request(method="GET", data=None):
    builder = EnvironBuilder(method=method, data=data)
    return Request(builder.get_environ())


def test_template_view_renders_custom_layout():
    response = TemplateIndex()(make_request())
    html = response.get_data(as_text=True)
    assert '<form method="post" novalidate>' in html
    assert '<div class="left">' in html
    assert 'name="name"' in html
    assert '<button name="__trigger__" value="save">Save</button>' in html


def test_template_view_full_cycle():
    response = TemplateIndex()(make_request("POST", data={
        "__trigger__": "save", "name": "Jane", "agree": "true"}))
    assert response.get_data(as_text=True) == "saved"

    # invalid POST re-renders through the SAME template, with errors
    response = TemplateIndex()(make_request("POST", data={
        "__trigger__": "save", "agree": "true"}))
    html = response.get_data(as_text=True)
    assert '<div class="left">' in html
    assert '<span class="field-error" id="field-name-error">Field required</span>' in html
    assert 'checked="checked"' in html


class Address(BaseModel):
    city: str = Field(..., title="City")
    zip: str | None = None


class Person(BaseModel):
    name: str = Field(..., title="Name")
    address: Address
    pets: list[Address] = Field(default_factory=list, title="Pets")


def test_attributes_for_tal_attributes():
    assert FormRenderer().bind(Schema).attributes == {
        "method": "post", "novalidate": "novalidate"}

    class WithFile(BaseModel):
        doc: UploadedFile

    themed = FormRenderer(theme=Theme(form="my-form"), novalidate=False)
    assert themed.bind(WithFile).attributes == {
        "method": "post", "enctype": "multipart/form-data", "class": "my-form"}


def test_attrs_are_escaped():
    themed = FormRenderer(theme=Theme(form='"><script>'))
    assert "<script>" not in str(themed.bind(Schema).attrs)


def test_chameleon_template_places_nested_fields(tmp_path):
    (tmp_path / "layout.pt").write_text(
        """<form tal:attributes="form.attributes">"""
        """<div id="city">${form['address.city']}</div>"""
        """<div id="pet">${form['pets.1.city']}</div>"""
        """</form>""")
    form = FormRenderer().bind(
        Person,
        values={"address": {"city": "<Köln>"},
                "pets": [{"city": "a"}, {"city": "b"}]},
        errors={"address.city": "Too far"})
    html = str(render_template("layout.pt", dirs=(str(tmp_path),), form=form))
    assert html.startswith('<form method="post" novalidate')
    assert 'name="address.city"' in html
    assert 'value="&lt;Köln&gt;"' in html
    assert "Too far" in html
    assert 'name="pets.1.city"' in html
    assert 'value="b"' in html


def test_nested_fields_by_dot_path():
    form = FormRenderer().bind(Person)
    field = form["address.city"]
    assert field.name == "address.city"
    assert field.title == "City"
    assert 'name="address.city"' in str(field)
    # only the top level is iterated, also after a lookup
    assert [f.name for f in form] == ["name", "address", "pets"]
    assert form["address.city"] is field


def test_a_nested_field_takes_its_default_when_nothing_was_submitted():
    class Inner(BaseModel):
        city: str = "Köln"

    class Outer(BaseModel):
        inner: Inner = Field(default_factory=Inner)

    assert 'value="Köln"' in str(FormRenderer().bind(Outer)["inner.city"])


def test_a_model_instance_is_a_value_as_well():
    form = FormRenderer().bind(
        Person, values={"address": Address(city="Bonn")})
    assert 'value="Bonn"' in str(form["address.city"])


def test_a_row_without_a_value_stays_empty():
    form = FormRenderer().bind(Person)
    assert 'name="pets.3.city"' in str(form["pets.3.city"])
    assert "value=" not in str(form["pets.3.city"])


def test_a_whole_row_by_index():
    form = FormRenderer().bind(Person, values={"pets": [{"city": "a"}]})
    assert form["pets.0"].title == "Pets #1"
    assert 'value="a"' in str(form["pets.0"])


def test_nested_ui_schema_applies():
    ui = parse_ui({"address.city": {"ui:title": "Ort", "ui:unit": "km"},
                   "pets.items.city": {"ui:title": "Tierort"}})
    form = FormRenderer(ui=ui).bind(Person)
    assert form["address.city"].title == "Ort"
    assert "km" in str(form["address.city"])
    assert "Tierort" in str(form["pets.0.city"])


def test_top_level_title_follows_the_ui_schema():
    form = FormRenderer(ui=parse_ui({"name": {"ui:title": "Vorname"}})).bind(Person)
    assert form["name"].title == "Vorname"


def test_scripts_cover_placed_fields():
    class Inner(BaseModel):
        rows: list[str] = Field(default_factory=list)

    class Outer(BaseModel):
        inner: Inner

    form = FormRenderer().bind(Outer)
    assert 'name="inner.rows' in str(form["inner.rows"])
    assert "formidable-add-row" in str(form.scripts())


@pytest.mark.parametrize("path, message", [
    ("nope", "name, address, pets"),
    ("address.nope", "city, zip"),
    ("name.first", "nothing below 'first'"),
    ("pets.first", "nothing below 'first'"),
])
def test_unknown_paths_say_what_is_wrong(path, message):
    with pytest.raises(KeyError, match=message):
        FormRenderer().bind(Person)[path]
