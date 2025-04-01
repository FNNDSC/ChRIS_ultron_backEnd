from typing import Dict, Any, ContextManager
from tempfile import TemporaryDirectory
import unittest.mock
from contextlib import contextmanager

from core.storage.storagemanager import StorageManager
from core.storage.swiftmanager import SwiftManager
from core.storage.plain_fs import FilesystemManager


def connect_storage(settings) -> StorageManager:
    """
    :param settings: django.conf.settings object
    :returns: a manager for the storage configured by settings
    """
    storage_name = __get_storage_name(settings)
    if storage_name == 'SwiftStorage':
        return SwiftManager(settings.SWIFT_CONTAINER_NAME, settings.SWIFT_CONNECTION_PARAMS)
    elif storage_name == 'FileSystemStorage':
        return FilesystemManager(settings.MEDIA_ROOT)
    raise ValueError(f'Unsupported storage system: {storage_name}')


def verify_storage_connection(**kwargs) -> None:
    """
    Create a ``StorageManager`` for the given settings. Raises an exception if the connection
    or configuration is wrong.

    If the connection works, then ``StorageManager.create_container`` is called.
    """
    settings = _DummySettings(kwargs)
    storage_manager = connect_storage(settings)
    storage_manager.create_container()


@contextmanager
def mock_storage(target_settings) -> ContextManager[FilesystemManager]:
    """
    For testing only.

    Uses ``unittest.mock.patch`` to configure a given settings object to use a temporary directory
    for ChRIS files storage.

    :param target_settings: a django.conf settings object
    :returns: a FilesystemManager for the temporary directory
    """
    with TemporaryDirectory() as tmp_dir:
        settings = {
            'STORAGES': {
                'default': {'BACKEND': 'fake.FileSystemStorage'}
            },
            'MEDIA_ROOT': tmp_dir
        }
        with unittest.mock.patch.multiple(target_settings, **settings):
            yield FilesystemManager(tmp_dir)


class _DummySettings:

    def __init__(self, settings_dict: Dict[str, str]):
        for k, v in settings_dict.items():
            setattr(self, k, v)


def __get_storage_name(settings: Any) -> str:
    return settings.STORAGES['default']['BACKEND'].rsplit('.', maxsplit=1)[-1]
