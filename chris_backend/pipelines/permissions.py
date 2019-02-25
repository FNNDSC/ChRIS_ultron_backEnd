
from rest_framework import permissions


class IsOwnerOrChrisOrNotLockedReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to other users only
    when object is not locked.
    """

    def has_object_permission(self, request, view, obj):
        if (request.user.username == 'chris') or (obj.owner == request.user):
            # superuser 'chris' and owner always have read/write access
            return True

        # Read permissions are allowed to other users if object is not locked,
        return (request.method in permissions.SAFE_METHODS) and not obj.locked


class IsChirsOrOwnerAndLockedOrNotLockedReadOnly(permissions.BasePermission):
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
            return pipeline.owner == request.user
        else:
            # only allow read access (GET, HEAD or OPTIONS requests.)
            return request.method in permissions.SAFE_METHODS


class IsChirsOrOwnerOrNotLocked(permissions.BasePermission):
    """
    Custom permission to only allow access to the Superuser Chris or the object's owner.
    Access is granted to any other user when corresponding pipeline is not locked.
    """

    def has_object_permission(self, request, view, obj):
        pipeline = obj.pipeline
        if (request.user.username == 'chris') or (pipeline.owner == request.user):
            # superuser 'chris' and owner always have read/write access
            return True
        return not pipeline.locked