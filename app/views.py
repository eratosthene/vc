from flask import (
    abort,
    g,
    get_flashed_messages,
    make_response,
    render_template,
    request,
    session,
)
from wtforms import BooleanField
from flask_appbuilder import ModelView, CompactCRUDMixin, expose
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.security.decorators import has_access, permission_name
from app import app, appbuilder
from app.models import CollectionItem, Artist, Genre, Style, Category, Folder
from app.widgets import (
    CategorizeFormWidget,
    CategorizeListWidget,
    CategorizeRowWidget,
    CollectionModelListWidget,
)
from app.printview import PrintView


class CollectionItemModelView(CompactCRUDMixin, ModelView):
    """Categorize. Its edit button opens a modal (static/categorize.js), which
    uses the two endpoints below. The stock edit page still works behind it,
    for a browser without JavaScript or a request that fails."""

    datamodel = SQLAInterface(CollectionItem)
    list_widget = CategorizeListWidget
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

    def _get_edit_widget(self, form, exclude_cols=None, widgets=None):
        widgets = super()._get_edit_widget(form, exclude_cols, widgets)
        if g.get("categorize_modal"):
            widgets["edit"] = CategorizeFormWidget(
                form=form,
                include_cols=self.edit_columns,
                exclude_cols=exclude_cols or [],
            )
        return widgets

    def _render_row(self, pk):
        """The item's table row, as the list would draw it."""
        item = self.datamodel.get(pk, self._base_filters)
        if not item:
            abort(404)
        pk = self.datamodel.get_pk_value(item)
        return CategorizeRowWidget(
            item=next(iter(self.datamodel.get_values([item], self.list_columns))),
            pk=pk,
            label_columns=self.label_columns,
            include_columns=self.list_columns,
            formatters_columns=self.formatters_columns,
            actions=self.actions,
            filters=self._filters,
            modelview_name=self.__class__.__name__,
        )()

    # These borrow the stock edit and list permissions, so a role needs no new
    # one and can't have the modal without the edit page.
    @expose("/editmodal/<pk>", methods=["GET", "POST"])
    @has_access
    @permission_name("edit")
    def editmodal(self, pk):
        """GET: the edit form. POST: save it. A saved item answers with its new
        row. A form with errors answers 422 with the form, errors shown. Any
        other failure is a plain error, and the script opens the edit page."""
        pk = self._deserialize_pk_if_composite(pk)
        g.categorize_modal = True
        # The stock edit pushes its URL onto the "back" history. This one isn't
        # a page, so put the history back or the edit page's redirect and Back
        # would land on this fragment.
        history = session.get("page_history")
        history = None if history is None else list(history)
        widgets = self._edit(pk)
        if history is None:
            session.pop("page_history", None)
        else:
            session["page_history"] = history
        # The stock edit flashes its result for the next page. There is no next
        # page here, so take the messages or they would show on a later one.
        messages = get_flashed_messages(with_categories=True)
        if widgets is None:
            if any(category == "danger" for category, _ in messages):
                abort(500)
            return self._render_row(pk)
        response = make_response(widgets["edit"](form_action=request.path))
        if request.method == "POST":
            response.status_code = 422
        return response

    @expose("/row/<pk>")
    @has_access
    @permission_name("list")
    def row(self, pk):
        """The item's table row."""
        return self._render_row(self._deserialize_pk_if_composite(pk))


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
        "print_subtitle",
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
        "print_subtitle",
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
        "print_subtitle",
        "released",
    ]
    label_columns = {
        "release_show": "Release Id",
        "master_show": "Master Id",
        "print_subtitle": "Print Subtitle",
    }
    description_columns = {
        "print_subtitle": "Shown after the title in the Print View, to tell "
        "releases with the same title apart. The sync never changes it."
    }


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


@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
    ), 404
