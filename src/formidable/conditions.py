"""Conditions evaluated on the server, for pages without the controls the
conditions script looks at: read-only views and the steps of a Wizard.

Follows `static/conditions.js`, with the submitted values in place of the
controls. As there, this only decides what is shown.
"""

import enum
import math
import re
import typing as t

from pydantic import BaseModel

from formidable.ui import NO_UI, UIField, ui_path

ROW = re.compile(r"^(.*\.\d+)(?:\.|$)")


def value_at(root: t.Any, path: str) -> t.Any:
    """The value at a dot path through dicts, lists and models, or None."""
    current = root
    for part in path.split("."):
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        elif isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
    return current


def _answer(value: t.Any) -> str | list[str]:
    """A value as the script reads it from its control."""
    if isinstance(value, (list, tuple, set)):
        return [item for item in map(_answer, value) if isinstance(item, str)]
    if value is None or value is False or value == "false":
        return ""
    if value is True:
        return "true"
    if isinstance(value, enum.Enum):
        return str(value.value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _lookup(field: str, name: str, values: t.Any) -> tuple[str, t.Any]:
    """Where a condition finds its answer: within the row of `name` first."""
    if row := ROW.match(name):
        scope = value_at(values, row.group(1))
        for candidate in (field, field.split(".items.")[-1], field.split(".")[-1]):
            found = value_at(scope, candidate)
            if found is not None:
                return f"{row.group(1)}.{candidate}", found
    return field, value_at(values, field)


def _number(value: t.Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _empty(answer: str | list[str]) -> bool:
    return not answer or (isinstance(answer, str) and not answer.strip())


def _text(answer: str | list[str]) -> str:
    return ",".join(answer) if isinstance(answer, list) else answer


def check(operator: str, answer: str | list[str], expected: t.Any) -> bool:
    is_list = isinstance(answer, list)
    match operator:
        case "equals":
            return expected in answer if is_list else answer == expected
        case "not_equals":
            return expected not in answer if is_list else answer != expected
        case "contains":
            return not _empty(answer) and str(expected) in _text(answer)
        case "not_contains":
            return _empty(answer) or str(expected) not in _text(answer)
        case "starts_with":
            return not _empty(answer) and _text(answer).startswith(str(expected))
        case "ends_with":
            return not _empty(answer) and _text(answer).endswith(str(expected))
        case "greater_than":
            return _number(answer) > _number(expected)
        case "less_than":
            return _number(answer) < _number(expected)
        case "greater_equal":
            return _number(answer) >= _number(expected)
        case "less_equal":
            return _number(answer) <= _number(expected)
        case "empty":
            return _empty(answer)
        case "not_empty":
            return not _empty(answer)
        case "in":
            return isinstance(expected, list) and answer in expected
        case "not_in":
            return not isinstance(expected, list) or answer not in expected
    return False


def is_visible(name: str, ui: t.Mapping[str, UIField], values: t.Any,
               _seen: frozenset[str] = frozenset()) -> bool:
    """Whether the field at dot path `name` shows with these values."""
    path = ui_path(name)
    data = ui.get(path, NO_UI).condition_data
    if not data or not data.get("conditions") or path in _seen:
        return True
    seen = _seen | {path}

    def holds(condition: dict) -> bool:
        target, found = _lookup(condition["field"], name, values)
        # a hidden field has no answer: whatever depends on it hides as well
        if not is_visible(target, ui, values, seen):
            return False
        return check(condition["operator"], _answer(found), condition.get("value"))

    results = [holds(condition) for condition in data["conditions"]]
    return all(results) if data.get("logic", "and") == "and" else any(results)
