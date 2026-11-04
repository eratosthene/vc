vc
==

A Flask-AppBuilder app over a Discogs collection: list and edit views, a Print
View, and a Sync that pulls the collection, its folders and its notes from
Discogs. It runs on Flask-AppBuilder 5, Flask 3 and SQLAlchemy 2, against
MariaDB.

Tests
-----

- Run them (no ``config.py``, database or network needed)::

	pipenv install --dev
	pipenv run pytest


Syncing with Discogs
--------------------

The Sync button on the Collection list (a POST, for signed-in users) starts the
sync in the background and shows its log. "Dry run" next to it shows what would
change without saving anything. The same thing from the command line, in the
running container for the live app::

	docker exec <container> flask sync-discogs --dry-run
	docker exec <container> flask sync-discogs

It adds the folders Discogs has and renames the ones that changed, adds new
items and updates the ones that changed on Discogs (notes included), then
removes the items that are gone, listing them in the summary at the end of the
log. It never touches what's only kept in vc: categories, Filed Under, an
artist's sort name and Ignore, and a folder's Counts As LP. Only one sync runs
at a time. A job's state and log are files in ``SYNC_JOB_FOLDER`` (default:
``vc-sync-jobs`` in the system's temp folder), as several gunicorn workers
don't share memory.

Running with Docker
-------------------

Everything is in ``docker/``, with the repo root as the build context.

- A local copy to try changes on, from this checkout's code, with its own
  MariaDB (on ``127.0.0.1:3308``) and no access to the live database or
  Discogs. It needs a password for that database in ``docker/.env``::

	echo "VC_DEV_DB_PASSWORD=$(openssl rand -hex 16)" >> docker/.env
	dev-scripts/compose-up.sh

  The app is on http://127.0.0.1:5560. ``dev-scripts/run-local.sh`` runs it
  from the Pipenv environment instead, using ``config.py``.

- The live server: copy ``config.py.tpl`` to ``config.py`` and fill it in (the
  container mounts it read-only, so the image holds no secrets), then::

	docker/live-up.sh        # build and start; -n just restarts
	docker/live-logs.sh
	docker/live-down.sh

  The app is on port 19999. There's no database service: ``config.py``'s
  ``SQLALCHEMY_DATABASE_URI`` points at the MariaDB server's ``vc`` database,
  and the container runs ``flask setup-db`` as it starts.
