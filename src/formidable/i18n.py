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


def text(key: str, default: str, catalog: Catalog | None = None, **values) -> str:
    """Interface text: `ui_*` entries live in the same catalogs."""
    template = (_current if catalog is None else catalog).get(key, default)
    return template.format(**values) if values else template


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
    "ui_error_summary": "Bitte korrigieren Sie Folgendes:",
    "ui_yes": "Ja",
    "ui_no": "Nein",
    "ui_date_format": "%d.%m.%Y",
    "ui_datetime_format": "%d.%m.%Y %H:%M",
    "ui_steps": "Schritte",
    "ui_step_position": "Schritt {number} von {total}: {title}",
    "ui_next": "Weiter",
    "ui_back": "Zurück",
    "ui_save_draft": "Speichern und später fortsetzen",
    "ui_send": "Absenden",
    "ui_review": "Angaben prüfen",
    "ui_edit": "Ändern",
    "ui_saved": "Ihre Angaben wurden gespeichert. Sie können später hier fortfahren.",
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
    "literal_error": "Bitte einen gültigen Wert auswählen.",
    "string_pattern_mismatch": "Bitte prüfen Sie das Format der Eingabe.",
    "date_from_datetime_parsing": "Bitte ein gültiges Datum eingeben.",
    "is_instance_of": "Ungültige Eingabe.",
}

#: German labels for the upload widget: FormRenderer(upload_options=...)
UPLOAD_GERMAN: t.Mapping[str, str] = {
    "labelIdle": 'Dateien ablegen oder <span class="filepond--label-action">'
                 "auswählen</span>",
    "labelInvalidField": "Feld beinhaltet ungültige Dateien",
    "labelFileWaitingForSize": "Dateigröße berechnen",
    "labelFileSizeNotAvailable": "Dateigröße nicht verfügbar",
    "labelFileLoading": "Laden",
    "labelFileLoadError": "Fehler beim Laden",
    "labelFileProcessing": "Upload läuft",
    "labelFileProcessingComplete": "Upload abgeschlossen",
    "labelFileProcessingAborted": "Upload abgebrochen",
    "labelFileProcessingError": "Fehler beim Upload",
    "labelFileProcessingRevertError": "Fehler beim Wiederherstellen",
    "labelFileRemoveError": "Fehler beim Löschen",
    "labelTapToCancel": "abbrechen",
    "labelTapToRetry": "erneut versuchen",
    "labelTapToUndo": "rückgängig",
    "labelButtonRemoveItem": "Entfernen",
    "labelButtonAbortItemLoad": "Verwerfen",
    "labelButtonRetryItemLoad": "Erneut versuchen",
    "labelButtonAbortItemProcessing": "Abbrechen",
    "labelButtonUndoItemProcessing": "Rückgängig",
    "labelButtonRetryItemProcessing": "Erneut versuchen",
    "labelButtonProcessItem": "Upload",
    "labelMaxFileSizeExceeded": "Datei ist zu groß",
    "labelMaxFileSize": "Maximale Dateigröße: {filesize}",
    "labelMaxTotalFileSizeExceeded": "Maximale gesamte Dateigröße überschritten",
    "labelMaxTotalFileSize": "Maximale gesamte Dateigröße: {filesize}",
    "labelFileTypeNotAllowed": "Dateityp ungültig",
    "fileValidateTypeLabelExpectedTypes":
        "Erwartet {allButLastType} oder {lastType}",
}
