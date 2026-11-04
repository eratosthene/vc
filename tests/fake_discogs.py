"""
A stand-in for python3-discogs-client, so no test ever talks to Discogs.

It has just the shape app/sync.py reads: a client whose identity() has
collection_folders (folder 0 is "All", with the collection items in
`releases`), and collection items with an instance_id, folder_id, notes and a
release (artists, genres, styles, master, formats and fetch()).

Reading what the real library would fetch with another request (a release's
`released`, a master's year) is counted in `FakeDiscogs.requests`, so a test
can check how much the sync asks for.
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
        requests=None,
    ):
        self.requests = requests if requests is not None else []
        self.id = id
        self.title = title
        self.year = year
        self.artists = [SimpleNamespace(id=i, name=n) for i, n in artists]
        self.genres = list(genres)
        self.styles = list(styles)
        # (id, year), or None for a release with no master.
        self.master = FakeMaster(*master, requests=self.requests) if master else None
        self.formats = [dict(f) for f in formats]
        self._released = released

    def fetch(self, field):
        assert field == "released"
        self.requests.append(("release", self.id))
        return self._released


class FakeMaster:
    """Like the library's Master: its id is known, but its year costs a request."""

    def __init__(self, id, year, requests):
        self.id = id
        self._year = year
        self._requests = requests

    @property
    def year(self):
        self._requests.append(("master", self.id))
        return self._year


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
        self.folders = {}
        self.clients = []
        self.requests = []
        self.last_client = None
        self.last_listing = None

    def add_folder(self, id, name):
        self.folders[id] = name

    def add(self, instance_id, title, year, artists, folder_id=1, notes=(), **release):
        item = FakeCollectionItem(
            instance_id,
            FakeRelease(
                id=instance_id + 1000,
                title=title,
                year=year,
                artists=artists,
                requests=self.requests,
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
        # A list of the folders, as the library returns it: "All" first.
        self.last_listing = PagedItems(self.releases)
        folders = [SimpleNamespace(id=0, name="All", releases=self.last_listing)]
        folders += [
            SimpleNamespace(id=i, name=n, releases=PagedItems([]))
            for i, n in self.folders.items()
        ]
        # The library's client has `backoff_enabled`, on unless turned off.
        self.last_client = SimpleNamespace(
            backoff_enabled=True,
            identity=lambda: SimpleNamespace(collection_folders=folders),
        )
        return self.last_client


class PagedItems(list):
    """A list with the `per_page` the library's paginated lists have."""

    per_page = 50
