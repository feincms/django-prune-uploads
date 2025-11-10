Change log
==========

Next version
~~~~~~~~~~~~

- Fixed orphan detection and deletion to work correctly per storage backend when
  multiple storages are in use (files are now only deleted from storages where
  they are actually orphaned).


0.3 (2025-10-11)
~~~~~~~~~~~~~~~~

- Added support for S3-based storage backends (django-storages, django-s3-storage)
  using boto3 directly for significantly faster file enumeration.
- Added optional ``s3`` extra for installing boto3 dependency:
  ``pip install django-prune-uploads[s3]``
- Added progress reporting during file enumeration (prints status every 1000 files).
- Added support for multiple storage backends per project (when different FileFields
  use different storage backends).


0.2 (2022-08-09)
~~~~~~~~~~~~~~~~

- Switched from ``null=True`` to ``blank=True`` for file fields (renamed
  ``--nullify-missing`` to ``--blank-missing``).
- Added support for ``MEDIA_ROOT`` being a ``Path`` instance.


0.1 (2020-10-28)
~~~~~~~~~~~~~~~~

- Initial release.
