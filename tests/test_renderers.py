from beartype.door import TypeHint
from markupsafe import Markup
from pydantic import BaseModel, Field

from formidable.renderers import (
    BASIC_WIDGETS,
    FormRenderer,
    IFieldRenderer,
    StringFieldRenderer,
    resolve,
)


class Schema(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


def test_resolve_plain_type():
    hint, optional = resolve(str)
    assert hint == TypeHint(str)
    assert optional is False


def test_resolve_optional_union():
    hint, optional = resolve(str | None)
    assert hint == TypeHint(str)
    assert optional is True


def test_browser_validation_is_off_by_default():
    html = FormRenderer()(Schema)
    assert 'novalidate="novalidate"' in html
    # required attributes stay for accessibility and styling
    assert 'required="required"' in html


def test_browser_validation_can_be_reenabled():
    html = FormRenderer(novalidate=False)(Schema)
    assert "novalidate" not in html


def test_render_basic_form():
    html = FormRenderer()(Schema)
    assert '<input id="field-name" name="name" required="required" type="text">' in html
    assert '<input id="field-age" name="age" required="required" type="number">' in html
    assert '<input id="field-agree" name="agree" type="checkbox" value="true">' in html
    assert '<label for="field-name">Your Name</label>' in html


def test_optional_field_not_required():
    html = FormRenderer()(Schema)
    assert '<input id="field-nickname" name="nickname" type="text">' in html


def test_values_are_rendered():
    html = FormRenderer()(Schema, values={"name": "Jane", "agree": "true"})
    assert 'value="Jane"' in html
    assert 'checked="checked"' in html


def test_errors_are_rendered():
    html = FormRenderer()(Schema, errors={"age": "Field required"})
    assert '<span class="field-error" id="field-age-error">Field required</span>' in html


def test_unknown_type_renders_warning():
    class WithMapping(BaseModel):
        items: dict[str, str]

    html = FormRenderer()(WithMapping)
    assert "No renderer for type" in html


def test_custom_widget_by_field_name():
    class Custom(IFieldRenderer):
        def render(self, name, field_info, field_type, value=None, errors=None):
            return Markup("<div>custom!</div>")

    html = FormRenderer(custom_widgets={"name": Custom})(Schema)
    assert "custom!" in html
    assert 'id="field-name"' not in html


class Address(BaseModel):
    street: str = Field(..., title="Street")
    city: str = Field(..., title="City")


class User(BaseModel):
    id: int
    name: str = "Jane Doe"


class Nested(BaseModel):
    address: Address = Field(..., title="Address")
    users: list[User] = Field(default_factory=list, title="Users")


def test_nested_model_renders_fieldset_with_dot_paths():
    html = FormRenderer()(Nested)
    assert "<legend>Address</legend>" in html
    assert 'name="address.street"' in html
    assert 'name="address.city"' in html
    assert '<label for="field-address.street">Street</label>' in html


def test_list_of_models_renders_indexed_items():
    html = FormRenderer()(
        Nested,
        values={"address": {}, "users": [{"name": "Bob"}, {}]},
    )
    assert "<legend>Users #1</legend>" in html
    assert "<legend>Users #2</legend>" in html
    assert 'name="users.0.name"' in html
    assert 'name="users.1.id"' in html
    # submitted value round-trips into the right row
    assert '<input id="field-users.0.name" name="users.0.name" required="required" type="text" value="Bob">' in html
    # default applies where nothing was submitted
    assert 'value="Jane Doe"' in html


def test_list_of_scalars_renders_indexed_inputs():
    class WithTags(BaseModel):
        tags: list[str] = Field(default_factory=list, title="Tags")

    html = FormRenderer()(WithTags, values={"tags": ["a", "b"]})
    assert 'name="tags.0"' in html
    assert 'value="a"' in html
    assert 'name="tags.1"' in html
    assert 'value="b"' in html


def test_nested_errors_land_on_the_right_input():
    html = FormRenderer()(
        Nested,
        values={"address": {}, "users": [{"id": "xx"}]},
        errors={"users.0.id": "Not an integer"},
    )
    assert '<span class="field-error" id="field-users.0.id-error">Not an integer</span>' in html


def test_list_ships_template_and_row_buttons():
    html = FormRenderer()(Nested)
    # a blank-row template with index placeholders, plus JS-driven buttons
    assert "<template>" in html
    assert 'name="users.__index__.id"' in html
    assert "Users #__num__" in html
    assert '<button class="formidable-add-row" type="button">Add</button>' in html
    assert '<button class="formidable-remove-row" type="button">Remove</button>' in html


def test_row_script_injected_only_for_forms_with_lists():
    assert "__formidable_rows" in FormRenderer()(Nested)
    assert "__formidable_rows" not in FormRenderer()(Schema)


def test_rendered_rows_carry_their_index():
    html = FormRenderer()(Nested, values={"address": {}, "users": [{}, {}]})
    assert 'data-index="0"' in html
    assert 'data-index="1"' in html


def test_model_default_instance_prefills_inputs():
    class WithDefault(BaseModel):
        address: Address = Field(
            default_factory=lambda: Address(street="Main St", city="Springfield"),
            title="Address",
        )

    html = FormRenderer()(WithDefault)
    assert 'value="Main St"' in html
    assert 'value="Springfield"' in html


def test_widget_overrides_do_not_leak_between_instances():
    class Custom(StringFieldRenderer):
        pass

    FormRenderer(widgets={TypeHint(str): Custom})
    assert FormRenderer().widgets[TypeHint(str)] is StringFieldRenderer
    assert BASIC_WIDGETS[TypeHint(str)] is StringFieldRenderer
