from rest_framework import permissions


class IsOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Access and write permissions are only allowed to the authenticated owner and
        # superuser 'chris'.
        return (obj.owner == request.user) or (request.user.username == 'chris')