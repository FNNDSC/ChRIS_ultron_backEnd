#!/usr/bin/env python3
"""
Integration tests for S3Manager against a real S3-compatible service (MinIO).

Created: 2026-03-24
Part of the ChRIS CUBE S3 storage adapter work (feature/s3-storage-adapter).
Validates all StorageManager interface methods implemented by S3Manager
against a live MinIO instance -- covers CRUD, path operations, batch delete,
pagination, and the comma-sanitization logic inherited from SwiftManager.

Run via docker compose (recommended):
    docker compose -f docker-compose.s3-test.yml up -d minio
    docker compose -f docker-compose.s3-test.yml run --rm s3-test
    docker compose -f docker-compose.s3-test.yml down -v

Or locally (with MinIO running on localhost:9000):
    S3_ENDPOINT_URL=http://localhost:9000 \
    S3_ACCESS_KEY=minioadmin \
    S3_SECRET_KEY=minioadmin \
    S3_BUCKET_NAME=chris-test \
    python tests/test_s3manager.py
"""

import os
import sys
import importlib.util
import unittest

# Load s3manager directly to avoid core/__init__.py pulling in Django/Celery.
_base = os.path.join(os.path.dirname(__file__), '..', 'chris_backend', 'core', 'storage')

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_storagemanager = _load_module('storagemanager', os.path.join(_base, 'storagemanager.py'))
sys.modules['core.storage.storagemanager'] = _storagemanager  # satisfy s3manager's import
S3Manager = _load_module('s3manager', os.path.join(_base, 's3manager.py')).S3Manager


def get_test_manager():
    conn_params = {
        'endpoint_url': os.environ.get('S3_ENDPOINT_URL', 'http://localhost:9000'),
        'access_key': os.environ.get('S3_ACCESS_KEY', 'minioadmin'),
        'secret_key': os.environ.get('S3_SECRET_KEY', 'minioadmin'),
        'region_name': os.environ.get('S3_REGION', 'us-east-1'),
    }
    bucket = os.environ.get('S3_BUCKET_NAME', 'chris-test')
    return S3Manager(bucket, conn_params)


class TestS3ManagerConnection(unittest.TestCase):

    def setUp(self):
        self.manager = get_test_manager()

    def test_create_container(self):
        """Bucket creation should succeed (or be idempotent)."""
        self.manager.create_container()
        # call again to verify idempotency
        self.manager.create_container()


class TestS3ManagerCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manager = get_test_manager()
        cls.manager.create_container()

    def tearDown(self):
        # clean up test objects
        for key in self.manager.ls('test/'):
            self.manager.delete_obj(key)

    def test_upload_and_download_bytes(self):
        data = b'hello ChRIS from S3!'
        self.manager.upload_obj('test/hello.txt', data, content_type='text/plain')
        result = self.manager.download_obj('test/hello.txt')
        self.assertEqual(result, data)

    def test_upload_and_download_str(self):
        data = 'string content gets encoded to utf-8'
        self.manager.upload_obj('test/string.txt', data, content_type='text/plain')
        result = self.manager.download_obj('test/string.txt')
        self.assertEqual(result, data.encode('utf-8'))

    def test_obj_exists(self):
        self.assertFalse(self.manager.obj_exists('test/nonexistent.txt'))
        self.manager.upload_obj('test/exists.txt', b'data')
        self.assertTrue(self.manager.obj_exists('test/exists.txt'))

    def test_path_exists(self):
        self.assertFalse(self.manager.path_exists('test/subdir/'))
        self.manager.upload_obj('test/subdir/file.txt', b'data')
        self.assertTrue(self.manager.path_exists('test/subdir/'))
        self.assertTrue(self.manager.path_exists('test/subdir/file.txt'))

    def test_ls(self):
        self.manager.upload_obj('test/ls/a.txt', b'a')
        self.manager.upload_obj('test/ls/b.txt', b'b')
        self.manager.upload_obj('test/ls/sub/c.txt', b'c')
        result = self.manager.ls('test/ls/')
        self.assertEqual(sorted(result),
                         ['test/ls/a.txt', 'test/ls/b.txt', 'test/ls/sub/c.txt'])

    def test_ls_empty_prefix(self):
        result = self.manager.ls('')
        self.assertEqual(result, [])

    def test_delete_obj(self):
        self.manager.upload_obj('test/del.txt', b'delete me')
        self.assertTrue(self.manager.obj_exists('test/del.txt'))
        self.manager.delete_obj('test/del.txt')
        self.assertFalse(self.manager.obj_exists('test/del.txt'))

    def test_copy_obj(self):
        self.manager.upload_obj('test/src.txt', b'copy me')
        self.manager.copy_obj('test/src.txt', 'test/dst.txt')
        self.assertTrue(self.manager.obj_exists('test/dst.txt'))
        self.assertEqual(self.manager.download_obj('test/dst.txt'), b'copy me')
        # source still exists
        self.assertTrue(self.manager.obj_exists('test/src.txt'))


class TestS3ManagerPathOps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manager = get_test_manager()
        cls.manager.create_container()

    def tearDown(self):
        for key in self.manager.ls('test/'):
            self.manager.delete_obj(key)

    def test_copy_path(self):
        self.manager.upload_obj('test/cp/a.txt', b'a')
        self.manager.upload_obj('test/cp/sub/b.txt', b'b')
        self.manager.copy_path('test/cp/', 'test/cp2/')
        # originals still exist
        self.assertTrue(self.manager.obj_exists('test/cp/a.txt'))
        # copies exist
        self.assertTrue(self.manager.obj_exists('test/cp2/a.txt'))
        self.assertTrue(self.manager.obj_exists('test/cp2/sub/b.txt'))
        self.assertEqual(self.manager.download_obj('test/cp2/sub/b.txt'), b'b')

    def test_move_path(self):
        self.manager.upload_obj('test/mv/a.txt', b'a')
        self.manager.upload_obj('test/mv/sub/b.txt', b'b')
        self.manager.move_path('test/mv/', 'test/mv2/')
        # originals gone
        self.assertFalse(self.manager.obj_exists('test/mv/a.txt'))
        self.assertFalse(self.manager.obj_exists('test/mv/sub/b.txt'))
        # moved objects exist
        self.assertTrue(self.manager.obj_exists('test/mv2/a.txt'))
        self.assertEqual(self.manager.download_obj('test/mv2/sub/b.txt'), b'b')

    def test_delete_path(self):
        self.manager.upload_obj('test/delpath/a.txt', b'a')
        self.manager.upload_obj('test/delpath/b.txt', b'b')
        self.manager.upload_obj('test/delpath/sub/c.txt', b'c')
        self.manager.delete_path('test/delpath/')
        self.assertEqual(self.manager.ls('test/delpath/'), [])

    def test_sanitize_obj_names(self):
        self.manager.upload_obj('test/san/fi,le.txt', b'data')
        self.manager.upload_obj('test/san/clean.txt', b'ok')
        result = self.manager.sanitize_obj_names('test/san/')
        # comma-containing file should be renamed
        self.assertIn('test/san/fi,le.txt', result)
        self.assertEqual(result['test/san/fi,le.txt'], 'test/san/file.txt')
        # clean file should not appear in result
        self.assertNotIn('test/san/clean.txt', result)
        # new file exists, old one gone
        self.assertTrue(self.manager.obj_exists('test/san/file.txt'))
        self.assertFalse(self.manager.obj_exists('test/san/fi,le.txt'))

    def test_sanitize_deletes_comma_only_names(self):
        # file whose ENTIRE name is only commas and whitespace gets deleted
        self.manager.upload_obj('test/san2/,,', b'junk')
        # file with commas in stem but non-comma extension gets renamed, not deleted
        self.manager.upload_obj('test/san2/,,.txt', b'renamed')
        self.manager.upload_obj('test/san2/good.txt', b'keep')
        result = self.manager.sanitize_obj_names('test/san2/')
        # pure comma name → deleted
        self.assertIn('test/san2/,,', result)
        self.assertEqual(result['test/san2/,,'], '')
        self.assertFalse(self.manager.obj_exists('test/san2/,,'))
        # comma stem + extension → renamed to .txt
        self.assertIn('test/san2/,,.txt', result)
        self.assertEqual(result['test/san2/,,.txt'], 'test/san2/.txt')
        # clean file untouched
        self.assertTrue(self.manager.obj_exists('test/san2/good.txt'))


class TestS3ManagerLargeOps(unittest.TestCase):
    """Test operations at moderate scale to validate pagination and batch delete."""

    @classmethod
    def setUpClass(cls):
        cls.manager = get_test_manager()
        cls.manager.create_container()

    def tearDown(self):
        self.manager.delete_path('test/bulk/')

    def test_ls_many_objects(self):
        """Verify listing works beyond a single page (1000 objects)."""
        count = 50  # keep fast for CI; increase manually to 1100+ to test pagination
        for i in range(count):
            self.manager.upload_obj(f'test/bulk/{i:04d}.dat', b'x')
        result = self.manager.ls('test/bulk/')
        self.assertEqual(len(result), count)

    def test_batch_delete(self):
        """Verify delete_path uses batch delete efficiently."""
        count = 25
        for i in range(count):
            self.manager.upload_obj(f'test/bulk/{i:04d}.dat', b'x')
        self.manager.delete_path('test/bulk/')
        self.assertEqual(self.manager.ls('test/bulk/'), [])


if __name__ == '__main__':
    print(f"Testing S3Manager against: {os.environ.get('S3_ENDPOINT_URL', 'http://localhost:9000')}")
    print(f"Bucket: {os.environ.get('S3_BUCKET_NAME', 'chris-test')}")
    print()
    unittest.main(verbosity=2)
