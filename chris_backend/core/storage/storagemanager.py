import abc
from typing import List, AnyStr, Optional


class StorageManager(abc.ABC):
    """
    ``StorageManager`` provides an interface between ChRIS and its file storage backend.

    ``StorageManager`` methods implement helper functions for browsing stored files and retrieving
    file data. These functions are analogous to ``ls``, ``stat``, and ``cat`` commands.
    """

    @abc.abstractmethod
    def create_container(self) -> None:
        """
        Create the container where all ChRIS file data is to be stored.

        For Swift, a container is... a container. For S3, a container is a bucket.

        For a plain filesystem, a container is simply the top-level/parent directory.
        """
        ...

    def ls(self, path_prefix: str) -> List[str]:
        """
        :returns: a list of all files under a given path prefix.
        """
        ...

    def path_exists(self, path: str) -> bool:
        """
        :returns: True if path exists (whether it be a directory OR file)
        """
        ...

    def obj_exists(self, file_path: str) -> bool:
        """
        :returns: True if given path is an existing file
        """
        ...

    def upload_obj(self, file_path: str, contents: AnyStr, content_type: Optional[str] = None):
        """
        Upload file data to the storage service.

        :param file_path: file path to upload to
        :param contents: file data
        :param content_type: optional media type, e.g. "text/plain"
        """
        ...

    def download_obj(self, file_path: str) -> AnyStr:
        """
        Download file data from the storage service.
        """
        ...

    def copy_obj(self, src: str, dst: str) -> None:
        """
        Copy data to a new path.

        Instead of a copy, implementations may create links or shallow copies for efficiency.
        """
        ...

    def delete_obj(self, file_path: str) -> None:
        """
        Delete data from the given path.
        """
        ...
