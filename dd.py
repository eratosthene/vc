#!/usr/bin/env python

import discogs_client
d = discogs_client.Client('discogs_exporter/1.0', user_token='mKcjGwCgWFqbkNslaNqLIVdfooQTWLAEfYyTkGts')
me = d.identity()
#print(me)
#print(me.collection_folders)
ri = me.collection_items(8677931)
#ri = me.collection_items(7698859)
for i in ri:
    print(i)
    print(i.instance_id)
    print(i.release)
    print('Artists:')
    print(i.release.artists)
    print('Genres:')
    print(i.release.genres)
    print('Styles:')
    print(i.release.styles)
    print('Year: '+str(i.release.year))
    print(i.release.master)
    print('Master Year: '+str(i.release.master.year))
    print(i.notes)
    for f in me.collection_folders:
        if i.folder_id == f.id:
            print('-->Folder: ['+str(i.folder_id)+'] '+f.name)
        else:
            print('Folder: ['+str(f.id)+'] '+f.name)

