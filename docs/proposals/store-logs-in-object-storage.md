# Store ChRIS Logs in Object Storage

```text
---
title: Store ChRIS Logs in Object Storage
authors:
  - "@PridhiArora"
reviewers:
  - 
  
creation-date: 2022-10-14
last-updated: 2022-10-14
status: implementable
```

## Table of Contents

- [Store ChRIS Logs in Object Storage](#store-chris-logs-in-object-storage)
  - [Table of Contents](#table-of-contents)
  - [Glossary](#glossary)
  - [Summary](#summary)
  - [Motivation](#motivation)
    - [Goals](#goals)
  - [Proposal](#proposal)
    - [User Stories](#user-stories)
      - [Story - Decreasing the latency in ChRIS backend.](#story---decreasing-the-latency-in-chris-backend)
    - [Requirements](#requirements)
      - [Functional Requirements](#functional-requirements)
      - [Non-Functional Requirements](#non-functional-requirements)
    - [Implementation Details/Notes/Constraints](#implementation-detailsnotesconstraints](#implementation-detailsnotesconstraintsimplementation-detailsnotesconstraints)
      - [Proposed Changes](#proposed-changes)
    - [Test Plan](#test-plan)
    - [Graduation Criteria](#graduation-criteria)

## Glossary

- S3 - Amazon S3 is an object storage service that stores data as objects within buckets
- Minio - Minio is an open source distributed object storage server written in Go, designed for Private Cloud infrastructure providing S3 storage functionality

## Summary

ChRIS project currently stores log messages as strings in Postgres DB. This causes Postgres DB to be populated with strings which are relatively large in size. The large size hence causes the backend to slow down(****WHat exactly slows down? The retrieval of data from Postgres or the retrieval of logs? or what is causing the exact slowdown?)
One quick fix is to truncate the log string which is already implemented and use only a limited string. Rightnow a substring until 300 words is populated into the database and rest is truncated. But this devoids us of a lot of information. The decoration of log strings is done to make messages aesthetically pleasing. Removal of unncessary characters such as emojis and chineese characters reeduces the size of the string from 4000B to 2000B. Both the above fixes are still not enough as logs size increases everyday and it is uttermost important to find a better solution. This is where object storage comes into picture.


## Motivation

Absense of a proper storage system for logs is slowing the backend, causing a lot of frustration among the users. The idea is to have a proper system, so that ChRIS system is seamless. 



### Goals

1. To allow implementation of object storage for storage of logs.
2. < looks for other object in outreachy project summary>

## Proposal

### User Stories

#### Story - Decreasing the latency in ChRIS backend.

Stacy works at an IT department of an organization where ChRIS backend is used, she intends to use it on regular basis and needs logs to refer to. Storing logs in object storage would give her more readbale logs.

### Requirements

#### Functional Requirements

- FR1: Run Docker conatiner with Minio
- FR2: Connect Docker container to ChRIS' backend.
- FR3: Storge logs inside of Minio

#### Non-Functional Requirements

- NFR1: Unit tests MUST exist for the suport.


### Implementation Details/Notes/Constraints](#implementation-detailsnotesconstraints

#### Proposed Changes

Currently, the summary gets saved in Postgres. 

When object storage willbe implemented. The following lines would need to be changed.

```python
 self.c_plugin_inst.status = 'started'
self.c_plugin_inst.summary = self.get_job_status_summary()  # initial status
self.c_plugin_inst.raw = json_zip2str(d_resp)
self.c_plugin_inst.save()
```

Following is code snippet taken from official [Minio Doc](https://min.io/docs/minio/linux/developers/python/minio-py.html)s

```python
from minio import Minio
from minio.error import S3Error


def main():
    # Create a client with the MinIO server playground, its access key
    # and secret key.
    client = Minio(
        "play.min.io",
        access_key="Q3AM3UQ867SPQQA43P2F",
        secret_key="zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG",
    )

    # Make 'asiatrip' bucket if not exist.
    found = client.bucket_exists("asiatrip")
    if not found:
        client.make_bucket("asiatrip")
    else:
        print("Bucket 'asiatrip' already exists")

    # Upload '/home/user/Photos/asiaphotos.zip' as object name
    # 'asiaphotos-2015.zip' to bucket 'asiatrip'.
    client.fput_object(
        "asiatrip", "asiaphotos-2015.zip", "/home/user/Photos/asiaphotos.zip",
    )
    print(
        "'/home/user/Photos/asiaphotos.zip' is successfully uploaded as "
        "object 'asiaphotos-2015.zip' to bucket 'asiatrip'."
    )


if __name__ == "__main__":
    try:
        main()
    except S3Error as exc:
        print("error occurred.", exc)
Run File Uploader
$ python file_uploader.py
'/home/user/Photos/asiaphotos.zip' is successfully uploaded as object 'asiaphotos-2015.zip' to bucket 'asiatrip'.

```

### Test Plan

- Unit tests.



### Graduation Criteria

- Docker supported Minio
- Integratin of ChRIS with Minio
- Unit tests to test the functionality