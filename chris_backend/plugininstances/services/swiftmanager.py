"""
Swift storage manager module.
"""

from django.conf import settings

import swiftclient


class SwiftManager(object):

    @staticmethod
    def connect(*args, **kwargs):
        """
        Connect to swift storage and return the connection object,
        as well an optional "prepend" string to fully qualify
        object location in swift storage.
        """

        b_status = True
        b_prependBucketPath = False

        for k, v in kwargs.items():
            if k == 'prependBucketPath':    b_prependBucketPath = v

        d_ret = {
            'status': b_status,
            'conn': None,
            'prependBucketPath': ""
        }

        # initiate a swift service connection, based on internal
        # settings already available in the django variable space.
        try:
            d_ret['conn'] = swiftclient.Connection(
                user=settings.SWIFT_USERNAME,
                key=settings.SWIFT_KEY,
                authurl=settings.SWIFT_AUTH_URL,
            )
        except:
            d_ret['status'] = False

        if b_prependBucketPath:
            d_ret['prependBucketPath'] = ''

        return d_ret

    @staticmethod
    def ls(*args, **kwargs):
        """
        Return a list of objects in the swift storage
        """
        l_ls = []  # The listing of names to return
        ld_obj = {}  # List of dictionary objects in swift
        str_path = '/'
        str_fullPath = ''
        b_prependBucketPath = False
        b_status = False

        for k, v in kwargs.items():
            if k == 'path':                 str_path = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        # Remove any leading noise on the str_path, specifically
        # any leading '.' characters.
        # This is probably not very robust!
        while str_path[:1] == '.':  str_path = str_path[1:]

        d_conn = SwiftManager.connect(**kwargs)
        if d_conn['status'] and len(str_path):
            conn = d_conn['conn']
            if b_prependBucketPath:
                str_fullPath = '%s%s' % (d_conn['prependBucketPath'], str_path)
            else:
                str_fullPath = str_path

            # get the full list of objects in Swift storage with given prefix
            ld_obj = conn.get_container(settings.SWIFT_CONTAINER_NAME,
                                        prefix=str_fullPath,
                                        full_listing=True)[1]

            for d_obj in ld_obj:
                l_ls.append(d_obj['name'])
                b_status = True

        return {
            'status': b_status,
            'objectDict': ld_obj,
            'lsList': l_ls,
            'fullPath': str_fullPath
        }

    @staticmethod
    def objExists(*args, **kwargs):
        """
        Return True/False if passed object exists in swift storage
        """
        b_exists = False
        str_obj = ''

        for k, v in kwargs.items():
            if k == 'obj':                  str_obj = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        kwargs['path'] = str_obj
        d_swift_ls = SwiftManager.ls(*args, **kwargs)
        str_obj = d_swift_ls['fullPath']

        if d_swift_ls['status']:
            for obj in d_swift_ls['lsList']:
                if str_obj in obj:
                    b_exists = True

        return {
            'status': b_exists,
            'objPath': str_obj
        }

    @staticmethod
    def objPut(*args, **kwargs):
        """
        Put an object (or list of objects) into swift storage.

        By default, to location in storage will map 1:1 to the
        location name string in the local filesytem. This storage
        location can be remapped by using the '<toLocation>' and
        '<mapLocationOver>' kwargs. For example, assume
        a list of local locations starting with:

                /home/user/project/data/ ...

        and we want to pack everything in the 'data' dir to
        object storage, at location '/storage'. In this case, the
        pattern of kwargs specifying this would be:

                    fileList = ['/home/user/project/data/file1',
                                '/home/user/project/data/dir1/file_d1',
                                '/home/user/project/data/dir2/file_d2'],
                    toLocation      = '/storage',
                    mapLocationOver = '/home/user/project/data'

        will replace, for each file in <fileList>, the <mapLocationOver> with
        <toLocation>, resulting in a new list

                    '/storage/file1',
                    '/storage/dir1/file_d1',
                    '/storage/dir2/file_d2'

        Note that the <toLocation> is subject to <b_prependBucketPath>!

        """
        b_status = True
        l_localfile = []  # Name on the local file system
        l_objectfile = []  # Name in the object storage
        str_swiftLocation = ''
        str_mapLocationOver = ''
        str_localfilename = ''
        str_storagefilename = ''
        str_prependBucketPath = ''
        d_ret = {
            'status': b_status,
            'localFileList': [],
            'objectFileList': []
        }

        d_conn = SwiftManager.connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath = d_conn['prependBucketPath']

        str_swiftLocation = str_prependBucketPath

        for k, v in kwargs.items():
            if k == 'file':             l_localfile.append(v)
            if k == 'fileList':         l_localfile = v
            if k == 'toLocation':       str_swiftLocation = '%s%s' % (
            str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_objectfile = [w.replace(str_mapLocationOver, str_swiftLocation) \
                            for w in l_localfile]
        else:
            # Prepend the swiftlocation to each element in the localfile list:
            l_objectfile = [str_swiftLocation + '{0}'.format(i) for i in l_localfile]

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile):
                try:
                    d_ret['status'] = True and d_ret['status']
                    with open(str_localfilename, 'r') as fp:
                        d_conn['conn'].put_object(
                            settings.SWIFT_CONTAINER_NAME,
                            str_storagefilename,
                            contents=fp.read()
                        )
                except:
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret
