
from pathlib import Path
import shutil
from typing import Union, List, AnyStr, Optional

from core.storage.storagemanager import StorageManager


class FilesystemManager(StorageManager):
    """
    The simplest manager, something everyone has, the one you can trust...

    ``FilesystemManager`` is for storing files on disk as-is, no magic involved.
    More technically, ``FilesystemManager`` methods adapt method calls of ``pathlib`` to the ``StoreManager`` interface.

    This code can be used as a reference for how to implement ``StorageManager``
    for other file storage services.
    """

    def __init__(self, base: Union[str, Path]):
        self.__base = Path(base)

    def create_container(self) -> None:
        self.__base.mkdir(exist_ok=True, parents=True)

    def ls(self, path_prefix: str) -> List[str]:
        if self.obj_exists(path_prefix):
            return [path_prefix]
        all_paths = (self.__base / path_prefix).rglob('*')
        return [str(p.relative_to(self.__base)) for p in all_paths if p.is_file()]

    def path_exists(self, path: str) -> bool:
        return (self.__base / path).exists()

    def obj_exists(self, file_path: str) -> bool:
        return (self.__base / file_path).is_file()

    def upload_obj(self, file_path: str, contents: AnyStr, content_type: Optional[str] = None):
        dst = (self.__base / file_path)
        dst.parent.mkdir(exist_ok=True, parents=True)

        if self.__is_textual(content_type):
            dst.write_text(contents)
        else:
            dst.write_bytes(contents)

    @staticmethod
    def __is_textual(media_type: Optional[str]) -> bool:
        """
        :returns: True if given media type is a text-based media type.
        """
        return media_type is not None and media_type.split('/', maxsplit=1)[0] == 'text'

    def download_obj(self, file_path: str) -> AnyStr:
        return (self.__base / file_path).read_bytes()

    def copy_obj(self, src: str, dst: str) -> None:
        src_path = self.__base / src
        dst_path = self.__base / dst
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.link_to(dst_path)

    def delete_obj(self, file_path: str) -> None:
        (self.__base / file_path).unlink()

    def copy_path(self, src: str, dst: str) -> None:
        src_path = self.__base / src
        dst_path = self.__base / dst

        if not src_path.exists():
            raise FileNotFoundError(
                f"The source path '{src_path}' does not exist.")

        if src_path.is_dir():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_path, dst_path)
        else:
            self.copy_obj(src, dst)

    def move_path(self, src: str, dst: str) -> None:
        src_path = self.__base / src
        dst_path = self.__base / dst

        if not src_path.exists():
            raise FileNotFoundError(
                f"The source path '{src_path}' does not exist.")

        if src_path.is_dir():
            if src_path.parent == dst_path.parent:  # just a renaming
                src_path.rename(dst_path)
            else:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(src_path, dst_path)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)

    def delete_path(self, path: str) -> None:
        p = self.__base / path

        if not p.exists():
            raise FileNotFoundError(
                f"The source path '{p}' does not exist.")

        if p.is_dir():
            shutil.rmtree(p)
        else:
            self.delete_obj(path)
