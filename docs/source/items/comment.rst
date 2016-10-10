============
Comment item
============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read/write**


This resource type refers to a user's feed comment.


.. http:get:: /api/v1/comments/(int:comment_id)/

   :synopsis: Gets a feed comment.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/comments/1/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, PUT, DELETE
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/comments/1/",
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
              "links": [],
              "template": {
                  "data": [
                      {
                          "name": "content",
                          "value": ""
                      },
                      {
                          "name": "title",
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
   :statuscode 404: not found

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - **owner** (`string`) |--| the comment's owner's username. Read-only
    - **title** (`string`) |--| comment's title. Can be part of the template object in PUT
      and POST requests
    - **content** (`string`) |--| comment's content. Can be part of the template object in
      PUT and POST requests

   `Link Relations`_:

    - **feed** |--| links to the corresponding feed_

   .. _feed: feed.html
