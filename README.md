# vc

vc is a Flask-AppBuilder app over a Discogs collection, kept in MariaDB. It
adds what Discogs can't do: your own categories, sort names and filing notes
for each item, and a Print View that lays the whole collection out as a
printable catalogue.

- **Collection**: every item in the Discogs collection, with its artists,
  genres, styles, formats, folder, condition and notes. Categories, Filed
  Under and the artists' sort names are kept in vc only.
- **Sync**: pulls the collection, its folders and its notes from Discogs, and
  never touches what's kept only in vc.
- **Print View**: the collection by category and artist, as one page for all
  of it, or for a folder, a category or a decade.
- **Home page**: totals, and links to a random item, or a random item you
  haven't listened to, overall and by folder, category and decade.

## Documentation

- [Using vc](docs/using.md): categorizing items, sort names, Ignore and Filed
  Under, the Discogs notes vc reads, the Print View, and syncing.
- [Developing vc](docs/development.md): setting up, the tests, pre-commit and
  the Docker setup for trying changes.
- [Running vc in production](docs/production.md): `config.py`, starting and
  updating the app, the first database and admin user, syncing from the
  command line and backups.

## Quick start

To work on the app, with its own MariaDB in Docker, and no access to the live
database or Discogs:

```bash
pipenv install --dev
pre-commit install
echo "VC_DEV_DB_PASSWORD=$(openssl rand -hex 16)" >> docker/.env
dev-scripts/compose-up.sh
```

Then open http://127.0.0.1:5560. [Developing vc](docs/development.md) has
the first sign-in.

On the live server, from the repo root, with a `config.py` in place, to build
the image and start the app on port 19999:

```bash
docker/live-up.sh
```

[Running vc in production](docs/production.md) covers `config.py`, which it
needs first.
