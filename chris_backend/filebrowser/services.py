
from django.db import models

from core.models import ChrisFolder
from feeds.models import Feed


def get_authenticated_user_folder_queryset(pk_dict, user):
    """
    Convenience function to get a folder queryset for the authenticated user.
    """
    try:
        folder = ChrisFolder.objects.get(**pk_dict)
    except ChrisFolder.DoesNotExist:
        return ChrisFolder.objects.none()

    qs = ChrisFolder.objects.filter(**pk_dict)
    username = user.username

    if username == 'chris':  # chris user can see every existing folder
        return qs

    path = folder.path
    if path in ('', 'home') or path.startswith(('PIPELINES', 'SERVICES')):
        return qs

    path_tokens = path.split('/', 4)
    if path_tokens[1] == username:
        return qs

    shared_feed_creators = get_shared_feed_creators_set(user)

    if path_tokens[1] in shared_feed_creators:
        if len(path_tokens) == 2:
            return qs
        if path_tokens[2] == 'feeds':
            if len(path_tokens) == 3:
                return qs
            if path_tokens[3] in [f'feed_{f.id}' for f in Feed.objects.filter(
                    owner__username=path_tokens[1]).filter(
                models.Q(owner=user) | models.Q(public=True))]:
                return qs
    return ChrisFolder.objects.none()


def get_unauthenticated_user_folder_queryset(pk_dict):
    """
    Convenience function to get a folder queryset for the unauthenticated user.
    """
    try:
        folder = ChrisFolder.objects.get(**pk_dict)
    except ChrisFolder.DoesNotExist:
        return ChrisFolder.objects.none()

    path = folder.path
    if path.startswith('SERVICES'):
        return ChrisFolder.objects.none()

    qs = ChrisFolder.objects.filter(**pk_dict)

    if path in ('', 'home') or path.startswith('PIPELINES'):
        return qs

    path_tokens = path.split('/', 4)
    public_feed_creators = get_shared_feed_creators_set()

    if path_tokens[1] in public_feed_creators:
        if len(path_tokens) == 2:
            return qs
        if path_tokens[2] == 'feeds':
            if len(path_tokens) == 3:
                return qs
            if path_tokens[3] in [f'feed_{f.id}' for f in Feed.objects.filter(
                    owner__username=path_tokens[1]).filter(public=True)]:
                return qs
    return ChrisFolder.objects.none()


def get_authenticated_user_folder_children(folder, user):
    """
    Convenience function to get the list of the immediate subfolders under a folder
    for the authenticated user.
    """
    username = user.username
    if username == 'chris':  # chris user can see every existing folder
        return list(folder.children.all())

    path = folder.path
    if path == '' or path.startswith(('PIPELINES', 'SERVICES')):
        return list(folder.children.all())

    shared_feed_creators = set()
    computed_shared_feed_creators = False
    shared_feeds = []
    computed_shared_feeds = False
    children = []

    for child_folder in folder.children.all():
        path = child_folder.path
        path_tokens = path.split('/', 4)

        if path_tokens[1] == username:
            children.append(child_folder)
        else:
            if not computed_shared_feed_creators:
                shared_feed_creators = get_shared_feed_creators_set(user)
                computed_shared_feed_creators = True

            if path_tokens[1] in shared_feed_creators:
                if len(path_tokens) == 2:
                    children.append(child_folder)
                elif path_tokens[2] == 'feeds':
                    if len(path_tokens) == 3:
                        children.append(child_folder)
                    else:
                        if not computed_shared_feeds:
                            shared_feeds = [f'feed_{f.id}' for f in Feed.objects.filter(
                            owner__username=path_tokens[1]).filter(
                                models.Q(owner=user) | models.Q(public=True))]
                            computed_shared_feeds = True

                        if path_tokens[3] in shared_feeds:
                            children.append(child_folder)
    return children


def get_unauthenticated_user_folder_children(folder):
    """
    Convenience function to get the list of the immediate subfolders under a folder
    for the unauthenticated user.
    """
    path = folder.path
    if path == '':
        return list(folder.children.filter(
            models.Q(path='home') | models.Q(path='PIPELINES')))

    if path.startswith('PIPELINES'):
        return list(folder.children.all())

    public_feed_creators = get_shared_feed_creators_set()
    public_feeds = []
    computed_public_feeds = False
    children = []

    for child_folder in folder.children.all():
        path = child_folder.path
        path_tokens = path.split('/', 4)

        if path_tokens[1] in public_feed_creators:
            if len(path_tokens) == 2:
                children.append(child_folder)
            elif path_tokens[2] == 'feeds':
                if len(path_tokens) == 3:
                    children.append(child_folder)
                else:
                    if not computed_public_feeds:
                        public_feeds = [f'feed_{f.id}' for f in Feed.objects.filter(
                        owner__username=path_tokens[1]).filter(public=True)]
                        computed_public_feeds = True

                    if path_tokens[3] in public_feeds:
                        children.append(child_folder)
    return children


def get_shared_feed_creators_set(user=None):
    """
    Convenience function to get the set of creators of the feeds that have been shared
    with the passed user (including public feeds).
    """
    creators_set = set()
    if user is None:
        feeds_qs = Feed.objects.filter(public=True)
        username = ''
    else:
        feeds_qs = Feed.objects.filter(models.Q(owner=user) | models.Q(public=True))
        username = user.username
    for feed in feeds_qs.all():
        creator = feed.owner
        if creator.username != username:
            creators_set.add(creator.username)
    return creators_set
