=====================
Plugin Parameter item
=====================

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to a plugin parameter item.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

**"rel": "plugin_param"**


.. http:get:: /api/v1/parameters/(int:parameter_id)/

   :synopsis: Gets a plugin parameter.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/parameters/12/ HTTP/1.1
      Host: localhost:8000
      Accept: application/vnd.collection+json


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: application/vnd.collection+json

      {
          "collection": {
              "href": "https://localhost:8000/api/v1/plugins/parameters/12/",
              "items": [
                  {
                      "data": [
                          {
                              "name": "name",
                              "value": "dir"
                          },
                          {
                              "name": "type",
                              "value": "string"
                          },
                          {
                              "name": "optional",
                              "value": true
                          },
                          {
                              "name": "default",
                              "value": "./"
                          },
                          {
                              "name": "help",
                              "value": "look up directory"
                          }
                      ],
                      "href": "https://localhost:8000/api/v1/plugins/parameters/12/",
                      "links": [
                          {
                              "href": "https://localhost:8000/api/v1/plugins/12/",
                              "rel": "plugin"
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

    - **name** (`string`) |--| parameter's name
    - **type** (`string`) |--| paremeter's type. Any of the strings 'string', 'integer',
      'float' or 'boolean'
    - **optional** (`boolean`) |--| indicates whether the parameter has a default value
      and is not required in requests
    - **default** (`string`) |--| a string representation of the parameter's default value
      Only available if the value of the "optional" property is True
    - **help** (`string`) |--| a description of the parameter

   `Link Relations`_:

    - **plugin** |--| links to the corresponding plugin_

   .. _plugin: plugin.html
