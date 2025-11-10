import os
import re
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import FileField


EXCLUDE_DIRS = [
    r"^__.+__$",
]


class Command(BaseCommand):
    help = "Manage uploads"

    def _should_exclude_path(self, path):
        """Check if a path should be excluded based on EXCLUDE_DIRS patterns."""
        # Split path into parts and check each directory component
        parts = path.split("/")
        for part in parts[:-1]:  # Exclude the filename itself, only check directories
            for pattern in EXCLUDE_DIRS:
                if re.match(pattern, part):
                    return True
        return False

    def _is_s3_storage(self, storage):
        """Check if the storage backend is S3-based."""
        storage_class = storage.__class__.__name__
        return "S3" in storage_class or "s3" in storage_class.lower()

    def _get_s3_client(self, storage):
        """Get boto3 S3 client from storage backend."""
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 storage. Install it with: "
                "pip install django-prune-uploads[s3]"
            )

        # Try to get connection settings from the storage backend
        if hasattr(storage, "s3_connection"):
            # django-s3-storage (etianen)
            return storage.s3_connection
        elif hasattr(storage, "connection"):
            # django-storages S3Boto3Storage
            return storage.connection
        elif hasattr(storage, "bucket"):
            # Try to get the boto3 resource from bucket
            bucket = storage.bucket
            return bucket.meta.client
        else:
            # Fall back to creating a new client
            # This might not work in all cases, but is a reasonable fallback
            session_kwargs = {}
            if hasattr(storage, "access_key"):
                session_kwargs["aws_access_key_id"] = storage.access_key
            if hasattr(storage, "secret_key"):
                session_kwargs["aws_secret_access_key"] = storage.secret_key
            if hasattr(storage, "region_name"):
                session_kwargs["region_name"] = storage.region_name

            return boto3.client("s3", **session_kwargs)

    def _get_s3_bucket_and_prefix(self, storage):
        """Extract bucket name and prefix from storage backend."""
        bucket_name = None
        prefix = ""

        # django-s3-storage (etianen)
        if hasattr(storage, "settings"):
            settings = storage.settings
            if hasattr(settings, "AWS_S3_BUCKET_NAME"):
                bucket_name = settings.AWS_S3_BUCKET_NAME
            if hasattr(settings, "AWS_S3_KEY_PREFIX"):
                prefix = settings.AWS_S3_KEY_PREFIX or ""
        # django-storages and others
        elif hasattr(storage, "bucket_name"):
            bucket_name = storage.bucket_name
        elif hasattr(storage, "bucket"):
            bucket_name = storage.bucket.name

        # django-storages location attribute
        if not prefix and hasattr(storage, "location"):
            prefix = storage.location or ""

        # Ensure prefix ends with / if it exists
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        return bucket_name, prefix

    def _enumerate_s3_files(self, storage):
        """Enumerate files in S3 bucket using boto3 directly."""
        client = self._get_s3_client(storage)
        bucket_name, prefix = self._get_s3_bucket_and_prefix(storage)

        if not bucket_name:
            raise ValueError("Could not determine S3 bucket name from storage backend")

        files = set()
        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        count = 0
        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                # Remove prefix if present
                if prefix and key.startswith(prefix):
                    key = key[len(prefix) :]

                # Skip directories (keys ending with /) and excluded paths
                if not key.endswith("/") and not self._should_exclude_path(key):
                    files.add(key)
                    count += 1
                    if count % 1000 == 0:
                        self.stdout.write(f"  Found {count} files so far...")

        return files

    def _enumerate_filesystem_files(self, storage):
        """Enumerate files using os.walk for filesystem storage."""
        # Get the root directory from the storage
        if hasattr(storage, "location"):
            root = storage.location
        elif hasattr(storage, "base_location"):
            root = storage.base_location
        else:
            root = settings.MEDIA_ROOT

        root = str(root)

        existing = set()
        count = 0
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            for idx in range(len(dirnames) - 1, -1, -1):
                for exclude in EXCLUDE_DIRS:
                    if re.match(exclude, dirnames[idx]):
                        del dirnames[idx]

            existing |= {os.path.join(dirpath, name) for name in filenames}
            count += len(filenames)
            if count % 1000 == 0:
                self.stdout.write(f"  Found {count} files so far...")

        # Make paths relative to the storage root
        existing = {e[len(root) :].lstrip("/") for e in existing if e.startswith(root)}
        return existing

    def _delete_file(self, storage, filename):
        """Delete a file using Django's storage API."""
        storage.delete(filename)

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-orphans",
            action="store_true",
            help="Delete orphaned files.",
        )
        parser.add_argument(
            "--blank-missing",
            action="append",
            metavar="app.model.field",
            default=[],
            help=(
                "Empty blank file field <app.model.field> if referenced"
                " media file is missing."
            ),
        )
        parser.add_argument(
            "--delete-invalid",
            action="append",
            metavar="app.model.field",
            default=[],
            help=(
                "Delete instances where <app.model.field> references a"
                " non-existing media file."
            ),
        )

    def handle(self, **options):
        filefields = defaultdict(list)

        delete_invalid_names = {f.lower() for f in options["delete_invalid"]}
        delete_invalid_fields = set()

        blank_missing_names = {f.lower() for f in options["blank_missing"]}
        blank_missing_fields = set()

        for model in apps.get_models():
            for field in model._meta.get_fields():
                if not isinstance(field, FileField):
                    continue

                filefields[model].append(field)
                key = f"{model._meta.label_lower}.{field.name.lower()}"
                if key in delete_invalid_names:
                    delete_invalid_names.remove(key)
                    delete_invalid_fields.add(field)
                if key in blank_missing_names:
                    blank_missing_names.remove(key)
                    blank_missing_fields.add(field)

        if delete_invalid_names:
            raise Exception("delete-invalid: Invalid fields %r" % delete_invalid_names)
        if blank_missing_names:
            raise Exception("blank-missing: Invalid fields %r" % blank_missing_names)

        self.stdout.write("\n")
        self.stdout.write("#" * 79)
        self.stdout.write("File fields:")
        self.stdout.write(
            "\n".join(
                sorted(
                    "{}: {}".format(
                        model._meta.label, ", ".join(field.name for field in fields)
                    )
                    for model, fields in filefields.items()
                )
            )
        )
        self.stdout.write()

        # Collect known files and track their source (model, field, pk)
        known_with_source = {}

        for model, fields in filefields.items():
            for row in model._default_manager.order_by().values_list(
                "id", *[field.name for field in fields]
            ):
                for idx, name in enumerate(row[1:]):
                    if name:
                        field = fields[idx]
                        known_with_source[name] = (model, field, row[0])

        known = set(known_with_source.keys())

        # Collect all unique storage backends and derive known files per storage
        storages = set()
        for model, fields in filefields.items():
            for field in fields:
                storages.add(field.storage)

        # If no fields have custom storage, use default_storage
        if not storages:
            storages.add(default_storage)

        # Build known_by_storage from known_with_source
        known_by_storage = {storage: set() for storage in storages}
        for name, (model, field, pk) in known_with_source.items():
            known_by_storage[field.storage].add(name)

        self.stdout.write("\n")
        self.stdout.write("#" * 79)
        self.stdout.write("Known media files: %d" % len(known))

        self.stdout.write("Found %d storage backend(s)" % len(storages))

        # Enumerate files from all storage backends
        # Track which files belong to which storage (files can exist in multiple storages)
        existing_by_storage = {}
        for idx, storage in enumerate(storages, 1):
            if self._is_s3_storage(storage):
                bucket_name, prefix = self._get_s3_bucket_and_prefix(storage)
                self.stdout.write(
                    f"Storage {idx}/{len(storages)}: S3 ({storage.__class__.__name__}) "
                    f"bucket={bucket_name} prefix={prefix or '(none)'}"
                )
                files = self._enumerate_s3_files(storage)
            else:
                root = str(
                    getattr(
                        storage,
                        "location",
                        getattr(storage, "base_location", settings.MEDIA_ROOT),
                    )
                )
                self.stdout.write(
                    f"Storage {idx}/{len(storages)}: Filesystem ({storage.__class__.__name__}) "
                    f"location={root}"
                )
                files = self._enumerate_filesystem_files(storage)

            existing_by_storage[storage] = files

        # Combine all files for comparison with known files
        existing = set()
        for files in existing_by_storage.values():
            existing |= files

        self.stdout.write("Found media files: %d" % len(existing))

        self.stdout.write("\n")
        self.stdout.write("#" * 79)
        self.stdout.write(
            "Media files not in file system: %d" % (len(known - existing))
        )
        missing = defaultdict(list)

        for name in sorted(known - existing):
            model, field, pk = known_with_source[name]

            if field.blank and field in blank_missing_fields:
                self.stdout.write(
                    "Emptying {}.{} of {} ({})".format(
                        model._meta.label, field.name, pk, name
                    )
                )
                model._default_manager.filter(pk=pk).update(
                    **{
                        field.name: "",
                    }
                )

            elif field in delete_invalid_fields:
                self.stdout.write(
                    "Deleting {} of {} because of invalid {} ({})".format(
                        model._meta.label, pk, field.name, name
                    )
                )
                model._default_manager.filter(pk=pk).delete()

            else:
                missing[(model, field)].append(name)

        for key, value in missing.items():
            self.stdout.write(
                "{}.{}: {}".format(
                    key[0]._meta.label,
                    key[1].name,
                    len(value),
                )
            )
            if options["verbosity"] > 1:
                self.stdout.write("\n".join(sorted(value)))
                self.stdout.write()

        self.stdout.write("\n")
        self.stdout.write("#" * 79)

        # Calculate orphans per storage backend
        total_orphans = 0
        orphans_by_storage = {}
        for storage, files in existing_by_storage.items():
            storage_known = known_by_storage.get(storage, set())
            orphans = files - storage_known
            orphans_by_storage[storage] = orphans
            total_orphans += len(orphans)

        self.stdout.write("Media files not in DB: %d" % total_orphans)

        if options["delete_orphans"]:
            for storage, orphans in orphans_by_storage.items():
                if orphans:
                    self.stdout.write(
                        f"Deleting {len(orphans)} orphan(s) from {storage.__class__.__name__}"
                    )
                    for name in sorted(orphans):
                        self.stdout.write(f"  {name}")
                        self._delete_file(storage, name)
        else:
            if options["verbosity"] > 1:
                for storage, orphans in orphans_by_storage.items():
                    if orphans:
                        self.stdout.write(f"\n{storage.__class__.__name__}:")
                        self.stdout.write("\n".join(sorted(orphans)))
