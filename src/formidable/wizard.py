"""Forms over several steps, with drafts to continue later.

One model, split up by field names: its validators stay in one place and a
generated model needs no changes. What was entered so far stays raw in a
draft store, and the model validates it step by step and once more at the end.
"""

import copy
import hashlib
import json
import os
import secrets
import time
import typing as t
from pathlib import Path

from markupsafe import Markup
from pydantic import BaseModel, ValidationError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import redirect

from formidable.conditions import is_visible, value_at
from formidable.data import normalize
from formidable.renderers import resolve
from formidable.views import Form, trigger

REVIEW = "review"


class Step(t.NamedTuple):
    name: str
    title: str
    fields: tuple[str, ...] | None = None  # None: all not in another step


class StepLink(t.NamedTuple):
    name: str
    title: str
    current: bool


class DraftStore(t.Protocol):
    def load(self, key: str) -> dict | None: ...
    def save(self, key: str, data: dict) -> None: ...
    def delete(self, key: str) -> None: ...


class MemoryDraftStore:
    """Keeps drafts in this process: for tests and development."""

    def __init__(self):
        self.drafts: dict[str, dict] = {}

    def load(self, key):
        return copy.deepcopy(self.drafts.get(key))

    def save(self, key, data):
        self.drafts[key] = copy.deepcopy(data)

    def delete(self, key):
        self.drafts.pop(key, None)


class FileDraftStore:
    """Keeps each draft as a JSON file only its owner on this system can read.

    The contents are not encrypted. Call `purge()` regularly, as nothing else
    removes the drafts of forms that were never finished.
    """

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, key: str) -> Path:
        return self.folder / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def load(self, key):
        try:
            return json.loads(self.path(key).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def save(self, key, data):
        path = self.path(key)
        partial = path.with_suffix(f".{secrets.token_hex(4)}.tmp")
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file)
        partial.replace(path)

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def purge(self, max_age: float) -> int:
        """Remove drafts untouched for `max_age` seconds, returning how many."""
        limit = time.time() - max_age
        old = [path for path in self.folder.glob("*.json")
               if path.stat().st_mtime < limit]
        for path in old:
            path.unlink(missing_ok=True)
        return len(old)


def plain(value: t.Any) -> t.Any:
    """Submitted data without files, which a draft cannot hold."""
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()
                if not isinstance(item, FileStorage)}
    if isinstance(value, list):
        return [plain(item) for item in value
                if not isinstance(item, FileStorage)]
    return value


def holds_files(schema: type[BaseModel]) -> str | None:
    """The first field of a model that needs the upload itself, or None."""
    for name, model_field in schema.model_fields.items():
        hint = resolve(model_field.annotation)[0].hint
        if t.get_origin(hint) is list and (args := t.get_args(hint)):
            hint = resolve(args[0])[0].hint
        if hint in (FileStorage, bytes):
            return name
        is_model = isinstance(hint, type) and issubclass(hint, BaseModel)
        if is_model and (nested := holds_files(hint)):
            return f"{name}.{nested}"
    return None


class Wizard(Form):
    """A form over several steps. The submit of the last one calls `done`::

        class Claim(Wizard):
            steps = (Step("person", "Person", ("name", "address")),
                     Step("event", "Event"))
            store = FileDraftStore("/var/lib/myapp/drafts")

            def get_schema(self, request):
                return ClaimForm

            def done(self, request, data):
                ...
    """

    steps: t.ClassVar[tuple[Step, ...]] = ()
    store: t.ClassVar[DraftStore | None] = None
    review: t.ClassVar[bool] = True      # a page to check everything at the end
    drafts: t.ClassVar[bool] = True      # offer to save and continue later
    draft_cookie: t.ClassVar[str] = "formidable-draft"
    draft_max_age: t.ClassVar[int] = 30 * 24 * 60 * 60  # once saved on purpose

    def done(self, request, data: BaseModel):
        """Everything is valid: act on it. The draft goes afterwards."""
        raise NotImplementedError()

    def get_store(self, request) -> DraftStore:
        if self.store is None:
            raise TypeError(f"{type(self).__name__} needs a draft store: "
                            "set `store` or override get_store().")
        return self.store

    def get_draft_key(self, request) -> str:
        """Whose draft this is. By default a random token in a cookie; with
        logins, return the user's id instead, also to continue elsewhere."""
        token = request.environ.get("formidable.draft_token")
        if not token:
            token = request.cookies.get(self.draft_cookie) \
                or secrets.token_urlsafe(32)
            request.environ["formidable.draft_token"] = token
        return f"{type(self).__name__}:{token}"

    # --- steps ---

    def step_fields(self, request) -> dict[str, tuple[str, ...]]:
        """The fields of each step, by its name."""
        schema = self.get_schema(request)
        if name := holds_files(schema):
            raise TypeError(
                f"{name!r} needs the upload itself, which a draft cannot hold: "
                "declare it as `str` or `list[str]` and set an `upload_url`.")
        named = [field for step in self.steps for field in step.fields or ()]
        if unknown := set(named) - set(schema.model_fields):
            raise ValueError(f"{schema.__name__} has no fields {sorted(unknown)}")
        rest = tuple(f for f in schema.model_fields if f not in named)
        if rest and all(step.fields is not None for step in self.steps):
            raise ValueError(f"These fields are in no step: {list(rest)}")
        return {step.name: step.fields if step.fields is not None else rest
                for step in self.steps}

    def active_steps(self, request, draft: dict) -> list[Step]:
        """The steps with something to show, given the answers so far."""
        ui = self.get_renderer(request).ui
        fields = self.step_fields(request)
        return [step for step in self.steps
                if any(is_visible(field, ui, draft) for field in fields[step.name])]

    def current_step(self, request, draft: dict) -> str:
        active = self.active_steps(request, draft)
        wanted = request.args.get("step")
        if wanted == REVIEW and self.review:
            return REVIEW
        if any(step.name == wanted for step in active):
            return wanted
        return active[0].name if active else self.steps[0].name

    def neighbour(self, request, draft: dict, offset: int) -> str | None:
        """The step before or after the current one, None past the end."""
        names = [step.name for step in self.active_steps(request, draft)]
        if self.review:
            names.append(REVIEW)
        position = names.index(self.current_step(request, draft)) + offset
        return names[position] if 0 <= position < len(names) else None

    def to_step(self, request, step: str, **params):
        return redirect("?" + "&".join(
            f"{key}={value}" for key, value in {"step": step, **params}.items()),
            code=303)

    # --- drafts ---

    def load_draft(self, request) -> dict:
        return self.get_store(request).load(self.get_draft_key(request)) or {}

    def merge(self, request, submitted: dict) -> dict:
        """The draft with this step's fields as submitted, saved."""
        draft = self.load_draft(request)
        step = self.current_step(request, draft)
        if step != REVIEW:
            submitted = plain(submitted)
            for field in self.step_fields(request)[step]:
                draft.pop(field, None)
                if field in submitted:
                    draft[field] = submitted[field]
            self.get_store(request).save(self.get_draft_key(request), draft)
        return draft

    def validate(self, request, draft: dict) -> BaseModel:
        # fields of steps skipped by a condition were never normalized
        schema = self.get_schema(request)
        return schema(**normalize(schema, copy.deepcopy(draft)))

    def errors_for(self, request, draft: dict, step: str) -> dict[str, str]:
        """The errors to show on a step. The others' wait for their turn."""
        try:
            self.validate(request, draft)
        except ValidationError as exc:
            errors = self.errors_of(exc, request)
        else:
            return {}
        if step == REVIEW:
            return {path: msg for path, msg in errors.items() if not path}
        fields = self.step_fields(request)[step]
        last = not self.review and step == self.steps[-1].name
        return {path: msg for path, msg in errors.items()
                if path.split(".")[0] in fields or (last and not path)}

    def first_failing(self, request, draft: dict, exc: ValidationError) -> str:
        errors = self.errors_of(exc, request)
        fields = self.step_fields(request)
        for step in self.active_steps(request, draft):
            if any(path.split(".")[0] in fields[step.name] for path in errors):
                return step.name
        return REVIEW if self.review else self.steps[-1].name

    # --- what the form shows ---

    def get_fields(self, request):
        step = self.current_step(request, self.load_draft(request))
        return () if step == REVIEW else self.step_fields(request)[step]

    def get_hidden(self, request):
        """Answers from other steps that conditions here depend on."""
        draft = self.load_draft(request)
        fields = self.get_fields(request)
        hidden = {}
        for path, ui in self.get_renderer(request).ui.items():
            if path.split(".")[0] not in fields or not ui.condition_data:
                continue
            for condition in ui.condition_data.get("conditions", ()):
                target = condition["field"]
                if target.split(".")[0] not in fields and ".items." not in target:
                    value = value_at(draft, target)
                    unanswered = value in (None, False, "false")
                    hidden[target] = "" if unanswered else value
        return hidden

    def get_buttons(self, request):
        renderer = self.configured_renderer(request)
        draft = self.load_draft(request)
        step = self.current_step(request, draft)
        names = []
        if self.neighbour(request, draft, -1):
            names.append(("back", "ui_back", "Back"))
        if self.neighbour(request, draft, 1):
            names.append(("next", "ui_next", "Next"))
        else:
            names.append(("send", "ui_send", "Send"))
        if self.drafts and step != REVIEW:
            names.append(("save_draft", "ui_save_draft", "Save and continue later"))
        return [self.buttons[name]._replace(title=renderer.text(key, default))
                for name, key, default in names]

    def render_steps(self, request) -> Markup:
        """Where the user is: for own templates, above the form."""
        renderer = self.configured_renderer(request)
        draft = self.load_draft(request)
        current = self.current_step(request, draft)
        links = [StepLink(step.name, step.title, step.name == current)
                 for step in self.active_steps(request, draft)]
        if self.review:
            links.append(StepLink(
                REVIEW, renderer.text("ui_review", "Review"), current == REVIEW))
        if len(links) < 2:
            return Markup("")
        number = next(i for i, link in enumerate(links, 1) if link.current)
        return renderer.render_template(
            "formidable/steps.pt",
            label=renderer.text("ui_steps", "Steps"),
            position=renderer.text(
                "ui_step_position", "Step {number} of {total}: {title}",
                number=number, total=len(links), title=links[number - 1].title),
            steps=links)

    def render_status(self, request) -> Markup:
        if "saved" not in request.args:
            return Markup("")
        renderer = self.configured_renderer(request)
        return renderer.render_template(
            "formidable/status.pt",
            message=renderer.text(
                "ui_saved", "Your entries have been saved. You can continue later."))

    def render_review(self, request, draft: dict, errors=None) -> Markup:
        renderer = self.configured_renderer(request)
        schema = self.get_schema(request)
        fields = self.step_fields(request)
        sections = [
            {"name": step.name, "title": step.title,
             "fields": renderer(schema, values=draft, readonly=True,
                                only=fields[step.name])}
            for step in self.active_steps(request, draft)]
        return Markup("\n").join((
            renderer.render_template(
                "formidable/review.pt", sections=sections,
                edit=renderer.text("ui_edit", "Change")),
            renderer(schema, values=draft, errors=errors, readonly=True, only=(),
                     buttons=self.get_buttons(request),
                     csrf_token=self.get_csrf_token(request))))

    def render_step(self, request, values, errors):
        """The form of a step: override this for an own layout."""
        return Form.get_form(self, request, values=values, errors=errors)

    def get_form(self, request, values=None, errors=None):
        draft = self.load_draft(request)
        step = self.current_step(request, draft)
        if errors is None and "check" in request.args:
            errors = self.errors_for(request, draft, step)
        form = (self.render_review(request, draft, errors) if step == REVIEW
                else self.render_step(request, draft if values is None else values,
                                      errors))
        return Markup("\n").join(
            (self.render_steps(request), self.render_status(request), Markup(form)))

    # --- the buttons ---

    @trigger(name="next", title="Next", order=1)
    def next_step(self, request, data):
        draft = self.merge(request, data)
        step = self.current_step(request, draft)
        errors = self.errors_for(request, draft, step)
        if errors:
            return self.render_response(
                self.get_form(request, values=draft, errors=errors), request)
        return self.to_step(request, self.neighbour(request, draft, 1))

    @trigger(name="back", title="Back", order=0)
    def previous_step(self, request, data):
        draft = self.merge(request, data)
        target = self.neighbour(request, draft, -1)
        return self.to_step(request, target or self.current_step(request, draft))

    @trigger(name="save_draft", title="Save and continue later", order=3)
    def save_draft(self, request, data):
        draft = self.merge(request, data)
        request.environ["formidable.draft_keep"] = True
        return self.to_step(request, self.current_step(request, draft), saved=1)

    @trigger(name="send", title="Send", order=2)
    def send(self, request, data):
        draft = self.merge(request, data)
        try:
            model = self.validate(request, draft)
        except ValidationError as exc:
            return self.to_step(
                request, self.first_failing(request, draft, exc), check=1)
        response = self.done(request, model)
        self.get_store(request).delete(self.get_draft_key(request))
        if "formidable.draft_token" in request.environ:
            request.environ["formidable.draft_token"] = None
            response.delete_cookie(self.draft_cookie)
        return response

    def __call__(self, request):
        response = super().__call__(request)
        token = request.environ.get("formidable.draft_token")
        keep = request.environ.get("formidable.draft_keep")
        # only for this browser session, unless saved on purpose: someone
        # else may use this computer next
        if token and (keep or request.cookies.get(self.draft_cookie) != token):
            response.set_cookie(
                self.draft_cookie, token, httponly=True, samesite="Lax",
                secure=request.is_secure,
                max_age=self.draft_max_age if keep else None)
        return response
