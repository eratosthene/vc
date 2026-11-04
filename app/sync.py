"""
The Discogs sync: folders first, then items added or updated by `instance_id`
(notes included), then the items that are no longer on Discogs.

It only writes what comes from Discogs. What's kept only in vc is left alone:
categories, `filed_under`, an artist's `sort_name` and `ignore`, and a
folder's `counts_as_lp`.

`run()` does the work, for the `flask sync-discogs` command and the web
button's background job (app/syncjob.py) alike. With `dry_run=True` it does
all of it in a transaction that it rolls back, so nothing is saved.
"""

import fcntl
import logging
import os
import re
import tempfile
from contextlib import contextmanager

import discogs_client

from app import db

# The models are imported inside the functions that use them, not here: see
# the note in app/index.py.

logger = logging.getLogger("vc.sync")

# Commit after this many items, so a failure partway keeps what came before it.
BATCH = 50
# How often to log how far through the items the sync is.
PROGRESS_EVERY = 100


class SyncAlreadyRunning(Exception):
    """Another sync (from the web button or the command) is running."""


def lock_folder(app):
    """The folder for the sync's lock file and its background jobs' files."""
    folder = app.config.get("SYNC_JOB_FOLDER") or os.path.join(
        tempfile.gettempdir(), "vc-sync-jobs"
    )
    os.makedirs(folder, exist_ok=True)
    return folder


@contextmanager
def sync_lock(app):
    """
    Hold the sync's lock, or raise SyncAlreadyRunning. It's a file lock, so it
    covers the gunicorn workers and `flask sync-discogs` alike, and the system
    drops it if the process dies.
    """
    with open(os.path.join(lock_folder(app), "sync.lock"), "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SyncAlreadyRunning("A sync is already running.") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Summary:
    """What a sync did, or with a dry run, what it would do."""

    def __init__(self, dry_run):
        self.dry_run = dry_run
        self.folders_added = []
        self.folders_renamed = []
        self.items_total = 0
        self.added = []
        # (title, [the fields that changed])
        self.updated = []
        self.removed = []
        self.unchanged = 0
        self.artists_added = 0
        self.api_calls = 0

    def lines(self):
        verb = "Would" if self.dry_run else "Did"
        out = [
            ("Dry run: nothing was saved." if self.dry_run else "Sync finished.")
            + f" {verb}:"
        ]
        out.append(
            f"  folders: {len(self.folders_added)} added, "
            f"{len(self.folders_renamed)} renamed"
        )
        out.append(
            f"  items: {len(self.added)} added, {len(self.updated)} updated, "
            f"{len(self.removed)} removed, {self.unchanged} unchanged "
            f"(of {self.items_total} on Discogs)"
        )
        out.append(f"  new artists: {self.artists_added}")
        out.append(f"  extra Discogs requests (releases and masters): {self.api_calls}")
        if self.removed:
            out.append("  removed:" if not self.dry_run else "  would be removed:")
            out.extend(f"    - {title}" for title in self.removed)
        return out


def get_client(config):
    """A Discogs client with its rate-limit backoff on.

    python3-discogs-client waits and retries when Discogs answers 429 (60
    requests a minute with a token), unless `backoff_enabled` is turned off.
    It's on by default; this makes sure of it, rather than adding a limiter
    of our own.
    """
    settings = config["DISCOGS_SETTINGS"]
    client = discogs_client.Client(
        settings["USER_AGENT"], user_token=settings["USER_TOKEN"]
    )
    client.backoff_enabled = True
    return client


def get_or_add(model, **kwargs):
    """The row of `model` matching `kwargs`, added to the session if it's new."""
    row = db.session.query(model).filter_by(**kwargs).one_or_none()
    if row is None:
        row = model(**kwargs)
        db.session.add(row)
        db.session.flush()
        logger.debug("Adding " + model.__name__.lower() + " " + str(row))
    return row


def parse_notes(item):
    """Media and sleeve condition, notes, Listened and Includes from an item's
    Discogs notes, as a dict of CollectionItem fields."""
    from app.models import MediaCondition, SleeveCondition

    mc = None
    sc = None
    n = None
    listened = None
    i = None
    # An item with no notes has none in the listing at all.
    for note in item.notes or []:
        if note["field_id"] == 1:
            mc = get_or_add(MediaCondition, label=note["value"].rstrip())
        if note["field_id"] == 2:
            sc = get_or_add(SleeveCondition, label=note["value"].rstrip())
        if note["field_id"] == 3:
            n = note["value"].rstrip()
        if note["field_id"] == 4:
            listened = note["value"].rstrip() == "Yes"
        if note["field_id"] == 5:
            i = note["value"].rstrip()
    return {
        "media_condition": mc,
        "sleeve_condition": sc,
        "item_notes": n,
        "listened": listened,
        "includes": i,
    }


def sort_name_for(name):
    """The automatic sort name for a new artist, which is what vc shows.

    Discogs adds a number to tell artists of the same name apart ("Prince (2)"),
    which is dropped. "The X" becomes "X, The". It's "" when neither applies.
    Only a new artist gets one: an existing artist's name and sort name are
    never rewritten, so what's been set by hand stays.
    """
    shown = re.sub(r" \(\d+\)$", "", name)
    if shown.startswith("The "):
        return shown.removeprefix("The ") + ", The"
    return shown if shown != name else ""


def sync_folders(discogs_folders, summary):
    """Add the folders vc doesn't have and rename the ones that changed."""
    from app.models import Folder

    local = {f.discogs_id: f for f in db.session.query(Folder)}
    for df in discogs_folders:
        # Folder 0 is Discogs's "All", not a folder items live in.
        if df.id == 0:
            continue
        folder = local.get(df.id)
        if folder is None:
            logger.info(f"Adding folder {df.name!r}")
            folder = Folder(discogs_id=df.id, name=df.name)
            db.session.add(folder)
            local[df.id] = folder
            summary.folders_added.append(df.name)
        elif folder.name != df.name:
            logger.info(f"Renaming folder {folder.name!r} to {df.name!r}")
            summary.folders_renamed.append(f"{folder.name} -> {df.name}")
            folder.name = df.name
    db.session.flush()
    return local


def _artists(release, known, summary):
    artists = []
    for a in release.artists:
        artist = known.get(a.id)
        if artist is None:
            from app.models import Artist

            artist = Artist(
                discogs_id=a.id, name=a.name, sort_name=sort_name_for(a.name)
            )
            db.session.add(artist)
            db.session.flush()
            known[a.id] = artist
            summary.artists_added += 1
            logger.info(f"Adding artist {a.name!r}")
        artists.append(artist)
    return artists


def _formats(release):
    """The release's formats as comparable tuples."""
    return [
        (
            f["name"],
            int(f["qty"]) if f.get("qty") else None,
            f.get("text"),
            list(f.get("descriptions", [])),
        )
        for f in release.formats
    ]


def sync_item(item, local, folders, known_artists, masters, summary, dry_run):
    """
    Add or update one collection item. Returns "added", "updated" or
    "unchanged".

    Everything the listing carries (`basic_information`) is used as it is.
    Only a new item, or one whose release changed, needs the release's own
    page (for `released`), and a master's year is looked up once per master,
    and not at all if a local item with that master already has it.
    """
    from app.models import CollectionItem, CollectionItemFormat, Genre, Style

    release = item.release
    row = local.get(item.instance_id)
    is_new = row is None
    if is_new:
        row = CollectionItem(instance_id=item.instance_id)

    master = release.master
    master_id = master.id if master else None
    if master_id is None:
        master_year = release.year
    elif master_id in masters:
        master_year = masters[master_id]
    else:
        master_year = None
        if not dry_run:
            master_year = master.year
            summary.api_calls += 1
        masters[master_id] = master_year

    # Only the page of a new release has `released`: an item whose release id
    # hasn't changed keeps what it has.
    released = row.released
    if (is_new or row.release_id != release.id) and not dry_run:
        released = release.fetch("released")
        summary.api_calls += 1

    folder = folders.get(item.folder_id)
    if folder is None:
        logger.warning(
            f"{release.title!r} is in Discogs folder {item.folder_id}, "
            "which isn't in the folder list; leaving it without a folder"
        )

    wanted = {
        "release_id": release.id,
        "title": release.title,
        "year": release.year,
        "master_id": master_id,
        "master_year": master_year,
        "released": released,
        "folder": folder,
        **parse_notes(item),
    }
    changed = [f for f, v in wanted.items() if getattr(row, f) != v]
    for field in changed:
        setattr(row, field, wanted[field])

    artists = _artists(release, known_artists, summary)
    if {a.id for a in row.artists} != {a.id for a in artists}:
        row.artists = artists
        changed.append("artists")
    for field, model, names in (
        ("genres", Genre, release.genres or []),
        ("styles", Style, release.styles or []),
    ):
        if {x.name for x in getattr(row, field)} != set(names):
            setattr(row, field, [get_or_add(model, name=n) for n in names])
            changed.append(field)
    formats = _formats(release)
    current = [(f.name, f.qty, f.text, list(f.descriptions or [])) for f in row.formats]
    if current != formats:
        row.formats = [
            CollectionItemFormat(name=n, qty=q, text=t, descriptions=d)
            for n, q, t, d in formats
        ]
        changed.append("formats")

    if is_new:
        db.session.add(row)
        local[item.instance_id] = row
        summary.added.append(release.title)
        logger.info(f"Adding {release.title!r} ({item.instance_id})")
        return "added"
    if changed:
        summary.updated.append((release.title, changed))
        logger.info(
            f"Updating {release.title!r} ({item.instance_id}): " + ", ".join(changed)
        )
        return "updated"
    return "unchanged"


def run(app, client=None, dry_run=False):
    """
    Sync the collection from Discogs and return a Summary. Needs an app
    context. Raises SyncAlreadyRunning if another sync holds the lock.
    """
    from app.models import Artist, CollectionItem

    with sync_lock(app):
        summary = Summary(dry_run)
        logger.info("Starting the Discogs sync" + (" (dry run)" if dry_run else ""))
        if client is None:
            client = get_client(app.config)
        try:
            me = client.identity()
            discogs_folders = me.collection_folders
            logger.info(f"Discogs has {len(discogs_folders)} folders")
            folders = sync_folders(discogs_folders, summary)

            # Folder 0 is "All": every item in the collection. The whole
            # listing is read before anything is removed, so a failure
            # partway through can't look like a lot of removals.
            everything = next(f for f in discogs_folders if f.id == 0).releases
            everything.per_page = 100
            items = list(everything)
            summary.items_total = len(items)
            logger.info(f"Discogs has {len(items)} items")

            local = {i.instance_id: i for i in db.session.query(CollectionItem)}
            logger.info(f"vc has {len(local)} items")
            known_artists = {a.discogs_id: a for a in db.session.query(Artist)}
            masters = {
                i.master_id: i.master_year
                for i in local.values()
                if i.master_id is not None and i.master_year is not None
            }
            seen = set()
            for n, item in enumerate(items, 1):
                seen.add(item.instance_id)
                result = sync_item(
                    item, local, folders, known_artists, masters, summary, dry_run
                )
                if result == "unchanged":
                    summary.unchanged += 1
                if n % BATCH == 0 and not dry_run:
                    db.session.commit()
                if n % PROGRESS_EVERY == 0:
                    logger.info(f"Checked {n} of {len(items)} items")

            # Removals last, from a set rather than a search per item.
            for instance_id in set(local) - seen:
                row = local[instance_id]
                logger.info(f"Removing {row.title!r} ({instance_id})")
                summary.removed.append(row.title)
                db.session.delete(row)

            if dry_run:
                db.session.rollback()
            else:
                db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        for line in summary.lines():
            logger.info(line)
        return summary
