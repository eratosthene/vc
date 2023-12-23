#!/usr/bin/env python

import discogs_client
d = discogs_client.Client('discogs_exporter/1.0', user_token='mKcjGwCgWFqbkNslaNqLIVdfooQTWLAEfYyTkGts')
me = d.identity()
#print(me)
#print(me.collection_folders)
#ri = me.collection_items(2936214)
#ri = me.collection_items(528627)
#ri = me.collection_items(8984021)
#ri = me.collection_items(4168642)
ri = me.collection_items(1017762)
#ri = me.collection_items(22253038)
#ri = me.collection_items(8677931)
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
    print('Formats:')
    print(i.release.formats)
    print('Year: '+str(i.release.year))
    print(i.release.fetch('released'))
    print(i.release.fetch('released_formatted'))
    print(i.release.master)
    print('Master Year: '+str(i.release.master.year))
    print(i.release.master.main_release)
    print(i.release.master.main_release.fetch('released'))
    print(i.notes)
    for f in me.collection_folders:
        if i.folder_id == f.id:
            print('Folder: ['+str(i.folder_id)+'] '+f.name)
#        else:
#            print('Folder: ['+str(f.id)+'] '+f.name)

