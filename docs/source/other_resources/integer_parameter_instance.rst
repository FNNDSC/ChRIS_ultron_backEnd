==========================
Integer Parameter instance
==========================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to an integer plugin parameter's instance.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "int_inst"``


.. http:get:: /api/v1/plugins/int-parameter/(int:parameterinstance_id)/

   :synopsis: Gets an intger plugin parameter's instance.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/plugins/int-parameter/35/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/int-parameter/35/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "param_name",
                              "value": "counts"
                          },
                          {
                              "name": "value",
                              "value": "10"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/int-parameter/35/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/plugins/instances/45/",
                              "rel": "plugin_inst"
                          },
                          {
                              "href": "https://localhost:8000/api/v1/plugins/parameters/18/",
                              "rel": "plugin_param"
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

    - **param_name** (`string`) |--| name of the corresponding `plugin parameter`_
    - **value** (`int`) |--| parameter instance's value

   `Link Relations`_:

    - **plugin_inst** |--| links to the corresponding `plugin instance`_
    - **plugin_param** |--| links to the corresponding `plugin parameter`_

   .. _`plugin instance`: ../items/plugin_instance.html

   .. _`plugin parameter`: ../items/plugin_parameter.html
