#!/usr/bin/env python3
"""Copy vc's data from MongoDB into the MariaDB database, once.

Run it from the repository root (or /app in the image), with config.py set up
for the new database:

    python scripts/migrate_from_mongo.py --mongo-uri mongodb://HOST:27017/vc --dry-run
    python scripts/migrate_from_mongo.py --mongo-uri mongodb://HOST:27017/vc \\
        --not-lp "Edison Diamond Disc" --not-lp 45s

It reads MongoDB and never writes to it. Records are matched on Discogs ids
(artists, folders, items) and on names (genres, styles, categories and
conditions), not on Mongo's ids. A record already in MariaDB is left alone, so
the script can be run again; nothing is ever updated or deleted. With
--dry-run everything is done inside a transaction that is rolled back, so
nothing is written.

At the end it compares the row counts and lists everything it couldn't match,
and exits with status 1 if there was anything.
"""

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pymongo  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from app import app, db  # noqa: E402
from app.models import (  # noqa: E402
    Artist,
    Category,
    CollectionItem,
    CollectionItemFormat,
    Folder,
    Genre,
    MediaCondition,
    SleeveCondition,
    Style,
    set_artists,
)


class ReadOnlyCollection:
    """A Mongo collection that can only be read."""

    def __init__(self, collection):
        self._collection = collection

    def find(self, *args, **kwargs):
        return self._collection.find(*args, **kwargs)

    def count_documents(self, *args, **kwargs):
        return self._collection.count_documents(*args, **kwargs)


class Report:
    def __init__(self):
        self.unmatched = []
        self.created = Counter()
        self.existing = Counter()

    def problem(self, what, detail):
        self.unmatched.append(what + ": " + detail)


def label(doc):
    return str(doc.get("_id"))


def get_or_create(report, kind, model, key, defaults):
    """The row of `model` with the natural key `key`, created from `defaults`
    if it isn't there. Returns it, and whether it was created."""
    row = db.session.query(model).filter_by(**key).one_or_none()
    if row is not None:
        report.existing[kind] += 1
        return row, False
    row = model(**key, **defaults)
    db.session.add(row)
    db.session.flush()
    report.created[kind] += 1
    return row, True


def copy_simple(report, mongo, kind, collection, model, field, mongo_field=None):
    """Copy a collection with one unique name column, returning a map of
    Mongo ids to rows. Documents with the same name share a row."""
    mongo_field = mongo_field or field
    ids = {}
    seen = {}
    for doc in mongo[collection].find():
        name = doc.get(mongo_field)
        if not name or not str(name).strip():
            report.problem(kind, label(doc) + " has no " + mongo_field)
            continue
        if name in seen:
            report.problem(
                kind,
                label(doc) + " has the same " + mongo_field + " as " + seen[name]
                + " (" + repr(name) + "); both map to one row",
            )
        else:
            seen[name] = label(doc)
        try:
            with db.session.begin_nested():
                row, _ = get_or_create(report, kind, model, {field: name}, {})
        except sa.exc.SQLAlchemyError as e:
            report.problem(kind, label(doc) + " " + repr(name) + ": " + str(e.orig))
            continue
        ids[doc["_id"]] = row
    return ids


def copy_artists(report, mongo):
    ids = {}
    for doc in mongo["artist"].find():
        did = doc.get("artist_id")
        if did is None or not doc.get("name"):
            report.problem("artist", label(doc) + " has no artist_id or name")
            continue
        try:
            with db.session.begin_nested():
                row, _ = get_or_create(
                    report,
                    "artist",
                    Artist,
                    {"discogs_id": did},
                    {
                        "name": doc["name"],
                        "sort_name": doc.get("sort_name"),
                        "ignore": bool(doc.get("ignore", False)),
                    },
                )
        except sa.exc.SQLAlchemyError as e:
            report.problem("artist", label(doc) + " " + repr(doc["name"]) + ": " + str(e.orig))
            continue
        ids[doc["_id"]] = row
    return ids


def copy_folders(report, mongo, not_lp):
    ids = {}
    matched = set()
    for doc in mongo["folder"].find():
        did = doc.get("folder_id")
        if did is None or not doc.get("name"):
            report.problem("folder", label(doc) + " has no folder_id or name")
            continue
        flagged = [x for x in not_lp if x == doc["name"] or x == str(doc["_id"])]
        matched.update(flagged)
        try:
            with db.session.begin_nested():
                row, created = get_or_create(
                    report,
                    "folder",
                    Folder,
                    {"discogs_id": did},
                    {"name": doc["name"], "counts_as_lp": not flagged},
                )
        except sa.exc.SQLAlchemyError as e:
            report.problem("folder", label(doc) + " " + repr(doc["name"]) + ": " + str(e.orig))
            continue
        ids[doc["_id"]] = row
    for x in not_lp:
        if x not in matched:
            report.problem("--not-lp", repr(x) + " matched no folder")
    return ids


def copy_items(report, mongo, maps):
    count = 0
    for doc in mongo["collection_item"].find().sort("instance_id", 1):
        count += 1
        iid = doc.get("instance_id")
        title = doc.get("title")
        what = "item " + label(doc) + " (instance " + str(iid) + ")"
        if iid is None or doc.get("release_id") is None or not title:
            report.problem(what, "has no instance_id, release_id or title; skipped")
            continue
        refs = {}
        for field, mapname in (("folder", "folder"), ("filed_under", "artist"),
                               ("media_condition", "media"), ("sleeve_condition", "sleeve")):
            ref = doc.get(field)
            if ref is None:
                refs[field] = None
            elif ref in maps[mapname]:
                refs[field] = maps[mapname][ref]
            else:
                report.problem(what, field + " " + str(ref) + " matches nothing; left empty")
                refs[field] = None
        lists = {}
        for field, mapname in (("artists", "artist"), ("genres", "genre"),
                               ("styles", "style"), ("categories", "category")):
            rows = []
            for ref in doc.get(field) or []:
                if ref in maps[mapname]:
                    row = maps[mapname][ref]
                    if row not in rows:
                        rows.append(row)
                else:
                    report.problem(what, field + " " + str(ref) + " matches nothing; left out")
            lists[field] = rows
        if not lists["artists"]:
            report.problem(what, "has no artists that match")
        if db.session.query(CollectionItem).filter_by(instance_id=iid).count():
            report.existing["item"] += 1
            continue
        try:
            with db.session.begin_nested():
                item = CollectionItem(
                    instance_id=iid,
                    release_id=doc["release_id"],
                    title=title,
                    year=doc.get("year"),
                    released=doc.get("released"),
                    # Mongo used 0 for no master.
                    master_id=doc.get("master_id") or None,
                    master_year=doc.get("master_year"),
                    folder=refs["folder"],
                    filed_under=refs["filed_under"],
                    media_condition=refs["media_condition"],
                    sleeve_condition=refs["sleeve_condition"],
                    item_notes=doc.get("item_notes"),
                    listened=doc.get("listened"),
                    includes=doc.get("includes"),
                    genres=lists["genres"],
                    styles=lists["styles"],
                    categories=lists["categories"],
                    formats=[
                        CollectionItemFormat(
                            position=position,
                            name=f.get("name"),
                            qty=f.get("qty"),
                            text=f.get("text"),
                            descriptions=f.get("descriptions") or [],
                        )
                        for position, f in enumerate(doc.get("formats") or [])
                    ],
                )
                db.session.add(item)
                db.session.flush()
                set_artists(db.session, item, lists["artists"])
            report.created["item"] += 1
        except sa.exc.SQLAlchemyError as e:
            report.problem(what, "not copied: " + str(getattr(e, "orig", e)))
    return count


def table_count(name):
    return db.session.execute(sa.text("select count(*) from " + name)).scalar()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--mongo-uri", required=True, help="MongoDB URI, with the database")
    parser.add_argument("--mongo-db", help="database name, if the URI has none")
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument(
        "--not-lp",
        action="append",
        default=[],
        metavar="NAME_OR_MONGO_ID",
        help="a folder that doesn't count as LPs, by name or by its Mongo _id;"
        " repeat for each. Only sets new folders.",
    )
    args = parser.parse_args()

    client = pymongo.MongoClient(args.mongo_uri, serverSelectionTimeoutMS=10000)
    name = args.mongo_db or client.get_default_database(default="vc").name
    database = client[name]
    mongo = {n: ReadOnlyCollection(database[n]) for n in database.list_collection_names()}
    wanted = ["collection_item", "artist", "genre", "style", "category", "folder",
              "media_condition", "sleeve_condition"]
    for n in wanted:
        mongo.setdefault(n, ReadOnlyCollection(database[n]))
    print("Mongo database:", name, "| target:", db.engine.url.render_as_string(hide_password=True))

    tables = sa.inspect(db.engine).get_table_names()
    if "alembic_version" not in tables or "collection_item" not in tables:
        sys.exit("The target database has no vc tables: run `flask setup-db` first.")

    report = Report()
    with app.app_context():
        maps = {
            "folder": copy_folders(report, mongo, args.not_lp),
            "artist": copy_artists(report, mongo),
            "genre": copy_simple(report, mongo, "genre", "genre", Genre, "name"),
            "style": copy_simple(report, mongo, "style", "style", Style, "name"),
            "category": copy_simple(report, mongo, "category", "category", Category, "name"),
            "media": copy_simple(report, mongo, "media condition", "media_condition",
                                 MediaCondition, "label"),
            "sleeve": copy_simple(report, mongo, "sleeve condition", "sleeve_condition",
                                  SleeveCondition, "label"),
        }
        copy_items(report, mongo, maps)

        embedded = {"formats": 0, "artist links": 0}
        for doc in mongo["collection_item"].find():
            embedded["formats"] += len(doc.get("formats") or [])
            embedded["artist links"] += len(doc.get("artists") or [])
        rows = [
            ("folder", "folder", "folder"),
            ("artist", "artist", "artist"),
            ("genre", "genre", "genre"),
            ("style", "style", "style"),
            ("category", "category", "category"),
            ("media condition", "media_condition", "media_condition"),
            ("sleeve condition", "sleeve_condition", "sleeve_condition"),
            ("item", "collection_item", "collection_item"),
        ]
        print()
        print("%-18s %8s %9s %9s %9s" % ("", "Mongo", "created", "existing", "MariaDB"))
        for kind, collection, table in rows:
            print(
                "%-18s %8d %9d %9d %9d"
                % (kind, mongo[collection].count_documents({}), report.created[kind],
                   report.existing[kind], table_count(table))
            )
        print("%-18s %8d %9s %9s %9d" % ("item formats", embedded["formats"], "", "",
                                          table_count("collection_item_format")))
        print("%-18s %8d %9s %9s %9d" % ("item artist links", embedded["artist links"], "", "",
                                          table_count("collection_item_artist")))
        if args.dry_run:
            db.session.rollback()
            print("\nDry run: nothing was written. (Counts above are from inside the"
                  " rolled-back transaction.)")
        else:
            db.session.commit()
            print("\nCommitted.")

    if report.unmatched:
        print("\nNot matched or not copied (%d):" % len(report.unmatched))
        for line in report.unmatched:
            print("  -", line)
        sys.exit(1)
    print("\nNothing unmatched.")


if __name__ == "__main__":
    main()
