"""
Shared pytest fixtures for the vc test suite.

The real app (app/__init__.py) builds its Flask/SQLAlchemy/AppBuilder stack at
*import time*, reading connection settings from the top-level ``config``
module, which points at a real MariaDB server with real credentials. To keep
the test suite hermetic and runnable offline, an in-memory SQLite stand-in for
``config`` goes into ``sys.modules`` *before* ``app`` is ever imported, so
``app.config.from_object("config")`` picks up the fake module and never reads
config.py.
"""

import importlib
import logging
import math
import random
import sys
import types

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


def _install_fake_config():
    from flask_appbuilder.security.manager import AUTH_DB

    config = types.ModuleType("config")
    config.SECRET_KEY = "test-secret-key"
    config.SQLALCHEMY_DATABASE_URI = "sqlite://"
    # One connection shared by every thread, so the in-memory database is the
    # same one for the test client and the test.
    config.SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    config.SQLALCHEMY_TRACK_MODIFICATIONS = False
    config.CSRF_ENABLED = False
    config.WTF_CSRF_ENABLED = False
    config.APP_NAME = "vc-test"
    config.AUTH_TYPE = AUTH_DB
    config.AUTH_USER_REGISTRATION = False
    config.BABEL_DEFAULT_LOCALE = "en"
    config.DISCOGS_SETTINGS = {
        "USER_TOKEN": "test-discogs-token",
        "USER_AGENT": "vc-tests/1.0",
    }
    sys.modules["config"] = config


@event.listens_for(Engine, "connect")
def _sqlite_has_mariadb_functions(dbapi_connection, _record):
    # The app uses MariaDB's RAND() and FLOOR(); SQLite has random() and, only
    # when built with the math functions, floor().
    if not hasattr(dbapi_connection, "create_function"):
        return
    dbapi_connection.create_function("rand", 0, random.random)
    dbapi_connection.create_function("floor", 1, math.floor)


# Keep AppBuilder's permission-registration logging out of the test output.
logging.getLogger().setLevel(logging.ERROR)

_install_fake_config()

# A plain `import app` statement here must come after the fake config is
# installed above, which a linter would flag as an out-of-order import (E402);
# importlib.import_module is a regular call, so it doesn't.
vc = importlib.import_module("app")
importlib.import_module("app.models")


@pytest.fixture(scope="session")
def app():
    """The single, module-level Flask application under test."""
    return vc.app


@pytest.fixture(scope="session")
def db():
    """The single, module-level Flask-SQLAlchemy extension under test."""
    return vc.db


def _build_database():
    """Every table, the Admin role and the views' permissions, and an admin."""
    vc.db.session.remove()
    vc.db.drop_all()
    vc.db.create_all()
    sm = vc.appbuilder.sm
    # The Admin role, and the permissions of the views.
    sm.create_db()
    vc.appbuilder.add_permissions(update_perms=True)
    sm.add_user(
        "admin", "Ad", "Min", "admin@example.com", sm.find_role("Admin"), "password"
    )


@pytest.fixture(scope="session", autouse=True)
def database():
    """The database, built once for the whole run."""
    with vc.app.app_context():
        _build_database()
    yield


@pytest.fixture(autouse=True)
def app_context(database):
    """
    An application context for each test (a shared one would share Flask's `g`,
    and with it the signed-in user), and empty tables of the app's own when it
    ends. The security tables stay: building them takes most of a second.
    """
    with vc.app.app_context() as ctx:
        yield ctx
        vc.db.session.remove()
        for table in reversed(vc.db.metadata.sorted_tables):
            if not table.name.startswith("ab_"):
                vc.db.session.execute(table.delete())
        vc.db.session.commit()
        vc.db.session.remove()


@pytest.fixture
def rebuild_database():
    """For a test that leaves the database in a state the others can't use."""
    yield
    with vc.app.app_context():
        _build_database()


@pytest.fixture
def discogs(monkeypatch):
    """A fake Discogs account, in place of discogs_client.Client everywhere."""
    from fake_discogs import FakeDiscogs

    fake = FakeDiscogs()
    monkeypatch.setattr("discogs_client.Client", fake.Client)
    return fake


@pytest.fixture
def make(db):
    """Row builders. Each adds to the session, commits and returns the row."""
    from app import models

    class Make:
        counter = 0

        def _save(self, row):
            db.session.add(row)
            db.session.commit()
            return row

        def _n(self):
            self.counter += 1
            return self.counter

        def folder(self, name="Alphabetical", **kw):
            kw.setdefault("discogs_id", self._n())
            return self._save(models.Folder(name=name, **kw))

        def artist(self, name="Artist", **kw):
            kw.setdefault("discogs_id", self._n())
            return self._save(models.Artist(name=name, **kw))

        def category(self, name="Rock"):
            return self._save(models.Category(name=name))

        def item(self, title="Title", artists=(), categories=(), **kw):
            n = self._n()
            kw.setdefault("instance_id", n)
            kw.setdefault("release_id", n)
            kw.setdefault("year", 2000)
            # Each item has a master of its own, unless a test says otherwise.
            kw.setdefault("master_id", n)
            kw.setdefault("master_year", kw["year"])
            item = models.CollectionItem(title=title, **kw)
            item.artists = list(artists)
            item.categories = list(categories)
            return self._save(item)

    return Make()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    """The test client, signed in as an admin."""
    response = client.post(
        "/login/", data={"username": "admin", "password": "password"}
    )
    assert response.status_code == 302
    return client
