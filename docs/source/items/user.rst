=========
User item
=========

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to a registered user.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "owner"``


.. http:get:: /api/v1/users/(int:user_id)/

   :synopsis: Gets a registered user.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/users/2/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/users/2/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "username",
                              "value": "jbernal"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/users/2/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/33/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/34/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/36/",
                              "rel": "feed"
                          }
                      ]
                  }
              ],
              "links": [],
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

    - **username** (`string`) |--| user's username

   `Link Relations`_:

    - **feed** |--| links to a user's feed_

   .. _feed: feed.html
