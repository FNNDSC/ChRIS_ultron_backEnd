from rest_framework import permissions


class IsOwnerOrChrisOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit it. Read only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner and superuser 'chris'.
        if hasattr(obj.owner, 'all'):
            return (request.user in obj.owner.all()) or (request.user.username == 'chris')
        return (obj.owner == request.user) or (request.user.username == 'chris')
