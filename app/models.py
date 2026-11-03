from flask_appbuilder import Model
from markupsafe import Markup
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import relationship

# utf8mb4 on every table, whatever the database's default character set is, as
# artist and title names include non-Latin text.
TABLE_ARGS = {"mysql_charset": "utf8mb4"}

# Association tables for the many-to-many relationships. The artists table has a
# position, which keeps the order Discogs lists the artists in; see
# set_artists() for how it is filled in.
assoc_collection_item_artist = Table(
    "collection_item_artist",
    Model.metadata,
    Column(
        "collection_item_id",
        Integer,
        ForeignKey("collection_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("artist_id", Integer, ForeignKey("artist.id"), primary_key=True),
    Column("position", Integer, nullable=False, server_default="0"),
    **TABLE_ARGS,
)
assoc_collection_item_genre = Table(
    "collection_item_genre",
    Model.metadata,
    Column(
        "collection_item_id",
        Integer,
        ForeignKey("collection_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("genre_id", Integer, ForeignKey("genre.id"), primary_key=True),
    **TABLE_ARGS,
)
assoc_collection_item_style = Table(
    "collection_item_style",
    Model.metadata,
    Column(
        "collection_item_id",
        Integer,
        ForeignKey("collection_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("style_id", Integer, ForeignKey("style.id"), primary_key=True),
    **TABLE_ARGS,
)
assoc_collection_item_category = Table(
    "collection_item_category",
    Model.metadata,
    Column(
        "collection_item_id",
        Integer,
        ForeignKey("collection_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("category_id", Integer, ForeignKey("category.id"), primary_key=True),
    **TABLE_ARGS,
)


class MediaCondition(Model):
    __tablename__ = "media_condition"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False, unique=True)

    def __unicode__(self):
        return self.label

    def __repr__(self):
        return self.label


class SleeveCondition(Model):
    __tablename__ = "sleeve_condition"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False, unique=True)

    def __unicode__(self):
        return self.label

    def __repr__(self):
        return self.label


class Artist(Model):
    __tablename__ = "artist"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    discogs_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    sort_name = Column(String(255))
    ignore = Column(Boolean, nullable=False, default=False, server_default=false())

    def __unicode__(self):
        if self.sort_name:
            return self.sort_name
        else:
            return self.name

    def __repr__(self):
        if self.sort_name:
            return self.sort_name
        else:
            return self.name


class Genre(Model):
    __tablename__ = "genre"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name


class Style(Model):
    __tablename__ = "style"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name


class Category(Model):
    __tablename__ = "category"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name


class Folder(Model):
    __tablename__ = "folder"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    discogs_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    # Whether the folder's items count as LPs: in the LP total on the index
    # page, and in its random LP links.
    counts_as_lp = Column(Boolean, nullable=False, default=True, server_default=true())

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name


class CollectionItemFormat(Model):
    __tablename__ = "collection_item_format"
    __table_args__ = (UniqueConstraint("collection_item_id", "position"), TABLE_ARGS)
    id = Column(Integer, primary_key=True)
    collection_item_id = Column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE"), nullable=False
    )
    position = Column(Integer, nullable=False, default=0)
    name = Column(String(100), nullable=False)
    qty = Column(Integer)
    text = Column(String(255))
    descriptions = Column(JSON)

    def __unicode__(self):
        ret = ""
        if self.qty:
            ret = ret + str(self.qty) + "x "
        ret = ret + self.name
        if self.descriptions:
            ret = ret + " {"
            ret = ret + " ".join(self.descriptions)
            ret = ret + "}"
        if self.text:
            ret = ret + " (" + str(self.text) + ")"
        return ret

    def __repr__(self):
        return self.__unicode__()


class CollectionItem(Model):
    __tablename__ = "collection_item"
    __table_args__ = TABLE_ARGS
    id = Column(Integer, primary_key=True)
    instance_id = Column(BigInteger, nullable=False, unique=True)
    release_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    year = Column(Integer)
    released = Column(String(64))
    # Null when the release has no master.
    master_id = Column(Integer)
    master_year = Column(Integer, index=True)
    folder_id = Column(Integer, ForeignKey("folder.id"))
    filed_under_id = Column(Integer, ForeignKey("artist.id"))
    media_condition_id = Column(Integer, ForeignKey("media_condition.id"))
    sleeve_condition_id = Column(Integer, ForeignKey("sleeve_condition.id"))
    item_notes = Column(Text)
    listened = Column(Boolean)
    includes = Column(Text)

    artists = relationship(
        "Artist",
        secondary=assoc_collection_item_artist,
        order_by=[assoc_collection_item_artist.c.position, Artist.id],
    )
    genres = relationship("Genre", secondary=assoc_collection_item_genre)
    styles = relationship("Style", secondary=assoc_collection_item_style)
    categories = relationship("Category", secondary=assoc_collection_item_category)
    folder = relationship("Folder")
    filed_under = relationship("Artist", foreign_keys=[filed_under_id])
    media_condition = relationship("MediaCondition")
    sleeve_condition = relationship("SleeveCondition")
    formats = relationship(
        "CollectionItemFormat",
        order_by=CollectionItemFormat.position,
        cascade="all, delete-orphan",
    )

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return self.title

    def release_show(self):
        return Markup(
            '<a href="https://www.discogs.com/release/'
            + str(self.release_id)
            + '">'
            + str(self.release_id)
            + "</a>"
        )

    def master_show(self):
        if self.master_id is None:
            return ""
        return Markup(
            '<a href="https://www.discogs.com/master/'
            + str(self.master_id)
            + '">'
            + str(self.master_id)
            + "</a>"
        )


def set_artists(session, item, artists):
    """Set an item's artists, keeping the order they are given in.

    The order is kept in the association table's position column, which the
    relationship can't write, so the positions are written after a flush. An
    artist added in the Collection view's form gets position 0 and so sorts
    first, then by id; the order only matters for what the sync saves.
    """
    artists = list(artists)
    item.artists = artists
    session.flush()
    for position, artist in enumerate(artists):
        session.execute(
            assoc_collection_item_artist.update()
            .where(assoc_collection_item_artist.c.collection_item_id == item.id)
            .where(assoc_collection_item_artist.c.artist_id == artist.id)
            .values(position=position)
        )
    session.expire(item, ["artists"])
