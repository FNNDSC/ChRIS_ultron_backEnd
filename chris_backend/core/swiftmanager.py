"""
Swift storage manager module.
"""

import logging
import os

import swiftclient


logger = logging.getLogger(__name__)


class SwiftManager(object):

    def __init__(self, container_name, conn_params):
        self.container_name = container_name
        # swift storage connection parameters dictionary
        self.conn_params = conn_params
        # swift storage connection object
        self._conn = None

    def get_connection(self):
        """
        Connect to swift storage and return the connection object.
        """
        if self._conn is not None:
            return self._conn
        try:
            self._conn = swiftclient.Connection(**self.conn_params)
        except Exception as e:
            logger.error(str(e))
            raise
        return self._conn

    def create_container(self):
        """
        Create the storage container.
        """
        conn = self.get_connection()
        try:
            conn.put_container(self.container_name)
        except Exception as e:
            logger.error(str(e))
            raise

    def ls(self, path):
        """
        Return a list of objects in the swift storage with the provided path
        as a prefix.
        """
        l_ls = []  # listing of names to return
        if path:
            conn = self.get_connection()
            try:
                # get the full list of objects in Swift storage with given prefix
                ld_obj = conn.get_container(self.container_name,
                                            prefix=path,
                                            full_listing=True)[1]
            except Exception as e:
                logger.error(str(e))
                raise
            else:
                l_ls = [d_obj['name'] for d_obj in ld_obj]
        return l_ls

    def obj_exists(self, obj_path):
        """
        Return True/False if passed object exists in swift storage.
        """
        return obj_path in self.ls(obj_path)

    def upload_file(self, swift_path, contents, **kwargs):
        """
        Upload a file into swift storage.
        """
        if not self.obj_exists(swift_path):
            conn = self.get_connection()
            try:
                conn.put_object(self.container_name,
                                swift_path,
                                contents=contents,
                                **kwargs)
            except Exception as e:
                logger.error(str(e))
                raise

    def upload_files(self, local_dir, swift_prefix='', **kwargs):
        """
        Upload all the files within a local directory recursively to swift storage.

        By default, the location in swift storage will map 1:1 to the location of
        files in the local filesytem. This location can be remapped by using the
        <swift_prefix>. For example, assume a local directory /home/user/project/data/
        with the following files:

            '/home/user/project/data/file1',
            '/home/user/project/data/dir1/file_d1',
            '/home/user/project/data/dir2/file_d2'

        and we want to upload everything in that directory to object storage, at location
        '/storage'. In this case, swift_prefix='/storage' results in a new list

            '/storage/file1',
            '/storage/dir1/file_d1',
            '/storage/dir2/file_d2'
        """
        # upload all files down the <local_dir>
        for root, dirs, files in os.walk(local_dir):
            swift_base = root.replace(local_dir, swift_prefix) if swift_prefix else root
            for filename in files:
                local_file_path = os.path.join(root, filename)
                with open(local_file_path, 'r') as f:
                    swift_path = os.path.join(swift_base, filename)
                    self.upload_file(swift_path, f.read(), **kwargs)

    def delete_obj(self, obj_path):
        """
        Delete an object from swift storage.
        """
        conn = self.get_connection()
        try:
            conn.delete_object(self.container_name, obj_path)
        except Exception as e:
            logger.error(str(e))
            raise
