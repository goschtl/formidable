# Getting started

formidable needs Python 3.12 or newer. It isn't on PyPI, so install it from
GitHub:

```bash
uv add "formidable @ git+https://github.com/goschtl/formidable"
```

## A first form

A form is a Pydantic model plus a view. The view is a callable that takes a
werkzeug `Request` and returns a `Response`, so it fits any WSGI setup.
Save this as `app.py`:

```python
from pydantic import BaseModel, Field
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from formidable.themes import page
from formidable.themes.bootstrap import BOOTSTRAP
from formidable.views import Form, trigger


class ContactForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")


class Contact(Form):
    theme = BOOTSTRAP

    def get_schema(self, request):
        return ContactForm

    def render_response(self, html_form, request):
        return Response(page(html_form, self.get_theme(request), title="Contact"),
                        mimetype="text/html")

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        return Response(f"Thanks, {data.name}!")


view = Contact()


@Request.application
def app(request):
    return view(request)


if __name__ == "__main__":
    run_simple("localhost", 8000, app, use_reloader=True)
```

Run it with `uv run python app.py` and open <http://localhost:8000/>. Submit
it empty to see the validation errors.

`page()` wraps the form in a full HTML page with the theme's stylesheets.
Without a `render_response`, the view returns only the `<form>`, which is
what you want when your application has its own page layout.

## The example application

`ex.py` in the repository shows nearly everything in this documentation:

```bash
git clone https://github.com/goschtl/formidable.git
cd formidable
uv run python ex.py
```

| URL | Shows |
|---|---|
| `/` | Nested models, lists and a file upload, in the site-wide theme (Materialize) |
| `/material` | The same form, with the theme set on the view |
| `/custom` | [Your own layout](layouts.md) in a Chameleon template |
| `/rueckfrage` | A real model with a [UI schema](ui-schema.md) and [conditions](conditions.md) |
| `/ui-demo` | Units, help texts, masks, multiple files |
| `/upload-demo` | [Background uploads](uploads.md) with FilePond |
| `/wizard` | [Several steps and drafts](wizard.md), with a review page |
