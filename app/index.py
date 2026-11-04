import logging
from flask_appbuilder import IndexView
from flask_appbuilder.security.decorators import has_access
from flask_appbuilder.views import expose
from app import db, syncjob as sync_jobs
from app.counts import collection_counts
from flask import abort, redirect, current_app, jsonify, request, url_for
from flask_wtf.csrf import validate_csrf
from sqlalchemy import and_, func
from wtforms import ValidationError

# The models are imported inside the functions that use them, not here: this
# module is imported before Flask-AppBuilder is set up, and importing a model
# adds its table to the metadata, which Flask-AppBuilder would then create
# itself on a new database, ahead of the migrations.

logger = logging.getLogger()


def check_csrf():
    """Refuse a POST that doesn't carry the session's CSRF token (400). Like
    Flask-WTF's forms, it does nothing if WTF_CSRF_ENABLED is False."""
    if not current_app.config.get("WTF_CSRF_ENABLED", True):
        return
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        abort(400, "The CSRF token is missing or invalid.")


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

    @expose("/syncdiscogs", methods=["POST"])
    @has_access
    def syncdiscogs(self):
        """Start the Discogs sync in the background (a POST, so a link preview
        or a crawler can't start one) and go to the page that shows it."""
        check_csrf()
        job_id = sync_jobs.start(
            current_app._get_current_object(),
            dry_run=request.form.get("dry_run") == "1",
        )
        return redirect(url_for("MyIndexView.syncjob", job_id=job_id), code=303)

    @expose("/syncjob/<job_id>")
    @has_access
    def syncjob(self, job_id):
        """The page that shows a sync's progress."""
        self.update_redirect()
        job = sync_jobs.read(current_app._get_current_object(), job_id)
        if job is None:
            abort(404)
        return self.render_template(
            "syncjob.html",
            appbuilder=self.appbuilder,
            job_id=job_id,
            status_url=url_for("MyIndexView.syncjobstatus", job_id=job_id),
        )

    @expose("/syncjobstatus/<job_id>")
    @has_access
    def syncjobstatus(self, job_id):
        """A sync's state and the part of its log after `offset`, as JSON."""
        job = sync_jobs.read(
            current_app._get_current_object(),
            job_id,
            request.args.get("offset", 0, type=int),
        )
        if job is None:
            return jsonify(error="No such sync."), 404
        return jsonify(job)

    @expose("/")
    def index(self):
        self.update_redirect()
        return self.render_template(
            self.index_template,
            appbuilder=self.appbuilder,
            **collection_counts(),
        )
