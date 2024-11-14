
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


class IsChrisOrIsPACSUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and other users in the pacs_users
    group to create objects. Read only is allowed to all other users.
    """

    def has_permission(self, request, view):
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            return True

        return user.username == 'chris' or user.groups.filter(name='pacs_users').exists()


class IsChrisOrOwnerOrIsPACSUserReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' to create it.
    Read only is allowed to other users in the pacs_users group.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.username == 'chris' or user == obj.owner:
            return True

        return (request.method in permissions.SAFE_METHODS and user.groups.filter(
                name='pacs_users').exists())
