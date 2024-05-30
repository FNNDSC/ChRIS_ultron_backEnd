
from rest_framework import permissions


class IsOwnerOrChrisOrHasWritePermissionOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser 'chris' or users
    with write permission to modify/edit it. Read-only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner, superuser 'chris' and users
        # with write permission.
        user = request.user
        return (user == obj.owner or user.username == 'chris' or
                obj.has_user_permission(user, 'w'))


class IsOwnerOrChrisOrHasAnyPermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of an object to
    modify/edit it. Read-only access is allowed to other users that have been
    granted any permission.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.owner == user or user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.has_user_permission(user))


class IsOwnerOrChrisOrHasAnyPermissionOrObjIsPublic(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris', the owner of an object or any
    users that have been granted any permission to access an object. Also access is
    allowed to all users if the object is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        return (obj.owner == user or user.username == 'chris' or obj.public or
                obj.has_user_permission(user))


class IsFolderOwnerOrChrisOrHasAnyFolderPermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of an object's
    related folder to modify/edit the object. Read-only access is allowed to other users
    that have been granted any permission to the object's related folder.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.folder.owner == user or user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.folder.has_user_permission(user))


class IsFileOwnerOrChrisOrHasAnyFilePermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of an object's
    related file to modify/edit the object. Read-only access is allowed to other users
    that have been granted any permission to the object's related file.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.file.owner == user or user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.file.has_user_permission(user))


class IsLinkFileOwnerOrChrisOrHasAnyLinkFilePermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of an object's
    related link file to modify/edit the object. Read-only access is allowed to other
    users that have been granted any permission to the object's related link file.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.link_file.owner == user or user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.link_file.has_user_permission(user))
