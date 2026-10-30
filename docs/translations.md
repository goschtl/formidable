# Translations

Pydantic identifies errors by stable `type` strings. A catalog maps them to
message templates, with `{placeholders}` filled from the error context. A German
catalog ships as `formidable.i18n.GERMAN`, and unknown types fall back to
Pydantic's English.

```python
from formidable import i18n

i18n.use({**i18n.GERMAN, "nickname_required": "..."})   # site-wide


class Kontakt(Form):
    error_messages = {...}                  # for one view

    def get_messages(self, request):        # or per request, by Accept-Language
        ...
```

Your own `PydanticCustomError` types translate the same way.

## Interface texts

The same catalog holds interface texts, under keys starting with `ui_`:

| Key | Used for |
|---|---|
| `ui_error_summary` | The heading of the [error summary](accessibility.md) |
| `ui_yes`, `ui_no` | Checkboxes in a [read-only view](readonly.md) |
| `ui_date_format`, `ui_datetime_format` | Dates in a read-only view, in `strftime` format |
| `ui_next`, `ui_back`, `ui_send`, `ui_save_draft` | The buttons of a [Wizard](wizard.md) |
| `ui_steps`, `ui_step_position`, `ui_review`, `ui_edit`, `ui_saved` | The other texts of a Wizard |

The "Add" and "Remove" buttons of list rows and the "please choose the file
again" hint are still fixed English.

The labels of the upload widget are separate: pass `i18n.UPLOAD_GERMAN` as
`upload_options`, see [File uploads](uploads.md).
