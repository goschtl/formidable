import enum
import typing as t

from pydantic import BaseModel, Field, create_model
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.renderers import FormRenderer, RadioFieldRenderer
from formidable.themes import Theme
from formidable.views import Form, trigger


class Mood(enum.Enum):
    happy = "happy"
    over_the_moon = "over the moon"


class Schema(BaseModel):
    color: t.Literal["red", "green"] = Field(..., title="Color")
    mood: Mood | None = Field(None, title="Mood")


def test_literal_renders_select_with_options():
    html = FormRenderer()(Schema)
    assert '<select id="field-color" name="color" required="required">' in html
    assert '<option value="red">red</option>' in html
    assert '<option value="green">green</option>' in html


def test_unselected_field_gets_blank_option():
    html = FormRenderer()(Schema)
    assert '<option value=""></option>' in html


def test_submitted_value_is_selected():
    html = FormRenderer()(Schema, values={"color": "green"})
    assert '<option selected="selected" value="green">green</option>' in html


def test_enum_renders_values_and_titles():
    html = FormRenderer()(Schema)
    assert '<option value="happy">Happy</option>' in html
    assert '<option value="over the moon">Over The Moon</option>' in html
    # optional: no required attribute on the select
    assert '<select id="field-mood" name="mood">' in html


def test_enum_default_instance_is_selected():
    class WithDefault(BaseModel):
        mood: Mood = Mood.happy

    html = FormRenderer()(WithDefault)
    assert '<option selected="selected" value="happy">Happy</option>' in html


def test_select_theme_and_error_classes():
    theme = Theme(select="form-select", invalid="is-invalid", error="feedback")
    html = FormRenderer(theme=theme)(
        Schema, errors={"color": "Bad choice"})
    assert '<select aria-describedby="field-color-error" aria-invalid="true" class="form-select is-invalid"' in html
    assert '<span class="field-error feedback" id="field-color-error">Bad choice</span>' in html


def test_radio_group_renders_options():
    renderer = FormRenderer(custom_widgets={"color": RadioFieldRenderer})
    html = renderer(Schema)
    assert '<fieldset class="field-radiogroup" id="field-color">' in html
    assert '<legend>Color</legend>' in html
    assert ('<input id="field-color-0" name="color" required="required" '
            'type="radio" value="red">') in html
    assert '<label for="field-color-1">green</label>' in html


def test_radio_round_trips_value_and_errors():
    renderer = FormRenderer(custom_widgets={"color": RadioFieldRenderer})
    html = renderer(
        Schema, values={"color": "green"}, errors={"color": "Bad"})
    assert ('<input aria-invalid="true" checked="checked" id="field-color-1" name="color" '
            'required="required" type="radio" value="green">') in html
    assert '<span class="field-error" id="field-color-error">Bad</span>' in html


def test_radio_enum_source():
    renderer = FormRenderer(custom_widgets={"mood": RadioFieldRenderer})
    html = renderer(Schema, values={"mood": Mood.happy})
    assert '<label for="field-mood-0">Happy</label>' in html
    # optional group: no required attribute
    assert ('<input checked="checked" id="field-mood-0" name="mood" '
            'type="radio" value="happy">') in html


class RequestBoundIndex(Form):
    """The deform-deferred pattern: choices depend on the request."""

    csrf = False

    def get_schema(self, request):
        choices = tuple(request.args["choices"].split(","))
        return create_model(
            "RequestSchema",
            color=(t.Literal[choices], Field(..., title="Color")),
        )

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(data.color, mimetype="text/plain")


def post(query_string, data):
    builder = EnvironBuilder(
        method="POST", query_string=query_string,
        data={"__trigger__": "save", **data})
    return RequestBoundIndex()(Request(builder.get_environ()))


def test_request_bound_choices_render():
    builder = EnvironBuilder(method="GET", query_string="choices=a,b,c")
    response = RequestBoundIndex()(Request(builder.get_environ()))
    html = response.get_data(as_text=True)
    assert '<option value="a">a</option>' in html
    assert '<option value="c">c</option>' in html


def test_request_bound_choice_validates():
    response = post("choices=a,b,c", {"color": "b"})
    assert response.get_data(as_text=True) == "b"


def test_choice_outside_request_source_is_rejected():
    # "c" is a valid choice for another request, but not for this one
    response = post("choices=a,b", {"color": "c"})
    html = response.get_data(as_text=True)
    assert 'class="field-error"' in html
    # the form re-renders with exactly this request's choices
    assert '<option value="c">' not in html
