"""
A module for interfacing with file storage backends.

File storage backends are "services" which store arbitrary data identified by path-like strings.
Examples include OpenStack Swift object storage, AWS S3, Nooba on OpenShift, or of course,
a literal UNIX-y filesystem.

ChRIS files are immutable, so file storage services can be optimized for WORM
(write-once, read-many) workloads.

Note to developers: historically, *ChRIS* was tightly-coupled to OpenStack Swift, hence
variable and function names use Swift terminology.
"""
from typing import Dict

from .storagemanager import StorageManager
from .swiftmanager import SwiftManager
from .plain_fs import FilesystemManager
from .helpers import connect_storage, verify_storage_connection


__all__ = ['StorageManager', 'SwiftManager', 'FilesystemManager', 'connect_storage', 'verify_storage_connection']
