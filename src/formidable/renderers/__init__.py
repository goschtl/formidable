"""Widget rendering, split into logical parts:

* base — type resolution, shared helpers, the IFieldRenderer interface
* inputs — scalar widgets (text, number, temporal, password, file, ...)
* choices — select, radio group, multi-select
* structures — nested models and repeatable list rows (+ their JS)
* form — FormRenderer, the widget registries, BoundForm

Everything public is re-exported here; import from
`formidable.renderers` as before.
"""

from formidable.renderers.base import (
    CONDITIONS_SCRIPT,
    CSRF_FIELD,
    OPTIONAL,
    TEMPLATES,
    TRUTHY,
    IFieldRenderer,
    classes,
    default_value,
    field_title,
    field_value,
    is_choice,
    render_template,
    resolve,
    widget_hint,
)
from formidable.renderers.inputs import (
    BoolFieldRenderer,
    DateFieldRenderer,
    DateTimeFieldRenderer,
    EmailFieldRenderer,
    FileFieldRenderer,
    FloatFieldRenderer,
    InputFieldRenderer,
    IntFieldRenderer,
    PasswordFieldRenderer,
    StringFieldRenderer,
    TextareaFieldRenderer,
    TimeFieldRenderer,
)
from formidable.renderers.choices import (
    MultiSelectFieldRenderer,
    RadioFieldRenderer,
    SelectFieldRenderer,
)
from formidable.renderers.structures import (
    INDEX_PLACEHOLDER,
    LIST_SCRIPT,
    NUM_PLACEHOLDER,
    ListFieldRenderer,
    ModelFieldRenderer,
)
from formidable.renderers.form import (
    BASIC_WIDGETS,
    NAMED_WIDGETS,
    BoundField,
    BoundForm,
    FormRenderer,
)

__all__ = [
    "BASIC_WIDGETS",
    "CONDITIONS_SCRIPT",
    "CSRF_FIELD",
    "INDEX_PLACEHOLDER",
    "LIST_SCRIPT",
    "NAMED_WIDGETS",
    "NUM_PLACEHOLDER",
    "OPTIONAL",
    "TEMPLATES",
    "TRUTHY",
    "BoolFieldRenderer",
    "BoundField",
    "BoundForm",
    "DateFieldRenderer",
    "DateTimeFieldRenderer",
    "EmailFieldRenderer",
    "FileFieldRenderer",
    "FloatFieldRenderer",
    "FormRenderer",
    "IFieldRenderer",
    "InputFieldRenderer",
    "IntFieldRenderer",
    "ListFieldRenderer",
    "ModelFieldRenderer",
    "MultiSelectFieldRenderer",
    "PasswordFieldRenderer",
    "RadioFieldRenderer",
    "SelectFieldRenderer",
    "StringFieldRenderer",
    "TextareaFieldRenderer",
    "TimeFieldRenderer",
    "classes",
    "default_value",
    "field_title",
    "field_value",
    "is_choice",
    "render_template",
    "resolve",
    "widget_hint",
]
