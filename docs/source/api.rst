========
REST API
========

This API uses the standard Collection+JSON_ hypermedia type to exchange resource 
representations with clients. All the functionality provided by the API can be 
discovered by clients by doing :http:method:`get` requests to links ("href" elements)
presented by the hypermedia documents returned by the web server, starting with the API's
"home page". 

.. _Collection+JSON: http://amundsen.com/media-types/collection/

The API's "home page" relative url is: /api/v1/

There are two main type of resources:

Collection
  A resource to group other resources together. Its representation focuses on links to 
  other resources, though it may also include snippets from the representations of those
  other resources.

Item
  A standalone resource that is linked to from a collection’s representation.
  

The following table shows the protocol semantics for the HTTP resources served by the API:


.. table:: API's accepted HTTP requests

	=====================  =====================    =====================  =====================
 	                  Collection                                        Item
	--------------------------------------------    --------------------------------------------
	read-only              read/write               read-only              read/write
	=====================  =====================    =====================  =====================
	:http:method:`get`     :http:method:`get`       :http:method:`get`     :http:method:`get`

			       :http:method:`post`                             :http:method:`put`

			       			                               :http:method:`delete`
	=====================  =====================    =====================  =====================


However there are read-only Collection and Item resources which do not accept 
unsafe requeststhat could modify the resource state such as POST, PUT and DELETE




.. http:get:: /users/(int:user_id)/posts/(tag)

   The posts tagged with `tag` that the user (`user_id`) wrote.

   **Example request**:

   .. sourcecode:: http

      GET /users/123/posts/web HTTP/1.1
      Host: example.com
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: text/javascript

      [
        {
          "post_id": 12345,
          "author_id": 123,
          "tags": ["server", "web"],
          "subject": "I tried Nginx"
        },
        {
          "post_id": 12346,
          "author_id": 123,
          "tags": ["html5", "standards", "web"],
          "subject": "We go to HTML 5"
        }
      ]

   :query sort: one of ``hit``, ``created-at``
   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :reqheader Accept: the response content type depends on
                      :mailheader:`Accept` header
   :reqheader Authorization: optional OAuth token to authenticate
   :resheader Content-Type: this depends on :mailheader:`Accept`
                            header of request
   :statuscode 200: no error
   :statuscode 404: there's no user
