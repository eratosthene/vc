from flask_appbuilder import BaseView
from flask import abort
from flask_appbuilder.views import expose
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.counts import collection_counts
from app.models import CollectionItem, Category, Folder
import re


# The categories and the folder the Print View lays out in their own way, by
# name. Renaming one in the database quietly gives its section the normal layout.
SOUNDTRACKS = "Soundtracks"
SHOWTUNES = "Showtunes"
EDISON = "Edison Diamond Disc"
ALPHABETICAL = "Alphabetical"

# Sorts after every real slot.
NO_SLOT = 1000

# Releases in these categories always say which folder they're filed in.
FOLDER_NOTE_CATEGORIES = ("Christmas", "Halloween", SOUNDTRACKS)

# The names the template compares with, as template variables.
LAYOUT_NAMES = {
    "SOUNDTRACKS": SOUNDTRACKS,
    "SHOWTUNES": SHOWTUNES,
    "EDISON": EDISON,
    "ALPHABETICAL": ALPHABETICAL,
    "FOLDER_NOTE_CATEGORIES": FOLDER_NOTE_CATEGORIES,
}


def get_or_404(model, id):
    row = db.session.get(model, id)
    if row is None:
        abort(404)
    return row


def sortFunc(e):
    return str(e)


def yearSortFunc(e):
    return e["year"]


def yearRSortFunc(e):
    if e.released:
        return str(e.released)
    else:
        return str(e.year)


def releaseSortFunc(e):
    t = e.title.lower()
    if t.startswith("the "):
        return t.removeprefix("the ") + ", the"
    else:
        return t


def slotSortFunc(e):
    """An Edison Diamond Disc's place in the cabinet, from its notes: the top
    drawer's slots, then the bottom drawer's. One whose notes don't say both
    comes last."""
    n = e.item_notes or ""
    s = re.search(r"slot\s+([0-9]+)", n)
    d = re.search(r"(Top|Bottom) drawer", n)
    if s is None or d is None:
        return NO_SLOT
    if d.group(1) == "Top":
        return 100 + int(s.group(1))
    else:
        return 200 + int(s.group(1))


def listed_under(item):
    """The artists an item is listed under: each one that isn't ignored. If
    they all are, one of them anyway (the one it's filed under, else the first
    by sort name) so the item isn't missing from the page."""
    shown = [a for a in item.artists if not a.ignore]
    if shown or not item.artists:
        return shown
    if item.filed_under is not None:
        return [item.filed_under]
    return [min(item.artists, key=lambda a: (sortFunc(a), a.id))]


def order_releases(items):
    """
    One artist's items, in id order, as the page lists them: the releases of
    one master together (by release date), the masters by year, and an item
    with no master standing on its own, by its year.
    """
    groups = []
    by_master = {}
    for item in items:
        if item.master_id is None:
            groups.append([item])
        elif item.master_id in by_master:
            by_master[item.master_id].append(item)
        else:
            by_master[item.master_id] = [item]
            groups.append(by_master[item.master_id])
    groups.sort(key=lambda g: g[0].master_year or 0)
    return [i for g in groups for i in sorted(g, key=yearRSortFunc)]


class PrintView(BaseView):
    default_view = "printview"
    printview_template = "printview.html"
    printview_index_template = "printviewindex.html"

    def crunch(self, folder=None, category=None, decade=None):
        """
        What the page lists, from one query for the items that match the
        filter (with everything the page shows about them loaded alongside):
        the categories, then for each category (by id) its artists, a list of
        its items under each artist (by artist id), and the items of the
        categories that have a layout of their own.
        """
        categories = self.categories_query(category).all()
        by_category = {c.id: [] for c in categories}
        # In id order, as they were before, so the sorts below break ties the
        # same way.
        for item in self.items_query(folder, category, decade):
            for c in item.categories:
                if c.id in by_category:
                    by_category[c.id].append(item)

        artists = {}
        items = {}
        soundtrack_items = []
        showtunes_items = []
        edison_items = []
        for c in categories:
            under = {}
            for item in by_category[c.id]:
                for a in listed_under(item):
                    under.setdefault(a, []).append(item)
            artists[c.id] = sorted(under, key=lambda a: (sortFunc(a), a.id))
            items[c.id] = {a.id: order_releases(under[a]) for a in artists[c.id]}
            if c.name == SOUNDTRACKS:
                soundtrack_items = sorted(by_category[c.id], key=releaseSortFunc)
            if c.name == SHOWTUNES:
                showtunes_items = sorted(by_category[c.id], key=releaseSortFunc)
            if c.name == EDISON:
                edison_items = sorted(by_category[c.id], key=slotSortFunc)
        return (
            categories,
            artists,
            items,
            soundtrack_items,
            showtunes_items,
            edison_items,
        )

    @staticmethod
    def categories_query(category=None):
        query = db.session.query(Category).order_by(Category.name)
        if category:
            query = query.filter(Category.id == category)
        return query

    @staticmethod
    def items_query(folder=None, category=None, decade=None):
        """The items of one version of the page, with the artists, categories,
        folder, filed under artist and formats the page shows. The queries that
        load them don't depend on the number of artists or categories, only
        grow by one for each 500 items (SQLAlchemy's batch size)."""
        filters = []
        if category:
            filters.append(CollectionItem.categories.any(Category.id == category))
        if folder:
            filters.append(CollectionItem.folder_id == folder)
        elif decade:
            after = int(decade[:-1]) - 1
            before = int(decade[:-1]) + 10
            filters.append(CollectionItem.master_year > after)
            filters.append(CollectionItem.master_year < before)
        return (
            db.session.query(CollectionItem)
            .filter(*filters)
            .options(
                selectinload(CollectionItem.artists),
                selectinload(CollectionItem.categories),
                selectinload(CollectionItem.formats),
                joinedload(CollectionItem.folder),
                joinedload(CollectionItem.filed_under),
            )
            .order_by(CollectionItem.id)
        )

    def show_page(self, pagetitle, **filters):
        self.update_redirect()
        (
            categories,
            artists,
            items,
            soundtrack_items,
            showtunes_items,
            edison_items,
        ) = self.crunch(**filters)
        return self.render_template(
            self.printview_template,
            appbuilder=self.appbuilder,
            pagetitle=pagetitle,
            categories=categories,
            artists=artists,
            items=items,
            soundtrack_items=soundtrack_items,
            showtunes_items=showtunes_items,
            edison_items=edison_items,
            **LAYOUT_NAMES,
        )

    @expose("/")
    def printview(self):
        self.update_redirect()
        return self.render_template(
            self.printview_index_template,
            appbuilder=self.appbuilder,
            **collection_counts(),
        )

    @expose("/all")
    @expose("/all/")
    def all(self):
        return self.show_page("Our Vinyl Collection")

    @expose("/folder/<int:folder>")
    def folder(self, folder):
        name = get_or_404(Folder, folder).name
        return self.show_page("Folder: " + name, folder=folder)

    @expose("/category/<int:category>")
    def category(self, category):
        name = get_or_404(Category, category).name
        return self.show_page("Category: " + name, category=category)

    @expose("/decade/<string:decade>")
    def decade(self, decade):
        return self.show_page("Decade: " + str(decade), decade=decade)
