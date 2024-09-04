===========
Plugin item
===========

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to a plugin item.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "plugin"``


.. http:get:: /api/v1/plugins/(int:plugin_id)/

   :synopsis: Gets a system plugin.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/plugins/12/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/12/",
              "items": [
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

    - **name** (`string`) |--| plugin's name
    - **type** (`string`) |--| plugin's type. Can only be the strings 'fs' (filesystem
      plugin) or 'ds' (data plugin)

   `Link Relations`_:

    - **parameters** |--| links to the plugin's `collection of parameters`_
    - **instances** |--| links to the plugin's `collection of instances`_

   .. _`collection of parameters`: ../collections/plugin_parameter.html
   .. _`collection of instances`: ../collections/plugin_instance.html
