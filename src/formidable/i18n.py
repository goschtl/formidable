"""Translate Pydantic's validation error messages.

Pydantic identifies every error by a stable ``type`` string
("missing", "int_parsing", "string_too_short", ...) and carries the
message parameters in ``ctx``. A catalog maps those types to message
templates; ``{placeholders}`` are filled from the context, so
parametrized messages work. Types missing from the catalog fall back
to Pydantic's English message.

This also covers `PydanticCustomError`: its first argument is the
error type, so applications can add their own types to the catalog.
"""

import typing as t


Catalog = t.Mapping[str, str]

_current: Catalog = {}


def use(catalog: Catalog) -> Catalog:
    """Register the site-wide message catalog (call once at startup).

    Returns the previously registered catalog, handy for restoring it.
    """
    global _current
    previous = _current
    _current = catalog
    return previous


def current() -> Catalog:
    """The site-wide message catalog."""
    return _current


def translate(error: t.Mapping[str, t.Any],
              catalog: Catalog | None = None) -> str:
    """Translate one entry of `ValidationError.errors()`."""
    if catalog is None:
        catalog = _current
    template = catalog.get(error["type"])
    if template is None:
        return error["msg"]
    ctx = error.get("ctx") or {}
    try:
        return template.format(**ctx)
    except (KeyError, IndexError):
        return template


GERMAN: Catalog = {
    "missing": "Pflichtfeld.",
    "int_parsing": "Bitte eine ganze Zahl eingeben.",
    "int_type": "Bitte eine ganze Zahl eingeben.",
    "float_parsing": "Bitte eine Zahl eingeben.",
    "bool_parsing": "Bitte Ja oder Nein wählen.",
    "string_type": "Bitte einen Text eingeben.",
    "string_too_short": "Bitte mindestens {min_length} Zeichen eingeben.",
    "string_too_long": "Bitte höchstens {max_length} Zeichen eingeben.",
    "greater_than": "Der Wert muss größer als {gt} sein.",
    "greater_than_equal": "Der Wert muss mindestens {ge} betragen.",
    "less_than": "Der Wert muss kleiner als {lt} sein.",
    "less_than_equal": "Der Wert darf höchstens {le} betragen.",
    "enum": "Bitte einen gültigen Wert auswählen.",
    "is_instance_of": "Ungültige Eingabe.",
}
