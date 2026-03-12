#!/usr/bin/env python3
"""
Simple test script for AltaStataManager (standalone)
"""

import sys
import os

# Add the altastata package to path
sys.path.insert(0, '/Users/sergevilvovsky/eclipse-workspace/mcloud/altastata-python-package')

try:
    from altastata import AltaStataFunctions
    print("✅ Altastata package imported successfully")
    
    # Test basic Altastata functionality
    print("🚀 Testing AltastataFunctions directly...")
    
    # Initialize with your account
    altastata_functions = AltaStataFunctions.from_account_dir('/Users/sergevilvovsky/.altastata/accounts/amazon.rsa.alice222')
    altastata_functions.set_password("123")
    print("✅ Altastata connection established")
    
    # Test basic operations
    print("📁 Testing file operations...")
    
    # Create a test file
    test_content = b"Hello from ChRIS test!"
    result = altastata_functions.create_file('chris-test/test_file.txt', test_content)
    print(f"✅ create_file: {result.getOperationStateValue()}")
    
    # List files
    iterator = altastata_functions.list_cloud_files_versions('chris-test', True, None, None)
    print("📋 Files in chris-test:")
    for java_array in iterator:
        python_list = [str(element) for element in java_array]
        for file_path in python_list:
            print(f"   - {file_path}")
    
    # Get file content
    file_time_id = int(result.getCloudFileCreateTime())
    buffer = altastata_functions.get_buffer('chris-test/test_file.txt', file_time_id, 0, 4, 100)
    print(f"📄 File content: {buffer.decode('utf-8')}")
    
    # Copy file
    copy_result = altastata_functions.copy_file('chris-test/test_file.txt', 'chris-test/test_file_copy.txt')
    print(f"✅ copy_file: {copy_result.getOperationStateValue()}")
    
    # Delete files
    delete_result = altastata_functions.delete_files('chris-test', True, None, None)
    print(f"✅ delete_files: {delete_result[0].getOperationStateValue()}")
    
    print("\n🎉 Altastata package is working correctly!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure the altastata package is installed and accessible")
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
