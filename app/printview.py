import logging
from flask_appbuilder import BaseView
from flask_appbuilder.views import expose
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from app.models import CollectionItem, Category, Folder
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

class PrintView(BaseView):
    default_view = 'printview'
    printview_template = "printview.html"
    printview_index_template = "printviewindex.html"

    def crunch(self, folder=None, category=None, decade=None):
        categories = []
        artists = {}
        items = {}
        soundtrack_items = []
        showtunes_items = []
        edison_items = []
        if category:
            c_query = Category.objects(id=category).order_by('name')
        else:
            c_query = Category.objects().order_by('name')
        for c in c_query:
            categories.append(c)
            artists[c.id] = []
            items[c.id] = {}
            if folder:
                ci_query = CollectionItem.objects(categories=c.id, folder=folder)
            elif decade:
                after = int(decade[:-1])-1
                before = int(decade[:-1])+10
                ci_query = CollectionItem.objects(categories=c.id, master_year__gt=after, master_year__lt=before)
            else:
                ci_query = CollectionItem.objects(categories=c.id)
            for i in ci_query:
                for a in i.artists:
                    artists[c.id].append(a)
            artists[c.id] = list(set(artists[c.id]))
            artists[c.id].sort(key=sortFunc)
            for a in artists[c.id]:
                # logging.debug(a)
                items[c.id][a.id] = []
                releases = {}
                masters = []
                if folder:
                    cic_query = CollectionItem.objects(categories=c.id, artists=a.id, folder=folder)
                elif decade:
                    after = int(decade[:-1])-1
                    before = int(decade[:-1])+10
                    cic_query = CollectionItem.objects(categories=c.id, artists=a.id, master_year__gt=after, master_year__lt=before)
                else:
                    cic_query = CollectionItem.objects(categories=c.id, artists=a.id)
                for i in cic_query:
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
                for i in ci_query:
                    soundtrack_items.append(i)
                soundtrack_items.sort(key=releaseSortFunc)
            if c.name == 'Showtunes':
                for i in ci_query:
                    showtunes_items.append(i)
                showtunes_items.sort(key=releaseSortFunc)
            if c.name == 'Edison Diamond Disc':
                for i in ci_query:
                    edison_items.append(i)
                edison_items.sort(key=slotSortFunc)

        return categories, artists, items, soundtrack_items, showtunes_items, edison_items

    @expose('/')
    def printview(self):
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
            after = int(decade[:-1])-1
            before = int(decade[:-1])+10
            by_decade.append({'decade': decade, 'count': d['count'], 'before': before, 'after': after})
        return self.render_template(self.printview_index_template,
                appbuilder=self.appbuilder,
                lp_total=lp_total,
                full_total=full_total,
                by_folder=by_folder,
                by_category=by_category,
                by_decade=by_decade)

    @expose('/all')
    @expose('/all/')
    def all(self):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = self.crunch()
        pagetitle = 'Our Vinyl Collection'

        return self.render_template(self.printview_template,
                appbuilder=self.appbuilder,
                pagetitle=pagetitle,
                categories=categories,
                artists=artists,
                items=items,
                soundtrack_items=soundtrack_items,
                showtunes_items=showtunes_items,
                edison_items=edison_items)

    @expose('/folder/<string:folder>')
    def folder(self, folder):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = self.crunch(folder=folder)
        pagetitle = 'Folder: '+str(Folder.objects.get(id=folder).name)

        return self.render_template(self.printview_template,
                appbuilder=self.appbuilder,
                pagetitle=pagetitle,
                categories=categories,
                artists=artists,
                items=items,
                soundtrack_items=soundtrack_items,
                showtunes_items=showtunes_items,
                edison_items=edison_items)

    @expose('/category/<string:category>')
    def category(self, category):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = self.crunch(category=category)
        pagetitle = 'Category: '+str(Category.objects.get(id=category).name)

        return self.render_template(self.printview_template,
                appbuilder=self.appbuilder,
                pagetitle=pagetitle,
                categories=categories,
                artists=artists,
                items=items,
                soundtrack_items=soundtrack_items,
                showtunes_items=showtunes_items,
                edison_items=edison_items)

    @expose('/decade/<string:decade>')
    def decade(self, decade):
        self.update_redirect()
        categories, artists, items, soundtrack_items, showtunes_items, edison_items = self.crunch(decade=decade)
        pagetitle = 'Decade: '+str(decade)

        return self.render_template(self.printview_template,
                appbuilder=self.appbuilder,
                pagetitle=pagetitle,
                categories=categories,
                artists=artists,
                items=items,
                soundtrack_items=soundtrack_items,
                showtunes_items=showtunes_items,
                edison_items=edison_items)
