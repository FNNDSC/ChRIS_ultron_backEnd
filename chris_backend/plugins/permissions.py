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


class IsRelatedFeedOwnerOrChris(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or superuser
    'chris' to modify/edit a feed-related object (eg. a note).
    """

    def has_object_permission(self, request, view, obj):
        # Read and write permissions are only allowed to
        # the owner and superuser 'chris'.
        #import pdb; pdb.set_trace()
        if request.user.username == 'chris':
            return True
        if hasattr(obj.plugin_inst.feed, 'all'):
            owner_lists = [feed.owner.all() for feed in obj.plugin_inst.feed.all()]
            for owner_list in owner_lists:
                if request.user in owner_list:
                    return True
        elif request.user in obj.plugin_inst.feed.owner.all():
            return True
        return False




