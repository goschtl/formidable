from pydantic import BaseModel, Field
from formidable.form import setup_container
from formidable.renderers import FormRenderer


# --- Pydantic model example ---
class ExampleForm(BaseModel):
    name: str = Field(..., title="Your Name")
    age: int = Field(..., title="Age")
    agree: bool = Field(..., title="I agree to terms")
    nickname: str | None = Field(None, title="Nickname (optional)")


# --- Run it! ---
if __name__ == "__main__":
    container = setup_container()
    form_renderer: FormRenderer = container.get(FormRenderer)
    html_form = form_renderer.render(ExampleForm)

    print(html_form)
