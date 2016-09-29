=================
Plugin collection
=================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _plugin: ../items/plugin.html


**Read-only**


This resource type refers to the collection of plugin_ items.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "plugins"``


.. http:get:: /api/v1/plugins/

   :synopsis: Gets the list of system plugins.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/plugins/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": "simpledsapp"
                          },
                          {
                              "name": "type",
                              "value": "ds"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/13/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/plugins/13/parameters/",
                              "rel": "parameters"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/13/instances/",
                              "rel": "instances"
                          }
                      ]
                  },
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": "simplefsapp"
                          },
                          {
                              "name": "type",
                              "value": "fs"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/12/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/plugins/12/parameters/",
                              "rel": "parameters"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/12/instances/",
                              "rel": "instances"
                          }
                      ]
                  }
              ],
              "links": [
                  {
                      "href": "https://localhost:8000/api/v1/",
                      "rel": "feeds"
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

    - plugin_ item properties

   `Link Relations`_:

    - plugin_ item link relations
    - **feeds** |--| links to the `collection of feeds`_ for the currently authenticated
      user

   .. _`collection of feeds`: feed.html
