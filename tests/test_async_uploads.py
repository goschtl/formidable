import json
import re
from html import unescape

from pydantic import BaseModel, Field

from formidable.fields import FileUpload, UploadedFile
from formidable.renderers import FormRenderer
from formidable.ui import parse_ui


class Schema(BaseModel):
    many: list[str] = Field(default_factory=list)
    one: str | None = None
    real: list[UploadedFile] = Field(default_factory=list)
    blob: FileUpload | None = None


UI = parse_ui({name: {"ui:widget": "file"} for name in Schema.model_fields}
              | {"many": {"ui:widget": "file", "ui:multiple": True,
                          "ui:accept": ["application/pdf"]}})


def render(values=None, **options):
    renderer = FormRenderer(ui=UI, upload_url="/upload", **options)
    return str(renderer(Schema, values=values))


def input_tag(html, name):
    return re.search(rf'<input[^>]*name="{name}"[^>]*>', html).group(0)


def attribute(tag, name):
    return unescape(re.search(rf'{name}="([^"]*)"', tag).group(1))


def test_references_upload_apart():
    html = render()
    for name in ("many", "one"):
        assert attribute(input_tag(html, name), "data-upload-url") == "/upload"
    assert "multiple" in input_tag(html, "many")
    assert attribute(input_tag(html, "many"), "accept") == "application/pdf"


def test_files_wanted_by_the_model_stay_in_the_form():
    html = render()
    for name in ("real", "blob"):
        assert "data-upload-url" not in input_tag(html, name)
    assert 'enctype="multipart/form-data"' in html


def test_only_references_need_no_multipart():
    class OnlyReferences(BaseModel):
        many: list[str] = Field(default_factory=list)

    html = str(FormRenderer(ui=UI, upload_url="/upload")(OnlyReferences))
    assert "enctype" not in html


def test_without_an_upload_url_nothing_changes():
    html = str(FormRenderer(ui=UI)(Schema))
    assert "data-upload-url" not in html
    assert "FilePond" not in html


def test_widget_and_its_assets_only_where_needed():
    html = render()
    assert "FilePond" in html
    assert ".filepond--root" in html
    assert "FilePondPluginFileValidateType" in html


def test_earlier_uploads_come_back():
    html = render({"many": ["a", "b"], "one": "c"})
    assert json.loads(attribute(input_tag(html, "many"),
                                "data-upload-files")) == ["a", "b"]
    assert json.loads(attribute(input_tag(html, "one"),
                                "data-upload-files")) == ["c"]


def test_upload_ids_are_escaped():
    tag = input_tag(render({"one": '"><script>'}), "one")
    assert "<script>" not in tag


def test_options_reach_the_widget():
    html = render(upload_options={"labelIdle": 'Hier <span class="x">ablegen</span>'})
    options = json.loads(attribute(input_tag(html, "one"), "data-upload-options"))
    assert options == {"labelIdle": 'Hier <span class="x">ablegen</span>'}


def test_bound_forms_include_the_widget():
    renderer = FormRenderer(ui=UI, upload_url="/upload")
    bound = renderer.bind(Schema)
    assert "data-upload-url" in str(bound["one"])
    assert "FilePond" in str(bound.scripts())


def test_a_list_row_in_a_template_needs_the_assets():
    class Row(BaseModel):
        scan: str | None = None

    class Rows(BaseModel):
        rows: list[Row] = Field(default_factory=list)

    ui = parse_ui({"rows.items.scan": {"ui:widget": "file"}})
    html = str(FormRenderer(ui=ui, upload_url="/upload")(Rows))
    assert "data-upload-url" in html
    assert "FilePondPluginFileValidateSize" in html
