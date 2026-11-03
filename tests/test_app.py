"""The app's own setup: what app/__init__.py builds at import time."""

import sys

import app as vc
from app.index import MyIndexView
from app.printview import PrintView


def test_the_app_reads_the_fake_config_not_config_py(app):
    # tests/conftest.py's stand-in, which is not a file.
    assert not hasattr(sys.modules["config"], "__file__")
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert app.config["APP_NAME"] == "vc-test"


def test_the_index_view_is_ours(app):
    assert vc.appbuilder.indexview is MyIndexView


def test_every_view_is_registered(app):
    names = {v.__class__.__name__ for v in vc.appbuilder.baseviews}
    assert {
        "CollectionItemModelView",
        "CollectionModelView",
        "CategoryModelView",
        "ArtistModelView",
        "GenreModelView",
        "StyleModelView",
        "FolderModelView",
        "PrintView",
        "MyIndexView",
    } <= names
    assert any(isinstance(v, PrintView) for v in vc.appbuilder.baseviews)


def test_the_menu(app):
    menu = {
        item.name: [c.name for c in getattr(item, "childs", [])]
        for item in vc.appbuilder.menu.get_list()
    }
    assert "Categorize" in menu
    assert "Print View" in menu
    assert set(menu["Manage"]) >= {
        "Collection",
        "Artists",
        "Genres",
        "Styles",
        "Folders",
        "Categories",
    }


def test_the_routes_of_the_index_view(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert {
        "/",
        "/syncdiscogs",
        "/syncdiscogsnotes",
        "/random_lp",
        "/unlistened_lp",
        "/random_release",
        "/unlistened_release",
        "/random_folder/<int:folder>",
        "/unlistened_folder/<int:folder>",
        "/random_category/<int:category>",
        "/unlistened_category/<int:category>",
        "/random_decade/<string:decade>",
        "/unlistened_decade/<string:decade>",
    } <= rules


def test_the_routes_of_the_print_view(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert {
        "/printview/",
        "/printview/all",
        "/printview/all/",
        "/printview/folder/<int:folder>",
        "/printview/category/<int:category>",
        "/printview/decade/<string:decade>",
    } <= rules


def test_the_models_use_the_one_metadata_with_the_security_tables(db):
    tables = set(db.metadata.tables)
    assert {"collection_item", "ab_user"} <= tables
