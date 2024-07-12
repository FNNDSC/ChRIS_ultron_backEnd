

from django.db import models

from core.models import ChrisFolder


def get_folder_queryset(pk_dict, user=None):
    """
    Convenience function to get a single folder queryset.
    """
    qs = ChrisFolder.objects.filter(**pk_dict)

    if qs.exists():
        folder = qs.first()

        if user is None:  # unauthenticated user
            if not folder.public:
                return ChrisFolder.objects.none()
        else:
            if not (folder.owner == user or user.username == 'chris' or folder.public
                    or folder.has_user_permission(user)):
                return ChrisFolder.objects.none()
    return qs



def get_folder_children_queryset(folder, user=None):
    """
    Convenience function to get the queryset of the immediate subfolders under a folder.
    """
    if user is None:
        return folder.children.filter(public=True)

    if user.username == 'chris':
        return folder.children.all()

    lookup = models.Q(owner=user) | models.Q(public=True) | models.Q(
        shared_users=user) | models.Q(shared_groups__pk__in=[g.id for g
                                                             in user.groups.all()])
    return folder.children.filter(lookup)


def get_folder_files_queryset(folder, user=None):
    """
    Convenience function to get the queryset of the immediate files under a folder.
    """
    if user is None:
        return folder.chris_files.filter(public=True)

    if user.username == 'chris':
        return folder.chris_files.all()

    lookup = models.Q(owner=user) | models.Q(public=True) | models.Q(
        shared_users=user) | models.Q(shared_groups__pk__in=[g.id for g
                                                             in user.groups.all()])
    return folder.chris_files.filter(lookup)


def get_folder_link_files_queryset(folder, user=None):
    """
    Convenience function to get the queryset of the immediate link files under a folder.
    """
    if user is None:
        return folder.chris_link_files.filter(public=True)

    if user.username == 'chris':
        return folder.chris_link_files.all()

    lookup = models.Q(owner=user) | models.Q(public=True) | models.Q(
        shared_users=user) | models.Q(shared_groups__pk__in=[g.id for g
                                                             in user.groups.all()])
    return folder.chris_link_files.filter(lookup)
