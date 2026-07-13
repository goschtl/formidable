from pydantic import BaseModel, Field

from formidable.data import listify, normalize, unflatten


class User(BaseModel):
    id: int
    name: str = "Jane Doe"
    admin: bool = False


class Schema(BaseModel):
    name: str
    agree: bool
    nickname: str | None = None
    users: list[User] = Field(default_factory=list)


def test_unflatten_flat_keys_stay_flat():
    assert unflatten({"name": "Jane"}) == {"name": "Jane"}


def test_unflatten_dot_paths_nest():
    assert unflatten({"address.street": "Main", "address.city": "Springfield"}) == {
        "address": {"street": "Main", "city": "Springfield"},
    }


def test_unflatten_digit_segments_become_lists():
    assert unflatten({
        "users.0.name": "Bob",
        "users.1.name": "Alice",
    }) == {"users": [{"name": "Bob"}, {"name": "Alice"}]}


def test_unflatten_sparse_indices_keep_order():
    assert unflatten({
        "users.2.name": "C",
        "users.0.name": "A",
        "users.10.name": "D",
    }) == {"users": [{"name": "A"}, {"name": "C"}, {"name": "D"}]}


def test_unflatten_conflicting_keys_do_not_crash():
    assert unflatten({"a": "x", "a.b": "y"}) == {"a": "x"}


def test_listify_only_converts_all_digit_dicts():
    assert listify({"0": "a", "x": "b"}) == {"0": "a", "x": "b"}


def test_normalize_absent_checkbox_is_false():
    data = normalize(Schema, {"name": "Jane"})
    assert data["agree"] == "false"


def test_normalize_empty_optional_is_dropped():
    data = normalize(Schema, {"name": "Jane", "nickname": ""})
    assert "nickname" not in data


def test_normalize_recurses_into_list_items():
    data = normalize(Schema, {
        "name": "Jane",
        "users": [{"id": "1"}, {"id": "2", "admin": "true"}],
    })
    assert data["users"][0]["admin"] == "false"
    assert data["users"][1]["admin"] == "true"


def test_full_round_trip_validates():
    data = normalize(Schema, unflatten({
        "name": "Jane",
        "nickname": "",
        "users.0.id": "1",
        "users.0.name": "Bob",
        "users.1.id": "2",
    }))
    model = Schema(**data)
    assert model.agree is False
    assert model.nickname is None
    assert model.users[0].name == "Bob"
    assert model.users[1].id == 2
    assert model.users[1].admin is False
