=========
Feed item
=========

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read/write**


This resource type refers to a user's feed item.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "feed"``


.. http:get:: /api/v1/(int:feed_id)/

   :synopsis: Gets an authenticated user's feed.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/35/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, PUT, DELETE
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/35/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": ""
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/35/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/users/2/",
                              "rel": "owner"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/note35/",
                              "rel": "note"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/tags/",
                              "rel": "tags"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/comments/",
                              "rel": "comments"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/35/files/",
                              "rel": "files"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/60/",
                              "rel": "plugin_inst"
                          }
                      ]
                  }
              ],
              "links": [],
              "template": {
                  "data": [
                      {
                          "name": "name",
                          "value": ""
                      },
                      {
                          "name": "owner",
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

    - **name** (`string`) |--| feed's name. Can be part of the template object in PUT
      requests
    - **owner** (`string`) |--| username of a new feed's owner. Can be part of the template
      object in PUT requests. Feeds can have more than one owner so they can be shared
      between users

   `Link Relations`_:

    - **owner** |--| links to an owner_ of the feed
    - **note** |--| links to the feed's note_
    - **tags** |--| links to the feed's `collection of tags`_
    - **comments** |--| links to the feed's `collection of comments`_
    - **files** |--| links to the feed's `collection of files`_
    - **plugin_inst** |--| links to the `plugin instance`_ that created the feed

   .. _owner: user.html
   .. _note: ../other_resources/note.html
   .. _`collection of tags`: ../collections/tag.html
   .. _`collection of comments`: ../collections/comment.html
   .. _`collection of files`: ../collections/file.html
   .. _`plugin instance`: plugin_instance.html
