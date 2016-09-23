===============
Feed collection
===============

**Read-only**


This resource refers to a collection of user-specific feed_ items.

.. _feed: ../items/feed.html


A representation for this resource is served at the root of the API: /api/v1/. 


It is also linked in representations by any `link relation`_ with attribute:

**"rel": "feeds"**

.. _`link relation`: http://amundsen.com/media-types/collection/format/#link-relations


.. http:get:: /api/v1/auth-token/ 

   Gets the acces token for the user especified in the request content body.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1/auth-token/ HTTP/1.1
      Host: localhost:8000
      Accept: application/json

      {
        "username": "bob",
	"password": "bob-pass"
      }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Allow: POST, OPTIONS
      Content-Type: application/json

      {
        "token": "1612a857a43c21d688ccbe849dbfbf078cef8cc7"
      }

   :reqheader Accept: application/json
   :<json string username: the authenticating user's username
   :<json string password: the authenticating user's password
   :resheader Content-Type: application/json
   :>json string token: access token for future authentications 
   :statuscode 200: no error
   :statuscode 400: unable to log in with provided credentials
