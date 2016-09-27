==============
Tag collection
==============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _tag: ../items/tag.html

.. _feed: ../items/feed.html


**Read/write**


This resource type refers to a collection of feed_-specific tag_ items.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "tags"**


.. http:get:: /api/v1/(int:feed_id)/tags/

   :synopsis: Gets the list of tags for the feed (`feed_id`).

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/35/tags/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, POST
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/35/tags/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": "Completed"
                          },
                          {
                              "name": "owner",
                              "value": "jbernal"
                          },
                          {
                              "name": "color",
                              "value": "red"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/tags/1/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
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
              "template": {
                  "data": [
                      {
                          "name": "name",
                          "value": ""
                      },
                      {
                          "name": "color",
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

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - tag_ item properties

   `Link Relations`_:

    - tag_ item link relations
