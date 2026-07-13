from pydantic import BaseModel, Field
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from beartype.door import TypeHint

from formidable.renderers import BoolFieldRenderer, FormRenderer
from formidable.themes import Theme, page
from formidable.themes.bootstrap import BOOTSTRAP, BootstrapBoolRenderer
from formidable.views import Form, trigger


class User(BaseModel):
    id: int


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    agree: bool = Field(..., title="I agree")
    users: list[User] = Field(default_factory=list, title="Users")


def test_default_theme_adds_no_classes():
    html = FormRenderer()(Schema).render()
    assert 'form-control' not in html
    assert '<form method="post">' in html


def test_theme_classes_are_applied():
    theme = Theme(form="my-form", wrapper="wrap", label="lbl",
                  input="inp", checkbox="check", fieldset="fs",
                  legend="lg", row_button="rowbtn", button="btn")
    html = FormRenderer(theme=theme)(Schema).render()
    assert '<form class="my-form" method="post">' in html
    assert '<div class="wrap">' in html
    assert '<label class="lbl" for="field-name">Your Name</label>' in html
    assert 'class="inp"' in html
    assert 'class="check"' in html
    assert '<fieldset class="field-list fs">' in html
    assert '<legend class="lg">Users</legend>' in html
    assert 'class="formidable-add-row rowbtn"' in html
    assert 'class="formidable-remove-row rowbtn"' in html


def test_theme_marks_invalid_inputs_and_errors():
    theme = Theme(input="inp", invalid="is-invalid", error="feedback")
    html = FormRenderer(theme=theme)(
        Schema,
        values={"name": "x"},
        errors={"name": "Bad value"},
    ).render()
    assert 'class="inp is-invalid"' in html
    assert '<span class="field-error feedback">Bad value</span>' in html
    # untouched fields keep the plain input class
    assert 'class="inp"' in html


def test_theme_reaches_nested_rows():
    theme = Theme(input="inp")
    html = FormRenderer(theme=theme)(
        Schema, values={"users": [{"id": "1"}]}).render()
    assert 'name="users.0.id"' in html
    assert html.count('class="inp"') >= 2  # top-level and nested input


def test_trigger_buttons_are_themed():
    class Index(Form):
        def get_schema(self, request):
            return Schema

        def get_renderer(self, request):
            return FormRenderer(theme=BOOTSTRAP)

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):  # pragma: no cover
            raise AssertionError("not reached")

    builder = EnvironBuilder(method="GET")
    response = Index()(Request(builder.get_environ()))
    html = response.get_data(as_text=True)
    assert ('<button class="btn btn-primary me-2" '
            'name="__trigger__" value="save">Save</button>') in html


def test_theme_widgets_override_structure():
    html = FormRenderer(theme=BOOTSTRAP)(Schema).render()
    # the Bootstrap checkbox structure: .form-check with label after input
    assert '<div class="mb-3 form-check">' in html
    assert '<label class="form-check-label" for="field-agree">' in html


def test_explicit_widgets_beat_theme_widgets():
    renderer = FormRenderer(
        theme=BOOTSTRAP, widgets={TypeHint(bool): BoolFieldRenderer})
    assert renderer.widgets[TypeHint(bool)] is BoolFieldRenderer


def test_theme_widgets_beat_defaults():
    renderer = FormRenderer(theme=BOOTSTRAP)
    assert renderer.widgets[TypeHint(bool)] is BootstrapBoolRenderer


def test_material_input_structure():
    from formidable.themes.material import MATERIAL

    html = FormRenderer(theme=MATERIAL)(Schema, values={"name": "Jane"}).render()
    # label follows the input inside .input-field, active over a value
    assert '<div class="input-field">' in html
    assert ('<input class="validate" id="field-name" name="name" required="required"'
            ' type="text" value="Jane">'
            '\n    <label class="active" for="field-name">Your Name</label>') in html


def test_material_checkbox_and_file_structure():
    from io import BytesIO

    from pydantic import BaseModel

    from formidable.fields import UploadedFile
    from formidable.themes.material import MATERIAL

    class WithFile(BaseModel):
        agree: bool
        doc: UploadedFile

    html = FormRenderer(theme=MATERIAL)(WithFile).render()
    # checkbox: label wraps input + text span
    assert '<input class="filled-in"' in html
    assert "<span>agree</span>" in html
    # file: real input inside a .btn, decorative path field beside it
    assert '<div class="file-field input-field">' in html
    assert '<input class="file-path validate" type="text">' in html
    assert 'enctype="multipart/form-data"' in html


def test_material_marks_errors():
    from formidable.themes.material import MATERIAL

    html = FormRenderer(theme=MATERIAL)(
        Schema, values={"name": ""}, errors={"name": "Required"}).render()
    assert 'class="validate invalid"' in html
    assert '<span class="field-error helper-text red-text">Required</span>' in html


def test_page_includes_theme_assets():
    theme = Theme(container="wrap",
                  stylesheets=("https://cdn.example/x.css",),
                  scripts=("https://cdn.example/x.js",))
    html = page(FormRenderer()(Schema), theme, title="A <title>")
    assert '<link href="https://cdn.example/x.css" rel="stylesheet">' in html
    assert '<script src="https://cdn.example/x.js"></script>' in html
    assert '<main class="wrap">' in html
    assert "<title>A &lt;title&gt;</title>" in html
