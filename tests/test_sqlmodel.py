import re
import typing as t

import pytest
from pydantic import BaseModel, create_model
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select
from werkzeug.exceptions import NotFound
from werkzeug.test import Client
from werkzeug.utils import redirect
from werkzeug.wrappers import Request

from formidable.renderers import FormRenderer, check_schema
from formidable.ui import parse_ui
from formidable.views import Form, trigger
from formidable.wizard import MemoryDraftStore, Step, Wizard


class Team(SQLModel, table=True):
    __tablename__ = "docs_team"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class HeroBase(SQLModel):
    name: str = Field(title="Name", min_length=2)
    age: int | None = Field(default=None, title="Age")


class Hero(HeroBase, table=True):
    __tablename__ = "docs_hero"
    id: int | None = Field(default=None, primary_key=True)
    team_id: int | None = Field(default=None, foreign_key="docs_team.id")


class HeroForm(HeroBase):
    pass


class Holder(BaseModel):
    hero: Hero


class Many(BaseModel):
    heroes: list[Hero] = []


class Tree(BaseModel):
    name: str = "x"
    children: "list[Tree]" = []


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.mark.parametrize("schema", [Hero, Holder, Many])
def test_table_models_are_refused(schema):
    with pytest.raises(TypeError, match="Hero is a SQLModel table"):
        FormRenderer()(schema)
    with pytest.raises(TypeError, match="Hero is a SQLModel table"):
        FormRenderer().bind(schema)


def test_a_form_model_is_fine():
    assert 'name="name"' in str(FormRenderer()(HeroForm))
    assert 'name="id"' not in str(FormRenderer()(HeroForm))


def test_a_model_containing_itself_ends():
    check_schema(Tree)


def test_a_post_is_refused_without_rendering_first():
    class View(Form):
        def get_schema(self, request):
            return Hero

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            raise AssertionError("reached with unvalidated data")

    client = Client(Request.application(View()))
    client.set_cookie("formidable-csrf", "t")
    with pytest.raises(TypeError, match="SQLModel table"):
        client.post("/", data={"__csrf__": "t", "__trigger__": "save", "name": "x"})


def test_a_wizard_is_refused():
    class View(Wizard):
        steps = (Step("a", "A"),)
        store = MemoryDraftStore()

        def get_schema(self, request):
            return Hero

    with pytest.raises(TypeError, match="SQLModel table"):
        Client(Request.application(View())).get("/")


def test_read_only_accepts_a_table_row():
    html = str(FormRenderer()(Hero, values=Hero(name="Ann", id=1), readonly=True,
                              only=("name",)))
    assert "Ann" in html
    assert "<strong>id</strong>" not in html


def press(client, url, **data):
    client.get(url)
    token = client.get_cookie("formidable-csrf").value
    return client.post(url, data={"__csrf__": token, "__trigger__": "save", **data})


def test_creating_a_row(engine):
    class CreateHero(Form):
        def get_schema(self, request):
            return HeroForm

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            with Session(engine) as session:
                session.add(Hero.model_validate(data))
                session.commit()
            return redirect("/heroes", code=303)

    client = Client(Request.application(CreateHero()))
    assert press(client, "/", name="A").status_code == 200
    response = press(client, "/", name="Ann", age="30")
    assert response.status_code == 303
    with Session(engine) as session:
        hero = session.exec(select(Hero)).one()
    assert (hero.name, hero.age) == ("Ann", 30)
    assert isinstance(hero.id, int)


def test_editing_a_row(engine):
    with Session(engine) as session:
        hero = Hero(name="Ann", age=30)
        session.add(hero)
        session.commit()
        hero_id = hero.id

    class EditHero(Form):
        def hero(self, request, session):
            hero = session.get(Hero, request.args.get("id", type=int))
            if hero is None:
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

    client = Client(Request.application(EditHero()))
    url = f"/?id={hero_id}"
    html = client.get(url).text
    assert 'value="Ann"' in html and 'value="30"' in html
    # what was submitted wins over the row after an error
    html = press(client, url, name="B", age="31").text
    assert 'value="B"' in html and 'value="31"' in html
    assert press(client, url, name="Bea", age="31").status_code == 303
    with Session(engine) as session:
        assert session.get(Hero, hero_id).name == "Bea"
    assert client.get("/?id=999").status_code == 404


def test_choosing_a_related_row(engine):
    with Session(engine) as session:
        session.add(Team(name="Avengers"))
        session.add(Team(name="X-Men"))
        session.commit()

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
            options = [{"value": team.id, "label": team.name}
                       for team in self.teams()]
            return FormRenderer(
                theme=self.get_theme(request),
                ui=parse_ui({"team_id": {"ui:options": options}}))

        @trigger(name="save", title="Save", validate=True)
        def save(self, request, data):
            with Session(engine) as session:
                session.add(Hero.model_validate(data))
                session.commit()
            return redirect("/heroes", code=303)

    client = Client(Request.application(CreateHero()))
    html = client.get("/").text
    assert re.search(r'<option value="1">Avengers</option>', html)
    # an id that was not offered
    assert press(client, "/", name="Ann", team_id="99").status_code == 200
    assert press(client, "/", name="Ann", team_id="2").status_code == 303
    with Session(engine) as session:
        assert session.exec(select(Hero)).one().team_id == 2
