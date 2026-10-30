from io import BytesIO

from pydantic import BaseModel, Field
from werkzeug.datastructures import FileStorage
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.fields import FileUpload, UploadedFile, read_upload
from formidable.renderers import FormRenderer
from formidable.views import Form, trigger


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    avatar: FileUpload = Field(..., title="Avatar")
    attachment: FileUpload | None = Field(None, title="Attachment")


class Index(Form):
    csrf = False

    def get_schema(self, request):
        return Schema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(
            f"{data.name}:{data.avatar.decode()}:{data.attachment}",
            mimetype="text/plain")


def make_request(method="GET", data=None):
    builder = EnvironBuilder(method=method, data=data)
    return Request(builder.get_environ())


def test_read_upload_converts_filestorage():
    storage = FileStorage(BytesIO(b"content"), filename="a.txt")
    assert read_upload(storage) == b"content"
    assert read_upload("plain") == "plain"


def test_file_field_renders_file_input_and_enctype():
    renderer = FormRenderer()
    html = renderer(Schema).render()
    assert 'enctype="multipart/form-data"' in html
    assert '<input id="field-avatar" name="avatar" required="required" type="file">' in html
    # optional upload is not required
    assert '<input id="field-attachment" name="attachment" type="file">' in html


def test_forms_without_files_have_no_enctype():
    class Plain(BaseModel):
        name: str

    assert "enctype" not in FormRenderer()(Plain).render()


def test_file_input_never_prefills_value():
    html = FormRenderer()(Schema, values={"avatar": b"secret"}).render()
    assert "secret" not in html
    assert "please choose the file again" in html


def test_upload_reaches_validated_model():
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "avatar": (BytesIO(b"PNGDATA"), "avatar.png"),
    }))
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Jane:PNGDATA:None"


def test_empty_file_input_means_absent():
    # a file input left empty submits a part with no filename
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "avatar": (BytesIO(b"x"), "a.png"),
        "attachment": (BytesIO(b""), ""),
    }))
    assert response.get_data(as_text=True) == "Jane:x:None"


def test_missing_required_upload_rerenders_with_error():
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
    }))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="field-error"' in html
    assert 'value="Jane"' in html


def test_failed_validation_hints_at_lost_upload():
    # another field fails: the upload cannot round-trip, tell the user
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "avatar": (BytesIO(b"PNGDATA"), "avatar.png"),
    }))
    html = response.get_data(as_text=True)
    assert "please choose the file again" in html


class StreamSchema(BaseModel):
    doc: UploadedFile = Field(..., title="Document")
    note: UploadedFile | None = Field(None, title="Note")


class StreamIndex(Form):
    csrf = False

    def get_schema(self, request):
        return StreamSchema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(
            f"{data.doc.filename}:{data.doc.content_type}:"
            f"{data.doc.read().decode()}:{data.note}",
            mimetype="text/plain")


def test_uploaded_file_renders_file_input():
    html = FormRenderer()(StreamSchema).render()
    assert 'enctype="multipart/form-data"' in html
    assert '<input id="field-doc" name="doc" required="required" type="file">' in html
    assert '<input id="field-note" name="note" type="file">' in html


def test_uploaded_file_keeps_stream_and_metadata():
    response = StreamIndex()(make_request("POST", data={
        "__trigger__": "save",
        "doc": (BytesIO(b"the-content"), "report.pdf", "application/pdf"),
    }))
    assert response.status_code == 200
    assert response.get_data(as_text=True) == \
        "report.pdf:application/pdf:the-content:None"


def test_uploaded_file_rejects_non_files():
    # a plain string posted under the field name must not validate
    response = StreamIndex()(make_request("POST", data={
        "__trigger__": "save",
        "doc": "sneaky-string",
    }))
    assert response.status_code == 200
    assert 'class="field-error"' in response.get_data(as_text=True)


def test_nested_upload_via_dot_path():
    class Doc(BaseModel):
        data: FileUpload

    class WithDocs(BaseModel):
        docs: list[Doc] = Field(default_factory=list)

    class DocsIndex(Form):
        csrf = False

        def get_schema(self, request):
            return WithDocs

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            return Response(data.docs[0].data.decode())

    response = DocsIndex()(make_request("POST", data={
        "__trigger__": "save",
        "docs.0.data": (BytesIO(b"nested!"), "n.txt"),
    }))
    assert response.get_data(as_text=True) == "nested!"
