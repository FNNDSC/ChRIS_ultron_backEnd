# S3Manager Integration Test Results

**Date:** 2026-03-24
**Branch:** feature/s3-storage-adapter
**Ticket:** ASHAIW-13
**Target:** MinIO (minio/minio:latest) via docker-compose.s3-test.yml
**boto3 config:** path-style addressing, CRC checksums disabled (compatibility mode)

## Environment

- **S3 Backend:** MinIO latest (docker container)
- **Endpoint:** http://minio:9000
- **Bucket:** chris-test
- **Runner:** python:3.12-slim container
- **Orchestration:** docker-compose.s3-test.yml (standalone, no Django/CUBE stack required)

## Results: 16/16 PASSED

```
test_copy_obj (TestS3ManagerCRUD) ... ok
test_delete_obj (TestS3ManagerCRUD) ... ok
test_ls (TestS3ManagerCRUD) ... ok
test_ls_empty_prefix (TestS3ManagerCRUD) ... ok
test_obj_exists (TestS3ManagerCRUD) ... ok
test_path_exists (TestS3ManagerCRUD) ... ok
test_upload_and_download_bytes (TestS3ManagerCRUD) ... ok
test_upload_and_download_str (TestS3ManagerCRUD) ... ok
test_create_container (TestS3ManagerConnection) ... ok
test_batch_delete (TestS3ManagerLargeOps) ... ok
test_ls_many_objects (TestS3ManagerLargeOps) ... ok
test_copy_path (TestS3ManagerPathOps) ... ok
test_delete_path (TestS3ManagerPathOps) ... ok
test_move_path (TestS3ManagerPathOps) ... ok
test_sanitize_deletes_comma_only_names (TestS3ManagerPathOps) ... ok
test_sanitize_obj_names (TestS3ManagerPathOps) ... ok

----------------------------------------------------------------------
Ran 16 tests in 0.611s

OK
```

## Test Coverage by StorageManager Method

| Method | Test(s) | Status |
|---|---|---|
| `create_container()` | test_create_container (incl. idempotency) | PASS |
| `ls()` | test_ls, test_ls_empty_prefix, test_ls_many_objects | PASS |
| `path_exists()` | test_path_exists | PASS |
| `obj_exists()` | test_obj_exists | PASS |
| `upload_obj()` | test_upload_and_download_bytes, test_upload_and_download_str | PASS |
| `download_obj()` | test_upload_and_download_bytes, test_upload_and_download_str | PASS |
| `copy_obj()` | test_copy_obj | PASS |
| `delete_obj()` | test_delete_obj | PASS |
| `copy_path()` | test_copy_path | PASS |
| `move_path()` | test_move_path | PASS |
| `delete_path()` | test_delete_path, test_batch_delete | PASS |
| `sanitize_obj_names()` | test_sanitize_obj_names, test_sanitize_deletes_comma_only_names | PASS |

## Notable Findings

1. **boto3 >= 1.36.0 checksum breaking change:** Auto-CRC checksums (enabled Jan 2025) break
   all non-AWS S3 backends. Fixed via `botocore.config.Config` with
   `request_checksum_calculation='when_required'` and
   `response_checksum_validation='when_required'`.

2. **Path-style addressing required:** Virtual-hosted style (`bucket.endpoint`) does not work
   with non-AWS endpoints. Forced via `s3={'addressing_style': 'path'}`.

3. **Azure Blob has no native S3 endpoint:** Requires S3Proxy or similar gateway as a sidecar.
   Native AzureBlobManager (azure-storage-blob SDK) recommended for Azure production.

## How to Reproduce

```bash
# From repo root:
docker compose -f docker-compose.s3-test.yml up -d minio
docker compose -f docker-compose.s3-test.yml run --rm s3-test
docker compose -f docker-compose.s3-test.yml down -v
```
