
from rest_framework.parsers import JSONParser

class CollectionJsonParser(JSONParser):
    media_type = 'application/vnd.collection+json'
   
    def parse(self, stream, media_type=None, parser_context=None):

        return super(CollectionJsonParser, self).parse(stream, media_type,
                                                          parser_context)
