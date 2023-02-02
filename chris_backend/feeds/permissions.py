
from rest_framework import permissions


class IsOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        if hasattr(obj.owner, 'all'):
            return (request.user in obj.owner.all()) or (request.user.username == 'chris')
        return (obj.owner == request.user) or (request.user.username == 'chris')


class IsFeedOwnerOrChrisOrPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser 'chris' to
    modify/edit it. Read only is allowed to other users if the object is public.
    """

    def has_object_permission(self, request, view, obj):
        return (request.method in permissions.SAFE_METHODS and obj.public) or (
                request.user in obj.owner.all()) or (request.user.username == 'chris')


class IsRelatedFeedOwnerOrPublicReadOnlyOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of a feed associated to an object or superuser
    'chris' to modify/edit the object (eg. a note). Read only is allowed to other users
    if the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and obj.feed.public) or (
                request.user in obj.feed.owner.all())


class IsOwnerOrChrisOrReadOnlyOrRelatedFeedPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to other authenticated users.
    Read only is also allowed to unauthenticated users when the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.username == 'chris':
            return True

        return obj.owner == user or (request.method in permissions.SAFE_METHODS and (
                user.is_authenticated or obj.feed.public))


class IsAuthenticatedOrRelatedFeedPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to allow Read-only access to authenticated users.
    Read only is also allowed to unauthenticated users when the related feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        return request.method in permissions.SAFE_METHODS and (
                user.is_authenticated or obj.feed.public)


class IsRelatedTagOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow the owner of a tag associated to an object or
    superuser 'chris' to access the object (eg. a tagging).
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        if (request.user.username == 'chris') or (request.user == obj.tag.owner):
            return True
        return False
