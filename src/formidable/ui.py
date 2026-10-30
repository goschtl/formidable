"""UI schemas: presentation hints kept apart from the data model.

A UI schema maps dot paths to `ui:*` entries (array rows use `items`:
`users.items.street`). It decides how a field looks, never whether its
value is valid; that stays with the Pydantic model.
"""

import json
import re
import typing as t
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field


ROW_INDEX = re.compile(r"\.(\d+|__index__)(?=\.|$)")

# ui:attributes the conditions script reads from around the controls
WRAPPER_ATTRIBUTES = frozenset((
    "data-condition-logic", "data-conditional-options", "data-not-required"))


class UIOption(BaseModel):
    value: str | int
    label: str


class UIMask(BaseModel):
    mask: str
    mask_placeholder: str = "_"

    @property
    def hint(self) -> str:
        """The mask as a placeholder text: `99-9999` -> `##-####`."""
        slots = re.sub(r"[9a*]", self.mask_placeholder, self.mask)
        return slots.replace("?", "")


class UIField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    title: str | None = Field(None, alias="ui:title")
    description: str | None = Field(None, alias="ui:description")
    placeholder: str | None = Field(None, alias="ui:placeholder")
    widget: str | None = Field(None, alias="ui:widget")
    attributes: dict[str, t.Any] = Field(
        default_factory=dict, alias="ui:attributes")
    options: list[UIOption] | None = Field(None, alias="ui:options")
    mask: UIMask | None = Field(None, alias="ui:mask")
    unit: str | None = Field(None, alias="ui:unit")
    help: str | None = Field(None, alias="ui:help")
    multiple: bool = Field(False, alias="ui:multiple")
    accept: list[str] | str | None = Field(None, alias="ui:accept")
    conditions: list[dict] | None = Field(None, alias="ui:conditions")
    condition_logic: str = Field("or", alias="ui:condition_logic")

    @property
    def active_mask(self) -> UIMask | None:
        """As with deform, a mask only applies together with a `ui:widget`:
        generated schemas carry masks on fields that must not get them."""
        return self.mask if self.widget else None

    @property
    def accept_value(self) -> str | None:
        """The `accept` attribute of a file input."""
        if isinstance(self.accept, list):
            return ",".join(self.accept) or None
        return self.accept

    @property
    def conditions_json(self) -> str | None:
        """The `data-conditions` value read by the conditions script.

        Generated schemas may also carry it as a ready-made attribute."""
        if not self.conditions:
            return self.attributes.get("data-conditions")
        return json.dumps(
            {"conditions": self.conditions, "logic": self.condition_logic})

    @property
    def condition_data(self) -> dict | None:
        """The parsed conditions: `{"conditions": [...], "logic": ...}`."""
        text = self.conditions_json
        if not text:
            return None
        try:
            data = json.loads(text)
        except ValueError:
            # older generated templates use single quotes
            data = json.loads(text.replace("'", '"'))
        if "field" in data and "operator" in data:
            return {"conditions": [data], "logic": "and"}
        return data

    @property
    def needs_conditions_script(self) -> bool:
        return bool(self.conditions_json
                    or "data-conditional-options" in self.attributes)

    @property
    def attributes_without_conditions(self) -> dict[str, t.Any]:
        """Everything for fields without a control of their own."""
        return {**self.wrapper_attributes, **self.control_attributes}

    @property
    def wrapper_attributes(self) -> dict[str, t.Any]:
        """Attributes for the element around the field."""
        return {name: value for name, value in self.attributes.items()
                if name in WRAPPER_ATTRIBUTES}

    @property
    def control_attributes(self) -> dict[str, t.Any]:
        """Attributes for the input, select or textarea itself."""
        attributes = {
            name: value for name, value in self.attributes.items()
            if name not in WRAPPER_ATTRIBUTES and name != "data-conditions"}
        if self.active_mask:
            attributes["data-mask"] = self.active_mask.mask
        return attributes


NO_UI = UIField()


def parse_ui(mapping: t.Mapping[str, t.Mapping]) -> dict[str, UIField]:
    return {name: UIField(**config) for name, config in mapping.items()}


def load_ui(path: str | Path) -> dict[str, UIField]:
    return parse_ui(json.loads(Path(path).read_text(encoding="utf-8")))


def ui_path(name: str) -> str:
    """The UI schema key of a field: `users.0.street` -> `users.items.street`."""
    return ROW_INDEX.sub(".items", name)
