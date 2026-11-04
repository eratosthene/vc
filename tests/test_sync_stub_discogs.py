"""The sync with the real python3-discogs-client, against a small stub of the
Discogs API on localhost. It checks what the fake client can't: the shape of
the library's objects (`basic_information`, a listing with no `notes`, a
release with no master), its paging, its 429 backoff, and how many requests the
sync makes."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import discogs_client
import pytest

from app import models
from app import sync as discogs_sync

FORMATS = [{"name": "Vinyl", "qty": "1", "descriptions": ["LP"]}]


def basic(id, title, year, master_id=0, artist=(12, "Prince")):
    return {
        "id": id,
        "title": title,
        "year": year,
        "master_id": master_id,
        "artists": [{"id": artist[0], "name": artist[1]}],
        "genres": ["Funk / Soul"],
        "styles": ["Funk"],
        "formats": FORMATS,
    }


class Stub:
    """What the stub API serves, and what it was asked."""

    def __init__(self):
        self.requests = []
        self.rate_limit_once = False
        self.items = []

    def listing(self, query):
        per_page = int(query["per_page"][0])
        page = int(query["page"][0])
        chunk = self.items[(page - 1) * per_page : page * per_page]
        return {
            "pagination": {
                "page": page,
                "pages": max(1, -(-len(self.items) // per_page)),
                "per_page": per_page,
                "items": len(self.items),
            },
            "releases": chunk,
        }


@pytest.fixture
def stub(monkeypatch):
    stub = Stub()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            stub.requests.append(url.path)
            if stub.rate_limit_once:
                stub.rate_limit_once = False
                self.send_response(429)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            base = f"http://127.0.0.1:{server.server_port}"
            folders = f"{base}/users/me/collection/folders"
            routes = {
                "/oauth/identity": {
                    "id": 1,
                    "username": "me",
                    "resource_url": f"{base}/users/me",
                    "collection_folders_url": folders,
                },
                "/users/me/collection/folders": {
                    "folders": [
                        {
                            "id": 0,
                            "name": "All",
                            "count": len(stub.items),
                            "resource_url": f"{folders}/0",
                        },
                        {
                            "id": 1,
                            "name": "Uncategorized",
                            "count": 0,
                            "resource_url": f"{folders}/1",
                        },
                        {
                            "id": 2,
                            "name": "45s",
                            "count": 1,
                            "resource_url": f"{folders}/2",
                        },
                    ]
                },
                "/users/me/collection/folders/0/releases": stub.listing(query)
                if "page" in query
                else None,
                "/releases/1100": {"id": 1100, "released": "1999-05-01"},
                "/releases/1101": {"id": 1101, "released": "2001"},
                "/masters/5": {"id": 5, "year": 1999},
            }
            body = routes.get(url.path)
            if body is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        discogs_client.Client, "_base_url", f"http://127.0.0.1:{server.server_port}"
    )
    monkeypatch.setattr("discogs_client.utils.sleep", lambda s: None)
    logging.getLogger("vc.sync").disabled = False
    yield stub
    server.shutdown()
    server.server_close()


def item(instance_id, folder_id, info, notes=None):
    d = {
        "id": info["id"],
        "instance_id": instance_id,
        "folder_id": folder_id,
        "basic_information": info,
    }
    if notes is not None:
        d["notes"] = notes
    return d


def sync(app, **kw):
    return discogs_sync.run(app, **kw)


def asked(stub, prefix):
    return [r for r in stub.requests if r.startswith(prefix)]


def test_a_sync_with_the_real_client(app, db, stub):
    stub.items = [
        item(
            10,
            2,
            basic(1100, "Purple Rain", 1984, master_id=5),
            notes=[{"field_id": 1, "value": "Mint"}, {"field_id": 4, "value": "Yes"}],
        ),
        # No notes key at all, and no master.
        item(11, 1, basic(1101, "Sign o' the Times", 1987)),
    ]
    summary = sync(app)
    rows = {i.instance_id: i for i in db.session.query(models.CollectionItem)}
    purple = rows[10]
    assert (purple.title, purple.year, purple.master_id, purple.master_year) == (
        "Purple Rain",
        1984,
        5,
        1999,
    )
    assert purple.released == "1999-05-01"
    assert purple.folder.name == "45s"
    assert purple.media_condition.label == "Mint"
    assert purple.listened is True
    assert [g.name for g in purple.genres] == ["Funk / Soul"]
    assert [(f.name, f.qty, f.descriptions) for f in purple.formats] == [
        ("Vinyl", 1, ["LP"])
    ]
    sign = rows[11]
    assert sign.master_id is None
    assert sign.master_year == 1987
    assert sign.released == "2001"
    assert sign.folder.name == "Uncategorized"
    assert sign.media_condition is None
    assert len(summary.added) == 2
    # The listing, one release page and one master: nothing per artist or genre.
    assert asked(stub, "/releases/") == ["/releases/1100", "/releases/1101"]
    assert asked(stub, "/masters/") == ["/masters/5"]


def test_the_second_sync_reads_only_the_listing(app, stub):
    stub.items = [item(10, 1, basic(1100, "Purple Rain", 1984, master_id=5))]
    sync(app)
    stub.requests.clear()
    summary = sync(app)
    assert summary.unchanged == 1
    assert asked(stub, "/releases/") == []
    assert asked(stub, "/masters/") == []
    assert asked(stub, "/users/me/collection/folders/0/releases") != []


def test_the_listing_is_read_in_pages_of_100(app, db, stub):
    stub.items = [item(i, 1, basic(2000 + i, f"T{i}", 2000)) for i in range(1, 151)]
    sync(app, dry_run=True)
    listing = [r for r in stub.requests if r.endswith("/releases")]
    # 150 items is two pages of 100, not three of 50.
    assert len(listing) == 2


def test_a_dry_run_makes_no_requests_beyond_the_listing(app, stub):
    stub.items = [item(10, 1, basic(1100, "Purple Rain", 1984, master_id=5))]
    sync(app, dry_run=True)
    assert asked(stub, "/releases/") == []
    assert asked(stub, "/masters/") == []


def test_a_rate_limited_request_is_retried(app, db, stub):
    stub.rate_limit_once = True
    stub.items = [item(11, 1, basic(1101, "Sign o' the Times", 1987))]
    sync(app)
    assert db.session.query(models.CollectionItem).count() == 1


def test_the_client_has_backoff_on(app):
    client = discogs_sync.get_client(app.config)
    assert client.backoff_enabled is True
