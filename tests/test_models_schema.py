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
