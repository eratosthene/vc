import pytest
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError

from app import models


class TestStringForms:
    def test_artist_shows_its_name_without_a_sort_name(self):
        a = models.Artist(name="The Beatles")
        assert str(a.__unicode__()) == "The Beatles"
        assert repr(a) == "The Beatles"

    @pytest.mark.parametrize("sort_name", [None, ""])
    def test_artist_with_an_empty_sort_name_shows_its_name(self, sort_name):
        a = models.Artist(name="Prince", sort_name=sort_name)
        assert a.__unicode__() == "Prince"

    def test_artist_shows_its_sort_name_when_it_has_one(self):
        a = models.Artist(name="The Beatles", sort_name="Beatles, The")
        assert a.__unicode__() == "Beatles, The"
        assert repr(a) == "Beatles, The"

    @pytest.mark.parametrize(
        "model, field",
        [
            (models.MediaCondition, "label"),
            (models.SleeveCondition, "label"),
            (models.Genre, "name"),
            (models.Style, "name"),
            (models.Category, "name"),
            (models.Folder, "name"),
        ],
    )
    def test_simple_models_show_their_label_or_name(self, model, field):
        row = model(**{field: "Thing"})
        assert row.__unicode__() == "Thing"
        assert repr(row) == "Thing"

    def test_collection_item_shows_its_title(self):
        item = models.CollectionItem(title="Abbey Road")
        assert item.__unicode__() == "Abbey Road"
        assert repr(item) == "Abbey Road"

    @pytest.mark.parametrize(
        "fields, expected",
        [
            ({"name": "Vinyl"}, "Vinyl"),
            ({"name": "Vinyl", "qty": 2}, "2x Vinyl"),
            ({"name": "Vinyl", "qty": 0}, "Vinyl"),
            ({"name": "Vinyl", "descriptions": []}, "Vinyl"),
            ({"name": "Vinyl", "descriptions": ["LP", "Mono"]}, "Vinyl {LP Mono}"),
            ({"name": "Vinyl", "text": "Red"}, "Vinyl (Red)"),
            (
                {"name": "Vinyl", "qty": 2, "descriptions": ["LP"], "text": "Red"},
                "2x Vinyl {LP} (Red)",
            ),
        ],
    )
    def test_format_string_form(self, fields, expected):
        f = models.CollectionItemFormat(**fields)
        assert f.__unicode__() == expected
        assert repr(f) == expected


class TestLinks:
    def test_release_show_links_to_discogs(self):
        item = models.CollectionItem(release_id=123)
        link = item.release_show()
        assert isinstance(link, Markup)
        assert link == '<a href="https://www.discogs.com/release/123">123</a>'

    def test_master_show_links_to_discogs(self):
        item = models.CollectionItem(master_id=45)
        link = item.master_show()
        assert isinstance(link, Markup)
        assert link == '<a href="https://www.discogs.com/master/45">45</a>'

    def test_master_show_is_empty_without_a_master(self):
        assert models.CollectionItem(master_id=None).master_show() == ""


class TestUniqueness:
    @pytest.mark.parametrize(
        "model, first, second",
        [
            (models.MediaCondition, {"label": "Mint"}, {"label": "Mint"}),
            (models.SleeveCondition, {"label": "Mint"}, {"label": "Mint"}),
            (models.Genre, {"name": "Rock"}, {"name": "Rock"}),
            (models.Style, {"name": "Pop Rock"}, {"name": "Pop Rock"}),
            (models.Category, {"name": "Jazz"}, {"name": "Jazz"}),
            (
                models.Artist,
                {"discogs_id": 1, "name": "A"},
                {"discogs_id": 1, "name": "B"},
            ),
            (
                models.Folder,
                {"discogs_id": 1, "name": "A"},
                {"discogs_id": 1, "name": "B"},
            ),
            (
                models.CollectionItem,
                {"instance_id": 1, "release_id": 1, "title": "A"},
                {"instance_id": 1, "release_id": 2, "title": "B"},
            ),
        ],
    )
    def test_duplicates_are_refused(self, db, model, first, second):
        db.session.add(model(**first))
        db.session.commit()
        db.session.add(model(**second))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_artist_names_need_not_be_unique(self, make):
        make.artist("Same")
        make.artist("Same")

    def test_item_release_ids_need_not_be_unique(self, make):
        make.item("One", release_id=5)
        make.item("Two", release_id=5)


class TestRequiredFields:
    @pytest.mark.parametrize(
        "model, fields",
        [
            (models.Artist, {"discogs_id": 1}),
            (models.Artist, {"name": "A"}),
            (models.Folder, {"discogs_id": 1}),
            (models.Genre, {}),
            (models.CollectionItem, {"instance_id": 1, "release_id": 1}),
            (models.CollectionItem, {"release_id": 1, "title": "A"}),
        ],
    )
    def test_missing_required_field_is_refused(self, db, model, fields):
        db.session.add(model(**fields))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class TestDefaults:
    def test_artist_is_not_ignored_by_default(self, make):
        assert make.artist().ignore is False

    def test_folder_counts_as_an_lp_by_default(self, make):
        assert make.folder().counts_as_lp is True


class TestItemRelations:
    def test_artists_of_an_item(self, db, make):
        a, b = make.artist("A"), make.artist("B")
        item = make.item(artists=[a, b])
        db.session.expire_all()
        assert {x.name for x in item.artists} == {"A", "B"}

    def test_formats_come_back_in_the_order_they_were_added(self, db, make):
        item = make.item()
        item.formats = [
            models.CollectionItemFormat(name="Vinyl", qty=1),
            models.CollectionItemFormat(name="Box Set", qty=1),
            models.CollectionItemFormat(name="Cassette", qty=1),
        ]
        db.session.commit()
        db.session.expire_all()
        assert [f.name for f in item.formats] == ["Vinyl", "Box Set", "Cassette"]

    def test_format_descriptions_round_trip_as_a_list(self, db, make):
        item = make.item()
        item.formats = [
            models.CollectionItemFormat(name="Vinyl", descriptions=["LP", "Mono"])
        ]
        db.session.commit()
        db.session.expire_all()
        assert item.formats[0].descriptions == ["LP", "Mono"]

    def test_deleting_an_item_deletes_its_formats(self, db, make):
        item = make.item()
        item.formats = [models.CollectionItemFormat(name="Vinyl")]
        db.session.commit()
        db.session.delete(item)
        db.session.commit()
        assert db.session.query(models.CollectionItemFormat).count() == 0

    def test_deleting_an_item_keeps_its_artists_and_categories(self, db, make):
        a, c = make.artist(), make.category()
        item = make.item(artists=[a], categories=[c])
        db.session.delete(item)
        db.session.commit()
        assert db.session.query(models.Artist).count() == 1
        assert db.session.query(models.Category).count() == 1

    def test_filed_under_is_an_artist_apart_from_its_artists(self, db, make):
        a, b = make.artist("A"), make.artist("B")
        item = make.item(artists=[a], filed_under=b)
        db.session.expire_all()
        assert item.filed_under.name == "B"
        assert [x.name for x in item.artists] == ["A"]
