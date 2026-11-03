from flask import render_template
from wtforms import BooleanField
from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from app import appbuilder
from app.models import CollectionItem, Artist, Genre, Style, Category, Folder
from app.widgets import CollectionModelListWidget
from app.printview import PrintView


class CollectionItemModelView(CompactCRUDMixin, ModelView):
    datamodel = SQLAInterface(CollectionItem)
    list_columns = [
        "artists",
        "title",
        "master_year",
        "categories",
        "genres",
        "styles",
        "folder",
        "filed_under",
    ]
    edit_columns = ["categories"]


class CollectionModelView(ModelView):
    datamodel = SQLAInterface(CollectionItem)
    list_widget = CollectionModelListWidget
    list_columns = [
        "artists",
        "title",
        "master_year",
        "categories",
        "genres",
        "styles",
        "folder",
        "filed_under",
    ]
    edit_columns = [
        "artists",
        "title",
        "year",
        "master_id",
        "master_year",
        "categories",
        "genres",
        "styles",
        "media_condition",
        "sleeve_condition",
        "item_notes",
        "listened",
        "includes",
        "folder",
        "filed_under",
    ]
    add_columns = [
        "artists",
        "title",
        "year",
        "master_id",
        "master_year",
        "categories",
        "genres",
        "styles",
        "media_condition",
        "sleeve_condition",
        "item_notes",
        "listened",
        "includes",
        "folder",
        "filed_under",
    ]
    show_columns = [
        "instance_id",
        "release_show",
        "title",
        "year",
        "artists",
        "genres",
        "styles",
        "master_show",
        "master_year",
        "categories",
        "folder",
        "filed_under",
        "formats",
        "media_condition",
        "sleeve_condition",
        "item_notes",
        "listened",
        "includes",
        "released",
    ]
    label_columns = {"release_show": "Release Id", "master_show": "Master Id"}


class CategoryModelView(ModelView):
    datamodel = SQLAInterface(Category)
    base_order = ("name", "desc")
    related_views = [CollectionModelView]


class ArtistModelView(ModelView):
    datamodel = SQLAInterface(Artist)
    list_columns = ["name", "sort_name", "discogs_id", "ignore"]
    # These columns aren't nullable, which would make Flask-AppBuilder's
    # checkbox required, so it could never be unchecked.
    add_form_extra_fields = {"ignore": BooleanField("Ignore")}
    edit_form_extra_fields = {"ignore": BooleanField("Ignore")}
    related_views = [CollectionModelView]


class GenreModelView(ModelView):
    datamodel = SQLAInterface(Genre)
    base_order = ("name", "desc")
    related_views = [CollectionModelView]


class StyleModelView(ModelView):
    datamodel = SQLAInterface(Style)
    base_order = ("name", "desc")
    related_views = [CollectionModelView]


class FolderModelView(ModelView):
    datamodel = SQLAInterface(Folder)
    list_columns = ["name", "discogs_id", "counts_as_lp"]
    label_columns = {"counts_as_lp": "Counts As LP"}
    # As for the artists' Ignore: a required checkbox couldn't be unchecked.
    add_form_extra_fields = {"counts_as_lp": BooleanField("Counts As LP", default=True)}
    edit_form_extra_fields = {"counts_as_lp": BooleanField("Counts As LP")}
    base_order = ("name", "desc")
    related_views = [CollectionModelView]


appbuilder.add_view(CollectionItemModelView, "Categorize")
appbuilder.add_view(CollectionModelView, "Collection", category="Manage")
appbuilder.add_view(ArtistModelView, "Artists", category="Manage")
appbuilder.add_view(GenreModelView, "Genres", category="Manage")
appbuilder.add_view(StyleModelView, "Styles", category="Manage")
appbuilder.add_view(FolderModelView, "Folders", category="Manage")
appbuilder.add_view(CategoryModelView, "Categories", category="Manage")

appbuilder.add_view(PrintView, "Print View")


"""
    Application wide 404 error handler
"""


@appbuilder.app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
    ), 404
