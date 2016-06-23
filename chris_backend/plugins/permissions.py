from rest_framework import permissions


class IsChrisOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' to modify/edit it.
    Read only is allowed to other users.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the superuser 'chris'.
        return request.user.username == 'chris' 

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)   




