==================
Comment collection
==================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _comment: ../items/comment.html

.. _feed: ../items/feed.html


**Read/write**


This resource type refers to a collection of feed_-specific comment_ items.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "comments"**


.. http:get:: /api/v1/(int:feed_id)/comments/

   :synopsis: Gets the list of comments for the the feed (`feed_id`).

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/35/comments/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, POST
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/35/comments/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "title",
                              "value": "Looks good"
                          },
                          {
                              "name": "owner",
                              "value": "jbernal"
                          },
                          {
                              "name": "content",
                              "value": "The data looks really good!"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/comments/1/",
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

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - comment_ item properties

   `Link Relations`_:

    - comment_ item link relations
