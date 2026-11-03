"""The index page, and its random links."""

from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup


def text(el):
    return " ".join(el.get_text().split())


@pytest.fixture
def collection(make):
    """Two folders (one that doesn't count as LPs), two categories, four items."""
    c = SimpleNamespace()
    c.lps = make.folder("Alphabetical")
    c.singles = make.folder("45s", counts_as_lp=False)
    c.rock = make.category("Rock")
    c.jazz = make.category("Jazz")
    a = make.artist()
    c.a = make.item(
        "A",
        artists=[a],
        folder=c.lps,
        categories=[c.rock],
        master_year=1965,
        listened=True,
    )
    c.b = make.item(
        "B",
        artists=[a],
        folder=c.lps,
        categories=[c.rock, c.jazz],
        master_year=1969,
        listened=False,
    )
    c.c = make.item(
        "C",
        artists=[a],
        folder=c.singles,
        categories=[c.jazz],
        master_year=1971,
        listened=False,
    )
    c.d = make.item("D", artists=[a], folder=None, master_year=1972)
    return c


def index(admin):
    r = admin.get("/")
    assert r.status_code == 200
    return BeautifulSoup(r.data, "lxml")


def counts(table):
    return {
        text(tr.select("td")[0]): int(text(tr.select("td")[1]))
        for tr in table.select("tr")
    }


class TestCounts:
    def test_totals_and_the_counts_per_folder_category_and_decade(
        self, admin, collection
    ):
        soup = index(admin)
        assert "Total LPs: 2" in text(soup)
        assert "Total releases: 4" in text(soup)
        _, _, folders, categories, decades = soup.select("table")
        assert counts(folders) == {"45s": 1, "Alphabetical": 2}
        assert counts(categories) == {"Jazz": 2, "Rock": 2}
        assert counts(decades) == {"1960s": 2, "1970s": 2}

    def test_folders_categories_and_decades_are_in_order(self, admin, collection):
        _, _, folders, categories, decades = index(admin).select("table")
        assert list(counts(folders)) == ["45s", "Alphabetical"]
        assert list(counts(categories)) == ["Jazz", "Rock"]
        assert list(counts(decades)) == ["1960s", "1970s"]

    def test_an_empty_collection(self, admin):
        soup = index(admin)
        assert "Total LPs: 0" in text(soup)
        assert "Total releases: 0" in text(soup)
        assert [t.select("tr") for t in soup.select("table")[2:]] == [[], [], []]

    def test_loads_without_signing_in(self, client):
        assert client.get("/").status_code == 200

    def test_items_without_a_master_year_have_no_decade(self, admin, make):
        make.item("A", master_year=0)
        make.item("B", master_year=None)
        soup = index(admin)
        assert "Total releases: 2" in text(soup)
        assert soup.select("table")[4].select("tr") == []

    def test_an_item_without_a_folder_counts_in_no_folder(self, admin, make):
        make.item("Loose", folder=None)
        soup = index(admin)
        assert "Total releases: 1" in text(soup)
        assert "Total LPs: 0" in text(soup)

    def test_every_folder_that_counts_as_an_lp_is_in_the_total(self, admin, make):
        f1, f2 = make.folder("One"), make.folder("Two")
        make.item("A", folder=f1)
        make.item("B", folder=f2)
        make.item("C", folder=make.folder("Singles", counts_as_lp=False))
        assert "Total LPs: 2" in text(index(admin))

    def test_empty_folders_and_categories_are_listed_with_zero(self, admin, make):
        make.folder("Empty")
        make.category("Nothing")
        _, _, folders, categories, _ = index(admin).select("table")
        assert counts(folders) == {"Empty": 0}
        assert counts(categories) == {"Nothing": 0}

    def test_links_to_the_random_pages_and_print_views(self, admin, collection):
        soup = index(admin)
        content = soup.find("h1", string="Our Vinyl Collection").parent
        hrefs = [a["href"] for a in content.select("a")]
        f, c = collection.lps.id, collection.rock.id
        assert hrefs[:5] == [
            "/printview/all/",
            "/random_lp",
            "/unlistened_lp",
            "/random_release",
            "/unlistened_release",
        ]
        assert any(h.endswith(f"/random_folder/{f}") for h in hrefs)
        assert any(h.endswith(f"/unlistened_category/{c}") for h in hrefs)
        assert any(h.endswith("/random_decade/1960s") for h in hrefs)


def location(response):
    assert response.status_code == 302
    return response.headers["Location"]


def shown(admin, url, collection):
    """The item a random link goes to."""
    where = location(admin.get(url))
    prefix = "/collectionmodelview/show/"
    assert where.startswith(prefix) or prefix in where
    return int(where.rsplit("/", 1)[1])


class TestRandomLinks:
    @pytest.mark.parametrize("n", range(5))
    def test_random_release_is_any_item(self, admin, collection, n):
        ids = {i.id for i in (collection.a, collection.b, collection.c, collection.d)}
        assert shown(admin, "/random_release", collection) in ids

    def test_random_release_with_one_item_is_that_item(self, admin, make):
        item = make.item("Only")
        assert shown(admin, "/random_release", None) == item.id

    def test_random_release_redirects_to_the_show_page(self, admin, make):
        item = make.item("Only")
        assert location(admin.get("/random_release")).endswith(
            f"/collectionmodelview/show/{item.id}"
        )

    @pytest.mark.parametrize("n", range(5))
    def test_unlistened_release_is_an_item_marked_not_listened(
        self, admin, collection, n
    ):
        ids = {collection.b.id, collection.c.id}
        assert shown(admin, "/unlistened_release", collection) in ids

    @pytest.mark.parametrize("n", range(5))
    def test_random_lp_leaves_out_folders_that_do_not_count(self, admin, collection, n):
        # An item with no folder counts, as its folder isn't one that doesn't.
        ids = {collection.a.id, collection.b.id, collection.d.id}
        assert shown(admin, "/random_lp", collection) in ids

    @pytest.mark.parametrize("n", range(5))
    def test_unlistened_lp(self, admin, collection, n):
        assert shown(admin, "/unlistened_lp", collection) == collection.b.id

    @pytest.mark.parametrize("n", range(5))
    def test_random_folder(self, admin, collection, n):
        ids = {collection.a.id, collection.b.id}
        assert shown(admin, f"/random_folder/{collection.lps.id}", collection) in ids
        assert (
            shown(admin, f"/random_folder/{collection.singles.id}", collection)
            == collection.c.id
        )

    def test_unlistened_folder(self, admin, collection):
        url = f"/unlistened_folder/{collection.lps.id}"
        assert shown(admin, url, collection) == collection.b.id

    @pytest.mark.parametrize("n", range(5))
    def test_random_category(self, admin, collection, n):
        ids = {collection.b.id, collection.c.id}
        assert shown(admin, f"/random_category/{collection.jazz.id}", collection) in ids

    def test_unlistened_category(self, admin, collection):
        url = f"/unlistened_category/{collection.rock.id}"
        assert shown(admin, url, collection) == collection.b.id

    @pytest.mark.parametrize("n", range(5))
    def test_random_decade(self, admin, collection, n):
        ids = {collection.a.id, collection.b.id}
        assert shown(admin, "/random_decade/1960s", collection) in ids

    def test_decade_includes_both_ends(self, admin, make):
        low = make.item("Low", master_year=1960)
        high = make.item("High", master_year=1969)
        make.item("Before", master_year=1959)
        make.item("After", master_year=1970)
        got = {shown(admin, "/random_decade/1960s", None) for _ in range(40)}
        assert got == {low.id, high.id}

    def test_unlistened_decade(self, admin, collection):
        assert shown(admin, "/unlistened_decade/1970s", collection) == collection.c.id

    def test_a_random_pick_varies(self, admin, make):
        for n in range(6):
            make.item(f"I{n}")
        got = {shown(admin, "/random_release", None) for _ in range(60)}
        assert len(got) > 1


class TestNothingMatches:
    """Each link finds nothing in an empty collection. It's a 404 now; it used
    to raise StopIteration."""

    @pytest.mark.parametrize(
        "url",
        [
            "/random_lp",
            "/unlistened_lp",
            "/random_release",
            "/unlistened_release",
            "/random_folder/1",
            "/unlistened_folder/1",
            "/random_category/1",
            "/unlistened_category/1",
            "/random_decade/1960s",
            "/unlistened_decade/1960s",
        ],
    )
    def test_is_not_found(self, admin, url):
        assert admin.get(url).status_code == 404

    def test_unlistened_ignores_items_never_marked_as_heard_or_not(self, admin, make):
        make.item("Unknown", listened=None)
        assert admin.get("/unlistened_release").status_code == 404

    def test_lp_ignores_items_in_folders_that_do_not_count(self, admin, make):
        make.item("Single", folder=make.folder("45s", counts_as_lp=False))
        assert admin.get("/random_lp").status_code == 404

    def test_folder_must_be_a_number(self, admin):
        assert admin.get("/random_folder/abc").status_code == 404

    def test_a_decade_that_is_not_one_fails(self, admin, make):
        make.item("A")
        assert admin.get("/random_decade/nope").status_code == 500
