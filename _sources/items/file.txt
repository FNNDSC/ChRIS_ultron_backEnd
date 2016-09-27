=========
File item
=========

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read/write**


This resource type refers to a user's feed tag.


.. http:get:: /api/v1/files/(int:file_id)/

   :synopsis: Gets a feed file.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/files/30/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, PUT, DELETE
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/files/30/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "fname",
                              "value": "~/users/jbernal/feed_35/simplefsapp_60/simpledsapp_62/data/new_out.txt"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/files/30/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/files/30/new_out.txt",
                              "rel": "file_resource"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/62/",
                              "rel": "plugin_inst"
                          }
                      ]
                  }
              ],
              "links": [],
              "template": {
                  "data": [
                      {
                          "name": "fname",
                          "value": ""
                      }
                  ]
              },
              "version": "1.0"
          }
      }


   :reqheader Accept: application/vnd.collection+json
   :resheader Content-Type: application/vnd.collection+json
   :statuscode 200: no error
   :statuscode 401: authentication credentials were not provided
   :statuscode 403: you do not have permission to perform this action
   :statuscode 404: not found

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - **fname** (`string`) |--| file's name. Can be part of the template object in PUT
      requests

   `Link Relations`_:

    - **feed** |--| links to the corresponding feed_
    - **file_resource** |--| links to the `file's content`_
    - **plugin_inst** |--| links to the `plugin instance`_ that created the file

   .. _feed: feed.html
   .. _`file's content`: ../other_resources/file_content.html
   .. _`plugin instance`: plugin_instance.html
