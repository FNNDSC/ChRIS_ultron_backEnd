===============
User collection
===============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _user: ../items/user.html


**Read-only**


This resource type refers to the collection of registered users.


.. http:get:: /api/v1/users/

   :synopsis: Gets the list of registered users.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/users/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/users/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "username",
                              "value": "chris"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/users/1/"
                  },
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
                  },
                  {
                      "data": [
                          {
                              "name": "username",
                              "value": "jbernal1"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/users/3/"
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

   .. |--| unicode:: U+2013   .. en dash

   .. _Properties: http://amundsen.com/media-types/collection/format/#properties
   .. _`Link Relations`: http://amundsen.com/media-types/collection/format/#link-relations

   Properties_ (API semantic descriptors):

    - user_ item properties

   `Link Relations`_:

    - user_ item link relations
