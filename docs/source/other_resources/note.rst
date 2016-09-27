====
Note
====

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read/write**


This resource type refers to a feed note.


.. http:get:: /api/v1/note(int:note_id)/

   :synopsis: Gets a feed note.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/note35/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, PUT, DELETE
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/note35/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "title",
                              "value": ""
                          },
                          {
                              "name": "content",
                              "value": ""
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/note35/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
                          }
                      ]
                  }
              ],
              "links": [],
              "template": {
                  "data": [
                      {
                          "name": "title",
                          "value": ""
                      },
                      {
                          "name": "content",
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

    - **title** (`string`) |--| note's title. Can be part of the template object in PUT
      requests
    - **content** (`string`) |--| note's content. Can be part of the template object in
      PUT requests

   `Link Relations`_:

    - **feed** |--| links to the corresponding feed_

   .. _feed: feed.html
