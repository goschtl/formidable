import enum
import typing as t

from markupsafe import Markup
from pydantic import BaseModel, Field

from formidable.renderers import FormRenderer, RadioFieldRenderer, StringFieldRenderer
from formidable.themes import Theme


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")


def override(folder, template, body):
    target = folder / "formidable" / template
    target.parent.mkdir(exist_ok=True)
    target.write_text(body)
    return folder


def test_form_renders_markup():
    assert isinstance(FormRenderer()(Schema), Markup)


def test_own_templates_override_builtins(tmp_path):
    override(tmp_path, "input.pt", "<p>mine: ${name}</p>")
    html = FormRenderer(templates=[tmp_path])(Schema)
    assert "<p>mine: name</p>" in html
    assert 'id="field-name"' not in html


def test_theme_templates_override_builtins(tmp_path):
    override(tmp_path, "input.pt", "<p>themed</p>")
    theme = Theme(templates=(str(tmp_path),))
    assert "<p>themed</p>" in FormRenderer(theme=theme)(Schema)


def test_own_templates_beat_theme_templates(tmp_path):
    (tmp_path / "own").mkdir()
    (tmp_path / "themed").mkdir()
    own = override(tmp_path / "own", "input.pt", "<p>own</p>")
    themed = override(tmp_path / "themed", "input.pt", "<p>themed</p>")
    theme = Theme(templates=(str(themed),))
    html = FormRenderer(theme=theme, templates=[own])(Schema)
    assert "<p>own</p>" in html
    assert "<p>themed</p>" not in html


def test_overrides_can_use_builtin_partials(tmp_path):
    override(tmp_path, "input.pt", (
        "<p>${render_partial('formidable/error.pt', "
        "error=error, theme=theme)}</p>"))
    html = FormRenderer(templates=[tmp_path])(
        Schema, errors={"name": "Nope"})
    assert '<span class="field-error">Nope</span>' in html


def test_custom_renderer_picks_own_template(tmp_path):
    (tmp_path / "mine.pt").write_text("<em>${title}</em>")

    class Mine(StringFieldRenderer):
        template = "mine.pt"

    html = FormRenderer(templates=[tmp_path], custom_widgets={"name": Mine})(Schema)
    assert "<em>Your Name</em>" in html


def test_user_input_is_escaped():
    attack = '"><script>alert(1)</script>'

    class Color(enum.Enum):
        red = attack

    class Inner(BaseModel):
        street: str

    class Rich(BaseModel):
        name: str
        body: str = Field(..., json_schema_extra={"widget": "textarea"})
        color: Color
        radio: t.Literal["a"] = Field(..., json_schema_extra={"widget": "radio"})
        inner: Inner
        rows: list[Inner]
        title_field: str = Field(..., title=attack)

    html = FormRenderer()(
        Rich,
        values={"name": attack, "body": attack, "radio": attack,
                "inner": {"street": attack},
                "rows": [{"street": attack}]},
        errors={"name": attack, "": attack, "inner": attack, "rows": attack,
                "radio": attack},
    )
    # only the list-row script may contain a <script> tag
    assert "<script>alert" not in html
    assert '"><script' not in html
    assert html.count("<script>") == 1


def test_radio_ids_stay_indexed():
    class R(BaseModel):
        pick: t.Literal["a", "b"]

    html = FormRenderer(custom_widgets={"pick": RadioFieldRenderer})(R)
    assert 'id="field-pick-0"' in html and 'for="field-pick-1"' in html
