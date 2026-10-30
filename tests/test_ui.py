import json
import typing as t

from io import BytesIO

from pydantic import BaseModel, Field
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.fields import UploadedFile
from formidable.renderers import FormRenderer
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.ui import load_ui, parse_ui, ui_path
from formidable.views import Form, trigger


class Row(BaseModel):
    street: str = Field(..., title="Street")


class Schema(BaseModel):
    name: str = Field(..., title="Name", description="From the model")
    answer: t.Literal["a", "b"] = "a"
    body: str | None = None
    day: str | None = None
    rows: list[Row] = []


CONDITION = {"field": "answer", "operator": "equals", "value": "b"}


def render(ui, **kw):
    return FormRenderer(ui=parse_ui(ui))(Schema, **kw)


def test_ui_path_maps_rows_to_items():
    assert ui_path("name") == "name"
    assert ui_path("rows.0.street") == "rows.items.street"
    assert ui_path("rows.__index__.street") == "rows.items.street"
    assert ui_path("a.1.b.2") == "a.items.b.items"


def test_without_ui_nothing_changes():
    html = FormRenderer()(Schema)
    assert "data-conditions" not in html
    assert "FormidableConditions" not in html
    assert "placeholder" not in html


def test_title_and_description_override_the_model():
    html = render({"name": {"ui:title": "UI", "ui:description": "From UI"}})
    assert '<label for="field-name">UI</label>' in html
    assert "From UI" in html and "From the model" not in html


def test_description_falls_back_to_the_model():
    assert '<small class="field-description" id="field-name-description">From the model</small>' in render({})


def test_widget_and_placeholder():
    html = render({
        "body": {"ui:widget": "textarea", "ui:placeholder": "Type <here>"},
        "day": {"ui:widget": "date"},
    })
    assert "<textarea" in html and 'placeholder="Type &lt;here&gt;"' in html
    assert 'name="day" type="date"' in html


def test_options_set_labels_and_radio():
    html = render({"answer": {"ui:widget": "radio", "ui:options": [
        {"value": "a", "label": "Option A"},
        {"value": "b", "label": "Option B"},
    ]}})
    assert 'type="radio" value="a"' in html
    assert '<label for="field-answer-1">Option B</label>' in html


def test_conditions_render_as_json_on_the_wrapper():
    html = render({"body": {"ui:conditions": [CONDITION],
                            "ui:condition_logic": "and"}})
    expected = json.dumps({"conditions": [CONDITION], "logic": "and"})
    assert expected.replace('"', "&quot;") in html
    assert html.count('data-conditions="') == 1
    assert "FormidableConditions" in html


def test_row_fields_use_the_items_path():
    html = render(
        {"rows.items.street": {"ui:title": "Strasse",
                               "ui:conditions": [CONDITION]}},
        values={"rows": [{"street": "x"}]},
    )
    # the existing row and the blank <template> row
    assert html.count(">Strasse</label>") == 2
    assert html.count('data-conditions="') == 2


def test_attributes_go_on_the_control():
    html = render({
        "name": {"ui:attributes": {"data-condition-target": "body"}},
        "body": {"ui:widget": "textarea", "ui:attributes": {"data-x": "1"}},
        "answer": {"ui:attributes": {"data-y": "2"}},
    })
    assert 'id="field-name" name="name" required="required" type="text" data-condition-target="body">' in html
    assert '<textarea id="field-body" name="body" data-x="1">' in html
    assert '<select id="field-answer" name="answer" required="required" data-y="2">' in html
    assert "FormidableConditions" not in html


def test_attributes_on_every_radio():
    html = render({"answer": {"ui:widget": "radio",
                              "ui:attributes": {"data-t": "x"}}})
    assert html.count('data-t="x"') == 2


def test_attributes_on_structures():
    html = render({"rows": {"ui:attributes": {"data-r": "1"}}})
    assert '<fieldset class="field-list" id="field-rows" data-r="1">' in html


def test_attributes_are_escaped():
    html = render({"name": {"ui:attributes": {"data-x": '"><script>'}}})
    assert 'data-x="&quot;&gt;&lt;script&gt;"' in html


def test_boolean_and_empty_attributes():
    html = render({"name": {"ui:attributes": {
        "readonly": True, "disabled": False, "data-none": None}}})
    assert 'readonly="readonly"' in html
    assert "disabled" not in html.split("<script>")[0]
    assert "data-none" not in html


def test_conditions_attribute_goes_on_the_wrapper():
    raw = "{'field': 'answer', 'operator': 'equals', 'value': 'b'}"
    html = render({"body": {"ui:attributes": {
        "data-conditions": raw, "data-condition-logic": "and"}}})
    assert ('<div data-conditions="{\'field\': \'answer\', '
            "'operator': 'equals', 'value': 'b'}\" "
            'data-condition-logic="and">') in html
    assert "FormidableConditions" in html


def test_ui_conditions_beat_the_attribute():
    html = render({"body": {
        "ui:conditions": [CONDITION],
        "ui:attributes": {"data-conditions": "{'field': 'other'}"},
    }})
    assert "other" not in html.split("<script>")[0]
    assert "&quot;answer&quot;" in html


def test_wrapper_attributes_for_the_script():
    html = render({"body": {"ui:attributes": {
        "data-not-required": "true",
        "data-conditional-options": '{"source_field": "answer"}',
    }}})
    assert 'data-not-required="true"' in html
    assert "data-conditional-options=" in html
    assert "FormidableConditions" in html


def test_unit_wraps_the_input():
    html = render({"name": {"ui:unit": "EUR"}})
    assert '<div class="field-input-group"><input aria-describedby' in html
    assert '<span class="field-unit">EUR</span></div>' in html


def test_no_unit_no_wrapper():
    assert "field-input-group" not in render({})


def test_unit_uses_the_theme():
    html = FormRenderer(theme=BOOTSTRAP, ui=parse_ui(
        {"name": {"ui:unit": "km"}}))(Schema)
    assert '<div class="field-input-group input-group">' in html
    assert '<span class="field-unit input-group-text">km</span>' in html


def test_help_is_escaped_and_themed():
    html = render({"name": {"ui:help": "Hilfe <b>"}})
    assert '<div class="field-help" id="field-name-help">Hilfe &lt;b&gt;</div>' in html
    html = FormRenderer(theme=BOOTSTRAP, ui=parse_ui(
        {"name": {"ui:help": "Hilfe"}}))(Schema)
    assert '<div class="field-help form-text" id="field-name-help">Hilfe</div>' in html


def test_help_on_structures():
    html = render({"rows": {"ui:help": "Zeilen"}, "answer": {"ui:help": "Wahl"}})
    assert ">Zeilen</div>" in html and ">Wahl</div>" in html


class Files(BaseModel):
    docs: list[UploadedFile] = []


def test_multiple_and_accept():
    html = FormRenderer(ui=parse_ui({"docs": {
        "ui:widget": "file", "ui:multiple": True,
        "ui:accept": ["application/pdf", "image/png"],
    }}))(Files)
    assert ('<input accept="application/pdf,image/png" id="field-docs" '
            'multiple="multiple" name="docs"') in html
    assert 'enctype="multipart/form-data"' in html


def test_file_input_without_the_options():
    html = FormRenderer(ui=parse_ui({"docs": {"ui:widget": "file"}}))(Files)
    assert "multiple" not in html and "accept" not in html


def test_accept_can_be_a_string():
    html = FormRenderer(ui=parse_ui({"docs": {
        "ui:widget": "file", "ui:accept": ".pdf"}}))(Files)
    assert 'accept=".pdf"' in html


def test_several_uploads_reach_the_model():
    class View(Form):
        csrf = False

        def get_schema(self, request):
            return Files

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            return Response(",".join(doc.filename for doc in data.docs))

    def post(*names):
        return View()(Request(EnvironBuilder(method="POST", data={
            "__trigger__": "save",
            "docs": [(BytesIO(b"x"), name) for name in names],
        }).get_environ())).get_data(as_text=True)

    assert post("a.pdf", "b.pdf") == "a.pdf,b.pdf"
    assert post("a.pdf") == "a.pdf"


def test_mask_needs_a_widget():
    mask = {"mask": "99-9999", "mask_placeholder": "#"}
    html = render({"name": {"ui:mask": mask}})
    assert "data-mask" not in html and "##-####" not in html
    assert "__formidable_masks" not in html

    html = render({"name": {"ui:mask": mask, "ui:widget": "text"}})
    assert 'data-mask="99-9999"' in html
    assert 'placeholder="##-####"' in html
    assert "__formidable_masks" in html


def test_mask_keeps_an_explicit_placeholder():
    html = render({"name": {"ui:widget": "text", "ui:placeholder": "Nummer",
                            "ui:mask": {"mask": "99"}}})
    assert 'placeholder="Nummer"' in html


def test_scripts_are_only_included_when_needed():
    html = render({"body": {"ui:conditions": [CONDITION]}})
    assert html.count("<script>") == 2  # rows and conditions
    assert html.count("FormidableConditions") >= 1

    class Flat(BaseModel):
        name: str

    html = FormRenderer(ui=parse_ui({"name": {"ui:conditions": [CONDITION]}}))(Flat)
    assert html.count("<script>") == 1
    assert "__formidable_rows" not in html


def test_bound_forms_include_the_conditions_script():
    class Flat(BaseModel):
        name: str

    renderer = FormRenderer(ui=parse_ui({"name": {"ui:conditions": [CONDITION]}}))
    bound = renderer.bind(Flat)
    assert "FormidableConditions" in bound.scripts()
    assert 'data-conditions="' in str(bound["name"])
    assert FormRenderer().bind(Flat).scripts() == ""


def test_entries_without_a_field_are_ignored():
    assert "Hint" not in render(
        {"ht_x": {"ui:widget": "helptext", "ui:title": "Hint"}})


def test_load_ui(tmp_path):
    path = tmp_path / "ui_schema.json"
    path.write_text(json.dumps({"name": {"ui:title": "Ä", "ui:mask": {"mask": "9"}}}),
                    encoding="utf-8")
    assert load_ui(path)["name"].title == "Ä"
