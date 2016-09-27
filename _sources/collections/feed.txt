===============
Feed collection
===============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _feed: ../items/feed.html


**Read-only**


This resource type refers to a collection of user-specific feed_ items.

A Collection+JSON_ representation is served at the root of the API: /api/v1/.

In other resource representations this resource type is linked by any `link relation`_
with attribute:

**"rel": "feeds"**


.. http:get:: /api/v1/

   :synopsis: Gets the list of feeds for the authenticated user.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": ""
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/33/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/users/2/",
                              "rel": "owner"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/note33/",
                              "rel": "note"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/33/tags/",
                              "rel": "tags"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/33/comments/",
                              "rel": "comments"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/33/files/",
                              "rel": "files"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/58/",
                              "rel": "plugin_inst"
                          }
                      ]
                  },
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": ""
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/34/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/users/2/",
                              "rel": "owner"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/note34/",
                              "rel": "note"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/34/tags/",
                              "rel": "tags"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/34/comments/",
                              "rel": "comments"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/34/files/",
                              "rel": "files"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/59/",
                              "rel": "plugin_inst"
                          }
                      ]
                  }
              ],
              "links": [
                  {
                      "href": "https://localhost:8000/api/v1/plugins/",
                      "rel": "plugins"
                  }
              ],
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

    - feed_ item properties

   `Link Relations`_:

    - feed_ item link relations
    - **plugins** |--| links to the `collection of plugins`_ in the system

   .. _`collection of plugins`: plugin.html
