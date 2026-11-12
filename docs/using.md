# Using vc

What the app does and how to use it. To run it, see
[Developing vc](development.md) or [Running vc in production](production.md).

Sign in with a user the app has (the admin user, to begin with). The home
page, its random links and the Print View don't need a sign-in; everything
else does.

## The collection

**Manage > Collection** lists every item in your Discogs collection, with
its artists, title, master year, categories, genres, styles, folder and Filed
Under. Click an item for everything else: the Discogs release and master
ids (linked to Discogs), its formats, condition, notes, Listened and Includes.

Most of an item comes from Discogs, and the next sync puts it back if you
change it here. What's yours to change is described below. The sync adds items
and removes any Discogs no longer has, so it's not the place to keep one that
isn't in your Discogs collection.

### Categorizing items

**Categorize** is a list of the items with one thing to edit: their
categories. Give an item as many as you like. The Print View lists an item
under each of its categories, and an item with none isn't in the Print View at
all.

The edit button opens the categories in a small window over the list. Save
changes just that row. The page, sort and place on the page stay as they were.
If the window can't open, or the save fails in some way other than a mistake in
the form, the edit button takes you to the usual edit page instead.

**Manage > Categories** adds, renames and deletes the categories themselves.
Genres and styles come from Discogs, and the sync adds the ones it finds.

### Print Subtitle

Discogs gives some releases the same title, such as Weezer's three
self-titled albums, so on the Print View they can't be told apart. **Print
Subtitle** is an optional short text (up to 100 characters) on an item, in
Manage > Collection's edit form. The Print View shows it after the title:
"Weezer (Blue Album)". The sync never changes it.

Without one, the Print View adds text of its own when it has to: see "Same
title" under the Print View below.

### Sort names, and Ignore

**Manage > Artists** lists the artists. Each has:

- **Name**: what vc prints. A new artist's name is Discogs's with the number
  Discogs adds to tell artists of one name apart taken off: "Prince (2)"
  becomes "Prince".
- **Sort name**: what the Print View sorts and lists by. A new artist named
  "The Beatles" gets "Beatles, The"; any other new artist has none, and sorts
  by its name. Set one for the rest, such as "Cash, Johnny".
- **Ignore**: leaves the artist out of the Print View, so a release isn't listed
  under, say, a guest or a producer. If every artist on an item is ignored, the
  item is still listed under one of them, so it isn't missing: the one it's
  filed under, or else the first by sort name.

The sync adds new artists but never renames or changes an existing one.

### Filed Under

An item's **Filed Under** is an artist, for an item that lives on your shelf
under someone other than the artists Discogs lists, such as a compilation
filed under one of the artists. The Print View adds "(filed under X)" to it
whenever the artist it's listed under isn't X.

### Folders

**Manage > Folders** lists the folders the sync found on Discogs. Their names
come from Discogs. **Counts As LP** is yours: switch it off for folders that
hold something that isn't an LP, such as 45s, and the home page leaves them
out of Total LPs and its random LP links.

## The Discogs notes vc reads

vc reads five of the notes fields on each item in Discogs, by their number in
Discogs's collection settings:

| Field | What it is in Discogs            | What vc keeps                                 |
| ----- | -------------------------------- | --------------------------------------------- |
| 1     | Media Condition (Discogs's own)  | The media condition                           |
| 2     | Sleeve Condition (Discogs's own) | The sleeve condition                          |
| 3     | Notes (Discogs's own)            | The item's notes, as written                  |
| 4     | A custom field you add           | Listened: yes if it says `Yes`, else no       |
| 5     | A custom field you add           | Includes: what else comes with it, as written |

Fields 4 and 5 have to be the fourth and fifth fields in Discogs, in that
order; vc reads them by number, not by name. An item with no value for a field
has none in vc. Trailing spaces are dropped. Notes are also where the Print
View finds an Edison Diamond Disc's place (see below).

Edit these in Discogs, not vc: the next sync copies Discogs's values back.

## The home page

The home page shows the total number of items, and the total in folders that
count as LPs, with **Get random** and **Get random unlistened** links for
each. Below that it counts items per folder, per category and per decade of
the master's year, each with the same two links, and each name there links to
the Print View for it. An unlistened item is one whose Listened is no. An item
with no Listened value isn't counted as unlistened. The links go to a random
item's page, or give "Page not found" if nothing matches.

## The Print View

**Print View** in the menu opens its index: the same totals and counts, with a
link to each version of the page. It has no menu bar, to print cleanly. The
versions are:

- **All**: every item.
- **Folder**, **Category** and **Decade**: just the items in one folder, one
  category or one decade of master year. A decade like "1970s" holds the
  masters from 1970 to 1979, and items with no master year are in no decade.

Each version is laid out by category, in name order, with a contents list at
the top when there's more than one. Within a category, artists are listed by
sort name. Under an artist, the releases of one master are together, in order
of release, and the masters in order of year; a release with no master stands
alone. An item shows its year (the master's, or the release's when it has no
master), "Box Set", "Mono" and "Picture
Disc" where its formats have them, and "[1984 pressing]" when the pressing's
year differs from the master's.

A release says which folder it's filed in when it isn't in "Alphabetical", and
always does in the Christmas, Halloween and Soundtracks categories and under
an artist whose sort name is "Various Artists". It also says "filed under" for
Filed Under, as above.

**Same title.** When an artist has two or more releases with the same title in
one category, the page adds text from Discogs after the title of the ones it
can tell apart: the format's own text (such as "Blue Vinyl"), else the format
descriptions the releases don't all share (such as "Reissue"). "LP", "Album"
and 12" are never used, as every record has them. A release that has nothing
of its own gets nothing, so the rest of a group may look unchanged, and one
with a Print Subtitle shows that instead (and counts as a different title).
The order doesn't change. Catalogue numbers aren't stored, so aren't used; set
a Print Subtitle when Discogs has nothing that helps.

Three categories are laid out their own way, by name, so renaming one gives it
the normal layout:

- **Soundtracks** and **Showtunes**: one list by title ("The" ignored), with the
  artists after each title instead of before.
- **Edison Diamond Disc**: by place in the cabinet, read from each item's
  notes: "Top drawer" or "Bottom drawer" and "slot N", such as "Top drawer, slot
  12". Each item says "filed in" followed by its notes. One whose notes lack
  either part comes last.

## Syncing with Discogs

On **Manage > Collection**, **Sync** starts a sync in the background and
takes you to a page that shows its log as it goes. **Dry run** shows what a
sync would change without saving anything. Both need a signed-in user. The page
can be closed meanwhile: the sync keeps going, and you can start another
only when it's done.

A sync:

1. Adds the folders Discogs has, and renames the ones that changed.
2. Adds new items and updates the ones that changed on Discogs, notes
   included.
3. Removes the items that are gone from Discogs, and lists them in the summary
   at the end of the log.

It never touches what's kept only in vc: categories, Filed Under, an artist's
sort name and Ignore, and a folder's Counts As LP. Only one sync runs at a
time; start another from the web and you're taken to the running one. If the sync fails
partway, what it had already saved stays (it saves every 50 items), and
nothing is removed, so a failed run never looks like lots of removals.

The same thing is available from the command line, which is how to run it
from cron: [Syncing from the command line](production.md#syncing-from-the-command-line).
