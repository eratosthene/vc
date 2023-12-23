#!/usr/bin/env python3.10

import discogs_client
from mongoengine import *

class CollectionItem(Document):
    instance_id = IntField(required=True, unique=True)
    release_id  = IntField(required=True)
    title       = StringField(required=True)
    year        = IntField()
    artists     = ListField(ReferenceField('Artist'), required=True)
    genres      = ListField(ReferenceField('Genre'))
    styles      = ListField(ReferenceField('Style'))
    master_id   = IntField(required=True)
    master_year = IntField()
    categories  = ListField(ReferenceField('Category'))
    folder      = ReferenceField('Folder')
    filed_under = ReferenceField('Artist')
    formats     = ListField(DictField())
    notes       = ListField(DictField())
    released    = StringField()

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return self.title

    def category_list(self):
        return Markup(
            'asdfasdf'
        )

class Artist(Document):
    artist_id   = IntField(required=True, unique=True)
    name        = StringField(required=True)
    sort_name   = StringField()
    ignore      = BooleanField()

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

class Genre(Document):
    name        = StringField(required=True, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Style(Document):
    name        = StringField(required=True, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Category(Document):
    name        = StringField(required=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Folder(Document):
    folder_id   = IntField(required=True, unique=True)
    name        = StringField(required=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

connect(host="mongodb://192.168.1.10:27017/vc")
d = discogs_client.Client('discogs_exporter/1.0', user_token='mKcjGwCgWFqbkNslaNqLIVdfooQTWLAEfYyTkGts')
me = d.identity()
for item in me.collection_folders[0].releases:
    print(item)
    print("instance_id: "+str(item.instance_id))
    folder = Folder.objects().get(folder_id=item.folder_id)
    print(folder)
    artists = []
    genres = []
    styles = []
    for artist in item.release.artists:
        try:
            adoc = Artist.objects().get(artist_id=artist.id)
        except DoesNotExist:
            sn = ""
            n=artist.name
            if n.startswith("The "):
                sn = n.removeprefix("The ") + ", The"
                print("Replacing /"+n+"/ with /"+sn+"/")
            adoc = Artist(
                    artist_id = artist.id,
                    name = artist.name,
                    sort_name = sn
                    )
            adoc.save()
        artists.append(adoc)
    for genre in item.release.genres:
        try:
            gdoc = Genre.objects().get(name=genre)
        except DoesNotExist:
            gdoc = Genre(name = genre)
            gdoc.save()
        genres.append(gdoc)
    for style in item.release.styles:
        try:
            sdoc = Style.objects().get(name=style)
        except DoesNotExist:
            sdoc = Style(name = style)
            sdoc.save()
        styles.append(sdoc)
#    input()
    master_id = 0
    master_year = item.release.year
    if item.release.master:
        master_id = item.release.master.id
        master_year = item.release.master.year
    collection_item = CollectionItem.objects(instance_id=item.instance_id).modify(
            upsert = True,
            new = True,
            set__instance_id = item.instance_id,
            set__release_id = item.release.id,
            set__title = item.release.title,
            set__year = item.release.year,
            set__artists = artists,
            set__genres = genres,
            set__styles = styles,
            set__master_id = master_id,
            set__folder = folder,
            set__formats = item.release.formats,
            set__notes = item.notes,
            set__released = item.release.fetch('released')
            )
    collection_item.save()
    print(collection_item)
