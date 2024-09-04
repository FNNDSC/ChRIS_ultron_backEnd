
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
