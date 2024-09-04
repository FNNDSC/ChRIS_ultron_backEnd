
from rest_framework import permissions


class IsUserOrChrisOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the authenticated user and
        # superuser 'chris'.
        return (obj == request.user) or (request.user.username == 'chris')


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to modify/edit. Read only is allowed
    to normal users.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to normal users.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Raed/Write permissions are allowed to the admin users
        return request.user.is_staff
