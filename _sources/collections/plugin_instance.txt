==========================
Plugin Instance collection
==========================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations

.. _`plugin instance`: ../items/plugin_instance.html


**Read/write**


This resource type refers to the collection of a plugin's `plugin instance`_ items.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "instances"**


.. http:get:: /api/v1/plugins/(int:plugin_id)/instances/

   :synopsis: Gets the list of instances for the plugin (`plugin_id`).

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/plugins/12/instances/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, POST
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/12/instances/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "id",
                              "value": 60
                          },
                          {
                              "name": "plugin_name",
                              "value": "simplefsapp"
                          },
                          {
                              "name": "start_date",
                              "value": "2016-09-21T14:47:06.352445Z"
                          },
                          {
                              "name": "end_date",
                              "value": "2016-09-21T14:47:06.352502Z"
                          },
                          {
                              "name": "status",
                              "value": "started"
                          },
                          {
                              "name": "owner",
                              "value": "jbernal"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/instances/60/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/35/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/12/",
                              "rel": "plugin"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/string-parameter/56/",
                              "rel": "string_param"
                          }
                      ]
                  },
                  {
                      "data": [
                          {
                              "name": "id",
                              "value": 61
                          },
                          {
                              "name": "plugin_name",
                              "value": "simplefsapp"
                          },
                          {
                              "name": "start_date",
                              "value": "2016-09-21T14:50:41.694232Z"
                          },
                          {
                              "name": "end_date",
                              "value": "2016-09-21T14:50:41.694289Z"
                          },
                          {
                              "name": "status",
                              "value": "started"
                          },
                          {
                              "name": "owner",
                              "value": "jbernal"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/instances/61/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/36/",
                              "rel": "feed"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/12/",
                              "rel": "plugin"
                          }
                      ]
                  }
              ],
              "links": [
                  {
                      "href": "https://localhost:8000/api/v1/plugins/12/",
                      "rel": "plugin"
                  }
              ],
              "template": {
                  "data": [
                      {
                          "name": "previous",
                          "value": ""
                      },
                      {
                          "name": "dir",
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

    - `plugin instance`_ item properties

   `Link Relations`_:

    - `plugin instance`_ item link relations
    - **plugin** |--| links to the corresponding plugin_

   .. _plugin: ../items/plugin.html
