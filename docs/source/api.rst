========
REST API
========

This API uses the standard Collection+JSON_ hypermedia type to exchange resource 
representations with clients. All the functionality provided by the API can be 
discovered by clients by doing :http:method:`get` requests to links ("href" elements)
presented by the hypermedia documents returned by the web server, starting with the API's
"home page". 

.. _Collection+JSON: http://amundsen.com/media-types/collection/


The API's "home page" relative url is: /api/v1/ which serves a user-specific `collection
of feeds`_.

.. _`collection of feeds`: collections/feed.html


There are two main type of resources:

**Collection**
  A resource to group other resources together. Its representation focuses on links to 
  other resources, though it may also include snippets from the representations of those
  other resources.

**Item**
  A standalone resource that is linked to from a collection’s representation.
  

The following table shows the protocol semantics for the HTTP resources served by the API:


.. table:: **API's accepted HTTP requests**

	=====================  =====================    =====================  =====================
 	                  Collection                                        Item
	--------------------------------------------    --------------------------------------------
	read-only              read/write               read-only              read/write
	=====================  =====================    =====================  =====================
	:http:method:`get`     :http:method:`get`       :http:method:`get`     :http:method:`get`

			       :http:method:`post`                             :http:method:`put`

			       			                               :http:method:`delete`
	=====================  =====================    =====================  =====================




Following are the list of resource types: 


**Collections:**

.. toctree::
   :maxdepth: 2

   collections/feed
   collections/comment
   collections/tag
   collections/file
   collections/plugin
   collections/plugin_parameter
   collections/plugin_instance


**Items:**

.. toctree::
   :maxdepth: 2
   
   items/feed
   items/comment
   items/tag
   items/file
   items/plugin
   items/plugin_parameter
   items/plugin_instance


**Other resources:**

.. toctree::
   :maxdepth: 2
   
   other_resources/note
   other_resources/file_content

