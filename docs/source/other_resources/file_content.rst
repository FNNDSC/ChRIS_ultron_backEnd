============
File content
============

.. _Collection+JSON: http://amundsen.com/media-types/collection/

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


**Read-only**


This resource type refers to a feed file's content.

In other Collection+JSON_ resource representations this resource type is linked by any
`link relation`_ with attribute:

``"rel": "file_resource"``


.. http:get:: /api/v1/files/(int:file_id)/filename/

   :synopsis: Gets the content of a feed file.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/files/30/new_out.txt HTTP/1.1
      Host: localhost:8000
      Accept: */*


   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: GET
      Content-Type: */*


      This is the content of this file.


   :reqheader Accept: */*
   :resheader Content-Type: */*
   :statuscode 200: no error
   :statuscode 401: authentication credentials were not provided
   :statuscode 403: you do not have permission to perform this action
   :statuscode 404: not found
