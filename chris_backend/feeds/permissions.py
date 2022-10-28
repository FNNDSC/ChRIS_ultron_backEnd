
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
            return (
                request.user in obj.owner.all()) or (
                request.user.username == 'chris')
        return (obj.owner == request.user) or (
            request.user.username == 'chris')


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

        # Write permissions are only allowed to the owner and superuser
        # 'chris'.
        if hasattr(obj.owner, 'all'):
            return (
                request.user in obj.owner.all()) or (
                request.user.username == 'chris')
        return (obj.owner == request.user) or (
            request.user.username == 'chris')


class IsRelatedFeedOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of a feed associated to an object or superuser
    'chris' to modify/edit the object (eg. a note).
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        if request.user.username == 'chris':
            return True
        return request.user in obj.feed.owner.all()


class IsRelatedTagOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow the owner of a tag associated to an object or
    superuser 'chris' to access the object (eg. a tagging).
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        if (request.user.username == 'chris') or (
                request.user == obj.tag.owner):
            return True
        return False
