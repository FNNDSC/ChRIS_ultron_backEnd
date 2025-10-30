
from rest_framework import permissions


class IsOwnerOrChrisOrHasFeedPermissionReadOnlyOrPublicFeedReadOnly(
    permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser 'chris' to
    modify/edit it (e.g. a plugin instance).
    Read-only access is allowed to users that have been granted the object's feed
    access permission or to any user if the object's feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if hasattr(obj, 'plugin_inst'):
            obj = obj.plugin_inst

        if user.username == 'chris' or user == obj.owner:
            return True

        return request.method in permissions.SAFE_METHODS and (
                obj.feed.public or obj.feed.has_user_permission(user))


class IsNotDeleteFSPluginInstance(permissions.BasePermission):
    """
    Custom permission to only allow deleting a plugin instance if it is not of type
    'fs'.
    """

    def has_object_permission(self, request, view, obj):
        return request.method != 'DELETE' or obj.plugin.meta.type != 'fs'
