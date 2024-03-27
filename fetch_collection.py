#!/usr/bin/env python3.10

import discogs_client
from mongoengine import *
import sys
sys.path.insert(0, 'app')
from models import *
import argparse

parser = argparse.ArgumentParser(description='Import data from discogs collection to VC. Default action is to only import new items.')
parser.add_argument('-f', '--full', action='store_true', help='Full import, overwriting any existing values. Use with caution.')
parser.add_argument('-n', '--notes', action='store_true', help='Import notes only, overwriting any existing values.')
args = parser.parse_args()
connect(host="mongodb://192.168.1.10:27017/vc")
d = discogs_client.Client('discogs_exporter/1.0', user_token='mKcjGwCgWFqbkNslaNqLIVdfooQTWLAEfYyTkGts')
me = d.identity()
for item in me.collection_folders[0].releases:
    print(item)
    print("instance_id: "+str(item.instance_id))
    if not CollectionItem.objects(instance_id=item.instance_id) or args.full or args.notes:
        if args.notes:
            print('Updating notes for existing item')
            collection_item = CollectionItem.objects(instance_id=item.instance_id).modify(
                    set__notes = item.notes,
                    )
            collection_item.save()
            print(collection_item)
        else:
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
            master_id = 0
            master_year = item.release.year
            if item.release.master:
                master_id = item.release.master.id
                master_year = item.release.master.year
            if args.full:
                print('Full import of existing item')
            else:
                print('Inserting new item')
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
                    set__master_year = master_year,
                    set__folder = folder,
                    set__formats = item.release.formats,
                    set__notes = item.notes,
                    set__released = item.release.fetch('released')
                    )
            collection_item.save()
            print(collection_item)
    else:
        print('Skipped.')
