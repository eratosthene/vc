from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Category

def sortFunc(e):
    return str(e)
    
def yearSortFunc(e):
    return e.master_year
    
class MyIndexView(IndexView):
    index_template = "index.html"

    @expose('/')
    def index(self):
        self.update_redirect()
        categories = []
        artists = {}
        items = {}
        for c in Category.objects().order_by('name'):
            categories.append(c)
            artists[c.id] = []
            items[c.id] = {}
            for i in CollectionItem.objects(categories=c.id):
                for a in i.artists:
                    artists[c.id].append(a)
            artists[c.id] = list(set(artists[c.id]))
            artists[c.id].sort(key=sortFunc)
            for a in artists[c.id]:
                items[c.id][a.id] = []
                for i in CollectionItem.objects(categories=c.id,artists=a.id):
                    items[c.id][a.id].append(i)
                items[c.id][a.id].sort(key=yearSortFunc)
            # artists[c.id] = [dict(d) for d in set([frozenset(i.items()) for i in artists[c.id]])]
        return self.render_template(self.index_template, 
                appbuilder=self.appbuilder, 
                categories=categories,
                artists=artists,
                items=items)

