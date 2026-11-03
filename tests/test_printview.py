"""The Print View: its sort functions, crunch() and every version of the page."""

import re
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import event

from app import printview as pv
from app.printview import PrintView


def crunch(**kwargs):
    return PrintView.crunch(PrintView(), **kwargs)


def page(admin, url):
    r = admin.get(url)
    assert r.status_code == 200, r.data[:500]
    return BeautifulSoup(r.data, "lxml")


def text(el):
    return " ".join(el.get_text().split())


def categories_on(soup):
    """{category: [(artist, [(year, title, [notes])])]} from a normal page."""
    result = {}
    for block in soup.select(".category-block"):
        name = text(block.select_one(".category-header"))
        artists = []
        for a in block.select(".artist-block"):
            releases = [
                (
                    text(r.select_one(".release-year")),
                    text(r.select_one(".release-title")),
                    [text(n) for n in r.select(".release-filed-info, .formats")],
                )
                for r in a.select(".release-info-block")
            ]
            artists.append((text(a.select_one(".artist-header")), releases))
        result[name] = artists
    return result


def titles(soup, category):
    return [t for _, releases in categories_on(soup)[category] for _, t, _ in releases]


def special_items(soup):
    """The items in a Soundtracks, Showtunes or Edison section, as
    [(year, title, artists, [notes])]."""
    return [
        (
            text(i.select_one(".release-year")),
            text(i.select_one(".soundtrack-release-title")),
            text(i.select_one(".soundtrack-artist-block")),
            [text(n) for n in i.select(".release-filed-info, .formats")],
        )
        for i in soup.select(".soundtrack-release-info-block")
    ]


@pytest.fixture
def folder(make):
    return make.folder("Alphabetical")


class TestSortFunctions:
    def test_sortFunc_is_the_string_form(self, make):
        assert pv.sortFunc(make.artist("The Beatles", sort_name="Beatles, The")) == (
            "Beatles, The"
        )
        assert pv.sortFunc(make.artist("Prince")) == "Prince"

    def test_yearSortFunc_is_the_year_key(self):
        assert pv.yearSortFunc({"master_id": 1, "year": 1969}) == 1969

    def test_yearRSortFunc_prefers_the_release_date(self):
        item = SimpleNamespace(released="1987-05-01", year=1999)
        assert pv.yearRSortFunc(item) == "1987-05-01"

    def test_yearRSortFunc_falls_back_to_the_year_as_text(self):
        assert pv.yearRSortFunc(SimpleNamespace(released=None, year=1999)) == "1999"
        assert pv.yearRSortFunc(SimpleNamespace(released="", year=1999)) == "1999"

    @pytest.mark.parametrize(
        "title, key",
        [
            ("The Wall", "wall, the"),
            ("the wall", "wall, the"),
            ("Thelma", "thelma"),
            ("Abbey Road", "abbey road"),
            ("The The", "the, the"),
        ],
    )
    def test_releaseSortFunc_moves_a_leading_the_to_the_end(self, title, key):
        assert pv.releaseSortFunc(SimpleNamespace(title=title)) == key

    @pytest.mark.parametrize(
        "notes, key",
        [
            ("slot 3 Top drawer", 103),
            ("Top drawer, slot 12", 112),
            ("slot 3 Bottom drawer", 203),
            ("slot  7 Bottom drawer", 207),
        ],
    )
    def test_slotSortFunc(self, notes, key):
        assert pv.slotSortFunc(SimpleNamespace(item_notes=notes)) == key

    @pytest.mark.parametrize("notes", ["slot 3", "Top drawer", "nothing", None])
    def test_slotSortFunc_fails_without_a_slot_or_drawer_bug_10(self, notes):
        # #10: one Edison Diamond Disc without both breaks the whole page.
        with pytest.raises((AttributeError, TypeError)):
            pv.slotSortFunc(SimpleNamespace(item_notes=notes))


class TestCrunch:
    def test_nothing_in_an_empty_database(self):
        assert crunch() == ([], {}, {}, [], [], [])

    def test_categories_come_in_name_order(self, make):
        for name in ["Rock", "Jazz", "Christmas"]:
            make.category(name)
        categories = crunch()[0]
        assert [c.name for c in categories] == ["Christmas", "Jazz", "Rock"]

    def test_a_category_with_no_items_has_no_artists(self, make):
        c = make.category("Empty")
        _, artists, items, *_ = crunch()
        assert artists == {c.id: []}
        assert items == {c.id: {}}

    def test_artists_are_sorted_by_sort_name(self, make):
        rock = make.category()
        beatles = make.artist("The Beatles", sort_name="Beatles, The")
        abba = make.artist("Abba")
        zappa = make.artist("Frank Zappa", sort_name="Zappa, Frank")
        make.item("A", artists=[zappa], categories=[rock])
        make.item("B", artists=[beatles], categories=[rock])
        make.item("C", artists=[abba], categories=[rock])
        _, artists, *_ = crunch()
        assert [a.name for a in artists[rock.id]] == [
            "Abba",
            "The Beatles",
            "Frank Zappa",
        ]

    def test_an_artist_is_listed_once_however_many_items(self, make):
        rock = make.category()
        a = make.artist()
        make.item("A", artists=[a], categories=[rock])
        make.item("B", artists=[a], categories=[rock])
        _, artists, *_ = crunch()
        assert artists[rock.id] == [a]

    def test_items_are_in_master_year_order_then_release_date(self, make):
        rock = make.category()
        a = make.artist()
        make.item("Late", artists=[a], categories=[rock], master_id=2, master_year=1990)
        make.item(
            "Reissue B",
            artists=[a],
            categories=[rock],
            master_id=1,
            master_year=1970,
            year=2001,
            released="2001-06",
        )
        make.item(
            "Reissue A",
            artists=[a],
            categories=[rock],
            master_id=1,
            master_year=1970,
            year=1990,
            released="1990-01-01",
        )
        make.item(
            "Original",
            artists=[a],
            categories=[rock],
            master_id=1,
            master_year=1970,
            year=1970,
        )
        _, _, items, *_ = crunch()
        assert [i.title for i in items[rock.id][a.id]] == [
            "Original",
            "Reissue A",
            "Reissue B",
            "Late",
        ]

    def test_an_item_is_listed_under_each_of_its_artists(self, make):
        rock = make.category()
        a, b = make.artist("A"), make.artist("B")
        item = make.item("Split", artists=[a, b], categories=[rock])
        _, _, items, *_ = crunch()
        assert items[rock.id][a.id] == [item]
        assert items[rock.id][b.id] == [item]

    def test_an_item_in_two_categories_is_in_both(self, make):
        rock, pop = make.category("Rock"), make.category("Pop")
        a = make.artist()
        item = make.item("Both", artists=[a], categories=[rock, pop])
        _, _, items, *_ = crunch()
        assert items[rock.id][a.id] == [item]
        assert items[pop.id][a.id] == [item]

    def test_an_item_without_a_category_is_left_out(self, make):
        make.category()
        make.item("None", artists=[make.artist()])
        _, artists, *_ = crunch()
        assert list(artists.values()) == [[]]

    def test_the_category_filter(self, make):
        rock, pop = make.category("Rock"), make.category("Pop")
        a = make.artist()
        make.item("R", artists=[a], categories=[rock])
        make.item("P", artists=[a], categories=[pop])
        categories, _, items, *_ = crunch(category=rock.id)
        assert categories == [rock]
        assert list(items) == [rock.id]

    def test_the_folder_filter(self, make):
        rock = make.category()
        a = make.artist()
        f1, f2 = make.folder("One"), make.folder("Two")
        make.item("In one", artists=[a], categories=[rock], folder=f1)
        make.item("In two", artists=[a], categories=[rock], folder=f2)
        _, _, items, *_ = crunch(folder=f2.id)
        assert [i.title for i in items[rock.id][a.id]] == ["In two"]

    def test_the_decade_filter_includes_both_ends(self, make):
        rock = make.category()
        a = make.artist()
        for title, year in [
            ("1959", 1959),
            ("1960", 1960),
            ("1969", 1969),
            ("1970", 1970),
        ]:
            make.item(title, artists=[a], categories=[rock], master_year=year)
        _, _, items, *_ = crunch(decade="1960s")
        assert [i.title for i in items[rock.id][a.id]] == ["1960", "1969"]

    def test_the_folder_filter_wins_over_the_decade(self, make):
        rock = make.category()
        a = make.artist()
        f = make.folder()
        make.item("Old", artists=[a], categories=[rock], folder=f, master_year=1960)
        make.item("New", artists=[a], categories=[rock], folder=f, master_year=2010)
        _, _, items, *_ = crunch(folder=f.id, decade="1960s")
        assert len(items[rock.id][a.id]) == 2

    def test_soundtracks_showtunes_and_edison_items_in_their_own_lists(self, make):
        sound = make.category("Soundtracks")
        shows = make.category("Showtunes")
        edison = make.category("Edison Diamond Disc")
        a = make.artist()
        make.item("The Zed", artists=[a], categories=[sound])
        make.item("Alpha", artists=[a], categories=[sound])
        make.item("Hair", artists=[a], categories=[shows])
        make.item(
            "Late", artists=[a], categories=[edison], item_notes="slot 4 Bottom drawer"
        )
        make.item(
            "Early", artists=[a], categories=[edison], item_notes="slot 9 Top drawer"
        )
        _, _, _, soundtracks, showtunes, edisons = crunch()
        assert [i.title for i in soundtracks] == ["Alpha", "The Zed"]
        assert [i.title for i in showtunes] == ["Hair"]
        assert [i.title for i in edisons] == ["Early", "Late"]

    def test_no_master_items_are_listed_once_each_in_the_same_year(self, make):
        rock = make.category()
        a = make.artist()
        make.item(
            "One", artists=[a], categories=[rock], master_id=None, master_year=1990
        )
        make.item(
            "Two", artists=[a], categories=[rock], master_id=None, master_year=1990
        )
        _, _, items, *_ = crunch()
        assert sorted(i.title for i in items[rock.id][a.id]) == ["One", "Two"]

    def test_no_master_items_from_different_years_are_repeated_bug_10(self, make):
        # #10 (the "no master fix" todo): the no-master items share one entry
        # in `releases` but each year adds a `masters` entry, and every one of
        # them lists all the artist's no-master items again.
        rock = make.category()
        a = make.artist()
        make.item(
            "One", artists=[a], categories=[rock], master_id=None, master_year=1980
        )
        make.item(
            "Two", artists=[a], categories=[rock], master_id=None, master_year=1990
        )
        _, _, items, *_ = crunch()
        assert sorted(i.title for i in items[rock.id][a.id]) == [
            "One",
            "One",
            "Two",
            "Two",
        ]

    @pytest.mark.xfail(strict=True, reason="#10: no-master items are repeated")
    def test_no_master_items_from_different_years_are_listed_once(self, make):
        rock = make.category()
        a = make.artist()
        make.item(
            "One", artists=[a], categories=[rock], master_id=None, master_year=1980
        )
        make.item(
            "Two", artists=[a], categories=[rock], master_id=None, master_year=1990
        )
        _, _, items, *_ = crunch()
        assert [i.title for i in items[rock.id][a.id]] == ["One", "Two"]

    def test_an_edison_item_without_a_slot_breaks_crunch_bug_10(self, make):
        edison = make.category("Edison Diamond Disc")
        make.item(
            "Slotted",
            artists=[make.artist()],
            categories=[edison],
            item_notes="slot 1 Top drawer",
        )
        make.item(
            "Unslotted",
            artists=[make.artist()],
            categories=[edison],
            item_notes="no idea",
        )
        with pytest.raises(AttributeError):
            crunch()

    @pytest.mark.xfail(strict=True, reason="#10: an Edison item without a slot raises")
    def test_an_edison_item_without_a_slot_is_listed_last(self, make):
        edison = make.category("Edison Diamond Disc")
        a = make.artist()
        make.item("Unslotted", artists=[a], categories=[edison], item_notes="no idea")
        make.item(
            "Slotted", artists=[a], categories=[edison], item_notes="slot 1 Top drawer"
        )
        *_, edisons = crunch()
        assert [i.title for i in edisons] == ["Slotted", "Unslotted"]

    def test_queries_grow_with_the_number_of_artists_bug_10(self, db, make, app):
        # #10: one query per category, plus one per category and artist.
        rock = make.category()
        for n in range(3):
            make.item(f"I{n}", artists=[make.artist(f"A{n}")], categories=[rock])
        few = count_queries(db, crunch)
        for n in range(3, 8):
            make.item(f"I{n}", artists=[make.artist(f"A{n}")], categories=[rock])
        many = count_queries(db, crunch)
        assert many > few

    @pytest.mark.xfail(strict=True, reason="#10: one query per artist")
    def test_a_fixed_number_of_queries_whatever_the_size(self, db, make):
        rock = make.category()
        for n in range(3):
            make.item(f"I{n}", artists=[make.artist(f"A{n}")], categories=[rock])
        few = count_queries(db, crunch)
        for n in range(3, 8):
            make.item(f"I{n}", artists=[make.artist(f"A{n}")], categories=[rock])
        assert count_queries(db, crunch) == few


def count_queries(db, fn):
    db.session.expire_all()
    seen = []

    def count(*args):
        seen.append(1)

    event.listen(db.engine, "before_cursor_execute", count)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", count)
    return len(seen)


class TestIndexPage:
    def test_counts_per_folder_category_and_decade(self, admin, make):
        f1, f2 = make.folder("Alphabetical"), make.folder("45s", counts_as_lp=False)
        rock, jazz = make.category("Rock"), make.category("Jazz")
        a = make.artist()
        make.item("A", artists=[a], folder=f1, categories=[rock], master_year=1965)
        make.item(
            "B", artists=[a], folder=f1, categories=[rock, jazz], master_year=1969
        )
        make.item("C", artists=[a], folder=f2, categories=[jazz], master_year=1971)
        soup = page(admin, "/printview/")
        tables = [
            {
                text(tr.select("td")[0]): text(tr.select("td")[1])
                for tr in t.select("tr")
            }
            for t in soup.select("table")
        ]
        assert tables == [
            {"45s": "1", "Alphabetical": "2"},
            {"Jazz": "2", "Rock": "2"},
            {"1960s": "2", "1970s": "1"},
        ]
        assert "Total LPs: 2" in text(soup)
        assert "Total releases: 3" in text(soup)

    def test_links_to_each_version(self, admin, make):
        f = make.folder("Alphabetical")
        c = make.category("Rock")
        make.item(
            "A", artists=[make.artist()], folder=f, categories=[c], master_year=1965
        )
        soup = page(admin, "/printview/")
        links = [a["href"] for a in soup.select(".container a")]
        assert links == [
            "/printview/all/",
            f"/printview/folder/{f.id}",
            f"/printview/category/{c.id}",
            "/printview/decade/1960s",
        ]

    def test_an_empty_collection(self, admin):
        soup = page(admin, "/printview/")
        assert "Total LPs: 0" in text(soup)
        assert soup.select("table tr") == []


class TestAllPage:
    @pytest.mark.parametrize("url", ["/printview/all", "/printview/all/"])
    def test_loads(self, admin, url):
        page(admin, url)

    def test_categories_artists_and_items_in_order(self, admin, make, folder):
        rock, jazz = make.category("Rock"), make.category("Jazz")
        beatles = make.artist("The Beatles", sort_name="Beatles, The")
        abba = make.artist("Abba")
        make.item(
            "Z",
            artists=[beatles],
            categories=[rock],
            folder=folder,
            master_id=2,
            master_year=1970,
        )
        make.item(
            "Y",
            artists=[beatles],
            categories=[rock],
            folder=folder,
            master_id=1,
            master_year=1965,
        )
        make.item("X", artists=[abba], categories=[rock], folder=folder)
        make.item("J", artists=[abba], categories=[jazz], folder=folder)
        soup = page(admin, "/printview/all")
        got = categories_on(soup)
        assert list(got) == ["Jazz", "Rock"]
        # Artists are headed by their name, but ordered by their sort name.
        assert [(a, [r[1] for r in rs]) for a, rs in got["Rock"]] == [
            ("Abba", ["X"]),
            ("The Beatles", ["Y", "Z"]),
        ]

    def test_the_title_and_contents_list_only_categories_with_items(
        self, admin, make, folder
    ):
        rock = make.category("Rock")
        make.category("Empty")
        make.category("Jazz")
        make.item("A", artists=[make.artist()], categories=[rock], folder=folder)
        soup = page(admin, "/printview/all")
        assert text(soup.select_one("h1")) == "Our Vinyl Collection"
        assert [text(li) for li in soup.select(".toc li")] == ["Rock"]
        assert list(categories_on(soup)) == ["Rock"]

    def test_a_single_category_has_no_contents_list(self, admin, make, folder):
        make.category("Rock")
        soup = page(admin, "/printview/all")
        assert soup.select(".contents") == []

    def test_a_category_with_no_items_has_no_block(self, admin, make):
        make.category("Empty")
        make.category("Also empty")
        soup = page(admin, "/printview/all")
        assert soup.select(".category-block") == []

    def test_an_empty_database(self, admin):
        r = admin.get("/printview/all")
        assert r.status_code == 200

    def test_year_is_the_master_year_or_else_the_release_year(
        self, admin, make, folder
    ):
        rock = make.category()
        a = make.artist()
        make.item(
            "Has master",
            artists=[a],
            categories=[rock],
            folder=folder,
            year=1990,
            master_year=1970,
        )
        make.item(
            "No master year",
            artists=[a],
            categories=[rock],
            folder=folder,
            year=1995,
            master_year=0,
        )
        soup = page(admin, "/printview/all")
        years = {t: y for _, rs in categories_on(soup)["Rock"] for y, t, _ in rs}
        assert years == {"Has master": "1970", "No master year": "1995"}

    def test_pressing_year_when_it_differs_from_the_master_year(
        self, admin, make, folder
    ):
        rock = make.category()
        a = make.artist()
        make.item(
            "Reissue",
            artists=[a],
            categories=[rock],
            folder=folder,
            year=1990,
            master_year=1970,
        )
        make.item(
            "Original",
            artists=[a],
            categories=[rock],
            folder=folder,
            year=1970,
            master_year=1970,
        )
        make.item(
            "Undated",
            artists=[a],
            categories=[rock],
            folder=folder,
            year=0,
            master_year=1970,
        )
        soup = page(admin, "/printview/all")
        notes = {t: n for _, rs in categories_on(soup)["Rock"] for _, t, n in rs}
        assert notes == {
            "Reissue": ["[1990 pressing]"],
            "Original": [],
            "Undated": ["[no press date]"],
        }

    def test_box_sets_mono_and_picture_discs_are_noted(self, admin, db, make, folder):
        from app.models import CollectionItemFormat

        rock = make.category()
        a = make.artist()
        item = make.item("Special", artists=[a], categories=[rock], folder=folder)
        item.formats = [
            CollectionItemFormat(name="Box Set", descriptions=[]),
            CollectionItemFormat(
                name="Vinyl", descriptions=["LP", "Mono", "Picture Disc"]
            ),
            CollectionItemFormat(name="Vinyl", descriptions=["Stereo"]),
        ]
        db.session.commit()
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(Box Set)", "(Mono)", "(Picture Disc)"]

    def test_the_page_dumps_the_data_into_a_comment_bug_10(self, admin, make, folder):
        # #10: every Print View sends the whole collection twice, the second
        # time in an HTML comment.
        rock = make.category("Rock")
        make.item(
            "Secret title", artists=[make.artist()], categories=[rock], folder=folder
        )
        html = admin.get("/printview/all").get_data(as_text=True)
        comment = re.search(r"<!--(.*?)-->", html, re.S).group(1)
        assert "Secret title" in comment
        assert "Rock" in comment

    def test_no_stylesheet_link_is_missing(self, admin):
        html = admin.get("/printview/all").get_data(as_text=True)
        assert "printview.css" in html


class TestFiledUnder:
    def test_ignored_artists_are_skipped(self, admin, make, folder):
        rock = make.category()
        shown = make.artist("Shown")
        ignored = make.artist("Ignored", ignore=True)
        make.item("Both", artists=[shown, ignored], categories=[rock], folder=folder)
        soup = page(admin, "/printview/all")
        assert [a for a, _ in categories_on(soup)["Rock"]] == ["Shown"]

    def test_an_item_is_listed_under_each_artist_that_is_not_ignored(
        self, admin, make, folder
    ):
        rock = make.category()
        a, b = make.artist("A"), make.artist("B")
        make.item("Split", artists=[a, b], categories=[rock], folder=folder)
        soup = page(admin, "/printview/all")
        assert [(a, [r[1] for r in rs]) for a, rs in categories_on(soup)["Rock"]] == [
            ("A", ["Split"]),
            ("B", ["Split"]),
        ]

    def test_an_item_with_only_ignored_artists_disappears_bug_10(
        self, admin, make, folder
    ):
        # #10: an item is only listed under artists that aren't ignored.
        rock = make.category()
        make.item(
            "Lost", artists=[make.artist(ignore=True)], categories=[rock], folder=folder
        )
        make.item(
            "Found", artists=[make.artist("Other")], categories=[rock], folder=folder
        )
        soup = page(admin, "/printview/all")
        assert titles(soup, "Rock") == ["Found"]

    @pytest.mark.xfail(strict=True, reason="#10: items of ignored artists vanish")
    def test_an_item_with_only_ignored_artists_is_listed_under_one(
        self, admin, make, folder
    ):
        rock = make.category()
        make.item(
            "Lost", artists=[make.artist(ignore=True)], categories=[rock], folder=folder
        )
        soup = page(admin, "/printview/all")
        assert titles(soup, "Rock") == ["Lost"]

    def test_an_item_whose_only_artist_is_ignored_leaves_no_category_block(
        self, admin, make, folder
    ):
        rock = make.category()
        make.item(
            "Lost", artists=[make.artist(ignore=True)], categories=[rock], folder=folder
        )
        soup = page(admin, "/printview/all")
        # The category has artists, so it has a (blank) block and a contents entry.
        assert categories_on(soup) == {"Rock": []}

    def test_filed_under_another_artist_adds_a_line(self, admin, make, folder):
        rock = make.category()
        a, b = make.artist("A"), make.artist("Boss")
        make.item("Moved", artists=[a], categories=[rock], folder=folder, filed_under=b)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(filed under Boss)"]

    def test_filed_under_the_artist_shown_adds_no_line(self, admin, make, folder):
        rock = make.category()
        a, b = make.artist("A"), make.artist("B")
        make.item(
            "Same", artists=[a, b], categories=[rock], folder=folder, filed_under=a
        )
        soup = page(admin, "/printview/all")
        got = dict(categories_on(soup)["Rock"])
        assert got["A"][0][2] == []
        assert got["B"][0][2] == ["(filed under A)"]

    def test_filed_under_uses_the_sort_name(self, admin, make, folder):
        rock = make.category()
        a = make.artist("A")
        b = make.artist("The Boss", sort_name="Boss, The")
        make.item("Moved", artists=[a], categories=[rock], folder=folder, filed_under=b)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(filed under Boss, The)"]

    def test_the_folder_is_named_when_it_is_not_alphabetical(self, admin, make):
        rock = make.category()
        other = make.folder("Box")
        make.item("Boxed", artists=[make.artist()], categories=[rock], folder=other)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(filed under Box)"]

    @pytest.mark.parametrize("name", ["Christmas", "Halloween"])
    def test_the_folder_is_named_for_some_categories_even_if_alphabetical(
        self, admin, make, folder, name
    ):
        c = make.category(name)
        make.item("Song", artists=[make.artist()], categories=[c], folder=folder)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)[name][0][1]
        assert notes == ["(filed under Alphabetical)"]

    def test_the_folder_is_named_for_various_artists(self, admin, make, folder):
        rock = make.category()
        various = make.artist("Various", sort_name="Various Artists")
        make.item("Comp", artists=[various], categories=[rock], folder=folder)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(filed under Alphabetical)"]

    def test_an_item_without_a_folder_is_named_as_filed_under_nothing(
        self, admin, make
    ):
        rock = make.category()
        make.item("Loose", artists=[make.artist()], categories=[rock], folder=None)
        soup = page(admin, "/printview/all")
        ((_, _, notes),) = categories_on(soup)["Rock"][0][1]
        assert notes == ["(filed under None)"]


class TestSpecialSections:
    def test_soundtracks(self, admin, make, folder):
        sound = make.category("Soundtracks")
        other = make.folder("Box")
        in_soundtracks = make.folder("Soundtracks")
        a, b = make.artist("Composer"), make.artist("Singer")
        make.item(
            "The Zed",
            artists=[a],
            categories=[sound],
            folder=in_soundtracks,
            year=1980,
            master_year=1980,
        )
        make.item(
            "Alpha",
            artists=[a, b],
            categories=[sound],
            folder=other,
            year=1999,
            master_year=1970,
            filed_under=b,
        )
        soup = page(admin, "/printview/all")
        assert soup.select(".artist-block") == []
        got = special_items(soup)
        assert [g[:3] for g in got] == [
            ("1970", "Alpha", "Composer, Singer"),
            ("1980", "The Zed", "Composer"),
        ]
        assert got[0][3] == [
            "[1999 pressing]",
            "(filed under Box)",
            "(filed under Singer)",
        ]
        # Filed in a Soundtracks folder, or not at all, it's unremarkable.
        assert got[1][3] == []

    def test_soundtracks_alphabetical_folder_is_named_unless_soundtracks(
        self, admin, make, folder
    ):
        sound = make.category("Soundtracks")
        make.item("Alpha", artists=[make.artist()], categories=[sound], folder=folder)
        soup = page(admin, "/printview/all")
        assert special_items(soup)[0][3] == ["(filed under Alphabetical)"]

    def test_showtunes_always_name_the_folder(self, admin, make, folder):
        shows = make.category("Showtunes")
        make.item(
            "Hair", artists=[make.artist("Cast")], categories=[shows], folder=folder
        )
        make.item(
            "Cats",
            artists=[make.artist("Cats cast")],
            categories=[shows],
            folder=folder,
            filed_under=make.artist("Boss"),
        )
        soup = page(admin, "/printview/all")
        assert special_items(soup) == [
            (
                "2000",
                "Cats",
                "Cats cast",
                ["(filed under Alphabetical)", "(filed under Boss)"],
            ),
            ("2000", "Hair", "Cast", ["(filed under Alphabetical)"]),
        ]

    def test_edison_diamond_discs_are_listed_by_slot_with_their_notes(
        self, admin, make, folder
    ):
        edison = make.category("Edison Diamond Disc")
        a = make.artist("Edison Artist")
        make.item(
            "Bottom",
            artists=[a],
            categories=[edison],
            folder=folder,
            item_notes="slot 2 Bottom drawer",
            year=1920,
            master_year=1920,
        )
        make.item(
            "Top",
            artists=[a],
            categories=[edison],
            folder=folder,
            item_notes="slot 5 Top drawer",
            year=1925,
            master_year=1921,
        )
        soup = page(admin, "/printview/all")
        assert special_items(soup) == [
            (
                "1921",
                "Top",
                "Edison Artist",
                ["[1925 pressing]", "(filed in slot 5 Top drawer)"],
            ),
            (
                "1920",
                "Bottom",
                "Edison Artist",
                ["(filed in slot 2 Bottom drawer)"],
            ),
        ]

    def test_a_special_category_with_no_items_falls_back_to_the_normal_layout(
        self, admin, make, folder
    ):
        make.category("Soundtracks")
        soup = page(admin, "/printview/all")
        # No items, so no artists either: nothing at all.
        assert soup.select(".category-block") == []

    def test_an_edison_item_without_a_slot_breaks_the_page_bug_10(
        self, admin, make, folder
    ):
        edison = make.category("Edison Diamond Disc")
        make.item(
            "Unslotted",
            artists=[make.artist()],
            categories=[edison],
            folder=folder,
            item_notes="no idea",
        )
        assert admin.get("/printview/all").status_code == 500


class TestFolderPage:
    def test_lists_only_that_folders_items(self, admin, make):
        rock = make.category("Rock")
        f1, f2 = make.folder("One"), make.folder("Two")
        a = make.artist()
        make.item("In one", artists=[a], categories=[rock], folder=f1)
        make.item("In two", artists=[a], categories=[rock], folder=f2)
        soup = page(admin, f"/printview/folder/{f2.id}")
        assert titles(soup, "Rock") == ["In two"]

    def test_the_title_names_the_folder(self, admin, make):
        make.category("Rock")
        make.category("Jazz")
        f = make.folder("Box")
        soup = page(admin, f"/printview/folder/{f.id}")
        assert text(soup.select_one("h1")) == "Folder: Box"

    def test_an_unknown_folder_is_not_found(self, admin):
        assert admin.get("/printview/folder/999").status_code == 404

    def test_a_folder_with_no_items(self, admin, make):
        make.category("Rock")
        f = make.folder("Empty")
        soup = page(admin, f"/printview/folder/{f.id}")
        assert soup.select(".category-block") == []


class TestCategoryPage:
    def test_lists_only_that_category(self, admin, make, folder):
        rock, jazz = make.category("Rock"), make.category("Jazz")
        a = make.artist()
        make.item("R", artists=[a], categories=[rock], folder=folder)
        make.item("J", artists=[a], categories=[jazz], folder=folder)
        soup = page(admin, f"/printview/category/{jazz.id}")
        assert list(categories_on(soup)) == ["Jazz"]

    def test_a_single_category_has_no_title_or_contents(self, admin, make):
        rock = make.category("Rock")
        make.category("Jazz")
        soup = page(admin, f"/printview/category/{rock.id}")
        assert soup.select(".contents") == []

    def test_an_unknown_category_is_not_found(self, admin):
        assert admin.get("/printview/category/999").status_code == 404

    def test_a_special_category(self, admin, make, folder):
        sound = make.category("Soundtracks")
        make.item("Alpha", artists=[make.artist()], categories=[sound], folder=folder)
        soup = page(admin, f"/printview/category/{sound.id}")
        assert [g[1] for g in special_items(soup)] == ["Alpha"]


class TestDecadePage:
    def test_lists_only_that_decade(self, admin, make, folder):
        rock = make.category("Rock")
        a = make.artist()
        make.item(
            "Sixties", artists=[a], categories=[rock], folder=folder, master_year=1965
        )
        make.item(
            "Seventies", artists=[a], categories=[rock], folder=folder, master_year=1975
        )
        soup = page(admin, "/printview/decade/1960s")
        assert titles(soup, "Rock") == ["Sixties"]

    def test_the_title_names_the_decade(self, admin, make):
        make.category("Rock")
        make.category("Jazz")
        soup = page(admin, "/printview/decade/1960s")
        assert text(soup.select_one("h1")) == "Decade: 1960s"

    def test_a_decade_with_no_items(self, admin, make):
        make.category("Rock")
        soup = page(admin, "/printview/decade/1930s")
        assert soup.select(".category-block") == []

    def test_a_decade_that_is_not_one_fails(self, admin, make):
        make.category("Rock")
        assert admin.get("/printview/decade/nope").status_code == 500


class TestAccess:
    @pytest.mark.parametrize(
        "url",
        [
            "/printview/",
            "/printview/all",
            "/printview/folder/1",
            "/printview/decade/1960s",
        ],
    )
    def test_the_pages_need_no_sign_in(self, client, make, url):
        # Pinned as it is today: PrintView's views have no @has_access.
        make.folder("Alphabetical")
        assert client.get(url).status_code == 200
