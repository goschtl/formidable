# Multi-step forms and drafts

A `Wizard` splits one model over several pages, keeps what was entered so far,
and lets people continue later.

```python
from formidable.wizard import FileDraftStore, Step, Wizard


class ClaimForm(BaseModel):
    name: str = Field(..., title="Name")
    birthday: datetime.date = Field(..., title="Birthday")
    accident_day: datetime.date = Field(..., title="Day of the accident")
    description: str = Field(..., title="What happened?")


class Claim(Wizard):
    steps = (
        Step("person", "Person", ("name", "birthday")),
        Step("accident", "Accident"),       # all fields not in another step
    )
    store = FileDraftStore("/var/lib/myapp/drafts")

    def get_schema(self, request):
        return ClaimForm

    def done(self, request, data):
        save(data)                          # `data` is a validated ClaimForm
        return Response(self.get_readonly(request, data), mimetype="text/html")
```

`/wizard` in `ex.py` is a full example. It needs nothing but the server: no
JavaScript, and the browser's back button works.

## How it behaves

- **One model.** Steps are lists of its top-level fields, so a generated model
  needs no changes and its validators stay in one place. Every field must be in
  a step.
- **Next** saves the step and checks its fields. Errors from other steps wait for
  their turn.
- **Back** saves without checking, so nothing is lost.
- **A review page** shows everything as [text](readonly.md), with a link to change
  each step. Set `review = False` to send from the last step instead.
- **Send** validates the whole model. If that fails, it goes to the first step
  with an error. `done` runs only with valid data, and the draft is deleted
  afterwards.
- **Conditions** work across steps. Answers from other steps travel along in
  hidden inputs for the script to read, and the server ignores them. A step with
  nothing to show is skipped.

!!! note "Cross-field validators run late"
    Pydantic only runs a `model_validator(mode="after")` once every field is
    valid, which usually means at the end. Its error then leads back to the step
    with that field, or shows on the review page if it names no field.

## Drafts

Everything entered goes straight into a draft store, as submitted. **Save and
continue later** adds a message and keeps the draft cookie for 30 days
(`draft_max_age`). Set `drafts = False` to hide that button.

A form with a single step is simply a form with drafts:

```python
steps = (Step("all", "Claim"),)
review = False
```

### Where drafts are kept

| Store | For |
|---|---|
| `MemoryDraftStore()` | Tests and development; lost on restart, and not shared between processes |
| `FileDraftStore(folder)` | One server: JSON files only their owner can read |
| Your own | Anything with `load(key)`, `save(key, data)` and `delete(key)`, such as a database table |

!!! danger "Drafts hold personal data"
    `FileDraftStore` does not encrypt anything. Put drafts where you'd put the
    submitted forms, cover them in your retention rules, and delete old ones
    regularly, because nothing else does: `store.purge(max_age=30 * 24 * 3600)`.

### Whose draft it is

By default, a random token in an HttpOnly cookie identifies the draft. The cookie
ends with the browser session unless someone saves on purpose, so that the next
person on a shared computer doesn't find their answers.

With logins, return the user's id instead. That needs no cookie, and people can
continue on another device:

```python
def get_draft_key(self, request):
    return f"claim:{request.user.id}"
```

## Files

A draft can't hold an uploaded file, so a `Wizard` refuses `UploadedFile` and
`FileUpload` with a clear error. Use [background uploads](uploads.md): the field
is `list[str]`, and the file is already stored when the step is saved. Set
`upload_label` so the review page shows file names.

## Your own layout

Override `render_step`, and show where the user is with `render_steps`, which
`get_form` adds for you above the form:

```python
def render_step(self, request, values, errors):
    return render_template("claim_step.pt", dirs=("templates",),
                           form=self.bind(request, values, errors))
```

`form` then only has the fields of the current step. In a template that handles
several steps, check for a field with `'name' in form`, or use one
template per step, choosing it with `self.current_step(request, draft)`.

## Texts

Buttons and labels come from the [catalog](translations.md): `ui_next`, `ui_back`,
`ui_send`, `ui_save_draft`, `ui_saved`, `ui_review`, `ui_edit`, `ui_steps` and
`ui_step_position`. `i18n.GERMAN` has them all.
