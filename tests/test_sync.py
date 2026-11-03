"""The Discogs sync (/syncdiscogs) and Sync Notes (/syncdiscogsnotes), against
the fake Discogs client."""

import pytest

from app import models

BEATLES = (10, "The Beatles")
STONES = (11, "The Rolling Stones")
PRINCE = (12, "Prince")


@pytest.fixture
def folder(make):
    """The folder the fake client puts items in by default (Discogs id 1)."""
    return make.folder("Alphabetical", discogs_id=1)


def sync(admin):
    return admin.get("/syncdiscogs")


def sync_notes(admin):
    return admin.get("/syncdiscogsnotes")


def items(db):
    return db.session.query(models.CollectionItem).order_by(models.CollectionItem.id)


def names(rows):
    return sorted(str(r) for r in rows)


class TestRedirect:
    def test_goes_to_the_collection_list(self, admin, discogs, folder):
        r = sync(admin)
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/collectionmodelview/list/")

    def test_goes_back_to_the_referrer(self, admin, discogs, folder):
        r = admin.get("/syncdiscogs", headers={"Referer": "http://localhost/back/"})
        assert r.headers["Location"] == "http://localhost/back/"

    def test_notes_goes_to_the_collection_list(self, admin, discogs, folder):
        r = sync_notes(admin)
        assert r.headers["Location"].endswith("/collectionmodelview/list/")

    def test_notes_goes_back_to_the_referrer(self, admin, discogs, folder):
        r = admin.get(
            "/syncdiscogsnotes", headers={"Referer": "http://localhost/back/"}
        )
        assert r.headers["Location"] == "http://localhost/back/"

    def test_uses_the_token_and_user_agent_from_the_config(
        self, admin, discogs, folder
    ):
        sync(admin)
        assert discogs.clients == [
            {"user_agent": "vc-tests/1.0", "user_token": "test-discogs-token"}
        ]


class TestNewItem:
    def test_adds_the_item_with_what_discogs_has(self, admin, db, discogs, folder):
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
        sync(admin)
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

    def test_format_without_qty_text_or_descriptions(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], formats=[{"name": "Cassette"}])
        sync(admin)
        (fmt,) = items(db).one().formats
        assert (fmt.name, fmt.qty, fmt.text, fmt.descriptions) == (
            "Cassette",
            None,
            None,
            [],
        )

    def test_formats_keep_their_order(self, admin, db, discogs, folder):
        discogs.add(
            100,
            "A",
            2000,
            [PRINCE],
            formats=[{"name": "Vinyl"}, {"name": "Box Set"}, {"name": "CD"}],
        )
        sync(admin)
        assert [f.name for f in items(db).one().formats] == ["Vinyl", "Box Set", "CD"]

    def test_adds_every_item_in_the_collection(self, admin, db, discogs, folder):
        discogs.add(100, "One", 2000, [PRINCE])
        discogs.add(101, "Two", 2001, [PRINCE])
        sync(admin)
        assert names(items(db)) == ["One", "Two"]

    def test_with_two_artists(self, admin, db, discogs, folder):
        discogs.add(100, "Split", 2000, [BEATLES, PRINCE])
        sync(admin)
        assert names(items(db).one().artists) == ["Beatles, The", "Prince"]

    def test_release_with_no_master_has_no_master_id(self, admin, db, discogs, folder):
        discogs.add(100, "A", 1995, [PRINCE])
        sync(admin)
        item = items(db).one()
        assert item.master_id is None
        # With no master, the master year is the release's own year.
        assert item.master_year == 1995

    def test_item_in_a_second_folder(self, admin, db, discogs, folder, make):
        other = make.folder("45s", discogs_id=2)
        discogs.add(100, "A", 1995, [PRINCE], folder_id=2)
        sync(admin)
        assert items(db).one().folder == other

    def test_empty_collection_adds_nothing(self, admin, db, discogs, folder):
        sync(admin)
        assert items(db).count() == 0


class TestNewArtistsGenresStyles:
    def test_new_artists_are_added(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        (artist,) = db.session.query(models.Artist).all()
        assert (artist.discogs_id, artist.name, artist.ignore) == (12, "Prince", False)

    def test_known_artist_is_reused(self, admin, db, discogs, folder, make):
        known = make.artist("Prince", discogs_id=12)
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        assert db.session.query(models.Artist).count() == 1
        assert items(db).one().artists == [known]

    def test_an_artist_on_two_items_is_added_once(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        discogs.add(101, "B", 2001, [PRINCE])
        sync(admin)
        assert db.session.query(models.Artist).count() == 1

    def test_new_genres_and_styles_are_added_once(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], genres=["Rock", "Pop"], styles=["Funk"])
        discogs.add(101, "B", 2001, [PRINCE], genres=["Rock"], styles=["Funk", "Soul"])
        sync(admin)
        assert names(db.session.query(models.Genre)) == ["Pop", "Rock"]
        assert names(db.session.query(models.Style)) == ["Funk", "Soul"]

    def test_known_genre_is_reused(self, admin, db, discogs, folder, make):
        genre = models.Genre(name="Rock")
        db.session.add(genre)
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE], genres=["Rock"])
        sync(admin)
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
    def test_new_artist_gets_its_sort_name(
        self, admin, db, discogs, folder, name, sort_name
    ):
        discogs.add(100, "A", 2000, [(50, name)])
        sync(admin)
        assert db.session.query(models.Artist).one().sort_name == sort_name

    def test_only_the_leading_the_moves(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [(50, "The Band of The Hand")])
        sync(admin)
        assert db.session.query(models.Artist).one().sort_name == (
            "Band of The Hand, The"
        )

    def test_a_sort_name_set_by_hand_survives_the_sync(
        self, admin, db, discogs, folder, make
    ):
        make.artist("The Beatles", discogs_id=10, sort_name="Fab Four")
        discogs.add(100, "A", 2000, [BEATLES])
        sync(admin)
        assert db.session.query(models.Artist).one().sort_name == "Fab Four"

    def test_a_sort_name_set_by_hand_survives_sync_notes(
        self, admin, db, discogs, folder, make
    ):
        a = make.artist("The Beatles", discogs_id=10, sort_name="Fab Four")
        make.item("A", artists=[a], instance_id=100)
        discogs.add(100, "A", 2000, [BEATLES])
        sync_notes(admin)
        assert db.session.query(models.Artist).one().sort_name == "Fab Four"

    def test_an_ignored_artist_stays_ignored(self, admin, db, discogs, folder, make):
        make.artist("Prince", discogs_id=12, ignore=True)
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        assert db.session.query(models.Artist).one().ignore is True


class TestNotes:
    def test_each_notes_field(self, admin, db, discogs, folder):
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
        sync(admin)
        item = items(db).one()
        assert item.media_condition.label == "Near Mint (NM or M-)"
        assert item.sleeve_condition.label == "Very Good Plus (VG+)"
        assert item.item_notes == "Signed"
        assert item.listened is True
        assert item.includes == "Poster"

    def test_no_notes_leaves_everything_empty(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        item = items(db).one()
        assert item.media_condition is None
        assert item.sleeve_condition is None
        assert item.item_notes is None
        assert item.listened is None
        assert item.includes is None

    @pytest.mark.parametrize(
        "value, listened", [("Yes", True), ("No", False), ("", False)]
    )
    def test_listened(self, admin, db, discogs, folder, value, listened):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(4, value)])
        sync(admin)
        assert items(db).one().listened is listened

    def test_values_lose_trailing_whitespace(self, admin, db, discogs, folder):
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
        sync(admin)
        item = items(db).one()
        assert item.media_condition.label == "Mint"
        assert item.sleeve_condition.label == "Good"
        assert item.item_notes == "Note"
        assert item.listened is True
        assert item.includes == "X"

    def test_unknown_fields_are_ignored(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(9, "Whatever")])
        sync(admin)
        assert items(db).count() == 1

    def test_conditions_are_added_once_and_shared(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE], notes=[(1, "Mint"), (2, "Good")])
        discogs.add(101, "B", 2001, [PRINCE], notes=[(1, "Mint"), (2, "Fair")])
        sync(admin)
        assert names(db.session.query(models.MediaCondition)) == ["Mint"]
        assert names(db.session.query(models.SleeveCondition)) == ["Fair", "Good"]

    def test_known_condition_is_reused(self, admin, db, discogs, folder):
        mc = models.MediaCondition(label="Mint")
        db.session.add(mc)
        db.session.commit()
        discogs.add(100, "A", 2000, [PRINCE], notes=[(1, "Mint")])
        sync(admin)
        assert db.session.query(models.MediaCondition).count() == 1
        assert items(db).one().media_condition == mc


class TestExistingItem:
    def test_is_not_added_again(self, admin, db, discogs, folder, make):
        make.item("A", instance_id=100)
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        assert items(db).count() == 1

    def test_keeps_the_categories_set_by_hand(self, admin, db, discogs, folder, make):
        rock = make.category("Rock")
        make.item("A", instance_id=100, categories=[rock])
        discogs.add(100, "A", 2000, [PRINCE])
        sync(admin)
        assert items(db).one().categories == [rock]

    def test_skips_what_changed_on_discogs_bug_11(
        self, admin, db, discogs, folder, make
    ):
        # #11: an item that's already in vc is skipped, so a corrected title or
        # year on Discogs never comes across. When #11 lands this flips.
        make.item("Old title", instance_id=100, year=1990)
        discogs.add(100, "New title", 1991, [PRINCE])
        sync(admin)
        item = items(db).one()
        assert (item.title, item.year) == ("Old title", 1990)

    def test_skips_a_moved_folder_bug_11(self, admin, db, discogs, folder, make):
        old = make.folder("Old", discogs_id=2)
        make.item("A", instance_id=100, folder=old)
        discogs.add(100, "A", 2000, [PRINCE], folder_id=1)
        sync(admin)
        assert items(db).one().folder == old

    def test_second_sync_changes_nothing(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [BEATLES], genres=["Rock"], notes=[(1, "Mint")])
        sync(admin)
        sync(admin)
        assert items(db).count() == 1
        assert db.session.query(models.Artist).count() == 1


class TestRemovedItem:
    def test_item_no_longer_on_discogs_is_deleted(
        self, admin, db, discogs, folder, make
    ):
        make.item("Gone", instance_id=100)
        make.item("Kept", instance_id=101)
        discogs.add(101, "Kept", 2000, [PRINCE])
        sync(admin)
        assert names(items(db)) == ["Kept"]

    def test_everything_is_removed_from_an_empty_account(
        self, admin, db, discogs, folder, make
    ):
        make.item("Gone", instance_id=100)
        sync(admin)
        assert items(db).count() == 0

    def test_removing_keeps_artists_and_categories(
        self, admin, db, discogs, folder, make
    ):
        a, c = make.artist(), make.category()
        make.item("Gone", instance_id=100, artists=[a], categories=[c])
        sync(admin)
        assert db.session.query(models.Artist).count() == 1
        assert db.session.query(models.Category).count() == 1

    def test_adds_and_removes_in_one_sync(self, admin, db, discogs, folder, make):
        make.item("Gone", instance_id=100)
        discogs.add(101, "New", 2000, [PRINCE])
        sync(admin)
        assert names(items(db)) == ["New"]


class TestMissingFolderBug11:
    def test_a_folder_vc_does_not_have_stops_the_sync(self, admin, db, discogs, folder):
        # #11: folders have to be added by hand first; nothing reads them from
        # Discogs. The sync fails partway, so the items after it aren't added.
        discogs.add(100, "Fine", 2000, [PRINCE], folder_id=1)
        discogs.add(101, "No folder", 2000, [PRINCE], folder_id=99)
        discogs.add(102, "After", 2000, [PRINCE], folder_id=1)
        r = sync(admin)
        assert r.status_code == 500
        assert names(items(db)) == ["Fine"]


class TestSyncNotes:
    def test_copies_the_notes_to_an_item(self, admin, db, discogs, folder, make):
        make.item("A", instance_id=100)
        discogs.add(
            100,
            "A",
            2000,
            [PRINCE],
            notes=[(1, "Mint"), (2, "Good"), (3, "Signed"), (4, "Yes"), (5, "Poster")],
        )
        sync_notes(admin)
        item = items(db).one()
        assert item.media_condition.label == "Mint"
        assert item.sleeve_condition.label == "Good"
        assert item.item_notes == "Signed"
        assert item.listened is True
        assert item.includes == "Poster"

    def test_listened_no(self, admin, db, discogs, folder, make):
        make.item("A", instance_id=100, listened=True)
        discogs.add(100, "A", 2000, [PRINCE], notes=[(4, "No")])
        sync_notes(admin)
        assert items(db).one().listened is False

    def test_adds_new_conditions_once(self, admin, db, discogs, folder, make):
        make.item("A", instance_id=100)
        make.item("B", instance_id=101)
        discogs.add(100, "A", 2000, [PRINCE], notes=[(1, "Mint"), (2, "Good")])
        discogs.add(101, "B", 2000, [PRINCE], notes=[(1, "Mint"), (2, "Good")])
        sync_notes(admin)
        assert db.session.query(models.MediaCondition).count() == 1
        assert db.session.query(models.SleeveCondition).count() == 1

    def test_clears_notes_removed_on_discogs(self, admin, db, discogs, folder, make):
        mc = models.MediaCondition(label="Mint")
        db.session.add(mc)
        make.item("A", instance_id=100, media_condition=mc, item_notes="Old")
        discogs.add(100, "A", 2000, [PRINCE])
        sync_notes(admin)
        item = items(db).one()
        assert item.media_condition is None
        assert item.item_notes is None

    def test_changes_only_the_notes(self, admin, db, discogs, folder, make):
        rock = make.category("Rock")
        make.item("Old", instance_id=100, categories=[rock])
        discogs.add(100, "New", 2001, [PRINCE], notes=[(3, "Note")])
        sync_notes(admin)
        item = items(db).one()
        assert (item.title, item.item_notes, item.categories) == ("Old", "Note", [rock])

    def test_does_not_remove_items(self, admin, db, discogs, folder, make):
        make.item("Local only", instance_id=100)
        sync_notes(admin)
        assert items(db).count() == 1

    def test_item_vc_does_not_have_stops_it_bug_11(
        self, admin, db, discogs, folder, make
    ):
        # #11: the item isn't in vc yet, and the lookup finds no row, so Sync
        # Notes fails there and the items after it aren't updated.
        make.item("After", instance_id=102)
        discogs.add(101, "New on Discogs", 2000, [PRINCE], notes=[(3, "x")])
        discogs.add(102, "After", 2000, [PRINCE], notes=[(3, "y")])
        r = sync_notes(admin)
        assert r.status_code == 500
        assert items(db).one().item_notes is None


class TestWhoCanSync:
    def test_anyone_can_start_a_sync_bug_11(self, client, db, discogs, folder, make):
        # #11: the routes have no @has_access, and they're plain GET links, so
        # someone who isn't signed in can start a sync that deletes items.
        make.item("Gone", instance_id=100)
        r = client.get("/syncdiscogs")
        assert r.status_code == 302
        assert items(db).count() == 0

    def test_anyone_can_start_sync_notes_bug_11(
        self, client, db, discogs, folder, make
    ):
        make.item("A", instance_id=100)
        discogs.add(100, "A", 2000, [PRINCE], notes=[(3, "Note")])
        client.get("/syncdiscogsnotes")
        assert items(db).one().item_notes == "Note"

    @pytest.mark.xfail(strict=True, reason="#11: sync needs a signed-in user")
    def test_someone_not_signed_in_cannot_start_a_sync(
        self, client, db, discogs, folder, make
    ):
        make.item("Kept", instance_id=100)
        client.get("/syncdiscogs")
        assert items(db).count() == 1
