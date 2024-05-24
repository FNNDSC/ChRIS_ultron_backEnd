
from rest_framework import permissions


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


class IsNotDeleteFSPluginInstance(permissions.BasePermission):
    """
    Custom permission to only allow deleting a plugin instance if it is not of type
    'fs'.
    """

    def has_object_permission(self, request, view, obj):
        return request.method != 'DELETE' or obj.plugin.meta.type != 'fs'


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
