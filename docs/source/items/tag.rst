========
Tag item
========

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read/write**


This resource type refers to a user's feed tag.


.. http:get:: /api/v1/tags/(int:tag_id)/

   :synopsis: Gets a feed tag.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/tags/1/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, PUT, DELETE
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/tags/1/",
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
              "links": [],
              "template": {
                  "data": [
                      {
                          "name": "color",
                          "value": ""
                      },
                      {
                          "name": "name",
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

    - **owner** (`string`) |--| the tag's owner's username. Read-only
    - **name** (`string`) |--| tag's name. Can be part of the template object in PUT and
      POST requests
    - **color** (`string`) |--| tag's color. Can be part of the template object in PUT
      and POST requests

   `Link Relations`_:

    - **feed** |--| links to the corresponding feed_

   .. _feed: feed.html
