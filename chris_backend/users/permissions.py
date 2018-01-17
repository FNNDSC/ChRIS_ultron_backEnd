from rest_framework import permissions


class IsUserOrChris(permissions.BasePermission):
    """
    Custom permission to only allow the user or superuser
    'chris' to acces, modify/edit the user's information.
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        return (obj.username == request.user.username) or (request.user.username == 'chris')


