"""
A stand-in for python3-discogs-client, so no test ever talks to Discogs.

It has just the shape app/index.py reads: a client whose identity() has
collection_folders[0].releases, a list of collection items, each with an
instance_id, folder_id, notes and a release (artists, genres, styles, master,
formats and fetch()).
"""

from types import SimpleNamespace


class FakeRelease:
    def __init__(
        self,
        id,
        title,
        year,
        artists,
        genres=(),
        styles=(),
        master=None,
        formats=(),
        released=None,
    ):
        self.id = id
        self.title = title
        self.year = year
        self.artists = [SimpleNamespace(id=i, name=n) for i, n in artists]
        self.genres = list(genres)
        self.styles = list(styles)
        # (id, year), or None for a release with no master.
        self.master = SimpleNamespace(id=master[0], year=master[1]) if master else None
        self.formats = [dict(f) for f in formats]
        self._released = released

    def fetch(self, field):
        assert field == "released"
        return self._released


class FakeCollectionItem:
    def __init__(self, instance_id, release, folder_id=1, notes=()):
        self.instance_id = instance_id
        self.release = release
        self.folder_id = folder_id
        # Discogs' custom fields: 1 media condition, 2 sleeve condition,
        # 3 notes, 4 Listened, 5 Includes.
        self.notes = [{"field_id": f, "value": v} for f, v in notes]

    def __str__(self):
        return f"<CollectionItem {self.instance_id} {self.release.title!r}>"


class FakeDiscogs:
    """The fake account: what's in the collection, and what the app asked for."""

    def __init__(self):
        self.releases = []
        self.clients = []

    def add(self, instance_id, title, year, artists, folder_id=1, notes=(), **release):
        item = FakeCollectionItem(
            instance_id,
            FakeRelease(
                id=instance_id + 1000,
                title=title,
                year=year,
                artists=artists,
                **release,
            ),
            folder_id=folder_id,
            notes=notes,
        )
        self.releases.append(item)
        return item

    def remove(self, instance_id):
        self.releases = [r for r in self.releases if r.instance_id != instance_id]

    def Client(self, user_agent, user_token=None):
        self.clients.append({"user_agent": user_agent, "user_token": user_token})
        folder = SimpleNamespace(releases=self.releases)
        return SimpleNamespace(
            identity=lambda: SimpleNamespace(collection_folders=[folder])
        )
