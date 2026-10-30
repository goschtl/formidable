# formidable

Generate HTML forms from [Pydantic](https://docs.pydantic.dev/) models:
rendering, parsing, validation, themes and translations, with the model as
the single source of truth.

```python
from pydantic import BaseModel, Field
from werkzeug.wrappers import Response
from formidable.views import Form, trigger


class ContactForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


class Contact(Form):
    def get_schema(self, request):
        return ContactForm

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        # `data` is a validated ContactForm instance
        return Response(f"Thanks, {data.name}!")
```

`GET` renders the form. `POST` parses it, validates it and calls the action
of the pressed button. If validation fails, the form comes back with the
submitted values and an error message at each field.

## What's included

- **[Fields and widgets](fields.md)**: every model field becomes a widget, including nested models and repeatable rows.
- **[Multi-step forms and drafts](wizard.md)**: one model over several pages, to continue later.
- **[Read-only views](readonly.md)**: the answers as text, for review and confirmation pages.
- **[Accessibility](accessibility.md)**: an error summary and linked messages for screen readers.
- **[Saving with SQLModel](sqlmodel.md)**: the same models for forms and database tables.
- **[Your own form layout](layouts.md)**: place each field yourself in a Chameleon template.
- **[UI schemas](ui-schema.md)**: titles, help texts, units, masks and more, kept apart from the model.
- **[Conditional fields](conditions.md)**: show and hide fields without jQuery.
- **[File uploads](uploads.md)**: with the form, or one by one in the background with FilePond.
- **[Themes](themes.md)**: Bootstrap 5 and Materialize ship with it.
- **[Translations](translations.md)**: German error messages included.

CSRF protection is on by default.
