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

The labels of the upload widget are separate: pass `i18n.UPLOAD_GERMAN` as
`upload_options`, see [File uploads](uploads.md).
