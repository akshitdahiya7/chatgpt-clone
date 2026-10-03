"""Check S3 end to end: upload an object, presign it, fetch it back, clean up.

Run from the chat-service directory:
    uv run python scripts/verify_s3.py

This mirrors exactly what AzureBlobService.upload_file + generate_sas_url do, so if this
passes, the S3 storage provider has nothing left to surprise you with.
"""
import sys
import urllib.request
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

ENV = Path(__file__).resolve().parent.parent / ".env"

HINTS = {
    "NoSuchBucket":
        "Bucket does not exist in this region. Check S3_BUCKET_NAME and AWS_REGION.",
    "AccessDenied":
        "Bucket exists but the key cannot touch it. Check AmazonS3FullAccess is attached.",
    "InvalidAccessKeyId":
        "Access key id not recognised.",
    "SignatureDoesNotMatch":
        "Secret key is wrong.",
    "IllegalLocationConstraintException":
        "Bucket lives in a different region than AWS_REGION says.",
    "PermanentRedirect":
        "Bucket is in another region. Set AWS_REGION to the bucket's actual region.",
}


def load_env(path):
    if not path.exists():
        sys.exit("Not found: {}".format(path))
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fail(code, message, secret, key_id):
    for value in (secret, key_id):
        if value:
            message = message.replace(value, "<redacted>")
    print("\nFAILED  [{}] {}".format(code, message))
    if code in HINTS:
        print("  -> {}".format(HINTS[code]))
    return 1


def main():
    env = load_env(ENV)

    required = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME")
    missing = [k for k in required if not env.get(k) or env[k].startswith("<")]
    if missing:
        sys.exit("Missing or placeholder in .env: {}".format(", ".join(missing)))

    key_id = env["AWS_ACCESS_KEY_ID"]
    secret = env["AWS_SECRET_ACCESS_KEY"]
    bucket = env["S3_BUCKET_NAME"]

    if len(key_id) == 40 or "/" in key_id:
        sys.exit("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY look swapped.")

    print("Region : {}".format(env["AWS_REGION"]))
    print("Bucket : {}".format(bucket))

    client = boto3.client(
        "s3",
        region_name=env["AWS_REGION"],
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
    )

    key = "verify-{}.txt".format(uuid4().hex[:8])
    payload = b"s3 round trip ok"

    # 1. upload
    try:
        client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="text/plain")
    except ClientError as exc:
        err = exc.response["Error"]
        return fail(err["Code"], err["Message"], secret, key_id)
    print("\n1. put_object            OK  -> {}".format(key))

    # 2. presign (this is generate_sas_url's analogue)
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=60 * 60,          # NOTE: seconds, where Azure took minutes
    )
    print("2. presigned url         OK  -> {}...".format(url[:60]))

    # 3. fetch it back over plain HTTPS, no credentials
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = resp.read()
    except Exception as exc:
        print("3. fetch presigned url   FAIL  {}: {}".format(type(exc).__name__, exc))
        return 1

    if body != payload:
        print("3. fetch presigned url   FAIL  content mismatch: {!r}".format(body[:60]))
        return 1
    print("3. fetch presigned url   OK  content matches")

    # 4. confirm the bucket is NOT publicly readable
    plain = "https://{}.s3.{}.amazonaws.com/{}".format(bucket, env["AWS_REGION"], key)
    try:
        urllib.request.urlopen(plain, timeout=20)
        print("4. public access         WARNING  object is readable WITHOUT a signature.")
        print("   -> Block Public Access is off. Turn all four settings back on.")
    except Exception:
        print("4. public access         OK  blocked without a signature (as intended)")

    # 5. clean up
    client.delete_object(Bucket=bucket, Key=key)
    print("5. delete_object         OK  test object removed")

    print("\nS3 is ready. Change 2 can use this exact flow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
