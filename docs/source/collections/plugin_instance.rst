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

``"rel": "instances"``


.. http:get:: /api/v1/plugins/(int:plugin_id)/instances/

   :synopsis: Gets the list of instances for the plugin (`plugin_id`).

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/plugins/4/instances/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET, POST
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "http://localhost:8000/api/v1/plugins/4/instances/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "id",
                              "value": 8
                          },
                          {
                              "name": "previous_id",
                              "value": 5
                          },
                          {
                              "name": "plugin_name",
                              "value": "simpledsapp"
                          },
                          {
                              "name": "start_date",
                              "value": "2016-11-16T17:27:19.192067Z"
                          },
                          {
                              "name": "end_date",
                              "value": "2016-11-16T17:27:19.192118Z"
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
                      "href": "http://localhost:8000/api/v1/plugins/instances/8/",
                      "links": [
                          {
                              "href": "http://localhost:8000/api/v1/plugins/instances/5/",
                              "rel": "previous"
                          },
                          {
                              "href": "http://localhost:8000/api/v1/plugins/4/",
                              "rel": "plugin"
                          },
                          {
                              "href": "http://localhost:8000/api/v1/plugins/string-parameter/6/",
                              "rel": "string_param"
                          }
                      ]
                  },
                  {
                      "data": [
                          {
                              "name": "id",
                              "value": 9
                          },
                          {
                              "name": "previous_id",
                              "value": 6
                          },
                          {
                              "name": "plugin_name",
                              "value": "simpledsapp"
                          },
                          {
                              "name": "start_date",
                              "value": "2016-11-16T17:27:39.508197Z"
                          },
                          {
                              "name": "end_date",
                              "value": "2016-11-16T17:27:39.508248Z"
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
                      "href": "http://localhost:8000/api/v1/plugins/instances/9/",
                      "links": [
                          {
                              "href": "http://localhost:8000/api/v1/plugins/instances/6/",
                              "rel": "previous"
                          },
                          {
                              "href": "http://localhost:8000/api/v1/plugins/4/",
                              "rel": "plugin"
                          },
                          {
                              "href": "http://localhost:8000/api/v1/plugins/string-parameter/7/",
                              "rel": "string_param"
                          }
                      ]
                  },
              ],
              "links": [
                  {
                      "href": "http://localhost:8000/api/v1/plugins/4/",
                      "rel": "plugin"
                  }
              ],
              "queries": [
                  {
                      "data": [
                          {
                              "name": "root_id",
                              "value": ""
                          },
                          {
                              "name": "status",
                              "value": ""
                          },
                          {
                              "name": "previous_id",
                              "value": ""
                          },
                          {
                              "name": "min_start_date",
                              "value": ""
                          },
                          {
                              "name": "max_start_date",
                              "value": ""
                          },
                          {
                              "name": "min_end_date",
                              "value": ""
                          },
                          {
                              "name": "max_end_date",
                              "value": ""
                          }
                      ],
                      "href": "http://localhost:8000/api/v1/plugins/instances/search/",
                      "rel": "search"
                  }
              ],
              "template": {
                  "data": [
                      {
                          "name": "prefix",
                          "value": ""
                      },
                      {
                          "name": "sleepLength",
                          "value": ""
                      },
                      {
                          "name": "previous_id",
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
