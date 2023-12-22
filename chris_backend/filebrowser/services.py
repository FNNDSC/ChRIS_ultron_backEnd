
from django.db import models
from django.contrib.auth.models import User

from feeds.models import Feed
from servicefiles.models import ServiceFile
from pacsfiles.models import PACSFile
from userfiles.models import UserFile
from pipelines.models import PipelineSourceFile


def get_path_file_model_class(path):
    """
    Convenience function to get the file model class associated to a path.
    """
    path_tokens = path.split('/', 3)
    model_class = UserFile

    if path_tokens[0] == 'PIPELINES':
        model_class = PipelineSourceFile
    elif path_tokens[0] == 'SERVICES':
        if len(path_tokens) > 1 and path_tokens[1] == 'PACS':
            model_class = PACSFile
        else:
            model_class = ServiceFile
    return model_class


def get_path_file_queryset(path, user):
    """
    Convenience function to get the file queryset associated with a path. Raises
    ValueError if the path is not found.
    """
    username = user.username
    model_class = UserFile
    path_tokens = path.split('/', 4)

    if path_tokens[0] == 'home':
        if len(path_tokens) > 1:
            if path_tokens[1] == username:
                if len(path_tokens) > 2 and path_tokens[2] == 'feeds':
                    model_class = UserFile
            else:
                if path_tokens[1] not in get_shared_feed_creators_set(user):
                    if username != 'chris': # chris special case (can see others' not shared feeds)
                        raise ValueError('Path not found.')

                if len(path_tokens) > 3 and path_tokens[2] == 'feeds':
                    shared_feeds_qs = Feed.objects.filter(
                        owner__username=path_tokens[1]).filter(
                        models.Q(owner=user) | models.Q(public=True))
                    if path_tokens[3] not in [f'feed_{feed.id}' for feed in
                                              shared_feeds_qs .all()]:
                        if username != 'chris':
                            raise ValueError('Path not found.')
                model_class = UserFile
        else:
            return UserFile.objects.none()

    elif path_tokens[0] == 'PIPELINES':
        model_class = PipelineSourceFile

    elif path_tokens[0] == 'SERVICES':
        model_class = ServiceFile
        if len(path_tokens) > 1:
            if path_tokens[1] == 'PACS':
                model_class = PACSFile

    qs = model_class.objects.filter(fname__startswith=path)
    try:
        qs[0]
    except IndexError:
        if path not in ('PIPELINES', 'SERVICES', 'SERVICES/PACS', 'home',
                        f'home/{username}', f'home/{username}/feeds'):
            raise ValueError('Path not found.')
    return qs


def get_unauthenticated_user_path_file_queryset(path):
    """
    Convenience function to get the file queryset associated to a path for unauthenticated
    users. Raises ValueError if the path is not found.
    """
    model_class = PipelineSourceFile
    path_tokens = path.split('/', 4)

    if path_tokens[0] == 'home':
        if len(path_tokens) > 1:
            if path_tokens[1] not in get_shared_feed_creators_set():
                raise ValueError('Path not found.')
            if len(path_tokens) > 3 and path_tokens[2] == 'feeds':
                public_feeds_qs = Feed.objects.filter(
                    public=True).filter(owner__username=path_tokens[1])
                if path_tokens[3] not in [f'feed_{feed.id}' for feed in
                                          public_feeds_qs.all()]:
                    raise ValueError('Path not found.')
        else:
            return UserFile.objects.none()
        model_class = PluginInstanceFile

    qs = model_class.objects.filter(fname__startswith=path)
    try:
        qs[0]
    except IndexError:
        if path not in ('PIPELINES', 'home'):
            raise ValueError('Path not found.')
    return qs


def get_path_folders(path, user):
    """
    Convenience function to get the immediate subfolders under a path.
    """
    username = user.username
    if not path:
        return ['PIPELINES', 'SERVICES', 'home']

    path_tokens = path.split('/', 3)
    if len(path_tokens) == 3 and path_tokens[0] == 'home' and path_tokens[2] == 'feeds':
        if path_tokens[1] != username and username != 'chris':
            return sorted([f'feed_{f.id}' for f in Feed.objects.filter(
                owner__username=path_tokens[1]).filter(
                models.Q(owner=user) | models.Q(public=True))])

    hash_set = set()
    if path_tokens[0] == 'home':
        if path == 'home':
            if username == 'chris':
                return sorted([u.username for u in User.objects.all() if u.feed.count()])
            shared_feed_creators = get_shared_feed_creators_set(user)
            shared_feed_creators.add(username)
            return sorted(shared_feed_creators)
        if path == f'home/{username}':
            hash_set.add('feeds')
    elif path == 'SERVICES':
        hash_set.add('PACS')

    qs = get_path_file_queryset(path, user)

    existing_path = False
    for obj in qs:
        name = obj.fname.name
        if name.startswith(path + '/'):
            existing_path = True
            folder = name.replace(path + '/', '', 1)
            try:
                first_slash_ix = folder.index('/')
            except ValueError:
                pass  # no folders under this path (only files)
            else:
                folder = folder[:first_slash_ix]
                hash_set.add(folder)

    if len(qs) and not existing_path:
        raise ValueError('Path not found.')
    return sorted(hash_set)


def get_unauthenticated_user_path_folders(path):
    """
    Convenience function to get the immediate subfolders under a path for unauthenticated
    users.
    """
    if not path:
        return ['PIPELINES', 'home']

    if path == 'home':
        public_feed_creators = get_shared_feed_creators_set()
        return sorted(public_feed_creators)

    path_tokens = path.split('/', 3)
    if len(path_tokens) == 3 and path_tokens[0] == 'home' and path_tokens[2] == 'feeds':
        return sorted([f'feed_{f.id}' for f in Feed.objects.filter(public=True).filter(
            owner__username=path_tokens[1])])

    qs = get_unauthenticated_user_path_file_queryset(path)

    hash_set = set()
    existing_path = False
    for obj in qs:
        name = obj.fname.name
        if name.startswith(path + '/'):
            existing_path = True
            folder = name.replace(path + '/', '', 1)
            try:
                first_slash_ix = folder.index('/')
            except ValueError:
                pass  # no folders under this path (only files)
            else:
                folder = folder[:first_slash_ix]
                hash_set.add(folder)

    if len(qs) and not existing_path:
        raise ValueError('Path not found.')
    return sorted(hash_set)


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
        creator = feed.get_creator()
        if creator.username != username:
            creators_set.add(creator.username)
    return creators_set
