"""Create the ECR repositories this project pushes images to.

Run from the chat-service directory:
    uv run python scripts/setup_ecr.py

Idempotent: existing repositories are left alone. Prints the registry URI that
the GitHub Actions workflow needs.
"""
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPOSITORIES = ("gateway", "chat-service", "ai-service")
ENV = Path(__file__).resolve().parent.parent / ".env"


def load_env(path):
    if not path.exists():
        sys.exit(f"Not found: {path}")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main():
    env = load_env(ENV)

    missing = [
        k for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION")
        if not env.get(k)
    ]
    if missing:
        sys.exit("Missing in env file: " + ", ".join(missing))

    creds = {
        "region_name": env["AWS_REGION"],
        "aws_access_key_id": env["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": env["AWS_SECRET_ACCESS_KEY"],
    }

    account = boto3.client("sts", **creds).get_caller_identity()["Account"]
    registry = f"{account}.dkr.ecr.{env['AWS_REGION']}.amazonaws.com"

    print(f"account  : {account}")
    print(f"region   : {env['AWS_REGION']}")
    print(f"registry : {registry}")
    print()

    ecr = boto3.client("ecr", **creds)

    for name in REPOSITORIES:
        try:
            ecr.create_repository(
                repositoryName=name,
                # MUTABLE so the :latest tag can move between builds.
                imageTagMutability="MUTABLE",
                imageScanningConfiguration={"scanOnPush": False},
            )
            print(f"  {name:14} created")
        except ClientError as exc:
            error = exc.response["Error"]
            if error["Code"] == "RepositoryAlreadyExistsException":
                print(f"  {name:14} already exists")
            else:
                print(f"  {name:14} FAILED [{error['Code']}] {error['Message'][:90]}")
                return 1

    print()
    print("GitHub repository secrets to add:")
    print(f"  AWS_REGION       = {env['AWS_REGION']}")
    print(f"  AWS_ACCOUNT_ID   = {account}")
    print("  AWS_ACCESS_KEY_ID      = (the AKIA... value)")
    print("  AWS_SECRET_ACCESS_KEY  = (the 40-char secret)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
