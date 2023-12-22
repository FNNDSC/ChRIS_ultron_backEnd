
from rest_framework import permissions


class IsChrisOrOwnerOrNotLockedReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a pipeline or superuser
    'chris' to modify/edit it. Read only is allowed to other users only
    when object is not locked.
    """

    def has_object_permission(self, request, view, obj):
        pipeline = obj.pipeline if hasattr(obj, 'pipeline') else obj

        if (request.method in permissions.SAFE_METHODS) and not pipeline.locked:
            # Read permissions are allowed to any user if object is not locked
            return True

        # superuser 'chris' and owner always have read/write access
        return (request.user == pipeline.owner) or (request.user.username == 'chris')


class IsChrisOrOwnerAndLockedOrNotLockedReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow read/write access to the Superuser Chris or the
    object's owner when corresponding pipeline is locked. Read only access is granted to
    any user when corresponding pipeline is not locked.
    """

    def has_object_permission(self, request, view, obj):
        pipeline = obj.plugin_piping.pipeline

        if request.user.username == 'chris':
            # superuser 'chris' always has read/write access
            return True

        if pipeline.locked:
            # owner has read/write access
            return request.user == pipeline.owner

        # only allow read access (GET, HEAD or OPTIONS requests.)
        return request.method in permissions.SAFE_METHODS
