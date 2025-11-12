# Altastata Storage Configuration Guide

This document explains how to configure Altastata as a storage backend for the ChRIS Ultron Backend.

## Overview

Altastata is a secure cloud storage solution that provides encrypted, versioned file storage. The `AltaStataManager` implements the ChRIS `StorageManager` interface, allowing Altastata to be used as a drop-in replacement for Swift or filesystem storage.

## Prerequisites

### 1. System Requirements
- **Java 8 or higher** (Java 17 recommended)
- **Python 3.8 or higher**
- **Altastata account** and credentials

### 2. Install Altastata Package
Install the official Altastata package from PyPI:

```bash
pip install altastata
```

**Note**: The package is available at [https://pypi.org/project/altastata/](https://pypi.org/project/altastata/) and includes all necessary dependencies including Py4J for Java integration.

### 3. Verify Java Installation
Ensure Java is properly installed and accessible:

```bash
# Check Java version
java -version

# Should show Java 8 or higher (Java 17 recommended)
# Example output:
# openjdk version "17.0.2" 2022-01-18
# OpenJDK Runtime Environment (build 17.0.2+8-Ubuntu-120.04)
# OpenJDK 64-Bit Server VM (build 17.0.2+8-Ubuntu-120.04, mixed mode, sharing)
```

### 4. Altastata Account Setup
- Create an Altastata account
- Set up your account directory with credentials
- Ensure you have the `altastata` package installed

### 5. Account Directory Structure
```
~/.altastata/accounts/
└── amazon.rsa.alice222/  # Your account directory
    ├── account.properties
    ├── private_key_encrypted
    └── other_credential_files
```

## Configuration Options

### Option 1: Account Directory Authentication (Recommended)

```python
# In Django settings (local.py or production.py)
ALTAS_CONNECTION_PARAMS = {
    'account_dir_path': '/path/to/your/altastata/account',
    'password': 'your_encryption_password',
    'port': 25333  # Optional, defaults to 25333
}
```

### Option 2: Direct Credentials Authentication

```python
# In Django settings (local.py or production.py)
ALTAS_CONNECTION_PARAMS = {
    'user_properties': 'your_user_properties_string',
    'private_key_encrypted': 'your_encrypted_private_key',
    'password': 'your_encryption_password',
    'port': 25333  # Optional, defaults to 25333
}
```

## Django Settings Configuration

### 1. Update Storage Configuration

```python
# In settings/local.py or production.py
STORAGES['default'] = {'BACKEND': 'altastata.storage.AltaStataStorage'}
ALTAS_CONTAINER_NAME = 'chris-storage'  # Your container name
ALTAS_CONNECTION_PARAMS = {
    'account_dir_path': '/Users/yourusername/.altastata/accounts/amazon.rsa.alice222',
    'password': 'your_password',
    'port': 25333
}
```

### 2. Environment Variables (Recommended for Production)

```bash
# Environment variables
export ALTAS_ACCOUNT_DIR_PATH="/path/to/altastata/account"
export ALTAS_PASSWORD="your_encryption_password"
export ALTAS_PORT="25333"
export ALTAS_CONTAINER_NAME="chris-storage"
```

```python
# In settings/production.py
ALTAS_CONNECTION_PARAMS = {
    'account_dir_path': os.getenv('ALTAS_ACCOUNT_DIR_PATH'),
    'password': os.getenv('ALTAS_PASSWORD'),
    'port': int(os.getenv('ALTAS_PORT', '25333'))
}
ALTAS_CONTAINER_NAME = os.getenv('ALTAS_CONTAINER_NAME', 'chris-storage')
```

## Docker Configuration

### 1. Docker Compose Environment

```yaml
# In docker-compose.yml
services:
  chris-backend:
    environment:
      - STORAGE_ENV=altastata
      - ALTAS_ACCOUNT_DIR_PATH=/app/altastata/accounts/amazon.rsa.alice222
      - ALTAS_PASSWORD=your_password
      - ALTAS_PORT=25333
      - ALTAS_CONTAINER_NAME=chris-storage
    volumes:
      - ./altastata-accounts:/app/altastata/accounts:ro
```

### 2. Dockerfile Configuration

```dockerfile
# In Dockerfile
# Copy Altastata account directory
COPY altastata-accounts/ /app/altastata/accounts/

# Set environment variables
ENV ALTAS_ACCOUNT_DIR_PATH=/app/altastata/accounts/amazon.rsa.alice222
ENV ALTAS_PASSWORD=your_password
ENV ALTAS_PORT=25333
```

## Integration with ChRIS Backend

### 1. Update Storage Helpers

Add to `chris_backend/core/storage/helpers.py`:

```python
from core.storage.altastatamanager import AltaStataManager

def connect_storage(settings) -> StorageManager:
    storage_name = __get_storage_name(settings)
    if storage_name == 'SwiftStorage':
        return SwiftManager(settings.SWIFT_CONTAINER_NAME, settings.SWIFT_CONNECTION_PARAMS)
    elif storage_name == 'AltaStataStorage':  # NEW
        return AltaStataManager(settings.ALTAS_CONTAINER_NAME, settings.ALTAS_CONTAINER_PARAMS)
    elif storage_name == 'FileSystemStorage':
        return FilesystemManager(settings.MEDIA_ROOT)
    raise ValueError(f'Unsupported storage system: {storage_name}')
```

### 2. Update Settings Files

Add to `chris_backend/config/settings/local.py`:

```python
# Altastata configuration
if STORAGE_ENV == 'altastata':
    STORAGES['default'] = {'BACKEND': 'altastata.storage.AltaStataStorage'}
    ALTAS_CONTAINER_NAME = 'chris-storage'
    ALTAS_CONNECTION_PARAMS = {
        'account_dir_path': '/path/to/your/altastata/account',
        'password': 'your_password',
        'port': 25333
    }
```

## Testing Configuration

### 1. Run Altastata Tests

```bash
# Test Altastata package directly
python chris_backend/core/tests/altastata/test_altastata_simple.py

# Test AltaStataManager
python chris_backend/core/tests/altastata/test_altastata_standalone.py
```

### 2. Verify Configuration

```python
# In Django shell
from core.storage.helpers import connect_storage
from django.conf import settings

# Test connection
storage_manager = connect_storage(settings)
storage_manager.create_container()  # Should succeed
```

## Security Considerations

### 1. Credential Security
- **Never commit** account directories or passwords to version control
- **Use environment variables** for production deployments
- **Rotate passwords** regularly
- **Use secrets management** in cloud deployments

### 2. Network Security
- **Firewall rules** - Allow port 25333 for Py4J communication
- **VPN/Private networks** - Use secure networks for Altastata communication
- **Encryption** - All data is encrypted by Altastata

### 3. Access Control
- **Account permissions** - Ensure proper Altastata account permissions
- **Container access** - Configure container-level access controls
- **User isolation** - Use separate accounts for different environments

## Troubleshooting

### Common Issues

#### 1. Connection Errors
```
Error: Unable to connect to Altastata
```
**Solution**: Check account directory path and password

#### 2. Port Conflicts
```
Error: Port 25333 already in use
```
**Solution**: Use different port in configuration

#### 3. Import Errors
```
Error: No module named 'altastata'
```
**Solution**: Install altastata-python-package

#### 4. Java-related Errors
```
Error: Java not found or version too old
```
**Solution**: Install Java 8 or higher (Java 17 recommended)

```
Error: Py4J gateway connection failed
```
**Solution**: Ensure Java is accessible and port 25333 is available

#### 5. Permission Errors
```
Error: Access denied to container
```
**Solution**: Check Altastata account permissions

### Debug Mode

Enable debug logging:

```python
# In Django settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'altastata.log',
        },
    },
    'loggers': {
        'core.storage.altastatamanager': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Performance Considerations

### 1. Connection Pooling
- Altastata connections are cached per manager instance
- Multiple operations reuse the same connection
- Connections are automatically cleaned up

### 2. File Operations
- **Upload**: Files are uploaded in chunks for large files
- **Download**: Files are downloaded with parallel chunks
- **Listing**: Directory listings are optimized for performance

### 3. Memory Usage
- **Chunked operations** prevent memory issues with large files
- **Connection reuse** reduces memory overhead
- **Automatic cleanup** prevents memory leaks

## Migration from Other Storage

### From Swift to Altastata

1. **Configure Altastata** settings
2. **Test connection** with Altastata
3. **Update storage backend** in settings
4. **Verify functionality** with existing data
5. **Migrate data** if needed (separate process)

### From Filesystem to Altastata

1. **Set up Altastata** account and configuration
2. **Update settings** to use Altastata
3. **Test basic operations** (upload, download, list)
4. **Migrate existing files** (if needed)

## Support and Resources

### Documentation
- **Altastata Documentation**: [Altastata Official Docs]
- **ChRIS Documentation**: [ChRIS Project Documentation]
- **Django Storage**: [Django Storage Documentation]

### Community
- **ChRIS Slack**: [ChRIS Community Slack]
- **GitHub Issues**: [ChRIS Backend Issues]
- **Altastata Support**: [Altastata Support]

### Examples
- **Test Files**: `chris_backend/core/tests/altastata/`
- **Configuration Examples**: See test files for usage examples
- **Integration Examples**: Check `helpers.py` for integration patterns

---

**Note**: This configuration guide assumes you have a working Altastata account and the `altastata-python-package` installed. For Altastata-specific setup, refer to the official Altastata documentation.
