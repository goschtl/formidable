from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from formidable.views import Form, trigger


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


class Index(Form):
    csrf = False

    def get_schema(self, request):
        return Schema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        assert isinstance(data, Schema)
        return Response(data.model_dump_json(), mimetype="application/json")


def make_request(method="GET", data=None):
    builder = EnvironBuilder(method=method, data=data)
    return Request(builder.get_environ())


def test_get_renders_form_with_buttons():
    response = Index()(make_request())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<form method="post" novalidate="novalidate">' in html
    assert '<button name="__trigger__" value="save">Save</button>' in html


def test_post_valid_data_runs_action():
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "age": "30",
        "agree": "true",
        "nickname": "",
    }))
    assert response.status_code == 200
    assert response.json == {
        "name": "Jane", "age": 30, "agree": True, "nickname": None,
    }


def test_post_unchecked_checkbox_is_false():
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "age": "30",
    }))
    assert response.json["agree"] is False


def test_post_invalid_data_rerenders_with_errors_and_values():
    response = Index()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "age": "not-a-number",
    }))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="field-error"' in html
    assert 'value="Jane"' in html


def test_post_unknown_trigger_is_400():
    response = Index()(make_request("POST", data={"__trigger__": "nope"}))
    assert response.status_code == 400


def test_post_without_trigger_is_400():
    response = Index()(make_request("POST", data={"name": "Jane"}))
    assert response.status_code == 400


def test_unsupported_method_is_405():
    response = Index()(make_request("PUT"))
    assert response.status_code == 405
    assert response.headers["Allow"] == "GET, POST"


class User(BaseModel):
    id: int
    name: str = "Jane Doe"


class NestedSchema(BaseModel):
    name: str = Field(..., title="Your Name")
    users: list[User] = Field(default_factory=list, title="Users")


class NestedIndex(Form):
    csrf = False

    def get_schema(self, request):
        return NestedSchema

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        assert isinstance(data, NestedSchema)
        return Response(data.model_dump_json(), mimetype="application/json")

    @trigger(name="add_user", title="Add user")
    def add_user(self, request, data):
        data.setdefault("users", []).append({})
        html_form = self.get_form(request, values=data)
        return Response(html_form.render(), mimetype="text/html")

    @trigger(name="remove_user", title="Remove user")
    def remove_user(self, request, data, index):
        users = data.get("users", [])
        if index.isdigit() and int(index) < len(users):
            users.pop(int(index))
        html_form = self.get_form(request, values=data)
        return Response(html_form.render(), mimetype="text/html")


def test_post_nested_data_validates():
    response = NestedIndex()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "users.0.id": "1",
        "users.0.name": "Bob",
        "users.1.id": "2",
    }))
    assert response.status_code == 200
    assert response.json["users"] == [
        {"id": 1, "name": "Bob"}, {"id": 2, "name": "Jane Doe"},
    ]


def test_post_nested_invalid_rerenders_with_error_on_row():
    response = NestedIndex()(make_request("POST", data={
        "__trigger__": "save",
        "name": "Jane",
        "users.0.id": "not-a-number",
    }))
    html = response.get_data(as_text=True)
    assert 'name="users.0.id"' in html
    assert 'value="not-a-number"' in html
    assert 'class="field-error"' in html


def test_add_row_trigger_rerenders_with_extra_row():
    response = NestedIndex()(make_request("POST", data={
        "__trigger__": "add_user",
        "name": "Jane",
        "users.0.id": "1",
    }))
    html = response.get_data(as_text=True)
    # existing input survives, a new empty row appears, nothing validated
    assert 'value="Jane"' in html
    assert 'name="users.0.id"' in html
    assert 'name="users.1.id"' in html


def test_trigger_with_argument_removes_the_right_row():
    response = NestedIndex()(make_request("POST", data={
        "__trigger__": "remove_user:0",
        "name": "Jane",
        "users.0.name": "Bob",
        "users.1.name": "Alice",
    }))
    html = response.get_data(as_text=True)
    assert 'value="Alice"' in html
    assert 'value="Bob"' not in html
    assert 'name="users.1.name"' not in html


def test_model_level_error_renders_at_form_top():
    class Conditional(BaseModel):
        agree: bool
        nickname: str | None = None

        @model_validator(mode="after")
        def nickname_required_when_agreeing(self):
            if self.agree and not self.nickname:
                raise PydanticCustomError(
                    "nickname_required", "Nickname required when agreeing.")
            return self

    class CondIndex(Form):
        csrf = False

        def get_schema(self, request):
            return Conditional

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            return Response("ok")

    response = CondIndex()(make_request("POST", data={
        "__trigger__": "save", "agree": "true",
    }))
    html = response.get_data(as_text=True)
    assert '<div class="form-errors">' in html
    assert ('<span class="field-error">'
            'Nickname required when agreeing.</span>') in html
    # the submitted state survives the re-render
    assert "checked" in html

    response = CondIndex()(make_request("POST", data={
        "__trigger__": "save", "agree": "true", "nickname": "ck",
    }))
    assert response.get_data(as_text=True) == "ok"


def test_model_level_error_can_bind_to_a_field():
    class Conditional(BaseModel):
        agree: bool
        nickname: str | None = None

        @model_validator(mode="after")
        def nickname_required_when_agreeing(self):
            if self.agree and not self.nickname:
                raise PydanticCustomError(
                    "nickname_required", "Nickname required when agreeing.",
                    {"field": "nickname"})
            return self

    class CondIndex(Form):
        csrf = False

        def get_schema(self, request):
            return Conditional

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):  # pragma: no cover
            raise AssertionError("not reached")

    response = CondIndex()(make_request("POST", data={
        "__trigger__": "save", "agree": "true",
    }))
    html = response.get_data(as_text=True)
    # bound to the nickname widget, not the form top
    assert '<div class="form-errors">' not in html
    assert ('<input id="field-nickname" name="nickname" type="text">'
            '\n    <span class="field-error">'
            'Nickname required when agreeing.</span>') in html


def test_non_validating_trigger_receives_raw_dict():
    class RawIndex(Index):
        @trigger(name="peek", title="Peek")
        def peek(self, request, data):
            assert isinstance(data, dict)
            return Response(str(data["age"]))

    response = RawIndex()(make_request("POST", data={
        "__trigger__": "peek", "age": "30",
    }))
    # untouched string, no validation applied
    assert response.get_data(as_text=True) == "30"


def test_validation_error_raised_inside_action_is_caught():
    class ManualIndex(Index):
        @trigger(name="manual", title="Manual")
        def manual(self, request, data):
            model = self.get_schema(request)(**data)
            return Response(model.model_dump_json(), mimetype="application/json")

    response = ManualIndex()(make_request("POST", data={
        "__trigger__": "manual", "name": "Jane", "age": "not-a-number",
    }))
    assert response.status_code == 200
    assert 'class="field-error"' in response.get_data(as_text=True)


def test_buttons_are_ordered():
    class Multi(Index):
        @trigger(name="reset", title="Reset", order=-1)
        def reset(self, request, data):
            return Response("reset")

    assert list(Multi().buttons) == ["reset", "save"]
