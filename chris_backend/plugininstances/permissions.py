from rest_framework import permissions


class IsRelatedFeedOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to access a feed-related object (eg. a plugin instance).
    """

    def has_object_permission(self, request, view, obj):
        # Access is only allowed to related feed owners and superuser 'chris'.
        #import pdb; pdb.set_trace()
        if request.user.username == 'chris':
            return True
        if hasattr(obj, 'plugin_inst'):
            related_feed = obj.plugin_inst.feed
        else:
            related_feed = obj.feed
        if request.user in related_feed.owner.all():
            return True
        return False


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


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object modify/edit it.
    Read only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner and superuser 'chris'.
        return request.user == obj.owner
