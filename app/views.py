from flask import render_template
from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.mongoengine.interface import MongoEngineInterface
from flask_appbuilder.actions import action
from app import appbuilder
from app.models import CollectionItem, Artist, Genre, Style, Category, Folder
from app.widgets import CollectionListWidget

class CollectionItemModelView(CompactCRUDMixin,ModelView):
    datamodel = MongoEngineInterface(CollectionItem)
    list_columns = [
        'artists',
        'title',
        'master_year',
        'categories',
        'genres',
        'styles',
        'folder',
        'filed_under'
    ]
    edit_columns = [
        'categories'
    ]
    base_order = ('artists','desc')

class CollectionModelView(ModelView):
    datamodel = MongoEngineInterface(CollectionItem)
    list_columns = [
        'artists',
        'title',
        'master_year',
        'categories',
        'genres',
        'styles',
        'folder',
        'filed_under'
    ]
    edit_columns = [
        'artists',
        'title',
        'master_year',
        'categories',
        'genres',
        'styles',
        'folder',
        'filed_under'
    ]
    add_columns = [
        'artists',
        'title',
        'master_year',
        'categories',
        'genres',
        'styles',
        'folder',
        'filed_under'
    ]
    base_order = ('artists','asc')

class CategoryModelView(ModelView):
    datamodel = MongoEngineInterface(Category)
    base_order = ('name','desc')
    related_views = [ CollectionModelView ]

class ArtistModelView(ModelView):
    datamodel = MongoEngineInterface(Artist)
    list_columns = [
        'name',
        'sort_name',
        'artist_id',
        'ignore'
    ]
    base_order = ('name', 'desc')
    related_views = [ CollectionModelView ]

class GenreModelView(ModelView):
    datamodel = MongoEngineInterface(Genre)
    base_order = ('name', 'desc')
    related_views = [ CollectionModelView ]

class StyleModelView(ModelView):
    datamodel = MongoEngineInterface(Style)
    base_order = ('name', 'desc')
    related_views = [ CollectionModelView ]
    
class FolderModelView(ModelView):
    datamodel = MongoEngineInterface(Folder)
    list_columns = [
        'name',
        'folder_id'
    ]
    base_order = ('name', 'desc')
    related_views = [ CollectionModelView ]

appbuilder.add_view(CollectionItemModelView, "Categorize")
appbuilder.add_view(CollectionModelView, "Collection")
appbuilder.add_view(ArtistModelView, "Artists")
appbuilder.add_view(GenreModelView, "Genres")
appbuilder.add_view(StyleModelView, "Styles")
appbuilder.add_view(FolderModelView, "Folders")
appbuilder.add_view(CategoryModelView, "Categories")


"""
    Application wide 404 error handler
"""
@appbuilder.app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', base_template=appbuilder.base_template, appbuilder=appbuilder), 404

