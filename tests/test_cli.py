"""`flask setup-db`."""

import pytest
import sqlalchemy as sa

from app import models

MODEL_TABLES = [
    "artist",
    "category",
    "collection_item",
    "collection_item_artist",
    "collection_item_category",
    "collection_item_format",
    "collection_item_genre",
    "collection_item_style",
    "folder",
    "genre",
    "media_condition",
    "sleeve_condition",
    "style",
]


@pytest.fixture(autouse=True)
def from_the_project_folder(request, monkeypatch):
    # The app finds its migrations folder relative to the working directory.
    monkeypatch.chdir(request.config.rootpath)


@pytest.fixture
def new_database(db, rebuild_database):
    """The database as Flask-AppBuilder leaves a new one: its own ab_* tables
    only, with none of ours and no alembic_version."""
    db.session.remove()
    for table in reversed(db.metadata.sorted_tables):
        if not table.name.startswith("ab_"):
            table.drop(db.engine, checkfirst=True)
    db.engine.dispose()


def tables(db):
    return set(sa.inspect(db.engine).get_table_names())


def version(db):
    with db.engine.connect() as conn:
        return conn.execute(sa.text("select version_num from alembic_version")).all()


def head():
    from alembic.script import ScriptDirectory
    from flask_migrate import Config

    config = Config("migrations/alembic.ini")
    config.set_main_option("script_location", "migrations")
    return ScriptDirectory.from_config(config).get_current_head()


def run(app):
    return app.test_cli_runner().invoke(args=["setup-db"])


class TestSetupDb:
    def test_the_command_is_registered(self, app):
        assert "setup-db" in app.cli.commands

    def test_a_new_database_gets_every_table_at_the_latest_migration(
        self, app, db, new_database
    ):
        assert not tables(db) & set(MODEL_TABLES)
        result = run(app)
        assert result.exit_code == 0, result.output
        assert "Created a new database at the latest migration." in result.output
        assert set(MODEL_TABLES) <= tables(db)
        assert version(db) == [(head(),)]

    def test_a_new_database_keeps_the_security_tables(self, app, db, new_database):
        run(app)
        assert {"ab_user", "ab_role", "ab_permission"} <= tables(db)

    def test_a_database_that_is_already_set_up_is_migrated_not_recreated(
        self, app, db, new_database, make
    ):
        run(app)
        make.folder("Kept")
        result = run(app)
        assert result.exit_code == 0, result.output
        assert "Created a new database" not in result.output
        assert version(db) == [(head(),)]
        assert db.session.query(models.Folder).count() == 1

    def test_the_migration_from_nothing_builds_the_models_schema(
        self, app, db, new_database
    ):
        # With an alembic_version table already there, the command runs the
        # migrations rather than create_all().
        with db.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "create table alembic_version (version_num varchar(32) not null)"
                )
            )
        result = run(app)
        assert result.exit_code == 0, result.output
        assert set(MODEL_TABLES) <= tables(db)
        assert version(db) == [(head(),)]
