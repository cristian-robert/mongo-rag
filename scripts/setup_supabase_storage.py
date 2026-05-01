"""Bootstrap the Supabase Storage bucket used by SupabaseBlobStore.

Idempotent — safe to run multiple times. Run once per environment after deploying.

Authenticates with a DISTINCT S3 access-key/secret pair minted under the Supabase
dashboard (Project Settings → Storage → S3 Connection). These are NOT the
service-role JWT-signing key (`SUPABASE_SECRET_KEY`); using the service-role key
here returns SignatureDoesNotMatch / 403 from Supabase Storage's S3-compat layer.

Usage:
    BLOB_STORE=supabase \\
    SUPABASE_URL=https://<ref>.supabase.co \\
    SUPABASE_S3_ACCESS_KEY=... \\
    SUPABASE_S3_SECRET_KEY=... \\
    SUPABASE_STORAGE_BUCKET=mongorag-uploads \\
    uv run python scripts/setup_supabase_storage.py
"""

from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET")
    supabase_url = os.environ.get("SUPABASE_URL")
    access_key = os.environ.get("SUPABASE_S3_ACCESS_KEY")
    secret_key = os.environ.get("SUPABASE_S3_SECRET_KEY")

    if not (bucket and supabase_url and access_key and secret_key):
        print(
            "ERROR: SUPABASE_STORAGE_BUCKET, SUPABASE_URL, "
            "SUPABASE_S3_ACCESS_KEY, SUPABASE_S3_SECRET_KEY required. "
            "Mint S3 credentials under Supabase dashboard → "
            "Project Settings → Storage → S3 Connection. "
            "These are NOT the service-role SUPABASE_SECRET_KEY."
        )
        return 1

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/s3"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )

    # Create bucket if missing.
    try:
        client.head_bucket(Bucket=bucket)
        print(f"Bucket {bucket!r} already exists")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchBucket", "NotFound"):
            client.create_bucket(Bucket=bucket)
            print(f"Created bucket {bucket!r}")
        else:
            raise

    # 24h expiration lifecycle rule.
    rules = {
        "Rules": [
            {
                "ID": "delete-stale-uploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Expiration": {"Days": 1},
            }
        ]
    }
    try:
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket, LifecycleConfiguration=rules
        )
        print(f"Lifecycle rule installed on {bucket!r} (delete after 1 day)")
    except ClientError as e:
        # Supabase Storage's S3-compat layer may not implement lifecycle ops.
        # Print a clear hint and exit 0 — bucket creation succeeded.
        code = e.response.get("Error", {}).get("Code")
        print(
            f"WARNING: lifecycle config failed ({code}). "
            f"If Supabase doesn't support lifecycle via S3 API, "
            f"configure the 1-day expiration via the Supabase dashboard."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
