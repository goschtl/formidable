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


class UIOption(BaseModel):
    value: str | int
    label: str


class UIField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    title: str | None = Field(None, alias="ui:title")
    description: str | None = Field(None, alias="ui:description")
    placeholder: str | None = Field(None, alias="ui:placeholder")
    widget: str | None = Field(None, alias="ui:widget")
    options: list[UIOption] | None = Field(None, alias="ui:options")
    conditions: list[dict] | None = Field(None, alias="ui:conditions")
    condition_logic: str = Field("or", alias="ui:condition_logic")

    @property
    def conditions_json(self) -> str | None:
        """The `data-conditions` value read by conditionalfield.js."""
        if not self.conditions:
            return None
        return json.dumps(
            {"conditions": self.conditions, "logic": self.condition_logic})


NO_UI = UIField()


def parse_ui(mapping: t.Mapping[str, t.Mapping]) -> dict[str, UIField]:
    return {name: UIField(**config) for name, config in mapping.items()}


def load_ui(path: str | Path) -> dict[str, UIField]:
    return parse_ui(json.loads(Path(path).read_text(encoding="utf-8")))


def ui_path(name: str) -> str:
    """The UI schema key of a field: `users.0.street` -> `users.items.street`."""
    return ROW_INDEX.sub(".items", name)
