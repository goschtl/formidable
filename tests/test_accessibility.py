import re
import typing as t

from pydantic import BaseModel, Field

from formidable.renderers import FormRenderer, RadioFieldRenderer
from formidable.themes import page
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.themes.material import MATERIAL
from formidable.ui import parse_ui


class Address(BaseModel):
    city: str = Field(..., title="City")


class Schema(BaseModel):
    name: str = Field(..., title="Name", description="Your full name")
    color: str = Field(..., title="Color")
    agree: bool = Field(False, title="Agree")
    address: Address = Field(..., title="Address")
    tags: list[str] = Field(default_factory=list, title="Tags")


def tag(html, name):
    return re.search(rf'<[a-z]+[^>]*\bname="{re.escape(name)}"[^>]*>', html).group(0)


def test_nothing_extra_without_errors():
    html = str(FormRenderer()(Schema))
    assert "aria-invalid" not in html
    assert "form-errors" not in html
    assert 'aria-describedby' not in tag(html, "color")


def test_input_points_at_its_error_description_and_help():
    ui = parse_ui({"name": {"ui:help": "Help"}})
    html = str(FormRenderer(ui=ui)(Schema, errors={"name": "Bad"}))
    input_tag = tag(html, "name")
    assert 'aria-invalid="true"' in input_tag
    assert ('aria-describedby="field-name-error field-name-description '
            'field-name-help"') in input_tag
    for part in ("error", "description", "help"):
        assert f'id="field-name-{part}"' in html


def test_nested_paths_keep_their_ids():
    html = str(FormRenderer()(Schema, errors={"address.city": "Bad"}))
    assert 'aria-describedby="field-address.city-error"' in tag(html, "address.city")
    assert 'id="field-address.city-error"' in html


def test_groups_describe_the_fieldset():
    class Choice(BaseModel):
        color: str

    class Radio(BaseModel):
        color: Choice

    html = str(FormRenderer()(Radio, errors={"color": "Bad"}))
    assert ('<fieldset aria-describedby="field-color-error" '
            'class="field-model" id="field-color">') in html


def test_radios_are_marked_invalid():
    class Radio(BaseModel):
        color: t.Literal["a", "b"]

    renderer = FormRenderer(custom_widgets={"color": RadioFieldRenderer})
    html = str(renderer(Radio, errors={"color": "Bad"}))
    assert '<fieldset aria-describedby="field-color-error"' in html
    assert html.count('aria-invalid="true"') == 2


def test_every_theme_has_the_attributes():
    for theme in (BOOTSTRAP, MATERIAL):
        html = str(FormRenderer(theme=theme)(
            Schema, errors={"name": "Bad", "agree": "Bad"}))
        assert 'aria-invalid="true"' in tag(html, "name")
        assert 'aria-invalid="true"' in tag(html, "agree")
        assert 'aria-describedby="field-agree-error"' in tag(html, "agree")


def test_summary_links_to_each_field():
    html = str(FormRenderer()(Schema, errors={
        "name": "Too short", "address.city": "Unknown", "": "Does not add up"}))
    assert 'role="alert"' in html
    assert 'tabindex="-1"' in html
    assert "autofocus" in html
    assert '<a href="#field-name">Name: Too short</a>' in html
    assert '<a href="#field-address.city">City: Unknown</a>' in html
    assert "Does not add up" in html


def test_summary_finds_the_widget_of_an_item():
    class Multi(BaseModel):
        tags: list[str] = Field(default_factory=list, title="Tags")

    html = str(FormRenderer()(Multi, errors={"tags.0": "Bad"}))
    assert '<a href="#field-tags">Tags: Bad</a>' in html


def test_summary_is_escaped():
    html = str(FormRenderer()(Schema, errors={"name": "<script>"}))
    assert "<script>" not in html.split("</form>")[0].split("field-list")[0]


def test_summary_follows_ui_title_and_messages():
    ui = parse_ui({"name": {"ui:title": "Vorname"}})
    html = str(FormRenderer(ui=ui, messages={"ui_error_summary": "Bitte!"})(
        Schema, errors={"name": "Falsch"}))
    assert "Bitte!" in html
    assert '<a href="#field-name">Vorname: Falsch</a>' in html


def test_a_field_left_out_of_a_template_still_shows_its_error():
    form = FormRenderer().bind(Schema, errors={"color": "Required"})
    assert "Color: Required" in str(form.form_errors())


def test_page_language():
    assert '<html lang="en">' in page("x")
    assert '<html lang="de">' in page("x", lang="de")
