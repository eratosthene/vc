"""The Flask-AppBuilder views: every list, show, add and edit page for a
signed-in admin, and what editing saves."""

import pytest
from bs4 import BeautifulSoup

from app import models, widgets
from app.views import (
    ArtistModelView,
    CategoryModelView,
    CollectionItemModelView,
    CollectionModelView,
    FolderModelView,
    GenreModelView,
    StyleModelView,
)


@pytest.fixture
def data(db, make):
    """One of everything, linked together."""
    d = type("Data", (), {})()
    d.folder = make.folder("Alphabetical")
    d.artist = make.artist("The Beatles", sort_name="Beatles, The")
    d.category = make.category("Rock")
    d.genre = models.Genre(name="Pop")
    d.style = models.Style(name="Beat")
    d.mc = models.MediaCondition(label="Mint")
    d.sc = models.SleeveCondition(label="Good")
    db.session.add_all([d.genre, d.style, d.mc, d.sc])
    d.item = make.item(
        "Abbey Road",
        artists=[d.artist],
        categories=[d.category],
        folder=d.folder,
        filed_under=d.artist,
        master_year=1969,
        released="1969-09-26",
        media_condition=d.mc,
        sleeve_condition=d.sc,
        item_notes="Signed",
        listened=True,
        includes="Poster",
    )
    d.item.genres = [d.genre]
    d.item.styles = [d.style]
    d.item.formats = [
        models.CollectionItemFormat(name="Vinyl", qty=1, descriptions=["LP"])
    ]
    db.session.commit()
    return d


def get(admin, url):
    r = admin.get(url)
    assert r.status_code == 200, (url, r.status_code)
    return BeautifulSoup(r.data, "lxml")


def body(soup):
    return " ".join(soup.get_text().split())


LISTS = [
    "/collectionitemmodelview/list/",
    "/collectionmodelview/list/",
    "/categorymodelview/list/",
    "/artistmodelview/list/",
    "/genremodelview/list/",
    "/stylemodelview/list/",
    "/foldermodelview/list/",
]


class TestLists:
    @pytest.mark.parametrize("url", LISTS)
    def test_loads_empty(self, admin, url):
        get(admin, url)

    @pytest.mark.parametrize("url", LISTS)
    def test_loads_with_data(self, admin, data, url):
        get(admin, url)

    def test_the_collection_list_shows_the_items(self, admin, data):
        text = body(get(admin, "/collectionmodelview/list/"))
        for expected in ["Abbey Road", "Beatles, The", "Rock", "Pop", "Beat", "1969"]:
            assert expected in text

    def test_the_collection_list_has_the_sync_buttons(self, admin, data):
        soup = get(admin, "/collectionmodelview/list/")
        buttons = {a.get_text(strip=True): a["href"] for a in soup.select("a.btn")}
        assert buttons["Sync"] == "/syncdiscogs"
        assert buttons["Sync Notes"] == "/syncdiscogsnotes"

    def test_the_categorize_list_has_no_sync_buttons(self, admin, data):
        soup = get(admin, "/collectionitemmodelview/list/")
        assert "/syncdiscogs" not in str(soup)

    def test_the_artist_list_shows_sort_names_and_ids(self, admin, data):
        text = body(get(admin, "/artistmodelview/list/"))
        assert "The Beatles" in text
        assert "Beatles, The" in text

    def test_the_folder_list_shows_counts_as_lp(self, admin, data):
        text = body(get(admin, "/foldermodelview/list/"))
        assert "Counts As LP" in text

    def test_the_widget_is_the_collection_list_widget(self):
        assert widgets.CollectionModelListWidget.template == "widgets/cmlw.html"
        assert CollectionModelView.list_widget is widgets.CollectionModelListWidget


class TestShow:
    def test_the_collection_item(self, admin, data):
        text = body(get(admin, f"/collectionmodelview/show/{data.item.id}"))
        for expected in [
            "Abbey Road",
            "Beatles, The",
            "Release Id",
            "Master Id",
            "1969",
            "Rock",
            "Alphabetical",
            "1x Vinyl {LP}",
            "Mint",
            "Good",
            "Signed",
            "Poster",
            "1969-09-26",
        ]:
            assert expected in text, expected

    def test_links_to_the_release_and_master_on_discogs(self, admin, data):
        data.item.master_id = 77
        soup = get(admin, f"/collectionmodelview/show/{data.item.id}")
        hrefs = [a["href"] for a in soup.select("a")]
        assert f"https://www.discogs.com/release/{data.item.release_id}" in hrefs
        assert "https://www.discogs.com/master/77" in hrefs

    def test_an_item_without_a_master(self, admin, make):
        item = make.item("No master", master_id=None)
        get(admin, f"/collectionmodelview/show/{item.id}")

    def test_an_item_with_nothing_else(self, admin, db):
        item = models.CollectionItem(instance_id=1, release_id=1, title="Bare")
        db.session.add(item)
        db.session.commit()
        get(admin, f"/collectionmodelview/show/{item.id}")

    def test_the_categorize_item(self, admin, data):
        get(admin, f"/collectionitemmodelview/show/{data.item.id}")

    @pytest.mark.parametrize(
        "view, thing",
        [
            ("categorymodelview", "category"),
            ("artistmodelview", "artist"),
            ("genremodelview", "genre"),
            ("stylemodelview", "style"),
            ("foldermodelview", "folder"),
        ],
    )
    def test_the_other_models(self, admin, data, view, thing):
        row = getattr(data, thing)
        get(admin, f"/{view}/show/{row.id}")

    def test_an_unknown_item_is_not_found(self, admin):
        assert admin.get("/collectionmodelview/show/999").status_code == 404


class TestEditPages:
    def test_the_collection_item(self, admin, data):
        get(admin, f"/collectionmodelview/edit/{data.item.id}")

    def test_the_categorize_item_has_no_edit_page_of_its_own(self, admin, data):
        # Its edit form is POSTed from the compact list page; a GET goes back
        # to the index.
        r = admin.get(f"/collectionitemmodelview/edit/{data.item.id}")
        assert r.status_code == 302

    @pytest.mark.parametrize(
        "view, thing",
        [
            ("categorymodelview", "category"),
            ("artistmodelview", "artist"),
            ("genremodelview", "genre"),
            ("stylemodelview", "style"),
            ("foldermodelview", "folder"),
        ],
    )
    def test_the_other_models(self, admin, data, view, thing):
        get(admin, f"/{view}/edit/{getattr(data, thing).id}")


class TestAddPages:
    @pytest.mark.parametrize(
        "view",
        [
            "collectionmodelview",
            "categorymodelview",
            "artistmodelview",
            "genremodelview",
            "stylemodelview",
            "foldermodelview",
        ],
    )
    def test_loads(self, admin, data, view):
        get(admin, f"/{view}/add")


class TestEditing:
    def test_categorize_saves_an_items_categories(self, admin, db, data, make):
        jazz = make.category("Jazz")
        r = admin.post(
            f"/collectionitemmodelview/edit/{data.item.id}",
            data={"categories": [data.category.id, jazz.id]},
        )
        assert r.status_code == 302
        db.session.expire_all()
        assert sorted(c.name for c in data.item.categories) == ["Jazz", "Rock"]

    def test_categorize_can_clear_the_categories(self, admin, db, data):
        admin.post(f"/collectionitemmodelview/edit/{data.item.id}", data={})
        db.session.expire_all()
        assert data.item.categories == []

    def test_categorize_changes_nothing_else(self, admin, db, data, make):
        jazz = make.category("Jazz")
        admin.post(
            f"/collectionitemmodelview/edit/{data.item.id}",
            data={"categories": [jazz.id], "title": "Changed"},
        )
        db.session.expire_all()
        assert data.item.title == "Abbey Road"
        assert data.item.filed_under == data.artist

    def test_the_collection_view_saves_filed_under(self, admin, db, data, make):
        other = make.artist("Other")
        r = admin.post(
            f"/collectionmodelview/edit/{data.item.id}",
            data={
                "artists": [data.artist.id],
                "title": "Abbey Road",
                "year": "1969",
                "master_id": "5",
                "master_year": "1969",
                "categories": [data.category.id],
                "genres": [data.genre.id],
                "styles": [data.style.id],
                "folder": data.folder.id,
                "filed_under": other.id,
            },
        )
        assert r.status_code == 302
        db.session.expire_all()
        assert data.item.filed_under == other
        assert data.item.master_id == 5

    def test_the_artist_ignore_box_can_be_set_and_cleared(self, admin, db, data):
        url = f"/artistmodelview/edit/{data.artist.id}"
        fields = {"name": "The Beatles", "discogs_id": data.artist.discogs_id}
        admin.post(url, data={**fields, "ignore": "y", "sort_name": "Beatles, The"})
        db.session.expire_all()
        assert data.artist.ignore is True
        admin.post(url, data={**fields, "sort_name": "Beatles, The"})
        db.session.expire_all()
        assert data.artist.ignore is False

    def test_a_sort_name_is_saved(self, admin, db, data):
        admin.post(
            f"/artistmodelview/edit/{data.artist.id}",
            data={"name": "The Beatles", "discogs_id": 1, "sort_name": "Fab Four"},
        )
        db.session.expire_all()
        assert data.artist.sort_name == "Fab Four"

    def test_the_folder_counts_as_lp_box_can_be_set_and_cleared(self, admin, db, data):
        url = f"/foldermodelview/edit/{data.folder.id}"
        fields = {"name": "Alphabetical", "discogs_id": data.folder.discogs_id}
        admin.post(url, data=fields)
        db.session.expire_all()
        assert data.folder.counts_as_lp is False
        admin.post(url, data={**fields, "counts_as_lp": "y"})
        db.session.expire_all()
        assert data.folder.counts_as_lp is True

    def test_a_new_folder_counts_as_an_lp_by_default(self, admin, db):
        soup = get(admin, "/foldermodelview/add")
        assert soup.select_one("[name=counts_as_lp]").has_attr("checked")

    def test_adding_a_category(self, admin, db):
        r = admin.post("/categorymodelview/add", data={"name": "Jazz"})
        assert r.status_code == 302
        assert [c.name for c in db.session.query(models.Category)] == ["Jazz"]

    def test_deleting_a_category(self, admin, db, data):
        r = admin.get(f"/categorymodelview/delete/{data.category.id}")
        assert r.status_code == 302
        assert db.session.query(models.Category).count() == 0

    def test_a_duplicate_category_is_refused(self, admin, db, data):
        admin.post("/categorymodelview/add", data={"name": "Rock"})
        assert db.session.query(models.Category).count() == 1


class TestRelatedViews:
    def test_each_view_lists_the_items_that_use_it(self, admin, data):
        # related_views show the collection under a category, artist, genre,
        # style or folder.
        for view, thing in [
            ("categorymodelview", data.category),
            ("artistmodelview", data.artist),
            ("genremodelview", data.genre),
            ("stylemodelview", data.style),
            ("foldermodelview", data.folder),
        ]:
            assert "Abbey Road" in body(get(admin, f"/{view}/show/{thing.id}")), view

    def test_the_view_classes_are_wired_to_their_models(self):
        views = {
            CollectionItemModelView: models.CollectionItem,
            CollectionModelView: models.CollectionItem,
            CategoryModelView: models.Category,
            ArtistModelView: models.Artist,
            GenreModelView: models.Genre,
            StyleModelView: models.Style,
            FolderModelView: models.Folder,
        }
        for view, model in views.items():
            assert view.datamodel.obj is model


class TestAccess:
    @pytest.mark.parametrize("url", LISTS)
    def test_a_list_needs_a_sign_in(self, client, url):
        r = client.get(url)
        assert r.status_code == 302
        assert "/login/" in r.headers["Location"]

    def test_the_menu_for_an_admin(self, admin):
        text = body(get(admin, "/"))
        for entry in ["Categorize", "Manage", "Collection", "Artists", "Print View"]:
            assert entry in text, entry


class TestNotFoundPage:
    def test_an_unknown_url_gets_the_404_page(self, admin):
        r = admin.get("/no/such/page")
        assert r.status_code == 404
        assert "Page not found" in r.get_data(as_text=True)

    def test_the_404_page_has_the_menu(self, admin):
        r = admin.get("/no/such/page")
        assert "Print View" in r.get_data(as_text=True)

    def test_the_404_page_needs_no_sign_in(self, client):
        r = client.get("/no/such/page")
        assert r.status_code == 404
        assert "Page not found" in r.get_data(as_text=True)
