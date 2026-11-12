import pytest


def _foreign_keys(db):
    for table in db.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                yield column, fk.column


def test_foreign_keys_match_the_type_they_reference(db):
    # MariaDB refuses to create a foreign key between columns of different
    # types, e.g. an Integer pointing at a BigInteger primary key, so a
    # mismatch here breaks db.create_all() on a fresh database. SQLite doesn't
    # mind, so the check has to be made on the models.
    mismatched = [
        f"{column.table.name}.{column.name} ({column.type!r}) -> "
        f"{target.table.name}.{target.name} ({target.type!r})"
        for column, target in _foreign_keys(db)
        if column.type.compile() != target.type.compile()
    ]
    assert mismatched == []


@pytest.mark.parametrize(
    "table, column",
    [
        ("collection_item_artist", "collection_item_id"),
        ("collection_item_genre", "collection_item_id"),
        ("collection_item_style", "collection_item_id"),
        ("collection_item_category", "collection_item_id"),
        ("collection_item_format", "collection_item_id"),
    ],
)
def test_item_foreign_keys_cascade_on_delete(db, table, column):
    # An item's rows in the association and format tables go with it.
    (fk,) = db.metadata.tables[table].columns[column].foreign_keys
    assert fk.ondelete == "CASCADE"


def test_every_model_table_is_utf8mb4(db):
    # Artist and title names include non-Latin text.
    from app import models

    tables = [
        t
        for t in db.metadata.sorted_tables
        if not t.name.startswith("ab_") and t.name != "alembic_version"
    ]
    assert tables
    for table in tables:
        assert table.kwargs.get("mysql_charset") == "utf8mb4", table.name
    assert models.TABLE_ARGS == {"mysql_charset": "utf8mb4"}


def test_the_security_tables_have_the_shapes_migration_0002_gives_them(db):
    # Flask-AppBuilder 5 changed its own tables, and migration 0002 brings an
    # existing database to the same shapes. SQLite can't run that migration's
    # ALTERs, so this pins what it aims for; the Migrations workflow checks it
    # against MariaDB with `flask db check`.
    tables = db.metadata.tables
    for table in ("ab_user", "ab_register_user"):
        assert tables[table].c.username.type.length == 128
        assert tables[table].c.email.type.length == 320
        assert tables[table].c.email.unique
    for column in ("permission_id", "view_menu_id"):
        assert not tables["ab_permission_view"].c[column].nullable
    assert "ab_api_key" in tables


def test_the_print_subtitle_is_what_migration_0003_adds(db):
    # An optional short text, which an item has none of until one is typed in.
    # The Migrations workflow checks the migration against MariaDB with
    # `flask db check`; tests/test_cli.py runs it on SQLite.
    column = db.metadata.tables["collection_item"].c.print_subtitle
    assert column.type.length == 100
    assert column.nullable
    assert column.default is None and column.server_default is None
