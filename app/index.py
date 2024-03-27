import logging
from flask_appbuilder import IndexView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Category
import re

def sortFunc(e):
    return str(e)
    
def yearSortFunc(e):
    return e['year']
    
def yearRSortFunc(e):
    if e.released:
        return str(e.released)
    else:
        return str(e.year)

def releaseSortFunc(e):
    t = e.title.lower()
    if t.startswith("the "):
        return t.removeprefix("the ") + ", the"
    else:
        return t

def slotSortFunc(e):
    v = [element for element in e.notes if element['field_id'] == 3]
    n = v[0]['value']
    p = re.compile('slot\s+([0-9]+)')
    s = p.search(n)
    p = re.compile('(Top|Bottom) drawer')
    d = p.search(n)
    if d.group(1) == 'Top':
        return 100 + int(s.group(1))
    else:
        return 200 + int(s.group(1))
            
class MyIndexView(IndexView):
    index_template = "index.html"

    @expose('/')
    def index(self):
        self.update_redirect()
        categories = []
        artists = {}
        items = {}
        soundtrack_items = []
        showtunes_items = []
        edison_items = []
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
                # logging.debug(a)
                items[c.id][a.id] = []
                releases = {}
                masters = []
                for i in CollectionItem.objects(categories=c.id,artists=a.id):
                    if i.master_id in releases:
                        releases[i.master_id].append(i) # todo: no master fix
                    else:
                        releases[i.master_id] = [i]
                    masters.append({'master_id':i.master_id,'year':i.master_year})
                masters = [dict(t) for t in {tuple(d.items()) for d in masters}]
                masters.sort(key=yearSortFunc)
                # logging.debug(masters)
                for master_id in releases:
                    releases[master_id].sort(key=yearRSortFunc)
                # logging.debug(releases)
                for m in masters:
                    master_id=m['master_id']
                    for i in releases[master_id]:
                        items[c.id][a.id].append(i)
            if c.name == 'Soundtracks':
                for i in CollectionItem.objects(categories=c.id):
                    soundtrack_items.append(i)
                soundtrack_items.sort(key=releaseSortFunc)
            if c.name == 'Showtunes':
                for i in CollectionItem.objects(categories=c.id):
                    showtunes_items.append(i)
                showtunes_items.sort(key=releaseSortFunc)
            if c.name == 'Edison Diamond Disc':
                for i in CollectionItem.objects(categories=c.id):
                    edison_items.append(i)
                edison_items.sort(key=slotSortFunc)
        return self.render_template(self.index_template, 
                appbuilder=self.appbuilder, 
                categories=categories,
                artists=artists,
                items=items,
                soundtrack_items=soundtrack_items,
                showtunes_items=showtunes_items,
                edison_items=edison_items)

