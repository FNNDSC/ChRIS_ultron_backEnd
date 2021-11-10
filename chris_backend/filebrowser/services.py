
from servicefiles.models import ServiceFile
from servicefiles.serializers import ServiceFileSerializer
from pacsfiles.models import PACSFile
from pacsfiles.serializers import PACSFileSerializer
from uploadedfiles.models import UploadedFile
from uploadedfiles.serializers import UploadedFileSerializer
from plugininstances.models import PluginInstanceFile
from plugininstances.serializers import PluginInstanceFileSerializer


def get_path_file_model_class(path, username):
    """
    Convenience function to get the file model class associated to a path.
    """
    model_class = None
    if path.startswith('SERVICES/PACS'):
        model_class = PACSFile
    elif path.startswith('SERVICES'):
        model_class = ServiceFile
    elif path.startswith(f'{username}/uploads'):
        model_class = UploadedFile
    elif path.startswith(f'{username}'):
        model_class = PluginInstanceFile
    return model_class


def get_path_file_serializer_class(path, username):
    """
    Convenience function to get the file serializer class associated to a path.
    """
    model_class = get_path_file_model_class(path, username)
    if model_class is None:
        return None
    serializers_map = {'ServiceFile': ServiceFileSerializer,
                       'PACSFile': PACSFileSerializer,
                       'UploadedFile': UploadedFileSerializer,
                       'PluginInstanceFile': PluginInstanceFileSerializer
                       }
    return serializers_map[model_class.__name__]


def get_path_file_queryset(path, username):
    """
    Convenience function to get the queryset associated to a path. Raises ValueError
    if the path is not found.
    """
    model_class = get_path_file_model_class(path, username)
    if model_class is None:
        raise ValueError('Path not found.')
    qs = model_class.objects.filter(fname__startswith=path)
    try:
        qs[0]
    except IndexError:
        if path not in ('SERVICES', 'SERVICES/PACS', f'{username}', f'{username}/uploads'):
            raise ValueError('Path not found.')
    return qs


def get_path_folders(path, username):
    """
    Convenience function to get the immediate subfolders under a path.
    """
    qs = get_path_file_queryset(path, username)
    hash_set = set()
    for obj in qs:
        name = obj.fname.name
        folder = name.replace(path + '/', '', 1)
        try:
            first_slash_ix = folder.index('/')
        except ValueError:
            pass  # no folders under this path (only files)
        else:
            folder = folder[:first_slash_ix]
            if folder not in hash_set:
                hash_set.add(folder)
    subfolders = list(hash_set)
    if path == 'SERVICES':
        subfolders.append('PACS')
    if path == f'{username}':
        subfolders.append('uploads')
    return subfolders
