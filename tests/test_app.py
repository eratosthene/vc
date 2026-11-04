"""The app's own setup: what app/__init__.py builds at import time."""

import logging
import sys

import pytest

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


class TestLogLevel:
    @pytest.fixture(autouse=True)
    def restore_levels(self):
        root = logging.getLogger()
        sync = logging.getLogger("vc.sync")
        before = root.level, sync.level
        yield
        root.setLevel(before[0])
        sync.setLevel(before[1])

    @pytest.mark.parametrize(
        "setting, level",
        [
            ("DEBUG", logging.DEBUG),
            ("debug", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
        ],
    )
    def test_log_level_sets_the_root_logger(self, app, monkeypatch, setting, level):
        monkeypatch.setitem(app.config, "LOG_LEVEL", setting)
        vc.configure_logging(app)
        assert logging.getLogger().level == level

    def test_it_defaults_to_info(self, app, monkeypatch):
        monkeypatch.delitem(app.config, "LOG_LEVEL", raising=False)
        vc.configure_logging(app)
        assert logging.getLogger().level == logging.INFO

    def test_an_unknown_level_is_refused(self, app, monkeypatch):
        monkeypatch.setitem(app.config, "LOG_LEVEL", "LOUD")
        with pytest.raises(ValueError, match="LOG_LEVEL"):
            vc.configure_logging(app)

    def test_the_sync_log_keeps_info_when_the_rest_is_turned_down(
        self, app, monkeypatch
    ):
        monkeypatch.setitem(app.config, "LOG_LEVEL", "ERROR")
        vc.configure_logging(app)
        assert logging.getLogger("vc.sync").level == logging.INFO

    def test_the_sync_log_follows_debug(self, app, monkeypatch):
        monkeypatch.setitem(app.config, "LOG_LEVEL", "DEBUG")
        vc.configure_logging(app)
        assert logging.getLogger("vc.sync").level == logging.DEBUG


def test_the_404_page_renders(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Page not found" in response.get_data(as_text=True)
