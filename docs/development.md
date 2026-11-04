# Developing vc

How to work on the app: run it on this machine, test it, and try changes
against a database you can lose. For the live server, see
[Running vc in production](production.md).

## Setting up

- Install the dependencies (including the dev ones) from `Pipfile.lock`. It
  needs Python 3.12:

  ```bash
  pipenv install --dev
  ```

- Install the git hooks, once per clone. They run gitleaks, Ruff, mdformat and
  the file checks on every commit, and the test suite before every push.
  pre-commit isn't in the Pipfile; install it yourself, with `brew install pre-commit` or pipx:

  ```bash
  pre-commit install
  ```

- Run the tests. They need no `config.py`, database or network, as
  `tests/conftest.py` puts a fake `config` module (an in-memory SQLite
  database) in place before the app is imported:

  ```bash
  pipenv run pytest
  ```

## Running the app

### With Docker

`docker/compose.dev.yml` runs the app from this checkout's code with Flask's
reloading dev server, against its own MariaDB 10.11, like the live server's.
It doesn't use `config.py`: it mounts `docker/config.dev.py`, which has no
Discogs token, so a sync can't reach a real account. Nothing in it can reach
the live database.

1. Put a password for the dev database in `docker/.env` (not in git):

   ```bash
   echo "VC_DEV_DB_PASSWORD=$(openssl rand -hex 16)" >> docker/.env
   ```

2. Build and start it, with the logs attached (Ctrl-C stops it). `-d` runs it
   in the background:

   ```bash
   dev-scripts/compose-up.sh
   ```

3. The container runs `flask setup-db` as it starts, so the tables are there.
   Create a user to sign in with, in another terminal:

   ```bash
   docker compose -f docker/compose.dev.yml exec app flask fab create-admin
   ```

Then open http://127.0.0.1:5560. The app and `app/` and `migrations/` are
mounted, so edits show up without a rebuild. The database is on
`127.0.0.1:3308`, and keeps its data in a volume between runs. The database starts
empty, and the dev config has no Discogs token, so Sync can't fill it: add
items through the app's forms to have something to look at.

To stop it and keep the data: `docker compose -f docker/compose.dev.yml stop`.
To throw the data away too, add `-v` to `down`.

### On this machine

```bash
dev-scripts/run-local.sh
```

runs Flask's reloading dev server from the Pipenv environment on
http://127.0.0.1:5561 (`-H` and `-p` change the address and port, or set
`VC_HOST` and `VC_PORT`). It reads `config.py`, which isn't in git:
copy `config.py.tpl` and point `SQLALCHEMY_DATABASE_URI` at a database you can
lose, such as the one the dev compose file starts on `127.0.0.1:3308`, then
create its tables once:

```bash
pipenv run flask --app app setup-db
```

A worktree has no `config.py`. To run from one, link the main checkout's, then
make sure that one is safe to use here:

```bash
ln -s "$(git rev-parse --git-common-dir)/../config.py" .
```

## Changing the app

- Models are in `app/models.py`. After changing one, make a migration for it
  with a `config.py` pointing at a database you can lose, and read it over
  before committing: autogenerate misses data changes and renames.

  ```bash
  pipenv run flask --app app db migrate -m "Describe the change"
  ```

  New databases are built from the models, not the migrations, so the two have
  to agree. The Migrations workflow runs a new migration against MariaDB 10.11
  on the PR, up, down and up again, and checks the result matches the models
  (`flask db check`).

- Settings the app reads go in `config.py.tpl`, with a comment, and in
  [Running vc in production](production.md#setting-up) if the live server
  needs to know. `LOG_LEVEL` is one: set it to `DEBUG` to see more.

- The tests live in `tests/`: `test_models*.py` for the models and schema,
  `test_sync*.py` for the sync (which uses `tests/fake_discogs.py`, a stand-in
  for the Discogs client, so no test reaches Discogs), `test_printview.py`,
  `test_index.py`, `test_views.py`, `test_app.py` and `test_cli.py`.

## Checks on a PR

Each runs on every PR, and on pushes to `main`:

- **Tests**: `pytest`, with the results added to the PR description.
- **Pre-commit**: everything above that pre-commit runs, except the tests.
- **Docker build**: builds `docker/Dockerfile` to check it still builds.
- **Migrations**: only when `migrations/` or `app/models.py` changes.
- **Dependency audit**: when `Pipfile` or `Pipfile.lock` change, and weekly.

Dependabot opens PRs for GitHub Actions, Python packages and the Docker base
image, weekly.

## Building the image

To check the Docker image builds without touching the live one, give it a
tag of your own (the live server's is `vc:latest`):

```bash
docker build -f docker/Dockerfile -t vc:my-test .
```
