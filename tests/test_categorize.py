"""The Categorize list's edit modal: the list page's markup, and the two
endpoints the modal's script talks to."""

import pytest
from bs4 import BeautifulSoup

LIST = "/collectionitemmodelview/list/"


@pytest.fixture
def items(db, make):
    rock = make.category("Rock")
    jazz = make.category("Jazz")
    artist = make.artist("Miles")
    a = make.item("Alpha", artists=[artist], categories=[rock])
    b = make.item("Beta", artists=[artist], categories=[rock])
    return type("Items", (), {"a": a, "b": b, "rock": rock, "jazz": jazz})


def modal_url(item):
    return f"/collectionitemmodelview/editmodal/{item.id}"


def row_url(item):
    return f"/collectionitemmodelview/row/{item.id}"


def parse(r):
    return BeautifulSoup(r.data, "lxml")


class TestListPage:
    def test_has_the_modal_and_its_script(self, admin, items):
        soup = parse(admin.get(LIST))
        assert soup.find(id="categorize-modal") is not None
        assert soup.find("script", src=lambda s: s and s.endswith("categorize.js"))

    def test_each_row_knows_its_urls_and_keeps_its_edit_link(self, admin, items):
        soup = parse(admin.get(LIST))
        row = soup.find("tr", id=f"row-{items.a.id}")
        assert row["data-modal-url"] == modal_url(items.a)
        assert row["data-row-url"] == row_url(items.a)
        # The no-JS fallback: a plain link to the stock edit page.
        assert row.find("a", href=lambda h: h and f"/edit/{items.a.id}" in h)

    def test_the_script_is_served(self, admin):
        r = admin.get("/static/categorize.js")
        assert r.status_code == 200
        r.close()

    def test_other_lists_have_no_modal(self, admin, items):
        for url in ("/collectionmodelview/list/", "/categorymodelview/list/"):
            assert parse(admin.get(url)).find(id="categorize-modal") is None


class TestModalForm:
    def test_get_returns_just_the_form(self, admin, items):
        r = admin.get(modal_url(items.a))
        assert r.status_code == 200
        soup = parse(r)
        form = soup.find("form", id="categorize-form")
        assert form.find("select", {"name": "categories"}) is not None
        # Fields only: no Save button or Back link, and not a whole page.
        assert form.find("button") is None
        assert "navbar" not in r.text

    def test_the_form_posts_back_to_the_modal(self, admin, items):
        form = parse(admin.get(modal_url(items.a))).find("form")
        assert form["action"].startswith(modal_url(items.a))

    def test_an_unknown_item_is_not_found(self, admin):
        assert admin.get("/collectionitemmodelview/editmodal/999").status_code == 404


class TestModalSave:
    def test_saves_and_returns_the_new_row(self, admin, db, items):
        r = admin.post(
            modal_url(items.a), data={"categories": [items.rock.id, items.jazz.id]}
        )
        assert r.status_code == 200
        row = parse(r).find("tr")
        assert row["id"] == f"row-{items.a.id}"
        assert "Jazz" in row.get_text() and "Rock" in row.get_text()
        db.session.expire_all()
        assert sorted(c.name for c in items.a.categories) == ["Jazz", "Rock"]

    def test_other_rows_are_unchanged(self, admin, db, items):
        admin.post(modal_url(items.a), data={"categories": [items.jazz.id]})
        db.session.expire_all()
        assert [c.name for c in items.b.categories] == ["Rock"]
        assert "Jazz" not in parse(admin.get(row_url(items.b))).get_text()

    def test_the_row_matches_the_one_in_the_list(self, admin, items):
        listed = parse(admin.get(LIST)).find("tr", id=f"row-{items.b.id}")
        alone = parse(admin.get(row_url(items.b))).find("tr")
        assert str(listed) == str(alone)

    def test_clearing_the_categories_works(self, admin, db, items):
        r = admin.post(modal_url(items.a), data={})
        assert r.status_code == 200
        db.session.expire_all()
        assert items.a.categories == []

    def test_it_changes_nothing_else(self, admin, db, items):
        admin.post(
            modal_url(items.a), data={"categories": [items.jazz.id], "title": "X"}
        )
        db.session.expire_all()
        assert items.a.title == "Alpha"

    def test_it_leaves_no_message_for_the_next_page(self, admin, items):
        admin.post(modal_url(items.a), data={"categories": [items.jazz.id]})
        assert "alert-success" not in admin.get(LIST).text

    def test_an_invalid_form_is_422_with_the_form_and_its_error(
        self, admin, db, items, monkeypatch
    ):
        # Categorize's form has nothing to get wrong but the CSRF token, so
        # make the form refuse what it is given.
        def refuse(self, *args, **kwargs):
            self.categories.errors = ["Pick a better one"]
            return False

        monkeypatch.setattr("flask_appbuilder.forms.DynamicForm.validate", refuse)
        r = admin.post(modal_url(items.a), data={"categories": [items.jazz.id]})
        assert r.status_code == 422
        soup = parse(r)
        assert soup.find("form", id="categorize-form") is not None
        assert soup.find("tr", id=f"row-{items.a.id}") is None
        assert "Pick a better one" in soup.get_text()
        db.session.expire_all()
        assert [c.name for c in items.a.categories] == ["Rock"]


class TestBackHistory:
    def test_the_modal_leaves_the_back_history_alone(self, admin, items):
        admin.get(LIST)
        with admin.session_transaction() as s:
            before = s["page_history"]
        admin.get(modal_url(items.a))
        admin.post(modal_url(items.a), data={"categories": [items.jazz.id]})
        with admin.session_transaction() as s:
            assert s["page_history"] == before

    def test_the_stock_edit_page_still_returns_to_the_list(self, admin, items):
        admin.get(LIST)
        admin.get(modal_url(items.a))
        r = admin.get(f"/collectionitemmodelview/edit/{items.a.id}")
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/collectionitemmodelview/list/")


class TestAccess:
    @pytest.mark.parametrize("url", ["modal", "row"])
    def test_signed_out_goes_to_login(self, client, items, url):
        r = client.get((modal_url if url == "modal" else row_url)(items.a))
        assert r.status_code == 302
        assert "/login/" in r.headers["Location"]

    def test_signed_out_cannot_save(self, client, db, items):
        r = client.post(modal_url(items.a), data={"categories": []})
        assert r.status_code == 302
        db.session.expire_all()
        assert [c.name for c in items.a.categories] == ["Rock"]

    def test_the_permissions_are_the_stock_ones(self, app):
        from app.views import CollectionItemModelView as View

        assert View.editmodal._permission_name == "edit"
        assert View.row._permission_name == "list"

    def test_a_role_without_edit_cannot_use_the_modal(self, app, client, db, items):
        sm = app.appbuilder.sm
        role = sm.add_role("Reader")
        for perm in ("can_list", "can_show"):
            sm.add_permission_role(
                role, sm.add_permission_view_menu(perm, "CollectionItemModelView")
            )
        sm.add_user("rdr", "R", "R", "r@example.com", role, "password")
        client.post("/login/", data={"username": "rdr", "password": "password"})
        assert client.get(row_url(items.a)).status_code == 200
        assert client.get(modal_url(items.a)).status_code == 403
        assert client.post(modal_url(items.a), data={}).status_code == 403


class TestCsrf:
    @pytest.fixture
    def csrf_on(self, app):
        app.config["WTF_CSRF_ENABLED"] = True
        yield
        app.config["WTF_CSRF_ENABLED"] = False

    def test_a_post_without_the_token_is_refused(self, admin, db, items, csrf_on):
        r = admin.post(modal_url(items.a), data={"categories": [items.jazz.id]})
        assert r.status_code in (400, 422)
        db.session.expire_all()
        assert [c.name for c in items.a.categories] == ["Rock"]

    def test_the_form_carries_a_token_that_works(self, admin, db, items, csrf_on):
        form = parse(admin.get(modal_url(items.a))).find("form")
        token = form.find("input", {"name": "csrf_token"})["value"]
        r = admin.post(
            modal_url(items.a),
            data={"csrf_token": token, "categories": [items.jazz.id]},
        )
        assert r.status_code == 200
        db.session.expire_all()
        assert [c.name for c in items.a.categories] == ["Jazz"]
