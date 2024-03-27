import logging
from flask_appbuilder import BaseView, expose
from app.models import CollectionItem
from flask import redirect

class RandomItemView(BaseView):
    default_view = 'unlistened'

    @expose('/unlistened')
    def unlistened(self):
        docs = CollectionItem.objects().aggregate([
            {"$match":{"notes": {"$elemMatch": {"field_id":4, "value":'No'}}}},
            {"$sample":{"size":1}}
        ])
        doc = next(docs)
        return redirect('/collectionmodelview/show/' + str(doc['_id']))
