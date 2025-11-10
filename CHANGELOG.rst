Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

- Added support for S3-based storage backends (django-storages, django-s3-storage)
  using boto3 directly for significantly faster file enumeration.
- Added optional ``s3`` extra for installing boto3 dependency:
  ``pip install django-prune-uploads[s3]``
- Added progress reporting during file enumeration (prints status every 1000 files).
- Fixed ``EXCLUDE_DIRS`` not being respected for S3 storage backends.


`0.2`_ (2022-08-09)
~~~~~~~~~~~~~~~~~~~

- Switched from ``null=True`` to ``blank=True`` for file fields (renamed
  ``--nullify-missing`` to ``--blank-missing``).
- Added support for ``MEDIA_ROOT`` being a ``Path`` instance.


`0.1`_ (2020-10-28)
~~~~~~~~~~~~~~~~~~~

- Initial release.


.. _0.1: https://github.com/matthiask/django-prune-uploads/commit/9fbb67e
.. _0.2: https://github.com/matthiask/django-prune-uploads/commit/a916660
.. _Next version: https://github.com/matthiask/django-prune-uploads
