import logging
from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Folder
import re

class MyIndexView(IndexView):
    index_template = "index.html"

    @expose('/')
    def index(self):
        self.update_redirect()
        lp_total = 0
        full_total = CollectionItem.objects().count()
        by_folder = []
        for f in Folder.objects().order_by('name'):
            c = CollectionItem.objects(folder=f.id).count()
            by_folder.append({'folder': f, 'total': c})
            if f.name != 'Edison Diamond Disc':
                lp_total += c
        return self.render_template(self.index_template, 
                appbuilder=self.appbuilder,
                lp_total=lp_total,
                full_total=full_total,
                by_folder=by_folder)

