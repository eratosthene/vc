import logging
from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Folder, Category, Artist, Genre, Style, MediaCondition, SleeveCondition
from flask import redirect, current_app, request
from mongoengine import DoesNotExist
import discogs_client
import bson
import re

logger = logging.getLogger()

def add_discogs_release(item):
    folder = Folder.objects().get(folder_id=item.folder_id)
    artists = []
    genres = []
    styles = []
    notes = []
    for artist in item.release.artists:
        try:
            adoc = Artist.objects().get(artist_id=artist.id)
        except DoesNotExist:
            sn = ""
            n=artist.name
            if n.startswith("The "):
                sn = n.removeprefix("The ") + ", The"
                logger.debug("Replacing /"+n+"/ with /"+sn+"/")
            adoc = Artist(
                    artist_id = artist.id,
                    name = artist.name,
                    sort_name = sn
                    )
            adoc.save()
            logger.info('Adding artist ' + str(adoc))
        artists.append(adoc)
    for genre in item.release.genres:
        try:
            gdoc = Genre.objects().get(name=genre)
        except DoesNotExist:
            gdoc = Genre(name = genre)
            gdoc.save()
            logger.info('Adding genre ' + str(gdoc))
        genres.append(gdoc)
    for style in item.release.styles:
        try:
            sdoc = Style.objects().get(name=style)
        except DoesNotExist:
            sdoc = Style(name = style)
            sdoc.save()
            logger.info('Adding style ' + str(sdoc))
        styles.append(sdoc)
    mc = None
    sc = None
    n = None
    l = None
    i = None
    for note in item.notes:
        if note['field_id'] == 1:
            try:
                mc = MediaCondition.objects().get(label=note['value'].rstrip())
            except DoesNotExist:
                mc = MediaCondition(label=note['value'].rstrip())
                mc.save()
                logger.info('Adding media condition ' + str(mc))
        if note['field_id'] == 2:
            try:
                sc = SleeveCondition.objects().get(label=note['value'].rstrip())
            except DoesNotExist:
                sc = SleeveCondition(label=note['value'].rstrip())
                sc.save()
                logger.info('Adding sleeve condition ' + str(sc))
        if note['field_id'] == 3:
            n = note['value'].rstrip()
        if note['field_id'] == 4:
            if note['value'].rstrip() == 'Yes':
                l = True
            else:
                l = False
        if note['field_id'] == 5:
            i = note['value'].rstrip()
    master_id = 0
    master_year = item.release.year
    if item.release.master:
        master_id = item.release.master.id
        master_year = item.release.master.year
    collection_item = CollectionItem.objects(instance_id=item.instance_id).modify(
            upsert = True,
            new = True,
            set__release_id = item.release.id,
            set__instance_id = item.instance_id,
            set__title = item.release.title,
            set__year = item.release.year,
            set__artists = artists,
            set__genres = genres,
            set__styles = styles,
            set__master_id = master_id,
            set__master_year = master_year,
            set__formats = item.release.formats,
            set__released = item.release.fetch('released'),
            set__folder = folder,
            set__media_condition = mc,
            set__sleeve_condition = sc,
            set__item_notes = n,
            set__listened = l,
            set__includes = i
            )
    collection_item.save()
    logger.debug(collection_item)

class MyIndexView(IndexView):
    index_template = "index.html"

    @expose('/unlistened_lp')
    def unlistened_lp(self):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"listened": False},
                    {"folder": {"$ne": bson.objectid.ObjectId("658240b5fe0b918a7c829f7c")}},
                    {"folder": {"$ne": bson.objectid.ObjectId("66403dc17ebe177e316c5a00")}},
                    {"folder": {"$ne": bson.objectid.ObjectId("66be46fbf1094eb6ef18c2da")}}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/random_lp')
    def random_lp(self):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"folder": {"$ne": bson.objectid.ObjectId("658240b5fe0b918a7c829f7c")}},
                    {"folder": {"$ne": bson.objectid.ObjectId("66403dc17ebe177e316c5a00")}},
                    {"folder": {"$ne": bson.objectid.ObjectId("66be46fbf1094eb6ef18c2da")}}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/unlistened_release')
    def unlistened_release(self):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                    {"listened": False}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/random_release')
    def random_release(self):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/unlistened_folder/<string:folder>')
    def unlistened_folder(self, folder):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"listened": False},
                    {"folder": bson.objectid.ObjectId(folder)}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/random_folder/<string:folder>')
    def random_folder(self, folder):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"folder": bson.objectid.ObjectId(folder)}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/unlistened_category/<string:category>')
    def unlistened_category(self, category):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"listened": False},
                    {"categories": bson.objectid.ObjectId(category)}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/random_category/<string:category>')
    def random_category(self, category):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"categories": bson.objectid.ObjectId(category)}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/unlistened_decade/<string:decade>')
    def unlistened_decade(self, decade):
        self.update_redirect()
        after = int(decade[:-1])-1
        before = int(decade[:-1])+10
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"listened": False},
                    {"master_year": {"$gt": after}},
                    {"master_year": {"$lt": before}}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/random_decade/<string:decade>')
    def random_decade(self, decade):
        self.update_redirect()
        after = int(decade[:-1])-1
        before = int(decade[:-1])+10
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"master_year": {"$gt": after}},
                    {"master_year": {"$lt": before}}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/syncdiscogs')
    def syncdiscogs(self):
        self.update_redirect()
        logger.info('Updating discogs...')
        d = discogs_client.Client(current_app.config['DISCOGS_SETTINGS']['USER_AGENT'], user_token=current_app.config['DISCOGS_SETTINGS']['USER_TOKEN'])
        me = d.identity()
        releases = me.collection_folders[0].releases
        local_releases = CollectionItem.objects()
        logger.info('Total releases: ' + str(len(releases)))
        logger.info('Total local releases: ' + str(len(local_releases)))
        for item in releases:
            logger.debug('Checking discogs: ' + str(item))
            if not CollectionItem.objects(instance_id=item.instance_id):
                logger.info('Adding ' + str(item))
                add_discogs_release(item)
                
        for item in local_releases:
            logger.debug('Checking local: ' + str(item))
            if not any(x.instance_id == item.instance_id for x in releases):
                logger.info('Removing ' + str(item))
                item.delete()
        
        ref = request.referrer
        if ref:
            return redirect(ref)
        else:
            return redirect('/collectionmodelview/list/')

    @expose('/syncdiscogsnotes')
    def syncdiscogsnotes(self):
        self.update_redirect()
        logger.info('Updating discogs notes...')
        d = discogs_client.Client(current_app.config['DISCOGS_SETTINGS']['USER_AGENT'], user_token=current_app.config['DISCOGS_SETTINGS']['USER_TOKEN'])
        me = d.identity()
        releases = me.collection_folders[0].releases
        logger.info('Total releases: ' + str(len(releases)))
        for item in releases:
            logger.info('Updating notes for '+str(item))
            mc = None
            sc = None
            n = None
            l = None
            i = None
            for note in item.notes:
                if note['field_id'] == 1:
                    try:
                        mc = MediaCondition.objects().get(label=note['value'].rstrip())
                    except DoesNotExist:
                        mc = MediaCondition(label=note['value'].rstrip())
                        mc.save()
                        logger.info('Adding media condition ' + str(mc))
                if note['field_id'] == 2:
                    try:
                        sc = SleeveCondition.objects().get(label=note['value'].rstrip())
                    except DoesNotExist:
                        sc = SleeveCondition(label=note['value'].rstrip())
                        sc.save()
                        logger.info('Adding sleeve condition ' + str(sc))
                if note['field_id'] == 3:
                    n = note['value'].rstrip()
                if note['field_id'] == 4:
                    if note['value'].rstrip() == 'Yes':
                        l = True
                    else:
                        l = False
                if note['field_id'] == 5:
                    i = note['value'].rstrip()
            collection_item = CollectionItem.objects(instance_id=item.instance_id).modify(
                    set__media_condition = mc,
                    set__sleeve_condition = sc,
                    set__item_notes = n,
                    set__listened = l,
                    set__includes = i
                    )
            collection_item.save()
        
        ref = request.referrer
        if ref:
            return redirect(ref)
        else:
            return redirect('/collectionmodelview/list/')

    @expose('/')
    def index(self):
        self.update_redirect()
        lp_total = 0
        full_total = CollectionItem.objects().count()
        by_folder = []
        by_category = []
        by_decade = []
        for f in Folder.objects().order_by('name'):
            c = CollectionItem.objects(folder=f.id).count()
            by_folder.append({'folder': f, 'total': c})
            if f.name != 'Edison Diamond Disc' and f.name != '45s':
                lp_total += c
        for f in Category.objects().order_by('name'):
            c = CollectionItem.objects(categories=f.id).count()
            by_category.append({'category': f, 'total': c})
        dc = CollectionItem.objects().aggregate([
            {"$match": {
                "master_year": {"$gt": 0}
            }},
            { "$group": {
                "_id": {
                    "decade": { "$concat": [ { "$substr": [ {"$toString": "$master_year"}, 0, 3 ] } , "0s" ] }
                },
                "count": { "$sum": {"$toInt": 1} }
            }},
            {"$sort": {
                "_id": 1
            }}
        ])
        for d in dc:
            decade = d['_id']['decade']
            by_decade.append({'decade': decade, 'count': d['count']})
        return self.render_template(self.index_template,
                appbuilder=self.appbuilder,
                lp_total=lp_total,
                full_total=full_total,
                by_folder=by_folder,
                by_category=by_category,
                by_decade=by_decade)

