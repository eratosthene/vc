import logging
import click
import sqlalchemy as sa
from flask import Flask
from flask_appbuilder import AppBuilder, Model
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, stamp, upgrade

"""
 Logging configuration
"""

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)
app.config.from_object("config")
# Flask-AppBuilder's Model is the models' base class, so passing it here puts
# its metadata (ours and the ab_* tables) on db.
db = SQLAlchemy(app, model_class=Model)
migrate = Migrate(app, db)
# The views import `db`, so they can only be imported once it exists.
from app.index import MyIndexView  # noqa: E402

# Flask-AppBuilder reads the config and sets up its security tables through
# current_app, so it needs an app context, here and when adding views.
with app.app_context():
    appbuilder = AppBuilder(app, db.session, indexview=MyIndexView)


@app.cli.command("setup-db")
def setup_db():
    """Create a new database from the models, or migrate an existing one."""
    # Importing the app has already created Flask-AppBuilder's ab_* tables
    # (and, in a new database, only those: see the note in app/index.py).
    tables = sa.inspect(db.engine).get_table_names()
    if "alembic_version" in tables:
        upgrade()
    else:
        # The models match the migrations' head, so build the schema from them
        # and record it as being at head (Alembic's recipe for new databases).
        from app import models  # noqa: F401

        db.create_all()
        stamp()
        click.echo("Created a new database at the latest migration.")


@app.cli.command("sync-discogs")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be added, changed and removed, and save nothing.",
)
def sync_discogs(dry_run):
    """Sync the collection from Discogs: folders, then items added or updated
    (notes included), then the items that are gone from Discogs. The log ends
    with a summary."""
    from app import sync

    try:
        sync.run(app, dry_run=dry_run)
    except sync.SyncAlreadyRunning as e:
        raise click.ClickException(str(e))


# The views import `appbuilder`, so they can only be imported once it exists.
with app.app_context():
    from app import views  # noqa: E402, F401
