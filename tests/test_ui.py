import json
import typing as t

from pydantic import BaseModel, Field

from formidable.renderers import FormRenderer
from formidable.ui import load_ui, parse_ui, ui_path


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
    assert '<small class="field-description">From the model</small>' in render({})


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
