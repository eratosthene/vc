import logging
from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Folder, Category
from flask import redirect
import bson
import re

class MyIndexView(IndexView):
    index_template = "index.html"

    @expose('/unlistened_lp')
    def unlistened_lp(self):
        self.update_redirect()
        docs = CollectionItem.objects().aggregate([
            {"$match":
                {"$and": [
                    {"notes": {"$elemMatch": {"field_id":4, "value":'No'}}},
                    {"folder": {"$ne": bson.objectid.ObjectId("658240b5fe0b918a7c829f7c")}}
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
                    {"notes": {"$elemMatch": {"field_id":4, "value":'No'}}}
            },
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
                    {"notes": {"$elemMatch": {"field_id":4, "value":'No'}}},
                    {"folder": bson.objectid.ObjectId(folder)}
                ]}
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
                    {"notes": {"$elemMatch": {"field_id":4, "value":'No'}}},
                    {"categories": bson.objectid.ObjectId(category)}
                ]}
            },
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))

    @expose('/')
    def index(self):
        self.update_redirect()
        lp_total = 0
        full_total = CollectionItem.objects().count()
        by_folder = []
        by_category = []
        for f in Folder.objects().order_by('name'):
            c = CollectionItem.objects(folder=f.id).count()
            by_folder.append({'folder': f, 'total': c})
            if f.name != 'Edison Diamond Disc':
                lp_total += c
        for f in Category.objects().order_by('name'):
            c = CollectionItem.objects(categories=f.id).count()
            by_category.append({'category': f, 'total': c})
        return self.render_template(self.index_template, 
                appbuilder=self.appbuilder,
                lp_total=lp_total,
                full_total=full_total,
                by_folder=by_folder,
                by_category=by_category)

