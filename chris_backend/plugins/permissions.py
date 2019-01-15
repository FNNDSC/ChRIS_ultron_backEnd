from rest_framework import permissions


class IsRelatedFeedOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to access a feed-related object (eg. a plugin instance).
    """

    def has_object_permission(self, request, view, obj):
        # Access is only allowed to related feed owners and superuser 'chris'.
        #import pdb; pdb.set_trace()
        if request.user.username == 'chris':
            return True
        if hasattr(obj, 'plugin_inst'):
            related_feed = obj.plugin_inst.feed
        else:
            related_feed = obj.feed
        if request.user in related_feed.owner.all():
            return True
        return False
