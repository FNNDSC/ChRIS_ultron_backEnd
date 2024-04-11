
from rest_framework import permissions

from feeds.models import Feed


class IsOwnerOrChrisOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner and superuser 'chris'.
        return (request.user == obj.owner) or (request.user.username == 'chris')


class IsOwnerOrChrisOrRelatedFeedOwnerOrPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of the object, owners of a feed associated
    to an object or superuser 'chris' to modify/edit the object. Read only is allowed
    to other users if the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        path = obj.fname.name
        path_tokens = path.split('/', 4)

        if  path_tokens[0] == 'PIPELINES':  # accessible to everybody
            return True

        if not user.is_authenticated:
            if (len(path_tokens) > 3 and path_tokens[0] == 'home' and path_tokens[2] ==
                    'feeds'):
                feed_id = int(path_tokens[3].split('_')[1])
                feed = Feed.objects.get(id=feed_id)
                return request.method in permissions.SAFE_METHODS and feed.public
            return False

        if  path_tokens[0] == 'SERVICES':  # accessible to all authenticated users
            return True

        if request.user.username == 'chris' or obj.owner == request.user:
            return True

        if (len(path_tokens) > 3 and path_tokens[0] == 'home' and path_tokens[2] ==
                'feeds'):
            feed_id = int(path_tokens[3].split('_')[1])
            feed = Feed.objects.get(id=feed_id)
            return request.user in feed.owner.all() or (
                    request.method in permissions.SAFE_METHODS and feed.public)
        return False
