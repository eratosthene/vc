"""The Discogs sync (app/sync.py) against the fake Discogs client, and the
button and routes that start it."""

import logging

import pytest

from app import models
from app import sync as discogs_sync

BEATLES = (10, "The Beatles")
STONES = (11, "The Rolling Stones")
PRINCE = (12, "Prince")


@pytest.fixture(autouse=True)
def sync_logger_on():
    # The migrations' fileConfig() (run by the setup-db tests) switches off
    # loggers that already exist.
    logging.getLogger("vc.sync").disabled = False


@pytest.fixture
def folder(make):
    """The folder the fake client puts items in by default (Discogs id 1)."""
    return make.folder("Alphabetical", discogs_id=1)


def sync(dry_run=False):
    from app import app

    return discogs_sync.run(app, dry_run=dry_run)


def items(db):
    return db.session.query(models.CollectionItem).order_by(models.CollectionItem.id)


def names(rows):
    return sorted(str(r) for r in rows)


class TestNewItem:
    def test_adds_the_item_with_what_discogs_has(self, db, discogs, folder):
        discogs.add(
            100,
            "Abbey Road",
            1987,
            [BEATLES],
            genres=["Rock"],
            styles=["Pop Rock"],
            master=(555, 1969),
            formats=[
                {
                    "name": "Vinyl",
                    "qty": "1",
                    "text": "Red",
                    "descriptions": ["LP", "Reissue"],
                }
            ],
            released="1987-05-01",
        )
        sync()
        (item,) = items(db)
        assert item.instance_id == 100
        assert item.release_id == 1100
        assert item.title == "Abbey Road"
        assert item.year == 1987
        assert item.master_id == 555
        assert item.master_year == 1969
        assert item.released == "1987-05-01"
        assert item.folder == folder
        assert names(item.artists) == ["Beatles, The"]
        assert names(item.genres) == ["Rock"]
        assert names(item.styles) == ["Pop Rock"]
        (fmt,) = item.formats
        assert (fmt.name, fmt.qty, fmt.text, fmt.descriptions) == (
            "Vinyl",
            1,
            "Red",
            ["LP", "Reissue"],
        )
        assert item.categories == []
        assert item.filed_under is None

    def test_format_without_qty_text_or_descriptions(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], formats=[{"name": "Cassette"}])
        sync()
        (fmt,) = items(db).one().formats
        assert (fmt.name, fmt.qty, fmt.text, fmt.descriptions) == (
            "Cassette",
            None,
            None,
            [],
        )

    def test_formats_keep_their_order(self, db, discogs, folder):
        discogs.add(
            100,
            "A",
            2000,
            [PRINCE],
            formats=[{"name": "Vinyl"}, {"name": "Box Set"}, {"name": "CD"}],
        )
        sync()
        assert [f.name for f in items(db).one().formats] == ["Vinyl", "Box Set", "CD"]

    def test_adds_every_item_in_the_collection(self, db, discogs, folder):
        discogs.add(100, "One", 2000, [PRINCE])
        discogs.add(101, "Two", 2001, [PRINCE])
        sync()
        assert names(items(db)) == ["One", "Two"]

    def test_with_two_artists(self, db, discogs, folder):
        discogs.add(100, "Split", 2000, [BEATLES, PRINCE])
        sync()
        assert names(items(db).one().artists) == ["Beatles, The", "Prince"]

    def test_release_with_no_master_has_no_master_id(self, db, discogs, folder):
        discogs.add(100, "A", 1995, [PRINCE])
        sync()
        item = items(db).one()
        assert item.master_id is None
        # With no master, the master year is the release's own year.
        assert item.master_year == 1995

    def test_item_in_a_second_folder(self, db, discogs, folder, make):
        other = make.folder("45s", discogs_id=2)
        discogs.add(100, "A", 1995, [PRINCE], folder_id=2)
        sync()
        assert items(db).one().folder == other

    def test_empty_collection_adds_nothing(self, db, discogs, folder):
        sync()
        assert items(db).count() == 0


class TestNewArtistsGenresStyles:
    def test_new_artists_are_added(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        (artist,) = db.session.query(models.Artist).all()
        assert (artist.discogs_id, artist.name, artist.ignore) == (12, "Prince", False)

    def test_known_artist_is_reused(self, db, discogs, folder, make):
        known = make.artist("Prince", discogs_id=12)
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        assert db.session.query(models.Artist).count() == 1
        assert items(db).one().artists == [known]

    def test_an_artist_on_two_items_is_added_once(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        discogs.add(101, "B", 2001, [PRINCE])
        sync()
        assert db.session.query(models.Artist).count() == 1

    def test_new_genres_and_styles_are_added_once(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], genres=["Rock", "Pop"], styles=["Funk"])
        discogs.add(101, "B", 2001, [PRINCE], genres=["Rock"], styles=["Funk", "Soul"])
        sync()
        assert names(db.session.query(models.Genre)) == ["Pop", "Rock"]
        assert names(db.session.query(models.Style)) == ["Funk", "Soul"]

    def test_known_genre_is_reused(self, db, discogs, folder, make):
        genre = models.Genre(name="Rock")
        db.session.add(genre)
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE], genres=["Rock"])
        sync()
        assert db.session.query(models.Genre).count() == 1
        assert items(db).one().genres == [genre]


class TestSortNames:
    @pytest.mark.parametrize(
        "name, sort_name",
        [
            ("The Beatles", "Beatles, The"),
            ("The The", "The, The"),
            ("Prince", ""),
            ("Thelonious Monk", ""),
            ("the Pogues", ""),
            ("Various", ""),
        ],
    )
    def test_new_artist_gets_its_sort_name(self, db, discogs, folder, name, sort_name):
        discogs.add(100, "A", 2000, [(50, name)])
        sync()
        assert db.session.query(models.Artist).one().sort_name == sort_name

    def test_only_the_leading_the_moves(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [(50, "The Band of The Hand")])
        sync()
        assert db.session.query(models.Artist).one().sort_name == (
            "Band of The Hand, The"
        )

    def test_a_sort_name_set_by_hand_survives_the_sync(self, db, discogs, folder, make):
        make.artist("The Beatles", discogs_id=10, sort_name="Fab Four")
        discogs.add(100, "A", 2000, [BEATLES])
        sync()
        assert db.session.query(models.Artist).one().sort_name == "Fab Four"

    def test_an_ignored_artist_stays_ignored(self, db, discogs, folder, make):
        make.artist("Prince", discogs_id=12, ignore=True)
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        assert db.session.query(models.Artist).one().ignore is True


class TestNotes:
    def test_each_notes_field(self, db, discogs, folder):
        discogs.add(
            100,
            "A",
            2000,
            [PRINCE],
            notes=[
                (1, "Near Mint (NM or M-)"),
                (2, "Very Good Plus (VG+)"),
                (3, "Signed"),
                (4, "Yes"),
                (5, "Poster"),
            ],
        )
        sync()
        item = items(db).one()
        assert item.media_condition.label == "Near Mint (NM or M-)"
        assert item.sleeve_condition.label == "Very Good Plus (VG+)"
        assert item.item_notes == "Signed"
        assert item.listened is True
        assert item.includes == "Poster"

    def test_no_notes_leaves_everything_empty(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        item = items(db).one()
        assert item.media_condition is None
        assert item.sleeve_condition is None
        assert item.item_notes is None
        assert item.listened is None
        assert item.includes is None

    @pytest.mark.parametrize(
        "value, listened", [("Yes", True), ("No", False), ("", False)]
    )
    def test_listened(self, db, discogs, folder, value, listened):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(4, value)])
        sync()
        assert items(db).one().listened is listened

    def test_values_lose_trailing_whitespace(self, db, discogs, folder):
        discogs.add(
            100,
            "A",
            2000,
            [PRINCE],
            notes=[
                (1, "Mint  "),
                (2, "Good\n"),
                (3, "Note \n"),
                (4, "Yes "),
                (5, "X "),
            ],
        )
        sync()
        item = items(db).one()
        assert item.media_condition.label == "Mint"
        assert item.sleeve_condition.label == "Good"
        assert item.item_notes == "Note"
        assert item.listened is True
        assert item.includes == "X"

    def test_unknown_fields_are_ignored(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(9, "Whatever")])
        sync()
        assert items(db).count() == 1

    def test_conditions_are_added_once_and_shared(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(1, "Mint"), (2, "Good")])
        discogs.add(101, "B", 2001, [PRINCE], notes=[(1, "Mint"), (2, "Fair")])
        sync()
        assert names(db.session.query(models.MediaCondition)) == ["Mint"]
        assert names(db.session.query(models.SleeveCondition)) == ["Fair", "Good"]

    def test_known_condition_is_reused(self, db, discogs, folder):
        mc = models.MediaCondition(label="Mint")
        db.session.add(mc)
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE], notes=[(1, "Mint")])
        sync()
        assert db.session.query(models.MediaCondition).count() == 1
        assert items(db).one().media_condition == mc


class TestExistingItem:
    def test_is_not_added_again(self, db, discogs, folder, make):
        make.item("A", instance_id=100)
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        assert items(db).count() == 1

    def test_keeps_the_categories_set_by_hand(self, db, discogs, folder, make):
        rock = make.category("Rock")
        make.item("A", instance_id=100, categories=[rock])
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        assert items(db).one().categories == [rock]

    def test_second_sync_changes_nothing(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [BEATLES], genres=["Rock"], notes=[(1, "Mint")])
        sync()
        sync()
        assert items(db).count() == 1
        assert db.session.query(models.Artist).count() == 1


class TestRemovedItem:
    def test_item_no_longer_on_discogs_is_deleted(self, db, discogs, folder, make):
        make.item("Gone", instance_id=100)
        make.item("Kept", instance_id=101)
        discogs.add(101, "Kept", 2000, [PRINCE])
        sync()
        assert names(items(db)) == ["Kept"]

    def test_everything_is_removed_from_an_empty_account(
        self, db, discogs, folder, make
    ):
        make.item("Gone", instance_id=100)
        sync()
        assert items(db).count() == 0

    def test_removing_keeps_artists_and_categories(self, db, discogs, folder, make):
        a, c = make.artist(), make.category()
        make.item("Gone", instance_id=100, artists=[a], categories=[c])
        sync()
        assert db.session.query(models.Artist).count() == 1
        assert db.session.query(models.Category).count() == 1

    def test_adds_and_removes_in_one_sync(self, db, discogs, folder, make):
        make.item("Gone", instance_id=100)
        discogs.add(101, "New", 2000, [PRINCE])
        sync()
        assert names(items(db)) == ["New"]


class TestChangesOnDiscogs:
    def test_a_corrected_title_and_year_come_across(self, db, discogs, folder, make):
        make.item("Old title", instance_id=100, year=1990)
        discogs.add(100, "New title", 1991, [PRINCE])
        sync()
        item = items(db).one()
        assert (item.title, item.year) == ("New title", 1991)

    def test_a_moved_folder_comes_across(self, db, discogs, folder, make):
        old = make.folder("Old", discogs_id=2)
        make.item("A", instance_id=100, folder=old)
        discogs.add(100, "A", 2000, [PRINCE], folder_id=1)
        sync()
        assert items(db).one().folder == folder

    def test_new_genres_and_styles_come_across(self, db, discogs, folder, make):
        rock = models.Genre(name="Rock")
        db.session.add(rock)
        item = make.item("A", instance_id=100)
        item.genres = [rock]
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE], genres=["Rock", "Funk"], styles=["Soul"])
        sync()
        assert names(items(db).one().genres) == ["Funk", "Rock"]
        assert names(items(db).one().styles) == ["Soul"]

    def test_genres_and_styles_dropped_on_discogs_go(self, db, discogs, folder, make):
        g = models.Genre(name="Rock")
        item = make.item("A", instance_id=100)
        item.genres = [g]
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        assert items(db).one().genres == []
        # The genre itself stays: other items may use it.
        assert db.session.query(models.Genre).count() == 1

    def test_changed_formats_and_artists_come_across(self, db, discogs, folder, make):
        old = make.artist("Old Artist", discogs_id=77)
        make.item("A", instance_id=100, artists=[old])
        discogs.add(100, "A", 2000, [PRINCE], formats=[{"name": "Vinyl", "qty": "2"}])
        sync()
        item = items(db).one()
        assert names(item.artists) == ["Prince"]
        assert [(f.name, f.qty) for f in item.formats] == [("Vinyl", 2)]

    def test_changed_notes_come_across(self, db, discogs, folder, make):
        make.item("A", instance_id=100, item_notes="Old", listened=False)
        discogs.add(100, "A", 2000, [PRINCE], notes=[(3, "New"), (4, "Yes")])
        sync()
        item = items(db).one()
        assert (item.item_notes, item.listened) == ("New", True)

    def test_notes_removed_on_discogs_are_cleared(self, db, discogs, folder, make):
        mc = models.MediaCondition(label="Mint")
        db.session.add(mc)
        make.item("A", instance_id=100, media_condition=mc, item_notes="Old")
        discogs.add(100, "A", 2000, [PRINCE])
        sync()
        item = items(db).one()
        assert item.media_condition is None
        assert item.item_notes is None

    def test_what_is_only_kept_in_vc_survives_an_update(
        self, db, discogs, folder, make
    ):
        a = make.artist("The Beatles", discogs_id=10, sort_name="Fab Four", ignore=True)
        other = make.artist("Prince", discogs_id=12)
        rock = make.category("Rock")
        make.folder("Old", discogs_id=2, counts_as_lp=False)
        make.item(
            "Old title",
            instance_id=100,
            artists=[a],
            categories=[rock],
            filed_under=other,
            folder=make.folder("Moved", discogs_id=3),
        )
        discogs.add_folder(2, "Old")
        discogs.add(100, "New title", 2001, [BEATLES], folder_id=2)
        sync()
        item = items(db).one()
        assert item.title == "New title"
        assert item.categories == [rock]
        assert item.filed_under == other
        assert item.folder.counts_as_lp is False
        artist = db.session.get(models.Artist, a.id)
        assert (artist.sort_name, artist.ignore) == ("Fab Four", True)


class TestFolders:
    def test_a_new_folder_is_added_before_its_items(self, db, discogs, folder):
        discogs.add_folder(7, "45s")
        discogs.add(100, "A", 2000, [PRINCE], folder_id=7)
        summary = sync()
        (item,) = items(db)
        assert item.folder.name == "45s"
        assert item.folder.discogs_id == 7
        assert summary.folders_added == ["45s"]

    def test_all_is_not_added_as_a_folder(self, db, discogs, folder):
        discogs.add_folder(1, "Alphabetical")
        sync()
        assert names(db.session.query(models.Folder)) == ["Alphabetical"]

    def test_a_renamed_folder_is_renamed(self, db, discogs, folder):
        discogs.add_folder(1, "A to Z")
        discogs.add(100, "A", 2000, [PRINCE], folder_id=1)
        summary = sync()
        assert names(db.session.query(models.Folder)) == ["A to Z"]
        assert items(db).one().folder == folder
        assert summary.folders_renamed == ["Alphabetical -> A to Z"]

    def test_counts_as_lp_survives_a_rename(self, db, discogs, make):
        make.folder("Singles", discogs_id=2, counts_as_lp=False)
        discogs.add_folder(2, "45s")
        sync()
        (f,) = db.session.query(models.Folder)
        assert (f.name, f.counts_as_lp) == ("45s", False)

    def test_a_new_folder_counts_as_lp_by_default(self, db, discogs):
        discogs.add_folder(2, "New")
        sync()
        assert db.session.query(models.Folder).one().counts_as_lp is True

    def test_an_item_in_an_unknown_folder_is_synced_without_one(
        self, db, discogs, folder
    ):
        discogs.add(100, "Odd", 2000, [PRINCE], folder_id=99)
        discogs.add(101, "After", 2000, [PRINCE], folder_id=1)
        sync()
        assert names(items(db)) == ["After", "Odd"]
        assert items(db).first().folder is None


class TestNotesForANewItem:
    def test_a_new_item_gets_its_notes_in_the_same_sync(self, db, discogs, folder):
        # Sync Notes used to fail on an item vc didn't have yet.
        discogs.add(100, "New", 2000, [PRINCE], notes=[(1, "Mint"), (3, "Signed")])
        sync()
        item = items(db).one()
        assert (item.media_condition.label, item.item_notes) == ("Mint", "Signed")


class TestRemovals:
    def test_the_summary_lists_what_was_removed(self, discogs, folder, make):
        make.item("Gone", instance_id=100)
        make.item("Kept", instance_id=101)
        discogs.add(101, "Kept", 2000, [PRINCE])
        summary = sync()
        assert summary.removed == ["Gone"]
        assert "    - Gone" in summary.lines()

    def test_removals_come_after_the_updates(self, db, discogs, folder, make):
        # If a later step failed, the earlier ones are in; removal is last.
        make.item("Gone", instance_id=100)
        discogs.add(101, "New", 2000, [PRINCE], folder_id=1)
        sync()
        assert names(items(db)) == ["New"]

    def test_a_failed_listing_removes_nothing(self, db, discogs, folder, make):
        make.item("Kept", instance_id=100)

        class Broken(list):
            per_page = 50

            def __iter__(self):
                raise RuntimeError("Discogs is down")

        discogs.releases = Broken()
        with pytest.raises(RuntimeError):
            sync()
        assert names(items(db)) == ["Kept"]


class TestRunningTwice:
    def test_the_second_sync_changes_nothing(self, db, discogs, folder, make):
        make.folder("45s", discogs_id=2)
        discogs.add_folder(2, "Singles")
        discogs.add(
            100,
            "A",
            2000,
            [BEATLES, PRINCE],
            genres=["Rock", "Pop"],
            styles=["Funk"],
            notes=[(1, "Mint"), (4, "No")],
            master=(5, 1999),
            formats=[{"name": "Vinyl", "qty": "1", "descriptions": ["LP"]}],
            released="2000-01-01",
            folder_id=2,
        )
        discogs.add(101, "B", 2001, [PRINCE])
        make.item("Gone", instance_id=102)
        first = sync()
        assert (len(first.added), len(first.removed)) == (2, 1)
        second = sync()
        assert second.added == []
        assert second.updated == []
        assert second.removed == []
        assert second.folders_added == [] and second.folders_renamed == []
        assert second.unchanged == 2

    def test_the_second_sync_asks_discogs_for_nothing_more(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999), released="x")
        sync()
        asked = len(discogs.requests)
        sync()
        assert len(discogs.requests) == asked


class TestRequests:
    def test_a_new_item_needs_its_release_and_master(self, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999), released="x")
        sync()
        assert sorted(discogs.requests) == [("master", 5), ("release", 1100)]

    def test_a_new_item_with_no_master_needs_only_its_release(self, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], released="x")
        sync()
        assert discogs.requests == [("release", 1100)]

    def test_items_with_the_same_master_ask_for_it_once(self, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999))
        discogs.add(101, "B", 2001, [PRINCE], master=(5, 1999))
        sync()
        assert [r for r in discogs.requests if r[0] == "master"] == [("master", 5)]

    def test_a_master_a_local_item_already_has_is_not_asked_for(
        self, db, discogs, folder, make
    ):
        make.item("Other pressing", instance_id=1, master_id=5, master_year=1999)
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999))
        discogs.add(1, "Other pressing", 2000, [PRINCE], master=(5, 1999))
        sync()
        assert [r for r in discogs.requests if r[0] == "master"] == []
        assert items(db).filter_by(instance_id=100).one().master_year == 1999

    def test_an_item_that_is_already_in_vc_needs_nothing(self, discogs, folder, make):
        make.item("A", instance_id=100, release_id=1100, master_id=5, master_year=1999)
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999))
        sync()
        assert discogs.requests == []

    def test_backoff_is_on_and_the_listing_is_read_in_big_pages(self, discogs, folder):
        sync()
        (client,) = discogs.clients
        assert client["user_token"] == "test-discogs-token"
        assert discogs.last_client.backoff_enabled is True
        assert discogs.last_listing.per_page == 100


class TestDryRun:
    def test_changes_nothing_and_says_what_it_would_do(self, db, discogs, folder, make):
        rock = make.category("Rock")
        make.item("Changed", instance_id=100, year=1990, categories=[rock])
        make.item("Gone", instance_id=101)
        discogs.add_folder(7, "New folder")
        discogs.add(100, "Changed", 1991, [BEATLES], genres=["Rock"])
        discogs.add(102, "New", 2000, [PRINCE], folder_id=7, notes=[(1, "Mint")])
        summary = sync(dry_run=True)
        assert summary.folders_added == ["New folder"]
        assert summary.added == ["New"]
        assert [t for t, _ in summary.updated] == ["Changed"]
        assert summary.removed == ["Gone"]
        assert summary.dry_run is True
        db.session.expire_all()
        assert names(items(db)) == ["Changed", "Gone"]
        assert items(db).filter_by(instance_id=100).one().year == 1990
        for model in (
            models.Artist,
            models.Genre,
            models.MediaCondition,
        ):
            assert db.session.query(model).count() == 0
        assert names(db.session.query(models.Folder)) == ["Alphabetical"]

    def test_makes_no_extra_requests(self, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], master=(5, 1999), released="x")
        sync(dry_run=True)
        assert discogs.requests == []

    def test_a_real_sync_after_it_does_everything(self, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        sync(dry_run=True)
        sync()
        assert names(items(db)) == ["A"]


class TestSummary:
    def test_counts(self, discogs, folder, make):
        make.item("Changed", instance_id=100, year=1990)
        make.item(
            "Same", instance_id=101, release_id=1101, master_id=None, folder=folder
        )
        make.item("Gone", instance_id=102)
        discogs.add(100, "Changed", 1991, [PRINCE])
        discogs.add(101, "Same", 2000, [])
        discogs.add(103, "New", 2000, [PRINCE])
        summary = sync()
        assert summary.items_total == 3
        assert summary.unchanged == 1
        assert len(summary.added) == 1
        assert len(summary.updated) == 1
        assert len(summary.removed) == 1
        assert summary.artists_added == 1
        text = "\n".join(summary.lines())
        assert "1 added, 1 updated, 1 removed" in text

    def test_the_log_ends_with_the_summary(self, discogs, folder, caplog):
        discogs.add(100, "A", 2000, [PRINCE])
        with caplog.at_level("INFO", logger="vc.sync"):
            sync()
        tail = [r.message for r in caplog.records][-5:]
        assert tail[0] == "Sync finished. Did:"
        assert tail[2].startswith("  items: 1 added, 0 updated, 0 removed")
        assert tail[-1].startswith("  extra Discogs requests")


class TestLock:
    def test_a_second_sync_while_one_runs_is_refused(self, app, discogs, folder):
        with discogs_sync.sync_lock(app):
            with pytest.raises(discogs_sync.SyncAlreadyRunning):
                sync()


class TestCommand:
    def run(self, app, *args):
        return app.test_cli_runner().invoke(args=["sync-discogs", *args])

    def test_syncs(self, app, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        result = self.run(app)
        assert result.exit_code == 0, result.output
        assert names(items(db)) == ["A"]

    def test_dry_run_saves_nothing(self, app, db, discogs, folder, make):
        make.item("Gone", instance_id=100)
        discogs.add(101, "New", 2000, [PRINCE])
        result = self.run(app, "--dry-run")
        assert result.exit_code == 0, result.output
        db.session.expire_all()
        assert names(items(db)) == ["Gone"]

    def test_fails_while_another_sync_runs(self, app, discogs, folder):
        with discogs_sync.sync_lock(app):
            result = self.run(app)
        assert result.exit_code == 1
        assert "already running" in result.output

    def test_fails_when_discogs_does(self, app, discogs, folder):
        class Broken(list):
            per_page = 50

            def __iter__(self):
                raise RuntimeError("Discogs is down")

        discogs.releases = Broken()
        result = self.run(app)
        assert result.exit_code == 1
