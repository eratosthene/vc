# vc

A Flask-AppBuilder app on MariaDB over one person's Discogs collection:
list and edit views, a Print View, and a sync from Discogs. One person runs
it and works on it; most changes start from a GitHub issue and arrive as a PR
from a `claude/` branch in its own worktree. `README.md` and `docs/` are the
user-facing guide; this file is what they don't say.

## Commands

- Tests: `pipenv run pytest` (add `-q` or a path to narrow it). The suite needs
  no `config.py`, database or network.
- Format and lint: Ruff for Python (`ruff-format`, then `ruff --fix`) and
  mdformat for Markdown, both through pre-commit, which pins them; neither is
  in the Pipfile. Commits run those, gitleaks and the file checks. The test
  suite runs before each push, not each commit, so run it yourself before
  committing.
- New migration: `pipenv run flask --app app db migrate -m "..."`, against a
  database you can lose, then read it over: autogenerate misses data changes
  and renames.
- Run the app: `dev-scripts/run-local.sh` (127.0.0.1:5561, needs `config.py`),
  or `dev-scripts/compose-up.sh` for the app on :5560 with its own MariaDB
  (`docker/compose.dev.yml`).
- Check the image builds: `docker build -f docker/Dockerfile -t vc:my-test .`.
  Never tag it `vc:latest`, which is the live server's.

## Layout

- `app/__init__.py` builds the app, the database and AppBuilder **at import
  time**, from the top-level `config` module, then defines the `setup-db` and `sync-discogs` commands. `app/views.py`
  registers the views and menu last, and the 404 page.
- `app/models.py`: the models. `app/index.py`: the home page, its random links
  and the sync's web routes. `app/counts.py`: the home page's counts, shared
  with the Print View's index. `app/printview.py`: the Print View.
- `app/sync.py`: the Discogs sync. `app/syncjob.py`: runs it in a background
  thread for the web button, with its state and log in files, since gunicorn
  workers don't share memory.
- `migrations/`: Alembic, through Flask-Migrate. `flask setup-db` builds a new
  database from the models and stamps it, or migrates an existing one.
- `scripts/migrate_from_mongo.py`: the one-off move from MongoDB, kept until
  its packages go. `dev-scripts/`: local helpers. `docker/`: the image, the
  live and dev compose files and the live server's scripts.

## Things that aren't obvious

- `tests/conftest.py` puts a fake `config` module (in-memory SQLite) in
  `sys.modules` before `app` is imported. Tests never read `config.py`.
- SQLite passing proves little about the schema. Live is MariaDB 10.11 and
  MySQL refuses foreign keys between columns of different types
  (`tests/test_models_schema.py` checks). The Migrations workflow runs new
  migrations against MariaDB and checks they match the models.
- `app/index.py`, `app/counts.py` and `app/sync.py` import models inside
  functions, not at the top: importing a model adds its table to the metadata,
  and Flask-AppBuilder would then create it on a new database, ahead of the
  migrations.
- Discogs is only reached through `app/sync.py`'s client. Tests use
  `tests/fake_discogs.py`, so none can touch Discogs.
- The sync reads an item's notes by Discogs field number (1 to 5), and the
  Print View finds categories and the folder by name (see the constants at the
  top of `app/printview.py`). Renaming those in the database changes the page.
- `LOG_LEVEL` sets the root level; `vc.sync` stays at INFO or lower as the
  progress page shows its log.
- The only translations are Flask-AppBuilder's own; vc has none.

## Safety

- `config.py` holds the live database credentials and Discogs token and isn't
  in git; `config.py.tpl` is its template, and any new setting goes there with
  a comment. Don't read `config.py` or `docker/.env`.
- Never touch the live server, the live database or the live Discogs account.
  Run the app from `docker/compose.dev.yml`, which has no Discogs token.
- `docker/compose.dev.yml`'s `vc-dev` project is throwaway, but still don't
  `down -v` it without being asked. For another, use another project name
  (`-p vc-something`).
- A worktree has no `config.py`. Don't link the live one in to run the app;
  use the compose setup.

## Writing

- Docs, comments, UI text and PR descriptions are plain English, short
  sentences, in the app's own names: Collection, Categorize, Print View,
  Filed Under, Counts As LP. Comments say why, not what.
- When behaviour or setup changes, update the doc it belongs in, in the same
  PR: `docs/using.md` for what the app does, `docs/development.md` for
  working on it, `docs/production.md` for the live server. `README.md` is an
  overview with links; change it only when that changes. Docs are Markdown,
  with commands in fenced `bash` blocks.
- PR descriptions follow this shape: `Closes #N.`, a one-line summary, then
  sections as needed: How it works, Differences from the issue, and Testing,
  which says what was run, against what, and what *wasn't* run. CI writes its
  results into the description, so don't add them by hand.
