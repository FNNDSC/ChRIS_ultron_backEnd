
from django.db import models

from feeds.models import Feed
from servicefiles.models import ServiceFile
from pacsfiles.models import PACSFile
from uploadedfiles.models import UploadedFile
from plugininstances.models import PluginInstanceFile
from pipelines.models import PipelineSourceFile


def get_path_file_model_class(path, username):
    """
    Convenience function to get the file model class associated to a path.
    """
    model_class = PluginInstanceFile
    if path.split('/', 1)[0] == 'PIPELINES':
        model_class = PipelineSourceFile
    elif path.startswith('SERVICES/PACS'):
        model_class = PACSFile
    elif path.split('/', 1)[0] == 'SERVICES':
        model_class = ServiceFile
    elif path.startswith(f'{username}/uploads'):
        model_class = UploadedFile
    return model_class


def get_path_file_queryset(path, user):
    """
    Convenience function to get the file queryset associated to a path. Raises ValueError
    if the path is not found.
    """
    username = user.username
    model_class = get_path_file_model_class(path, username)

    path_username = path.split('/', 1)[0]
    if model_class == PluginInstanceFile and not path_username == username:

        if username == 'chris':  # chris special case (can see others' not shared feeds)
            if path == path_username:
                return model_class.objects.filter(fname__startswith=path + '/')
            else:
                return model_class.objects.filter(fname__startswith=path)

        shared_feed_user = None
        shared_feed_creators = get_shared_feed_creators_set(user)
        for feed_creator in shared_feed_creators:
            if path_username == feed_creator.username:
                shared_feed_user = feed_creator
                break
        if shared_feed_user is None:
            # path doesn't start with a username that explictily shared a feed with this
            # user or created a public feed
            raise ValueError('Path not found.')
        elif path == shared_feed_user.username:
            qs = model_class.objects.none()
        else:
            shared_feeds_qs = Feed.objects.filter(owner=shared_feed_user).filter(
                models.Q(owner=user) | models.Q(public=True))
            shared_feed = None
            for feed in shared_feeds_qs.all():
                if path.startswith(f'{shared_feed_user.username}/feed_{feed.id}'):
                    shared_feed = feed
                    break
            if shared_feed is None:
                raise ValueError('Path not found.')
            else:
                qs = model_class.objects.filter(fname__startswith=path)
    else:
        if path == username:  # avoid colliding with usernames that are a superset of this
            qs = model_class.objects.filter(fname__startswith=path+'/')
        else:
            qs = model_class.objects.filter(fname__startswith=path)
        try:
            qs[0]
        except IndexError:
            if path not in ('PIPELINES', 'SERVICES', 'SERVICES/PACS', username,
                            f'{username}/uploads'):
                raise ValueError('Path not found.')
    return qs


def get_unauthenticated_user_path_file_queryset(path):
    """
    Convenience function to get the file queryset associated to a path for unauthenticated
    users. Raises ValueError if the path is not found.
    """
    path_username = path.split('/', 1)[0]
    if path_username == 'PIPELINES':
        return PipelineSourceFile.objects.filter(fname__startswith=path)
    public_feed_user = None
    public_feed_creators = get_shared_feed_creators_set()
    for feed_creator in public_feed_creators:
        if path_username == feed_creator.username:
            public_feed_user = feed_creator
            break
    if public_feed_user is None:
        # path doesn't start with a username that created a public feed
        raise ValueError('Path not found.')
    elif path == public_feed_user.username:
        qs = PluginInstanceFile.objects.none()
    else:
        public_feeds_qs = Feed.objects.filter(
            public=True).filter(owner=public_feed_user)
        public_feed = None
        for feed in public_feeds_qs.all():
            if path.startswith(f'{public_feed_user.username}/feed_{feed.id}'):
                public_feed = feed
                break
        if public_feed is None:
            raise ValueError('Path not found.')
        else:
            qs = PluginInstanceFile.objects.filter(fname__startswith=path)
    return qs


def get_path_folders(path, user):
    """
    Convenience function to get the immediate subfolders under a path.
    """
    qs = get_path_file_queryset(path, user)
    username = user.username
    model_class = get_path_file_model_class(path, username)

    if model_class == PluginInstanceFile and path.split('/', 1)[0] == path and path != \
            username and username != 'chris':  # handle chris special case
            shared_feeds_qs = Feed.objects.filter(owner__username=path).filter(
                models.Q(owner=user) | models.Q(public=True))
            subfolders = sorted([f'feed_{feed.id}' for feed in shared_feeds_qs])
    else:
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
        if path == 'SERVICES':
            hash_set.add('PACS')
        if path == username:
            hash_set.add('uploads')
        subfolders = sorted(hash_set)
    return subfolders


def get_unauthenticated_user_path_folders(path):
    """
    Convenience function to get the immediate subfolders under a path for unauthenticated
    users.
    """
    qs = get_unauthenticated_user_path_file_queryset(path)
    path_username = path.split('/', 1)[0]

    if path_username == path and path_username != 'PIPELINES':
            shared_feeds_qs = Feed.objects.filter(owner__username=path).filter(public=True)
            subfolders = sorted([f'feed_{feed.id}' for feed in shared_feeds_qs])
    else:
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
        subfolders = sorted(hash_set)
    return subfolders


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
            creators_set.add(creator)
    return creators_set
