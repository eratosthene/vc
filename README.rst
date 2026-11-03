Base Skeleton to start your application using Flask-AppBuilder and MongoEngine
------------------------------------------------------------------------------

- Install it::

	pip install flask-appbuilder
	git clone https://github.com/dpgaspar/Flask-AppBuilder-Skeleton.git

- Run it::

	fabmanager run


That's it!!


Tests
-----

- Run them (no ``config.py``, database or network needed)::

	pipenv install --dev
	pipenv run pytest

- Report coverage::

	pipenv run pytest --cov=app --cov-report=term-missing


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
