from pydantic import BaseModel, Field
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.fields import UploadedFile
from formidable.renderers import FormRenderer
from formidable.themes import Theme
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
    assert '<span class="field-error">Bad</span>' in str(bound["name"])
    assert bound.error("name") == "Bad"
    assert '<div class="form-errors">' in str(bound.form_errors())


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
    assert '<span class="field-error">Field required</span>' in html
    assert 'checked="checked"' in html
