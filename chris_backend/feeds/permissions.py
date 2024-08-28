
from rest_framework import permissions


class IsChrisOrFeedOwnerOrHasFeedPermissionOrPublicFeedReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris', the owner of a feed associated
    to an object and users that have been granted the feed permission to modify/edit the
    object (eg. a note). Read-only access is allowed to any user if the feed is public.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS and obj.feed.public:
            return True

        return (request.user.username == 'chris' or obj.feed.owner == request.user or
                obj.feed.has_user_permission(request.user))


class IsOwnerOrChrisOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser 'chris' to
    modify/edit it. Read-only is allowed to other users.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.owner == request.user or request.user.username == 'chris'


class IsOwnerOrChrisOrHasPermissionOrPublicReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris', the owner of a feed and
    users that have been granted the feed permission to modify/edit the feed.
    Read-only access is allowed to any user if the feed is public.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS and obj.public:
            return True

        return (obj.owner == request.user or request.user.username == 'chris' or
                obj.has_user_permission(request.user))


class IsOwnerOrChrisOrHasPermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of a feed to
    modify/edit the feed. Read-only access is allowed to other users that have been
    granted the feed permission.
    """

    def has_object_permission(self, request, view, obj):

        if obj.owner == request.user or request.user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.has_user_permission(request.user))


class IsChrisOrFeedOwnerOrHasFeedPermissionReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris' and the owner of a feed associated
    to an object to modify/edit the object. Read-only access is allowed to other users
    that have been granted the feed permission.
    """

    def has_object_permission(self, request, view, obj):

        if obj.feed.owner == request.user or request.user.username == 'chris':
            return True

        return (request.method in permissions.SAFE_METHODS and
                obj.feed.has_user_permission(request.user))


class IsOwnerOrChrisOrFeedOwnerOrHasFeedPermissionReadOnlyOrPublicFeedReadOnly(
    permissions.BasePermission):
    """
    Custom permission to only allow superuser 'chris', the owner of an object and the
    owner of the object's associated feed to modify/edit the object (eg. a comment).
    Read-only access is allowed to users that have been granted the associated feed
    access permission or to any user if the feed is public.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.owner == user or user.username == 'chris' or obj.feed.owner == user:
            return True

        return request.method in permissions.SAFE_METHODS and (
            obj.feed.public or obj.feed.has_user_permission(user))
