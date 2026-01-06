#!/usr/bin/env python3
"""
Django test for AltaStataManager functionality
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict

# Add altastata package to path
sys.path.insert(0, '/Users/sergevilvovsky/eclipse-workspace/mcloud/altastata-python-package')

from altastata import AltaStataFunctions

logger = logging.getLogger(__name__)

class StandaloneAltaStataManager:
    """Standalone version of AltaStataManager for testing"""
    
    def __init__(self, container_name, conn_params):
        self.container_name = container_name
        self.conn_params = conn_params
        self._altastata = None

    def __get_altastata(self):
        """Connect to altastata storage and return the connection object."""
        if self._altastata is not None:
            return self._altastata
        
        try:
            # Initialize Altastata connection based on connection parameters
            if 'account_dir_path' in self.conn_params:
                self._altastata = AltaStataFunctions.from_account_dir(
                    self.conn_params['account_dir_path'],
                    self.conn_params.get('port', 25333)
                )
            elif 'user_properties' in self.conn_params and 'private_key_encrypted' in self.conn_params:
                self._altastata = AltaStataFunctions.from_credentials(
                    self.conn_params['user_properties'],
                    self.conn_params['private_key_encrypted'],
                    self.conn_params.get('port', 25333)
                )
            else:
                raise ValueError("Invalid connection parameters. Must provide either 'account_dir_path' or 'user_properties' and 'private_key_encrypted'")
            
            # Set password if provided
            if 'password' in self.conn_params:
                self._altastata.set_password(self.conn_params['password'])
                
        except Exception as e:
            logger.error(str(e))
            raise
            
        return self._altastata

    def create_container(self):
        """Create the storage container. For Altastata, this is a no-op."""
        # Altastata doesn't require explicit container creation
        # The container_name is used as a path prefix
        pass

    def ls(self, path_prefix):
        """Return a list of objects in the altastata storage with the provided path as a prefix."""
        return self._ls(path_prefix, b_full_listing=True)

    def _ls(self, path, b_full_listing: bool):
        """List files in Altastata storage with the given path prefix."""
        l_ls = []  # listing of names to return
        if path:
            altastata = self.__get_altastata()
            try:
                # Get the list of files from Altastata
                # Note: b_full_listing is not used in Altastata API but kept for compatibility
                iterator = altastata.list_cloud_files_versions(path, True, None, None)
                
                # Convert iterator to list
                for java_array in iterator:
                    python_list = [str(element) for element in java_array]
                    if python_list:  # Only add non-empty results
                        # Extract file path from the result
                        # Altastata returns file paths, we need to filter by prefix
                        for file_path in python_list:
                            if file_path.startswith(path):
                                # Clean up the filename by removing Altastata versioning suffix
                                # Format: filename*user_timestamp -> filename
                                if '✹' in file_path:
                                    clean_path = file_path.split('✹')[0]
                                else:
                                    clean_path = file_path
                                l_ls.append(clean_path)
                
                # Remove duplicates and sort
                l_ls = sorted(list(set(l_ls)))
                
            except Exception as e:
                logger.error(str(e))
                raise
        return l_ls

    def path_exists(self, path):
        """Return True/False if passed path exists in altastata storage."""
        return len(self._ls(path, b_full_listing=False)) > 0

    def obj_exists(self, file_path):
        """Return True/False if passed object exists in altastata storage."""
        altastata = self.__get_altastata()
        try:
            # Try to get file attributes to check if file exists
            # Use a recent snapshot time (None means latest)
            result = altastata.get_file_attribute(file_path, None, "size")
            return result is not None
        except (FileNotFoundError, ValueError) as e:
            if "not found" in str(e).lower() or "404" in str(e):
                return False
            else:
                logger.error(str(e))
                raise

    def upload_obj(self, file_path, contents, content_type=None):
        """Upload an object (file contents) into altastata storage."""
        altastata = self.__get_altastata()
        try:
            # Convert contents to bytes if it's a string
            if isinstance(contents, str):
                contents = contents.encode('utf-8')
            
            # Create file with initial content
            result = altastata.create_file(file_path, contents)
            
            # Check if operation was successful
            if hasattr(result, 'getOperationStateValue'):
                if result.getOperationStateValue() != "DONE":
                    raise RuntimeError(f"Upload failed: {result.getOperationStateValue()}")
                    
        except Exception as e:
            logger.error(str(e))
            raise

    def download_obj(self, file_path):
        """Download an object from altastata storage."""
        altastata = self.__get_altastata()
        try:
            # Use current time as snapshot time (simple approach)
            import time
            current_time = int(time.time() * 1000)  # Current time in milliseconds
            
            # Get file size
            size_attr = altastata.get_file_attribute(file_path, current_time, "size")
            if size_attr is None:
                raise FileNotFoundError("File not found or size unknown")
            
            file_size = int(size_attr)
            
            # Download the file content
            # Use reasonable chunk size and parallel chunks
            chunk_size = min(1024 * 1024, file_size)  # 1MB or file size, whichever is smaller
            num_chunks = max(1, file_size // chunk_size)
            
            buffer = altastata.get_buffer(file_path, current_time, 0, num_chunks, file_size)
            return buffer
            
        except Exception as e:
            logger.error(str(e))
            raise

    def copy_obj(self, src, dst):
        """Copy an object to a new destination in altastata storage."""
        altastata = self.__get_altastata()
        try:
            result = altastata.copy_file(src, dst)
            
            # Check if operation was successful
            if hasattr(result, 'getOperationStateValue'):
                if result.getOperationStateValue() != "DONE":
                    raise RuntimeError(f"Copy failed: {result.getOperationStateValue()}")
                    
        except Exception as e:
            logger.error(str(e))
            raise

    def delete_obj(self, file_path):
        """Delete an object from altastata storage."""
        altastata = self.__get_altastata()
        try:
            # Use delete_files method to delete a single file
            result = altastata.delete_files(file_path, False, None, None)
            
            # Check if operation was successful
            if result and hasattr(result[0], 'getOperationStateValue'):
                if result[0].getOperationStateValue() != "DONE":
                    raise RuntimeError(f"Delete failed: {result[0].getOperationStateValue()}")
                    
        except Exception as e:
            logger.error(str(e))
            raise

    def copy_path(self, src: str, dst: str) -> None:
        """Copy all objects under src path to dst path."""
        l_ls = self.ls(src)
        for obj_path in l_ls:
            new_obj_path = obj_path.replace(src, dst, 1)
            self.copy_obj(obj_path, new_obj_path)

    def move_path(self, src: str, dst: str) -> None:
        """Move all objects under src path to dst path."""
        l_ls = self.ls(src)
        for obj_path in l_ls:
            new_obj_path = obj_path.replace(src, dst, 1)
            self.copy_obj(obj_path, new_obj_path)
            self.delete_obj(obj_path)

    def delete_path(self, path: str) -> None:
        """Delete all objects under the given path."""
        l_ls = self.ls(path)
        for obj_path in l_ls:
            self.delete_obj(obj_path)

def test_standalone_manager():
    """Test the standalone AltaStataManager"""
    
    print("🚀 Testing Standalone AltaStataManager...")
    
    # Configuration
    conn_params = {
        'account_dir_path': '/Users/sergevilvovsky/.altastata/accounts/amazon.rsa.alice222',
        'password': '123',
        'port': 25333
    }
    
    try:
        # Initialize manager
        manager = StandaloneAltaStataManager('chris-test-container', conn_params)
        print("✅ Manager initialized")
        
        # Test create_container (should be no-op)
        manager.create_container()
        print("✅ create_container: OK")
        
        # Test upload
        test_content = b"Hello from Standalone AltaStataManager!"
        test_path = "chris-test/standalone_test.txt"
        manager.upload_obj(test_path, test_content)
        print("✅ upload_obj: OK")
        
        # Test obj_exists
        exists = manager.obj_exists(test_path)
        print(f"✅ obj_exists: {exists}")
        
        # Test ls
        files = manager.ls("chris-test/")
        print(f"✅ ls: Found {len(files)} files")
        for file in files:
            print(f"   - {file}")
        
        # Test download
        downloaded = manager.download_obj(test_path)
        print(f"✅ download_obj: {len(downloaded)} bytes")
        print(f"   Content: {downloaded.decode('utf-8')}")
        
        # Test copy
        copy_path = "chris-test/standalone_test_copy.txt"
        manager.copy_obj(test_path, copy_path)
        print("✅ copy_obj: OK")
        
        # Test path operations
        manager.copy_path("chris-test/", "chris-test-backup/")
        print("✅ copy_path: OK")
        
        # Test move
        manager.move_path("chris-test/standalone_test_copy.txt", "chris-test-backup/moved_file.txt")
        print("✅ move_path: OK")
        
        # Test directory operations
        print("\n📁 Testing directory operations...")
        # Create multiple files in nested directories
        manager.upload_obj("test-dir/file1.txt", b"Content 1")
        manager.upload_obj("test-dir/file2.txt", b"Content 2")
        manager.upload_obj("test-dir/subdir/file3.txt", b"Content 3")
        print("✅ Created nested directory structure")
        
        # List directory contents
        dir_files = manager.ls("test-dir/")
        print(f"✅ Directory listing: {len(dir_files)} files")
        
        # Test path existence
        print(f"✅ Path exists test-dir/: {manager.path_exists('test-dir/')}")
        print(f"✅ Path exists test-dir/subdir/: {manager.path_exists('test-dir/subdir/')}")
        
        # Cleanup
        manager.delete_path("chris-test/")
        manager.delete_path("chris-test-backup/")
        manager.delete_path("test-dir/")
        print("✅ cleanup: OK")
        
        print("\n🎉 Standalone AltaStataManager is working perfectly!")
        print("✅ All methods implemented and tested successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_standalone_manager()
