from rest_framework import permissions


class IsRelatedFeedOwnerOrPublicReadOnlyOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of a feed associated to an object or superuser
    'chris' to modify/edit the object. Read only is allowed to other users if the related
    feed is public.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.username == 'chris':
            return True

        if hasattr(obj, 'plugin_inst'):
            feed = obj.plugin_inst.feed
        else:
            feed = obj.feed
        return (request.method in permissions.SAFE_METHODS and feed.public) or (
                request.user in feed.owner.all())


class IsOwnerOrChrisOrAuthenticatedReadOnlyOrPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to authenticated users and to
    unauthenticated users if the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.username == 'chris' or user == obj.owner:
            return True

        return request.method in permissions.SAFE_METHODS and (user.is_authenticated or
                                                               obj.feed.public)


class IsAuthenticatedReadOnlyOrPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to allow read only access to authenticated users and to
    unauthenticated users if the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS and (
                request.user.is_authenticated or obj.feed.public)


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
