=====================
Plugin Instance item
=====================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to a plugin instance item.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "plugin_inst"**


.. http:get:: /api/v1/instances/(int:instance_id)/

   :synopsis: Gets a plugin instance.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/instances/60/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/instances/60/",
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

    - **id** (`int`) |--| instance's id
    - **plugin_name** (`string`) |--| corresponding plugin's name
    - **start_date** (`string`) |--| starting date of the associated plugin process
    - **end_date** (`boolean`) |--| end date of the associated plugin process
    - **status** (`string`) |--| status of the associated plugin process
    - **owner** (`string`) |--| the plugin instance's owner's username

   `Link Relations`_:

    - **plugin** |--| links to the corresponding plugin_
    - **feed** |--| links to the corresponding feed_
    - **string_param** |--| links to a `string parameter instance`_
    - **int_param** |--| links to an `integer parameter instance`_
    - **float_param** |--| links to a `float parameter instance`_
    - **bool_param** |--| links to a `boolean parameter instance`_

   .. _plugin: plugin.html

   .. _feed: feed.html

   .. _`string parameter instance`: ../other_resources/string_parameter_instance.html

   .. _`integer parameter instance`: ../other_resources/integer_parameter_instance.html

   .. _`float parameter instance`: ../other_resources/float_parameter_instance.html

   .. _`boolean parameter instance`: ../other_resources/boolean_parameter_instance.html
