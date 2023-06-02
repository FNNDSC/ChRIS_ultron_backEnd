"""
Swift storage manager module.
"""

import logging
import os
import time

from swiftclient import Connection
from swiftclient.exceptions import ClientException


logger = logging.getLogger(__name__)


class SwiftManager(object):

    def __init__(self, container_name, conn_params):
        self.container_name = container_name
        # swift storage connection parameters dictionary
        self.conn_params = conn_params
        # swift storage connection object
        self._conn = None

    def __get_connection(self):
        """
        Connect to swift storage and return the connection object.
        """
        if self._conn is not None:
            return self._conn
        for i in range(5):  # 5 retries at most
            try:
                self._conn = Connection(**self.conn_params)
            except ClientException as e:
                logger.error(str(e))
                if i == 4:
                    raise  # give up
                time.sleep(0.4)
            else:
                return self._conn

    def create_container(self):
        """
        Create the storage container.
        """
        conn = self.__get_connection()
        try:
            conn.put_container(self.container_name)
        except ClientException as e:
            logger.error(str(e))
            raise

    def ls(self, path):
        """
        Return a list of objects in the swift storage with the provided path
        as a prefix.
        """
        return self._ls(path, b_full_listing=True)

    def _ls(self, path, b_full_listing: bool):
        """
        Note to developers: the body of ``_ls`` was originally the body of ``self.ls``,
        though it's been renamed to ``_ls`` so that ``self.ls``'s signature could be
        changed. ``self.ls`` originally accepted ``**kwargs`` but that is no longer the case.
        """
        l_ls = []  # listing of names to return
        if path:
            conn = self.__get_connection()
            for i in range(5):
                try:
                    # get the full list of objects in Swift storage with given prefix
                    ld_obj = conn.get_container(self.container_name,
                                                prefix=path,
                                                full_listing=b_full_listing)[1]
                except ClientException as e:
                    logger.error(str(e))
                    if i == 4:
                        raise
                    time.sleep(0.4)
                else:
                    l_ls = [d_obj['name'] for d_obj in ld_obj]
                    break
        return l_ls

    def path_exists(self, path):
        """
        Return True/False if passed path exists in swift storage.
        """
        return len(self._ls(path, b_full_listing=False)) > 0

    def obj_exists(self, obj_path):
        """
        Return True/False if passed object exists in swift storage.
        """
        conn = self.__get_connection()
        for i in range(5):
            try:
                conn.head_object(self.container_name, obj_path)
            except ClientException as e:
                if e.http_status == 404:
                    return False
                else:
                    logger.error(str(e))
                    if i == 4:
                        raise
                    time.sleep(0.4)
            else:
                return True

    def upload_obj(self, swift_path, contents, content_type=None):
        """
        Upload an object (a file contents) into swift storage.
        """
        conn = self.__get_connection()
        for i in range(5):
            try:
                conn.put_object(self.container_name,
                                swift_path,
                                contents=contents,
                                content_type=content_type)
            except ClientException as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break

    def download_obj(self, obj_path):
        """
        Download an object from swift storage.
        """
        conn = self.__get_connection()
        for i in range(5):
            try:
                resp_headers, obj_contents = conn.get_object(self.container_name, obj_path)
            except ClientException as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                return obj_contents

    def copy_obj(self, obj_path, dest_path):
        """
        Copy an object to a new destination in swift storage.
        """
        conn = self.__get_connection()
        dest = os.path.join('/' + self.container_name, dest_path.lstrip('/'))
        for i in range(5):
            try:
                conn.copy_object(self.container_name, obj_path, dest)
            except ClientException as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break

    def delete_obj(self, obj_path):
        """
        Delete an object from swift storage.
        """
        conn = self.__get_connection()
        for i in range(5):
            try:
                conn.delete_object(self.container_name, obj_path)
            except ClientException as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break
