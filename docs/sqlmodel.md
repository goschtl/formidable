# Saving with SQLModel

[SQLModel](https://sqlmodel.tiangolo.com/) classes are Pydantic models, so they
work with formidable as they are. formidable doesn't depend on SQLModel and adds
nothing for it, apart from the check below.

## Use a separate model for the form

Put the fields people may fill in on a base class. The table adds what only the
database should set, and the form uses a model without `table=True`:

```python
from sqlmodel import Field, SQLModel


class HeroBase(SQLModel):
    name: str = Field(title="Name", min_length=2)
    age: int | None = Field(default=None, title="Age")


class Hero(HeroBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class HeroForm(HeroBase):
    pass
```

!!! danger "A table model can't be the form's schema"
    SQLModel doesn't validate `table=True` models when they're created, so
    invalid input would reach your action. Their primary key and foreign keys
    would also become form fields that anyone can set. formidable refuses them
    with a `TypeError`, also when nested inside another model.

    A [read-only view](readonly.md) doesn't validate anything, so it accepts a
    table model. Hide `id` and similar fields with `only=`, or use the form model.

## Creating a row

`model_validate` turns the validated form model into a table row:

```python
class CreateHero(Form):
    def get_schema(self, request):
        return HeroForm

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        with Session(engine) as session:
            session.add(Hero.model_validate(data))
            session.commit()
        return redirect("/heroes", code=303)
```

## Editing a row

The row fills in the form on `GET`. After a validation error, `values` holds what
was submitted, and that must win:

```python
class EditHero(Form):
    def hero(self, request, session):
        hero = session.get(Hero, request.args.get("id", type=int))
        if hero is None:                       # and may this user edit it?
            raise NotFound()
        return hero

    def get_schema(self, request):
        return HeroForm

    def get_form(self, request, values=None, errors=None):
        if values is None:
            with Session(engine) as session:
                values = self.hero(request, session)
                return super().get_form(request, values, errors)
        return super().get_form(request, values, errors)

    @trigger(name="save", title="Save", validate=True)
    def save(self, request, data):
        with Session(engine) as session:
            hero = self.hero(request, session)
            hero.sqlmodel_update(data.model_dump())
            session.commit()
        return redirect("/heroes", code=303)
```

!!! warning "Check who may edit a row"
    formidable doesn't know about ownership. The `id` comes from the URL, so check
    on both `GET` and `POST` that this user may edit that row.

## Choosing a related row

Choices from the database belong in `get_schema`, which runs for both rendering
and validation, so nobody can submit an id they weren't offered. The options come
in as text, so the choices are text as well, and `model_validate` turns the chosen
one back into a number:

```python
class CreateHero(Form):
    def teams(self):
        with Session(engine) as session:
            return session.exec(select(Team)).all()

    def get_schema(self, request):
        ids = tuple(str(team.id) for team in self.teams())
        return create_model(
            "HeroForm", __base__=HeroBase,
            team_id=(t.Literal[ids], Field(title="Team")))

    def get_renderer(self, request):
        options = [{"value": team.id, "label": team.name} for team in self.teams()]
        return FormRenderer(
            theme=self.get_theme(request),
            ui=parse_ui({"team_id": {"ui:options": options}}))
```

An empty `t.Literal[()]` isn't valid, so handle the case of no rows at all before
you get here.

## What stays up to you

- **Lists of related rows.** A `list[...]` field gives you the submitted list.
  Working out which rows were added, changed or removed is your code.
- **Constraints only the database knows,** such as a unique name. Catch the
  `IntegrityError` when saving, or check beforehand in the action.
- **[Drafts](wizard.md).** A `Wizard` keeps drafts in its own store as raw JSON,
  and only `done` writes to your tables.
