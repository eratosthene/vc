# Running vc in production

How to set up the app and run it on the live server. For working on the app
itself, see [Developing vc](development.md).

## Setting up

Everything the app needs, apart from its code, is in `config.py`. It isn't in
git, since it holds the live credentials. Copy `config.py.tpl` to start one,
and fill in:

- `SECRET_KEY`: a long random string, such as the output of
  `openssl rand -hex 32`.
- `SQLALCHEMY_DATABASE_URI`: the `vc` database on the MariaDB server, with a
  user that has rights on that database only. Keep `?charset=utf8mb4`, and
  percent-encode any special characters in the password.
- `DISCOGS_SETTINGS`: `USER_TOKEN` is a personal access token from
  discogs.com > Settings > Developers. It gives full access to the Discogs
  account, so it only ever goes in `config.py`.
- `LOG_LEVEL`: `INFO` by default. Set it to `DEBUG` to see more, and
  recreate the container. The sync's own log keeps `INFO` whatever this is.
- `SYNC_JOB_FOLDER`: where the sync keeps its lock and job files. The default is
  in the container's temp folder, which is fine, as it only matters while the
  container runs.

Keep it readable only by you:

```bash
chmod 600 config.py
```

The MariaDB server needs the `vc` database and its user to exist. The app
creates its tables, or brings them up to date, with:

```bash
flask --app app setup-db
```

On a new database it builds the tables from the models and records them as
being at the latest migration. On one that's already set up it applies any
migrations it hasn't had. The container runs it itself each time it starts,
so it rarely needs running by hand.

To sign in, the app needs an admin user:

```bash
flask --app app fab create-admin
```

Both run inside the container, once it's up:

```bash
sudo docker compose -f docker/compose.yml exec vc flask fab create-admin
```

(`FLASK_APP=app` is set in the image, so `--app app` isn't needed there.)

## Running on the live server

The live server runs the app's Docker image with gunicorn (two workers), on
port 19999, from the repo root. There's no database service in
`docker/compose.yml`: `config.py` points at the MariaDB server. To build the
image and start the app:

```bash
docker/live-up.sh
```

It runs `docker compose build --pull` and then recreates the container, which
runs `flask setup-db` as it starts, so a new version's migrations are applied
then. With `-n` it skips the build, and starts the image that's already there,
which is all a change to `config.py` needs:

```bash
docker/live-up.sh -n
```

To follow its logs, from the last 100 lines (`-n` picks another number, or
`all`). Ctrl-C stops following, and leaves the app running:

```bash
docker/live-logs.sh
```

To stop it and remove its container (it never removes volumes):

```bash
docker/live-down.sh
```

To update, check out the new `main`, then run `docker/live-up.sh`. Take a
backup first if the update has a migration (see below).

The image holds no settings or secrets: the container mounts `config.py` from
the repo root, read-only, and won't start without it. The Docker files are all
in `docker/`, and the build context is the repo root.

## Syncing from the command line

The Sync button on the Collection list does the same as this, in the
background (see [Using vc](using.md#syncing-with-discogs)). From a terminal, in
the running container, with `--dry-run` first to see what would change:

```bash
sudo docker compose -f docker/compose.yml exec vc flask sync-discogs --dry-run
sudo docker compose -f docker/compose.yml exec vc flask sync-discogs
```

It logs as it goes and ends with a summary. It refuses to start if another
sync is running, whether from the button or another terminal: they share a
lock file in `SYNC_JOB_FOLDER`.

## Backups

vc's data is the `vc` database on the MariaDB server. It holds the whole
collection, and also what exists nowhere else: the categories, each item's
categories and Filed Under, the artists' sort names and Ignore, the folders'
Counts As LP, and the users and their passwords. A sync only rebuilds what
came from Discogs, so a lost database loses all of the rest.

What a backup has to include:

- The `vc` database, with its schema, all of its tables, and the
  `alembic_version` table, which says which migrations it has had. A dump of
  just that database is enough; no other database on the server is needed.
- `config.py`, kept apart from the database backup as it holds the secrets
  that open it. Without it, the secret key is lost and everyone is signed out,
  and the Discogs token has to be made again.

The image and the code come from git and need no backup.

Neither this repo nor fbc2's says how the MariaDB server is backed up, so
this page can't say. Check that whatever backs up the server's databases
includes `vc`: it's a database of its own, which this repo only connects to.

To take a dump by hand, from a machine that can reach the server (the dump
has the whole database, password hashes included, so keep it private):

```bash
mariadb-dump --single-transaction --default-character-set=utf8mb4 \
    -h HOST -u vc -p vc > vc-$(date +%F).sql
```

To restore it into an empty `vc` database (never over a live one; drop and
recreate it first, once you're sure):

```bash
mariadb --default-character-set=utf8mb4 -h HOST -u vc -p vc < vc-2026-01-01.sql
```

Then start the app. `flask setup-db` sees `alembic_version` and applies any
newer migrations, so restoring an older dump and then updating is safe.
A restore has not been tried for vc. Try one against a throwaway database
before you need it.
