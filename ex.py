import datetime
import enum
import hmac
import secrets
import tempfile
import typing as t
from pathlib import Path

from autoroutes import Routes as Autoroutes
from pydantic import BaseModel, Field, create_model, model_validator
from pydantic_core import PydanticCustomError
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.http import dump_options_header
from werkzeug.wrappers import Request, Response

from ex_forms.LD_000_0V1100.model import LD_000_0V1100Model
from formidable import i18n, themes
from formidable.fields import UploadedFile
from formidable.renderers import (
    FormRenderer,
    RadioFieldRenderer,
    StringFieldRenderer,
    render_template,
)
from formidable.themes import page
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.themes.material import MATERIAL
from formidable.ui import load_ui, parse_ui
from formidable.views import Form, trigger
from formidable.wizard import FileDraftStore, Step, Wizard

themes.use(MATERIAL)  # the site-wide default
i18n.use(
    {
        **i18n.GERMAN,
        # application-defined error types translate the same way
        "nickname_required": "Wenn Sie den Bedingungen zustimmen, "
        "ist ein Spitzname erforderlich.",
    }
)

routes = Autoroutes()

EX_TEMPLATES = Path(__file__).parent / "ex_templates"


class CustomFieldRenderer(StringFieldRenderer):
    """A custom widget must still render an input named `name`,
    otherwise the field is never submitted and validation always fails."""

    template = "custom_input.pt"


class User(BaseModel):
    id: int
    name: str = "Jane Doe"


class Salutation(enum.Enum):
    mr = "mr"
    mrs = "mrs"
    other = "other"


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    salutation: Salutation = Field(..., title="Salutation")
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")
    birthday: datetime.date | None = Field(None, title="Birthday")
    bio: str | None = Field(None, title="Bio", json_schema_extra={"widget": "textarea"})
    interests: list[t.Literal["sports", "music", "tech"]] = Field(
        default_factory=list, title="Interests"
    )
    avatar: UploadedFile | None = Field(None, title="Avatar")
    users: list[User] = Field(default_factory=list, title="Users")

    @model_validator(mode="after")
    def nickname_required_when_agreeing(self):
        if self.agree and not self.nickname:
            raise PydanticCustomError(
                "nickname_required",
                "When agreeing to the terms, a nickname is required.",
                {"field": "nickname"},
            )
        return self


def available_flavors(request) -> tuple[str, ...]:
    """A selection source that depends on the request — in real life a
    database query, the logged-in user's permissions, the tenant, ..."""
    flavors = ("vanilla", "chocolate", "strawberry")
    if "premium" in request.args:
        flavors += ("pistachio", "black truffle")
    return flavors


class Index(Form):
    def get_schema(self, request):
        # deform's "deferred" pattern: bind the schema to the request.
        # Validation then only accepts exactly these choices.
        flavors = available_flavors(request)
        return create_model(
            "RequestExampleForm",
            __base__=ExampleForm,
            flavor=(t.Literal[flavors], Field("vanilla", title="Flavor")),
        )

    def get_renderer(self, request):
        return FormRenderer(
            theme=self.get_theme(request),
            templates=[Path(__file__).parent / "ex_templates"],
            custom_widgets={
                "name": CustomFieldRenderer,
                # same choice source as the select, radio markup
                "salutation": RadioFieldRenderer,
            },
        )

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="formidable demo"),
            mimetype="text/html",
        )

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ExampleForm instance, not a raw dict.
        print(data)
        headers = {"Location": request.url}
        return Response(request.url, status=302, headers=headers)


class MaterialIndex(Index):
    theme = MATERIAL  # per-view override of the site default


# --- Explicit field rendering with an own template ---
class Anschrift(BaseModel):
    strasse: str = Field(..., title="Straße")
    plz: str = Field(..., title="PLZ")
    ort: str = Field(..., title="Ort")


class FeedbackForm(BaseModel):
    salutation: Salutation = Field(..., title="Salutation")
    name: str = Field(..., title="Name")
    email: str = Field(..., title="E-Mail")
    nickname: str | None = Field(None, title="Nickname")
    anschrift: Anschrift


class Feedback(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return FeedbackForm

    def get_form(self, request, values=None, errors=None):
        # explicit, template-driven rendering: place each field yourself
        return render_template(
            "feedback.pt", dirs=(str(EX_TEMPLATES),),
            form=self.bind(request, values, errors))

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="own template"),
            mimetype="text/html",
        )

    @trigger(name="send", title="Send", validate=True)
    def send(self, request, data):
        return Response(f"Danke, {data.name}!", mimetype="text/plain")


# --- A generated model plus a UI schema, with conditional fields ---

EX_FORMS = Path(__file__).parent / "ex_forms"
LD_000_0V1100_UI = load_ui(EX_FORMS / "LD_000_0V1100" / "ui_schema.json")


class Rueckfrage(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return LD_000_0V1100Model

    def get_renderer(self, request):
        return FormRenderer(theme=self.get_theme(request), ui=LD_000_0V1100_UI)

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request),
                 title=LD_000_0V1100Model.__doc__.splitlines()[0]),
            mimetype="text/html",
        )

    @trigger(name="send", title="Absenden", validate=True)
    def send(self, request, data):
        return Response(data.model_dump_json(indent=2), mimetype="text/plain")


# --- The remaining UI schema options ---


class UIDemoForm(BaseModel):
    kosten: float = Field(..., title="Kosten")
    nummer: str = Field(..., title="Nummer", pattern=r"^\d{2}-\d{4}$")
    belege: list[UploadedFile] = Field(default_factory=list, title="Belege")


UI_DEMO = parse_ui({
    "kosten": {"ui:unit": "EUR", "ui:help": "Bitte Belege beifügen."},
    "nummer": {"ui:widget": "text",
               "ui:mask": {"mask": "99-9999", "mask_placeholder": "#"}},
    "belege": {"ui:widget": "file", "ui:multiple": True,
               "ui:accept": ["application/pdf", "image/png"]},
})


class UIDemo(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return UIDemoForm

    def get_renderer(self, request):
        return FormRenderer(theme=self.get_theme(request), ui=UI_DEMO)

    def render_response(self, html_form, request):
        return Response(page(html_form, self.get_theme(request), title="UI demo"),
                        mimetype="text/html")

    @trigger(name="send", title="Absenden", validate=True)
    def send(self, request, data):
        files = [upload.filename for upload in data.belege]
        return Response(f"{data.kosten} EUR, {data.nummer}, {files}",
                        mimetype="text/plain")


# --- Files uploaded on their own, with FilePond ---


class Uploads:
    """The upload URL: POST stores a file and answers with its id, DELETE
    removes it, GET gives it back after a validation error.

    The upload belongs to whoever holds the CSRF cookie, so nobody can
    submit or fetch someone else's id. A real application also keeps the
    files somewhere lasting and removes those no form was submitted for.
    """

    allowed = frozenset(("application/pdf", "image/png"))

    def __init__(self):
        self.folder = Path(tempfile.mkdtemp(prefix="formidable-uploads-"))
        self.files = {}

    def __call__(self, request):
        owner = request.cookies.get(Form.csrf_cookie)
        if not owner:
            return Response("No session.", status=403)
        if request.method == "GET":
            return self.restore(owner, request.args.get("id", ""))
        token = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(owner, token):
            return Response("Invalid CSRF token.", status=403)
        if request.method == "POST":
            return self.store(owner, request)
        if request.method == "DELETE":
            return self.remove(owner, request.get_data(as_text=True))
        return Response(status=405, headers={"Allow": "GET, POST, DELETE"})

    def store(self, owner, request):
        upload = next(iter(request.files.values()), None)
        # as declared by the browser: inspect the content if it matters
        if upload is None or upload.content_type not in self.allowed:
            return Response("File type not allowed.", status=415)
        upload_id = secrets.token_urlsafe(16)
        upload.save(self.folder / upload_id)
        self.files[upload_id] = (owner, upload.filename, upload.content_type)
        return Response(upload_id, mimetype="text/plain")

    def remove(self, owner, upload_id):
        if not self.owned(owner, upload_id):
            return Response(status=404)
        del self.files[upload_id]
        (self.folder / upload_id).unlink()
        return Response(status=204)

    def restore(self, owner, upload_id):
        if not self.owned(owner, upload_id):
            return Response(status=404)
        _, filename, content_type = self.files[upload_id]
        disposition = dump_options_header("attachment", {"filename": filename})
        return Response(
            (self.folder / upload_id).read_bytes(), mimetype=content_type,
            headers={"Content-Disposition": disposition,
                     "X-Content-Type-Options": "nosniff"})

    def owned(self, owner, upload_id):
        entry = self.files.get(upload_id)
        return entry is not None and hmac.compare_digest(entry[0], owner)

    def label(self, request, upload_id):
        """A file's name for its owner; anyone else just sees the id."""
        owner = request.cookies.get(Form.csrf_cookie, "")
        if self.owned(owner, upload_id):
            return self.files[upload_id][1]
        return upload_id

    def filenames(self, request, upload_ids):
        """The names of submitted uploads, refusing anyone else's."""
        owner = request.cookies.get(Form.csrf_cookie, "")
        if not all(self.owned(owner, upload_id) for upload_id in upload_ids):
            raise BadRequest("Unknown upload.")
        return [self.files[upload_id][1] for upload_id in upload_ids]


uploads = Uploads()


class UploadDemoForm(BaseModel):
    name: str = Field(..., title="Name")
    belege: list[str] = Field(..., title="Belege")
    hat_attest: t.Literal["ja", "nein"] = Field("nein", title="Attest vorhanden?")
    attest: str | None = Field(None, title="Attest")


UPLOAD_DEMO = parse_ui({
    "belege": {"ui:widget": "file", "ui:multiple": True,
               "ui:accept": ["application/pdf", "image/png"],
               "ui:help": "PDF oder PNG, höchstens 2 MB je Datei."},
    "hat_attest": {"ui:widget": "radio"},
    "attest": {"ui:widget": "file",
               "ui:attributes": {"data-max-file-size": "2MB"},
               "ui:conditions": [{"field": "hat_attest", "operator": "equals",
                                  "value": "ja"}]},
})


class UploadDemo(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return UploadDemoForm

    def get_renderer(self, request):
        return FormRenderer(theme=self.get_theme(request), ui=UPLOAD_DEMO,
                            upload_url="/upload", upload_options=i18n.UPLOAD_GERMAN)

    def render_response(self, html_form, request):
        return Response(page(html_form, self.get_theme(request), title="Upload demo"),
                        mimetype="text/html")

    @trigger(name="send", title="Absenden", validate=True)
    def send(self, request, data):
        attest = [data.attest] if data.attest else []
        return Response(f"{data.name}: {uploads.filenames(request, data.belege)}, "
                        f"Attest {uploads.filenames(request, attest)}",
                        mimetype="text/plain")


# --- A form over several steps, with drafts and a review page ---


class UnfallForm(BaseModel):
    name: str = Field(..., title="Name")
    geburtsdatum: datetime.date = Field(..., title="Geburtsdatum")
    unfalltag: datetime.date = Field(..., title="Unfalltag")
    hergang: str = Field(..., title="Unfallhergang",
                         json_schema_extra={"widget": "textarea"})
    verletzt: t.Literal["ja", "nein"] = Field(..., title="Wurden Sie verletzt?")
    verletzung: str | None = Field(None, title="Welche Verletzung?")
    arzt: str | None = Field(None, title="Behandelnder Arzt")
    belege: list[str] = Field(default_factory=list, title="Belege")
    bestaetigt: bool = Field(False, title="Meine Angaben sind richtig")

    @model_validator(mode="after")
    def verletzung_angeben(self):
        if self.verletzt == "ja" and not self.verletzung:
            raise PydanticCustomError(
                "missing", "Pflichtfeld.", {"field": "verletzung"})
        return self

    @model_validator(mode="after")
    def unfall_nach_geburt(self):
        if self.unfalltag < self.geburtsdatum:
            raise PydanticCustomError(
                "unfall_vor_geburt", "Der Unfalltag liegt vor dem Geburtsdatum.")
        return self


UNFALL_UI = parse_ui({
    "verletzt": {"ui:widget": "radio"},
    "verletzung": {"ui:conditions": [{"field": "verletzt", "operator": "equals",
                                      "value": "ja"}]},
    "arzt": {"ui:conditions": [{"field": "verletzt", "operator": "equals",
                                "value": "ja"}]},
    "belege": {"ui:widget": "file", "ui:multiple": True,
               "ui:accept": ["application/pdf", "image/png"]},
})


class UnfallMeldung(Wizard):
    theme = BOOTSTRAP
    steps = (
        Step("person", "Person", ("name", "geburtsdatum")),
        Step("unfall", "Unfall", ("unfalltag", "hergang", "verletzt", "verletzung")),
        Step("behandlung", "Behandlung", ("arzt",)),
        Step("abschluss", "Abschluss", ("belege", "bestaetigt")),
    )
    store = FileDraftStore(Path(tempfile.gettempdir()) / "formidable-drafts")

    def get_schema(self, request):
        return UnfallForm

    def get_renderer(self, request):
        return FormRenderer(
            theme=self.get_theme(request), ui=UNFALL_UI, upload_url="/upload",
            upload_options=i18n.UPLOAD_GERMAN,
            upload_label=lambda upload_id: uploads.label(request, upload_id))

    def render_response(self, html_form, request):
        return Response(
            page(html_form, self.get_theme(request), title="Unfallmeldung", lang="de"),
            mimetype="text/html")

    def done(self, request, data):
        uploads.filenames(request, data.belege)  # only the user's own files
        confirmation = self.get_readonly(request, data)
        return self.render_response(
            f"<h1>Vielen Dank</h1><p>Wir haben erhalten:</p>{confirmation}", request)


# URL routing rules
routes.add("/", endpoint=Index())
routes.add("/rueckfrage", endpoint=Rueckfrage())
routes.add("/ui-demo", endpoint=UIDemo())
routes.add("/upload-demo", endpoint=UploadDemo())
routes.add("/upload", endpoint=uploads)
routes.add("/wizard", endpoint=UnfallMeldung())
routes.add("/material", endpoint=MaterialIndex())
routes.add("/custom", endpoint=Feedback())


class LimitedRequest(Request):
    max_content_length = 2 * 1024 * 1024  # uploads beyond 2 MiB get a 413


# Main WSGI application
def wsgi_app(environ, start_response):
    request = LimitedRequest(environ)
    if matched := routes.match(request.path):
        (route, _params) = matched
        if route is not None:
            try:
                response = route["endpoint"](request)
            except HTTPException as exc:
                # e.g. 413 when an upload exceeds max_content_length
                response = exc
            return response(environ, start_response)

    response = Response("404 Not Found", status=404)
    return response(environ, start_response)


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    print("Serving on http://localhost:8000")
    run_simple("0.0.0.0", 8000, wsgi_app, use_debugger=True, use_reloader=True)
