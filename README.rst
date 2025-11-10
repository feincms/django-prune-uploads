======================================================
django-prune-uploads - Prune and maintain file uploads
======================================================

Installation
============

For filesystem storage (default)::

    pip install django-prune-uploads

For S3 storage backends::

    pip install django-prune-uploads[s3]

Then add ``prune_uploads`` to your ``INSTALLED_APPS``.

Usage
=====

1. Run ``./manage.py prune_uploads`` and have a look at the output (does
   not change anything in the database or the file system!)

2. Run ``./manage.py prune_uploads -v2`` for a potentially much more
   verbose report.

3. Run ``./manage.py prune_uploads --help`` to learn about the available
   options for actually changing and/or removing files and records.

Storage Backend Support
=======================

This package supports both filesystem storage and S3-based storage backends:

**Filesystem Storage**

For projects using Django's default ``FileSystemStorage``, the command uses
``os.walk()`` to enumerate files in the ``MEDIA_ROOT`` directory.

**S3 Storage**

For projects using S3-based storage backends (such as ``django-storages`` with
``S3Boto3Storage`` or ``django-s3-storage``), the command automatically detects
the storage backend and uses boto3 directly to enumerate files. This is
significantly faster than using Django's storage API when dealing with buckets
containing many objects.

The command will automatically detect S3 storage backends and use the
appropriate enumeration method. No additional configuration is required beyond
installing the ``s3`` extra dependencies.
