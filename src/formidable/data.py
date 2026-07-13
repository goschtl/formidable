"""Convert flat HTML form submissions into nested structures.

Field names use dot paths (``users.0.name``); all-digit segments
become list indices. The resulting tree matches Pydantic's error
locations, which flatten the same way.
"""

import typing as t
from pydantic import BaseModel
from beartype.door import TypeHint
from formidable.renderers import resolve


BOOL = TypeHint(bool)


def listify(node):
    """Recursively convert dicts whose keys are all digits into lists."""
    if not isinstance(node, dict):
        return node
    node = {key: listify(value) for key, value in node.items()}
    if node and all(key.isdigit() for key in node):
        return [node[key] for key in sorted(node, key=int)]
    return node


def unflatten(flat: dict[str, str]) -> dict:
    """Fold a flat dot-path dict into a tree of dicts and lists."""
    root: dict = {}
    for key, value in flat.items():
        *path, leaf = key.split(".")
        node = root
        for part in path:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                # conflicting keys, e.g. both `a` and `a.b`: skip the deeper one
                break
        else:
            node[leaf] = value
    return listify(root)


def normalize(schema: type[BaseModel], data: dict) -> dict:
    """Patch HTML form semantics onto a data tree, recursively.

    Absent checkboxes become False, empty submissions for optional
    fields are dropped so their defaults apply.
    """
    for name, model_field in schema.model_fields.items():
        token, optional = resolve(model_field.annotation)
        hint = token.hint
        if token == BOOL:
            if name not in data:
                data[name] = "false"
        elif optional and data.get(name) == "":
            del data[name]
        elif isinstance(hint, type) and issubclass(hint, BaseModel):
            if isinstance(data.get(name), dict):
                normalize(hint, data[name])
        elif t.get_origin(hint) is list and (args := t.get_args(hint)):
            item_token, _ = resolve(args[0])
            item_hint = item_token.hint
            if isinstance(item_hint, type) and issubclass(item_hint, BaseModel):
                entries = data.get(name)
                for entry in entries if isinstance(entries, list) else []:
                    if isinstance(entry, dict):
                        normalize(item_hint, entry)
    return data
