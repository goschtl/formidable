import json
import os
import re
import stat
import typing as t

import pytest
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from werkzeug.test import Client
from werkzeug.wrappers import Request, Response

from formidable.fields import UploadedFile
from formidable.renderers import FormRenderer
from formidable.ui import parse_ui
from formidable.wizard import FileDraftStore, MemoryDraftStore, Step, Wizard


class Address(BaseModel):
    city: str = Field(..., title="City")


class Claim(BaseModel):
    name: str = Field(..., title="Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(False, title="Agree")
    hurt: t.Literal["yes", "no"] = Field("no", title="Hurt")
    injury: str | None = Field(None, title="Injury")
    doctor: str | None = Field(None, title="Doctor")
    address: Address = Field(..., title="Address")

    @model_validator(mode="after")
    def adults_only(self):
        if self.age < 18:
            raise PydanticCustomError("adult", "Adults only.")
        return self

    @model_validator(mode="after")
    def injury_when_hurt(self):
        if self.hurt == "yes" and not self.injury:
            raise PydanticCustomError("missing", "Say which.", {"field": "injury"})
        return self


UI = parse_ui({
    "injury": {"ui:conditions": [
        {"field": "hurt", "operator": "equals", "value": "yes"}]},
    "doctor": {"ui:conditions": [
        {"field": "hurt", "operator": "equals", "value": "yes"}]},
})


def make_view(**attributes):
    finished = []

    class View(Wizard):
        steps = (Step("person", "Person", ("name", "age", "agree")),
                 Step("event", "Event", ("hurt", "injury")),
                 Step("care", "Care", ("doctor",)),
                 Step("place", "Place"))
        store = MemoryDraftStore()

        def get_schema(self, request):
            return Claim

        def get_renderer(self, request):
            return FormRenderer(ui=UI)

        def done(self, request, data):
            finished.append(data)
            return Response("thanks")

    for name, value in attributes.items():
        setattr(View, name, value)
    view = View()
    view.finished = finished
    return view


class Browser:
    def __init__(self, view):
        self.view = view
        self.client = Client(Request.application(view))
        self.url = "/"

    def get(self, url="/"):
        self.url = url
        return self.client.get(url)

    def press(self, button, url=None, **data):
        url = url or self.url
        self.client.get(url)
        token = self.client.get_cookie("formidable-csrf").value
        response = self.client.post(url, data={
            "__csrf__": token, "__trigger__": button, **data})
        if response.status_code == 303:
            self.url = "/" + response.headers["Location"]
        return response


@pytest.fixture
def browser():
    return Browser(make_view())


def fill_person(browser):
    return browser.press("next", name="Ann", age="30")


def field_names(html):
    return re.findall(r'<(?:input|select|textarea)[^>]*\bname="([^"]+)"', html)


def test_first_step_shows_only_its_fields(browser):
    html = browser.get().text
    assert [n for n in field_names(html) if not n.startswith("__")] == [
        "name", "age", "agree"]


def test_progress_is_announced(browser):
    html = browser.get().text
    assert "Step 1 of 4: Person" in html
    assert 'aria-current="step"' in html
    assert re.search(r'aria-current="step"[^>]*><a[^>]*href="\?step=person"', html)


def test_steps_with_nothing_to_show_are_skipped(browser):
    fill_person(browser)
    response = browser.press("next", hurt="no")
    assert response.headers["Location"] == "?step=place"
    assert "Care" not in browser.get("/?step=place").text


def test_a_condition_makes_a_step_appear(browser):
    fill_person(browser)
    response = browser.press("next", hurt="yes", injury="arm")
    assert response.headers["Location"] == "?step=care"


def test_invalid_step_stays_with_only_its_errors(browser):
    response = browser.press("next", name="Ann", age="x")
    assert response.status_code == 200
    assert browser.view.finished == []
    assert 'name="age"' in response.text
    assert 'value="x"' in response.text
    assert 'id="field-age-error"' in response.text
    assert "field-address.city-error" not in response.text
    assert 'href="#field-address.city"' not in response.text


def test_answers_survive_going_back(browser):
    fill_person(browser)
    browser.press("back", hurt="yes", injury="half typed")
    assert browser.url == "/?step=person"
    assert 'value="Ann"' in browser.get("/?step=person").text
    html = browser.get("/?step=event").text
    assert "half typed" in html


def test_back_does_not_validate(browser):
    fill_person(browser)
    response = browser.press("back", hurt="nonsense")
    assert response.status_code == 303


def test_first_step_has_no_back_button(browser):
    assert 'value="back"' not in browser.get().text
    fill_person(browser)
    assert 'value="back"' in browser.get(browser.url).text


def test_cleared_field_leaves_the_draft(browser):
    fill_person(browser)
    browser.press("next", url="/?step=person", name="", age="30")
    assert 'value="Ann"' not in browser.get("/?step=person").text


def test_unchecked_box_is_remembered(browser):
    browser.press("next", name="Ann", age="30", agree="true")
    assert "checked" in browser.get("/?step=person").text
    browser.press("next", url="/?step=person", name="Ann", age="30")
    assert 'checked="checked"' not in browser.get("/?step=person").text


def walk_to_review(browser):
    fill_person(browser)
    browser.press("next", hurt="no")
    return browser.press("next", **{"address.city": "Bonn"})


def test_review_shows_everything_as_text(browser):
    response = walk_to_review(browser)
    assert response.headers["Location"] == "?step=review"
    html = browser.get("/?step=review").text
    assert ">Ann<" in html and ">Bonn<" in html and ">No<" in html
    assert "<strong>Injury</strong>" not in html
    assert 'href="?step=person"' in html
    assert 'value="send"' in html
    assert 'value="next"' not in html
    assert not [n for n in field_names(html) if not n.startswith("__")]


def test_send_calls_done_and_removes_the_draft(browser):
    walk_to_review(browser)
    response = browser.press("send")
    assert response.text == "thanks"
    model = browser.view.finished[0]
    assert model.name == "Ann" and model.address.city == "Bonn"
    assert model.agree is False
    assert browser.view.store.drafts == {}
    assert browser.client.get_cookie("formidable-draft") is None


def test_send_with_gaps_goes_to_the_first_failing_step(browser):
    fill_person(browser)
    response = browser.press("send", url="/?step=review")
    assert response.headers["Location"] == "?step=place&check=1"
    html = browser.get("/?step=place&check=1").text
    assert 'id="field-address-error"' in html


def test_model_level_error_shows_on_the_review_page(browser):
    browser.press("next", name="Ann", age="3")
    browser.press("next", hurt="no")
    browser.press("next", **{"address.city": "Bonn"})
    response = browser.press("send")
    assert response.headers["Location"] == "?step=review&check=1"
    assert "Adults only." in browser.get("/?step=review&check=1").text


def test_cross_field_error_goes_back_to_its_step(browser):
    # a model validator only runs once all fields are there: at the end
    fill_person(browser)
    assert browser.press("next", hurt="yes").status_code == 303
    browser.press("next", doctor="Who")
    browser.press("next", **{"address.city": "Bonn"})
    response = browser.press("send")
    assert response.headers["Location"] == "?step=event&check=1"
    assert "Say which." in browser.get("/?step=event&check=1").text


def test_without_review_the_last_step_sends():
    browser = Browser(make_view(review=False))
    fill_person(browser)
    browser.press("next", hurt="no")
    html = browser.get(browser.url).text
    assert 'value="send"' in html and 'value="next"' not in html
    assert "Review" not in html
    assert browser.press("send", **{"address.city": "Bonn"}).text == "thanks"


def test_without_review_a_model_level_error_shows_on_the_last_step():
    browser = Browser(make_view(review=False))
    browser.press("next", name="Ann", age="3")
    browser.press("next", hurt="no")
    response = browser.press("send", **{"address.city": "Bonn"})
    assert response.headers["Location"] == "?step=place&check=1"
    assert "Adults only." in browser.get("/?step=place&check=1").text


def test_a_single_step_is_a_form_with_a_draft():
    view = make_view(review=False, steps=(Step("all", "All"),))
    browser = Browser(view)
    html = browser.get().text
    assert "form-steps" not in html
    assert 'value="save_draft"' in html and 'value="send"' in html


def test_conditions_see_answers_of_other_steps(browser):
    fill_person(browser)
    browser.press("next", hurt="yes", injury="arm")
    html = browser.get("/?step=care").text
    assert re.search(r'name="hurt"[^>]*value="yes"', html)


def test_answers_carried_along_do_not_overwrite(browser):
    fill_person(browser)
    browser.press("next", hurt="yes", injury="arm")
    browser.press("next", doctor="Who", hurt="no")
    assert '"yes"' in json.dumps(browser.view.store.drafts)


def test_draft_is_saved_for_later(browser):
    response = browser.press("save_draft", name="Ann")
    assert response.headers["Location"] == "?step=person&saved=1"
    cookie = next(h for h in response.headers.getlist("Set-Cookie")
                  if h.startswith("formidable-draft="))
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Max-Age" in cookie
    html = browser.get("/?step=person&saved=1").text
    assert 'role="status"' in html
    assert 'value="Ann"' in html


def test_cookie_ends_with_the_browser_unless_saved_on_purpose(browser):
    response = browser.get()
    cookie = next(h for h in response.headers.getlist("Set-Cookie")
                  if h.startswith("formidable-draft="))
    assert "Max-Age" not in cookie


def test_another_browser_has_its_own_draft(browser):
    fill_person(browser)
    other = Browser(browser.view)
    assert 'value="Ann"' not in other.get("/?step=person").text


def test_csrf_is_required(browser):
    browser.client.get("/")
    assert browser.client.post("/", data={"__trigger__": "next"}).status_code == 403


def test_own_draft_key_needs_no_cookie():
    class Logged(type(make_view())):
        def get_draft_key(self, request):
            return "user-1"

    browser = Browser(Logged())
    fill_person(browser)
    assert browser.client.get_cookie("formidable-draft") is None
    assert "user-1" in browser.view.store.drafts


def test_an_unknown_step_falls_back(browser):
    assert "Step 1 of 4" in browser.get("/?step=<script>").text
    assert "<script>" not in browser.get("/?step=<script>").text.split("</nav>")[0]


def test_german_buttons():
    from formidable import i18n

    browser = Browser(make_view(error_messages=i18n.GERMAN))
    html = browser.get().text
    assert ">Weiter<" in html and "Schritt 1 von 4" in html


def test_upload_fields_are_refused_with_a_reason():
    class Upload(BaseModel):
        doc: UploadedFile

    class View(Wizard):
        steps = (Step("a", "A"),)
        store = MemoryDraftStore()

        def get_schema(self, request):
            return Upload

    with pytest.raises(TypeError, match="'doc' needs the upload"):
        Client(Request.application(View())).get("/")


def test_fields_in_no_step_are_refused():
    view = make_view(steps=(Step("a", "A", ("name",)),))
    with pytest.raises(ValueError, match="in no step"):
        Client(Request.application(view)).get("/")


def test_unknown_fields_are_refused():
    view = make_view(steps=(Step("a", "A", ("nope",)), Step("b", "B")))
    with pytest.raises(ValueError, match="nope"):
        Client(Request.application(view)).get("/")


def test_a_store_is_required():
    view = make_view(store=None)
    with pytest.raises(TypeError, match="draft store"):
        Client(Request.application(view)).get("/")


def test_file_store(tmp_path):
    store = FileDraftStore(tmp_path / "drafts")
    assert store.load("../../etc/passwd") is None
    store.save("../../etc/passwd", {"name": "Ann"})
    assert store.load("../../etc/passwd") == {"name": "Ann"}
    files = list((tmp_path / "drafts").iterdir())
    assert len(files) == 1 and files[0].parent == tmp_path / "drafts"
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "drafts").stat().st_mode) == 0o700
    store.delete("../../etc/passwd")
    store.delete("../../etc/passwd")
    assert store.load("../../etc/passwd") is None


def test_file_store_purge(tmp_path):
    store = FileDraftStore(tmp_path)
    store.save("old", {})
    store.save("new", {})
    os.utime(store.path("old"), (1, 1))
    assert store.purge(max_age=3600) == 1
    assert store.load("old") is None
    assert store.load("new") == {}


def test_wizard_through_the_file_store(tmp_path):
    browser = Browser(make_view(store=FileDraftStore(tmp_path)))
    walk_to_review(browser)
    assert browser.press("send").text == "thanks"
    assert list(tmp_path.iterdir()) == []


def test_a_bound_step_only_has_its_fields(browser):
    from werkzeug.test import EnvironBuilder

    request = Request(EnvironBuilder(path="/?step=person").get_environ())
    form = browser.view.bind(request)
    assert "name" in form
    assert "address" not in form
    assert [field.name for field in form] == ["name", "age", "agree"]
