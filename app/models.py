from mongoengine import Document, EmbeddedDocument
from mongoengine import IntField, StringField, ListField, ReferenceField, BooleanField, EmbeddedDocumentListField
from flask import Markup

class Format(EmbeddedDocument):
    name         = StringField()
    qty          = IntField()
    text         = StringField()
    descriptions = ListField(StringField())

    def __unicode__(self):
        ret = ''
        if self.qty:
            ret = ret + str(self.qty) + 'x '
        ret = ret + self.name
        if len(self.descriptions) > 0:
            ret = ret + ' {'
            ret = ret + ' '.join(self.descriptions)
            ret = ret + '}'
        if self.text:
            ret = ret + ' (' + str(self.text) + ')'
        return ret

    def __repr__(self):
        ret = ''
        if self.qty:
            ret = ret + str(self.qty) + 'x '
        ret = ret + self.name
        if len(self.descriptions) > 0:
            ret = ret + ' {'
            ret = ret + ' '.join(self.descriptions)
            ret = ret + '}'
        if self.text:
            ret = ret + ' (' + str(self.text) + ')'
        return ret

class MediaCondition(Document):
    label = StringField(required=True, unique=True)
    
    def __unicode__(self):
        return self.label
    
    def __repr__(self):
        return self.label
    
class SleeveCondition(Document):
    label = StringField(required=True, unique=True)
    
    def __unicode__(self):
        return self.label
    
    def __repr__(self):
        return self.label
    
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
    formats     = EmbeddedDocumentListField('Format')
    released    = StringField()
    media_condition = ReferenceField('MediaCondition')
    sleeve_condition = ReferenceField('SleeveCondition')
    item_notes  = StringField()
    listened = BooleanField()
    includes = StringField()
    
    def __unicode__(self):
        return self.title

    def __repr__(self):
        return self.title

    def release_show(self):
        return Markup(
            '<a href="https://www.discogs.com/release/' + str(self.release_id) + '">' + str(self.release_id) + '</a>'
        )
    
    def master_show(self):
        return Markup(
            '<a href="https://www.discogs.com/master/' + str(self.master_id) + '">' + str(self.master_id) + '</a>'
        )
        
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

