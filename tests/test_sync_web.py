"""The Sync button's routes: starting a sync in the background, showing its
progress, who can use them."""

import logging

import pytest

from app import models

PRINCE = (12, "Prince")


@pytest.fixture
def folder(make):
    """The folder the fake client puts items in by default (Discogs id 1)."""
    return make.folder("Alphabetical", discogs_id=1)


def items(db):
    return db.session.query(models.CollectionItem).order_by(models.CollectionItem.id)


def names(rows):
    return sorted(str(r) for r in rows)


class Broken(list):
    """A collection listing that fails, as Discogs being down does."""

    per_page = 50

    def __iter__(self):
        raise RuntimeError("Discogs is down")


@pytest.fixture(autouse=True)
def sync_logger_on():
    # The migrations' fileConfig() (run by the setup-db tests) switches off
    # loggers that already exist.
    logging.getLogger("vc.sync").disabled = False


class TestRoutes:
    @pytest.fixture(autouse=True)
    def inline_jobs(self, monkeypatch, tmp_path, app, caplog):
        """Run the background job in the request, in a folder of its own, and
        log at INFO as the app does (the tests' config quiets the root logger)."""
        caplog.set_level("INFO")
        monkeypatch.setitem(app.config, "SYNC_JOB_FOLDER", str(tmp_path))
        monkeypatch.setattr("app.syncjob._spawn", lambda target: target())

    def test_the_button_starts_a_sync_and_shows_it(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        r = admin.post("/syncdiscogs")
        assert r.status_code == 303
        assert "/syncjob/" in r.headers["Location"]
        assert names(items(db)) == ["A"]

    def test_the_job_page_and_its_status(self, admin, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        location = admin.post("/syncdiscogs").headers["Location"]
        page = admin.get(location)
        assert page.status_code == 200
        assert b"sync-log" in page.data
        job_id = location.rsplit("/", 1)[1]
        status = admin.get(f"/syncjobstatus/{job_id}").get_json()
        assert status["status"] == "done"
        assert status["errors"] == 0
        assert "items: 1 added" in status["log"]

    def test_the_log_can_be_read_from_an_offset(self, admin, discogs, folder):
        job_id = admin.post("/syncdiscogs").headers["Location"].rsplit("/", 1)[1]
        first = admin.get(f"/syncjobstatus/{job_id}").get_json()
        rest = admin.get(f"/syncjobstatus/{job_id}?offset={first['offset']}")
        assert rest.get_json()["log"] == ""

    def test_a_dry_run_from_the_button_saves_nothing(self, admin, db, discogs, folder):
        discogs.add(100, "A", 2000, [PRINCE])
        location = admin.post("/syncdiscogs", data={"dry_run": "1"}).headers["Location"]
        assert items(db).count() == 0
        job_id = location.rsplit("/", 1)[1]
        status = admin.get(f"/syncjobstatus/{job_id}").get_json()
        assert status["title"] == "Discogs sync (dry run)"
        assert "Dry run: nothing was saved." in status["log"]

    def test_a_failed_sync_is_shown_as_failed(self, admin, discogs, folder):
        discogs.releases = Broken()
        job_id = admin.post("/syncdiscogs").headers["Location"].rsplit("/", 1)[1]
        status = admin.get(f"/syncjobstatus/{job_id}").get_json()
        assert status["status"] == "failed"
        assert status["errors"] == 1
        assert "Discogs is down" in status["log"]

    def test_a_running_sync_is_not_started_twice(
        self, admin, monkeypatch, discogs, folder
    ):
        monkeypatch.setattr("app.syncjob._spawn", lambda target: None)
        first = admin.post("/syncdiscogs").headers["Location"]
        second = admin.post("/syncdiscogs").headers["Location"]
        assert first == second

    def test_a_job_whose_process_has_gone_is_marked_failed(
        self, admin, monkeypatch, discogs, folder
    ):
        monkeypatch.setattr("app.syncjob._spawn", lambda target: None)
        job_id = admin.post("/syncdiscogs").headers["Location"].rsplit("/", 1)[1]
        monkeypatch.setattr("app.syncjob._process_alive", lambda pid: False)
        status = admin.get(f"/syncjobstatus/{job_id}").get_json()
        assert status["status"] == "failed"
        assert "The server stopped" in status["log"]

    def test_an_unknown_job_is_a_404(self, admin):
        assert admin.get("/syncjob/" + "0" * 32).status_code == 404
        assert admin.get("/syncjobstatus/" + "0" * 32).status_code == 404
        assert admin.get("/syncjobstatus/not-an-id").status_code == 404

    def test_a_get_cannot_start_a_sync(self, admin, db, discogs, folder, make):
        make.item("Kept", instance_id=100)
        assert admin.get("/syncdiscogs").status_code == 405
        assert items(db).count() == 1

    def test_the_old_notes_route_is_gone(self, admin):
        assert admin.get("/syncdiscogsnotes").status_code == 404
        assert admin.post("/syncdiscogsnotes").status_code == 404

    def test_the_post_needs_the_csrf_token(self, admin, app, monkeypatch, db, discogs):
        monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
        r = admin.post("/syncdiscogs")
        assert r.status_code == 400
        assert items(db).count() == 0

    def test_the_post_works_with_the_csrf_token(
        self, admin, app, monkeypatch, db, discogs, folder
    ):
        monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
        page = admin.get("/collectionmodelview/list/").get_data(as_text=True)
        token = page.split('name="csrf_token" value="')[1].split('"')[0]
        discogs.add(100, "A", 2000, [PRINCE])
        r = admin.post("/syncdiscogs", data={"csrf_token": token})
        assert r.status_code == 303
        assert names(items(db)) == ["A"]

    def test_someone_not_signed_in_cannot_start_a_sync(
        self, client, db, discogs, folder, make
    ):
        make.item("Kept", instance_id=100)
        r = client.post("/syncdiscogs")
        assert r.status_code == 302
        assert "/login/" in r.headers["Location"]
        assert items(db).count() == 1
        assert discogs.clients == []

    @pytest.mark.parametrize(
        "url", ["/syncjob/" + "0" * 32, "/syncjobstatus/" + "0" * 32]
    )
    def test_someone_not_signed_in_cannot_see_a_job(self, client, url):
        r = client.get(url)
        assert r.status_code == 302
        assert "/login/" in r.headers["Location"]
