from flask_appbuilder import BaseView
from flask import abort
from flask_appbuilder.views import expose
from sqlalchemy import func
from app import db
from app.models import CollectionItem, Category, Folder
import re


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
    n = e.item_notes
    p = re.compile(r"slot\s+([0-9]+)")
    s = p.search(n)
    p = re.compile("(Top|Bottom) drawer")
    d = p.search(n)
    if d.group(1) == "Top":
        return 100 + int(s.group(1))
    else:
        return 200 + int(s.group(1))


class PrintView(BaseView):
    default_view = "printview"
    printview_template = "printview.html"
    printview_index_template = "printviewindex.html"

    def crunch(self, folder=None, category=None, decade=None):
        categories = []
        artists = {}
        items = {}
        soundtrack_items = []
        showtunes_items = []
        edison_items = []
        if category:
            c_query = (
                db.session.query(Category)
                .filter_by(id=category)
                .order_by(Category.name)
            )
        else:
            c_query = db.session.query(Category).order_by(Category.name)
        for c in c_query:
            categories.append(c)
            artists[c.id] = []
            items[c.id] = {}
            ci_filters = [CollectionItem.categories.any(Category.id == c.id)]
            if folder:
                ci_filters.append(CollectionItem.folder_id == folder)
            elif decade:
                after = int(decade[:-1]) - 1
                before = int(decade[:-1]) + 10
                ci_filters.append(CollectionItem.master_year > after)
                ci_filters.append(CollectionItem.master_year < before)
            ci_query = (
                db.session.query(CollectionItem)
                .filter(*ci_filters)
                .order_by(CollectionItem.id)
            )
            for i in ci_query:
                for a in i.artists:
                    artists[c.id].append(a)
            artists[c.id] = list(set(artists[c.id]))
            artists[c.id].sort(key=sortFunc)
            for a in artists[c.id]:
                # logging.debug(a)
                items[c.id][a.id] = []
                releases = {}
                masters = []
                cic_query = ci_query.filter(CollectionItem.artists.any(id=a.id))
                for i in cic_query:
                    if i.master_id in releases:
                        releases[i.master_id].append(i)  # todo: no master fix
                    else:
                        releases[i.master_id] = [i]
                    masters.append({"master_id": i.master_id, "year": i.master_year})
                # Without duplicates, in the order they were first seen.
                masters = [
                    dict(t) for t in dict.fromkeys(tuple(d.items()) for d in masters)
                ]
                masters.sort(key=yearSortFunc)
                # logging.debug(masters)
                for master_id in releases:
                    releases[master_id].sort(key=yearRSortFunc)
                # logging.debug(releases)
                for m in masters:
                    master_id = m["master_id"]
                    for i in releases[master_id]:
                        items[c.id][a.id].append(i)
            if c.name == "Soundtracks":
                for i in ci_query:
                    soundtrack_items.append(i)
                soundtrack_items.sort(key=releaseSortFunc)
            if c.name == "Showtunes":
                for i in ci_query:
                    showtunes_items.append(i)
                showtunes_items.sort(key=releaseSortFunc)
            if c.name == "Edison Diamond Disc":
                for i in ci_query:
                    edison_items.append(i)
                edison_items.sort(key=slotSortFunc)

        return (
            categories,
            artists,
            items,
            soundtrack_items,
            showtunes_items,
            edison_items,
        )

    @expose("/")
    def printview(self):
        self.update_redirect()
        lp_total = 0
        full_total = db.session.query(CollectionItem).count()
        by_folder = []
        by_category = []
        by_decade = []
        for f in db.session.query(Folder).order_by(Folder.name):
            c = db.session.query(CollectionItem).filter_by(folder_id=f.id).count()
            by_folder.append({"folder": f, "total": c})
            if f.counts_as_lp:
                lp_total += c
        for f in db.session.query(Category).order_by(Category.name):
            c = (
                db.session.query(CollectionItem)
                .filter(CollectionItem.categories.any(Category.id == f.id))
                .count()
            )
            by_category.append({"category": f, "total": c})
        decade = func.floor(CollectionItem.master_year / 10) * 10
        dc = (
            db.session.query(decade, func.count())
            .filter(CollectionItem.master_year > 0)
            .group_by(decade)
            .order_by(decade)
        )
        for d, count in dc:
            decade = str(int(d)) + "s"
            after = int(decade[:-1]) - 1
            before = int(decade[:-1]) + 10
            by_decade.append(
                {
                    "decade": decade,
                    "count": count,
                    "before": before,
                    "after": after,
                }
            )
        return self.render_template(
            self.printview_index_template,
            appbuilder=self.appbuilder,
            lp_total=lp_total,
            full_total=full_total,
            by_folder=by_folder,
            by_category=by_category,
            by_decade=by_decade,
        )

    @expose("/all")
    @expose("/all/")
    def all(self):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = (
            self.crunch()
        )
        pagetitle = "Our Vinyl Collection"

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
        )

    @expose("/folder/<int:folder>")
    def folder(self, folder):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = (
            self.crunch(folder=folder)
        )
        pagetitle = "Folder: " + get_or_404(Folder, folder).name

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
        )

    @expose("/category/<int:category>")
    def category(self, category):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = (
            self.crunch(category=category)
        )
        pagetitle = "Category: " + get_or_404(Category, category).name

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
        )

    @expose("/decade/<string:decade>")
    def decade(self, decade):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = (
            self.crunch(decade=decade)
        )
        pagetitle = "Decade: " + str(decade)

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
        )
