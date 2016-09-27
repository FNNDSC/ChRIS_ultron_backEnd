===============
File collection
===============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _file: ../items/file.html

.. _feed: ../items/feed.html


**Read-only**


This resource type refers to a collection of feed_-specific file_ items.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "files"**


.. http:get:: /api/v1/(int:feed_id)/files/

   :synopsis: Gets the list of files for the feed (`feed_id`).

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/35/files/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/35/files/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "fname",
                              "value": "~/users/jbernal/feed_35/simplefsapp_60/data/out.txt"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/files/28/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/files/28/out.txt",
                              "rel": "file_resource"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/60/",
                              "rel": "plugin_inst"
                          }
                      ]
                  },
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
              "links": [
                  {
                      "href": "https://localhost:8000/api/v1/35/",
                      "rel": "feed"
                  }
              ],
              "version": "1.0"
          }
      }


   :reqheader Accept: application/vnd.collection+json
   :resheader Content-Type: application/vnd.collection+json
   :statuscode 200: no error
   :statuscode 401: authentication credentials were not provided
   :statuscode 403: you do not have permission to perform this action

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - file_ item properties

   `Link Relations`_:

    - file_ item link relations
