
from rest_framework import permissions


class IsChrisOrIsPACSUserReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' to create it.
    Read only is allowed to other users in the pacs_users group.
    """

    def has_permission(self, request, view):
        user = request.user

        if user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and user.groups.filter(
                name='pacs_users').exists())
