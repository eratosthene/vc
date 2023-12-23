from mongoengine import Document
from mongoengine import IntField, StringField, ListField, ReferenceField, BooleanField, DictField

class CollectionItem(Document):
    instance_id = IntField(required=True, unique=True)
    release_id  = IntField(required=True)
    title       = StringField(required=True)
    year        = IntField()
    artists     = ListField(ReferenceField('Artist'), required=True)
    genres      = ListField(ReferenceField('Genre'))
    styles      = ListField(ReferenceField('Style'))
    master_id   = IntField(required=True)
    master_year = IntField()
    categories  = ListField(ReferenceField('Category'))
    folder      = ReferenceField('Folder')
    filed_under = ReferenceField('Artist')
    formats     = ListField(DictField())
    notes       = ListField(DictField())
    released    = StringField()
    
    def __unicode__(self):
        return self.title

    def __repr__(self):
        return self.title
        
class Artist(Document):
    artist_id   = IntField(required=True, unique=True)
    name        = StringField(required=True)
    sort_name   = StringField()
    ignore      = BooleanField(default=False)

    def __unicode__(self):
        if self.sort_name:
            return self.sort_name
        else:
            return self.name

    def __repr__(self):
        if self.sort_name:
            return self.sort_name
        else:
            return self.name

class Genre(Document):
    name        = StringField(required=True, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Style(Document):
    name        = StringField(required=True, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Category(Document):
    name        = StringField(required=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

class Folder(Document):
    folder_id   = IntField(required=True, unique=True)
    name        = StringField(required=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name
