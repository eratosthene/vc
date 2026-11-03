import logging
from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from app import db
from flask import abort, redirect, current_app, request
from sqlalchemy import and_, func
import discogs_client

# The models are imported inside the functions that use them, not here: this
# module is imported before Flask-AppBuilder is set up, and importing a model
# adds its table to the metadata, which Flask-AppBuilder would then create
# itself on a new database, ahead of the migrations.

logger = logging.getLogger()


def get_or_add(model, **kwargs):
    """The row of `model` matching `kwargs`, added to the session if it's new."""
    row = db.session.query(model).filter_by(**kwargs).one_or_none()
    if row is None:
        row = model(**kwargs)
        db.session.add(row)
        db.session.flush()
        logger.info("Adding " + model.__name__.lower() + " " + str(row))
    return row


def parse_notes(item):
    """Media and sleeve condition, notes, Listened and Includes from an item's
    Discogs notes, as a dict of CollectionItem fields."""
    from app.models import MediaCondition, SleeveCondition

    mc = None
    sc = None
    n = None
    listened = None
    i = None
    for note in item.notes:
        if note["field_id"] == 1:
            mc = get_or_add(MediaCondition, label=note["value"].rstrip())
        if note["field_id"] == 2:
            sc = get_or_add(SleeveCondition, label=note["value"].rstrip())
        if note["field_id"] == 3:
            n = note["value"].rstrip()
        if note["field_id"] == 4:
            if note["value"].rstrip() == "Yes":
                listened = True
            else:
                listened = False
        if note["field_id"] == 5:
            i = note["value"].rstrip()
    return {
        "media_condition": mc,
        "sleeve_condition": sc,
        "item_notes": n,
        "listened": listened,
        "includes": i,
    }


def add_discogs_release(item):
    from app.models import (
        CollectionItem,
        CollectionItemFormat,
        Folder,
        Artist,
        Genre,
        Style,
        set_artists,
    )

    folder = db.session.query(Folder).filter_by(discogs_id=item.folder_id).one()
    artists = []
    genres = []
    styles = []
    for artist in item.release.artists:
        adoc = db.session.query(Artist).filter_by(discogs_id=artist.id).one_or_none()
        if adoc is None:
            sn = ""
            n = artist.name
            if n.startswith("The "):
                sn = n.removeprefix("The ") + ", The"
                logger.debug("Replacing /" + n + "/ with /" + sn + "/")
            adoc = Artist(discogs_id=artist.id, name=artist.name, sort_name=sn)
            db.session.add(adoc)
            db.session.flush()
            logger.info("Adding artist " + str(adoc))
        artists.append(adoc)
    for genre in item.release.genres:
        genres.append(get_or_add(Genre, name=genre))
    for style in item.release.styles:
        styles.append(get_or_add(Style, name=style))
    notes = parse_notes(item)
    master_id = None
    master_year = item.release.year
    if item.release.master:
        master_id = item.release.master.id
        master_year = item.release.master.year
    collection_item = (
        db.session.query(CollectionItem)
        .filter_by(instance_id=item.instance_id)
        .one_or_none()
    )
    if collection_item is None:
        collection_item = CollectionItem(instance_id=item.instance_id)
        db.session.add(collection_item)
    collection_item.release_id = item.release.id
    collection_item.title = item.release.title
    collection_item.year = item.release.year
    collection_item.genres = genres
    collection_item.styles = styles
    collection_item.master_id = master_id
    collection_item.master_year = master_year
    collection_item.formats = [
        CollectionItemFormat(
            position=position,
            name=f["name"],
            qty=int(f["qty"]) if f.get("qty") else None,
            text=f.get("text"),
            descriptions=f.get("descriptions", []),
        )
        for position, f in enumerate(item.release.formats)
    ]
    collection_item.released = item.release.fetch("released")
    collection_item.folder = folder
    for field, value in notes.items():
        setattr(collection_item, field, value)
    set_artists(db.session, collection_item, artists)
    db.session.commit()
    logger.debug(collection_item)


def redirect_to_random(
    folder=None, category=None, decade=None, lp=False, unlistened=False
):
    """Redirect to the show page of a random item that matches the filters."""
    from app.models import CollectionItem, Category, Folder

    query = db.session.query(CollectionItem)
    if unlistened:
        query = query.filter(CollectionItem.listened.is_(False))
    if lp:
        # Items without a folder count too, as they did when the folders were
        # left out by id.
        query = query.filter(~CollectionItem.folder.has(Folder.counts_as_lp.is_(False)))
    if folder:
        query = query.filter(CollectionItem.folder_id == folder)
    if category:
        query = query.filter(CollectionItem.categories.any(Category.id == category))
    if decade:
        after = int(decade[:-1]) - 1
        before = int(decade[:-1]) + 10
        query = query.filter(
            and_(
                CollectionItem.master_year > after, CollectionItem.master_year < before
            )
        )
    item = query.order_by(func.rand()).first()
    if item is None:
        abort(404)
    return redirect("/collectionmodelview/show/" + str(item.id))


class MyIndexView(IndexView):
    index_template = "index.html"

    @expose("/unlistened_lp")
    def unlistened_lp(self):
        self.update_redirect()
        return redirect_to_random(lp=True, unlistened=True)

    @expose("/random_lp")
    def random_lp(self):
        self.update_redirect()
        return redirect_to_random(lp=True)

    @expose("/unlistened_release")
    def unlistened_release(self):
        self.update_redirect()
        return redirect_to_random(unlistened=True)

    @expose("/random_release")
    def random_release(self):
        self.update_redirect()
        return redirect_to_random()

    @expose("/unlistened_folder/<int:folder>")
    def unlistened_folder(self, folder):
        self.update_redirect()
        return redirect_to_random(folder=folder, unlistened=True)

    @expose("/random_folder/<int:folder>")
    def random_folder(self, folder):
        self.update_redirect()
        return redirect_to_random(folder=folder)

    @expose("/unlistened_category/<int:category>")
    def unlistened_category(self, category):
        self.update_redirect()
        return redirect_to_random(category=category, unlistened=True)

    @expose("/random_category/<int:category>")
    def random_category(self, category):
        self.update_redirect()
        return redirect_to_random(category=category)

    @expose("/unlistened_decade/<string:decade>")
    def unlistened_decade(self, decade):
        self.update_redirect()
        return redirect_to_random(decade=decade, unlistened=True)

    @expose("/random_decade/<string:decade>")
    def random_decade(self, decade):
        self.update_redirect()
        return redirect_to_random(decade=decade)

    @expose("/syncdiscogs")
    def syncdiscogs(self):
        from app.models import CollectionItem

        self.update_redirect()
        logger.info("Updating discogs...")
        d = discogs_client.Client(
            current_app.config["DISCOGS_SETTINGS"]["USER_AGENT"],
            user_token=current_app.config["DISCOGS_SETTINGS"]["USER_TOKEN"],
        )
        me = d.identity()
        releases = me.collection_folders[0].releases
        local_releases = db.session.query(CollectionItem).all()
        logger.info("Total releases: " + str(len(releases)))
        logger.info("Total local releases: " + str(len(local_releases)))
        for item in releases:
            logger.debug("Checking discogs: " + str(item))
            if (
                not db.session.query(CollectionItem)
                .filter_by(instance_id=item.instance_id)
                .count()
            ):
                logger.info("Adding " + str(item))
                add_discogs_release(item)

        for item in local_releases:
            logger.debug("Checking local: " + str(item))
            if not any(x.instance_id == item.instance_id for x in releases):
                logger.info("Removing " + str(item))
                db.session.delete(item)
                db.session.commit()

        ref = request.referrer
        if ref:
            return redirect(ref)
        else:
            return redirect("/collectionmodelview/list/")

    @expose("/syncdiscogsnotes")
    def syncdiscogsnotes(self):
        from app.models import CollectionItem

        self.update_redirect()
        logger.info("Updating discogs notes...")
        d = discogs_client.Client(
            current_app.config["DISCOGS_SETTINGS"]["USER_AGENT"],
            user_token=current_app.config["DISCOGS_SETTINGS"]["USER_TOKEN"],
        )
        me = d.identity()
        releases = me.collection_folders[0].releases
        logger.info("Total releases: " + str(len(releases)))
        for item in releases:
            logger.info("Updating notes for " + str(item))
            notes = parse_notes(item)
            collection_item = (
                db.session.query(CollectionItem)
                .filter_by(instance_id=item.instance_id)
                .one()
            )
            for field, value in notes.items():
                setattr(collection_item, field, value)
            db.session.commit()

        ref = request.referrer
        if ref:
            return redirect(ref)
        else:
            return redirect("/collectionmodelview/list/")

    @expose("/")
    def index(self):
        from app.models import CollectionItem, Folder, Category

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
            by_decade.append({"decade": str(int(d)) + "s", "count": count})
        return self.render_template(
            self.index_template,
            appbuilder=self.appbuilder,
            lp_total=lp_total,
            full_total=full_total,
            by_folder=by_folder,
            by_category=by_category,
            by_decade=by_decade,
        )
