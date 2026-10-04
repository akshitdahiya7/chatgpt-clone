"""Push the locally built docker-compose images to ECR.

Run from the chat-service directory:
    uv run python scripts/push_to_ecr.py          # report only
    uv run python scripts/push_to_ecr.py --push   # log in, tag and push

Useful when you want the EC2 instance to pull prebuilt images instead of
waiting on CI, or building on the instance itself.

The registry password is piped straight to `docker login` and never printed.
"""
import base64
import subprocess
import sys
from pathlib import Path

import boto3

SERVICES = ("gateway", "chat-service", "ai-service", "frontend")
LOCAL_PREFIX = "chatgpt-clone-"
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


def run(args, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True)


def main():
    push = "--push" in sys.argv
    env = load_env(ENV)

    creds = {
        "region_name": env["AWS_REGION"],
        "aws_access_key_id": env["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": env["AWS_SECRET_ACCESS_KEY"],
    }
    region = env["AWS_REGION"]
    ecr = boto3.client("ecr", **creds)
    account = boto3.client("sts", **creds).get_caller_identity()["Account"]
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"

    print(f"registry : {registry}")
    print()

    print("ECR contents:")
    for name in SERVICES:
        try:
            images = ecr.describe_images(repositoryName=name)["imageDetails"]
        except ecr.exceptions.RepositoryNotFoundException:
            print(f"  {name:14} repository missing")
            continue
        if not images:
            print(f"  {name:14} empty")
        else:
            newest = max(images, key=lambda i: i["imagePushedAt"])
            tags = ",".join(newest.get("imageTags", ["<untagged>"]))
            size = newest["imageSizeInBytes"] / 1_000_000
            print(f"  {name:14} {len(images)} image(s), newest {tags} ({size:.0f} MB)")

    print()
    print("Local images:")
    for name in SERVICES:
        local = f"{LOCAL_PREFIX}{name}:latest"
        result = run(["docker", "image", "inspect", local, "--format", "{{.Size}}"])
        if result.returncode == 0:
            print(f"  {local:34} {int(result.stdout.strip()) / 1_000_000:.0f} MB")
        else:
            print(f"  {local:34} NOT BUILT (run: docker compose build)")

    if not push:
        print()
        print("Report only. Re-run with --push to log in, tag and push.")
        return 0

    print()
    print("Logging in to ECR...")
    token = ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
    password = base64.b64decode(token).decode().split(":", 1)[1]
    login = run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        stdin=password,
    )
    if login.returncode != 0:
        print("  docker login failed:", login.stderr.strip()[:200])
        return 1
    print("  logged in")

    for name in SERVICES:
        local = f"{LOCAL_PREFIX}{name}:latest"
        remote = f"{registry}/{name}:latest"

        print(f"\n{name}:")
        tag = run(["docker", "tag", local, remote])
        if tag.returncode != 0:
            print("  tag failed:", tag.stderr.strip()[:200])
            return 1
        print(f"  tagged  -> {remote}")

        pushed = subprocess.run(["docker", "push", remote])
        if pushed.returncode != 0:
            print("  push failed")
            return 1
        print("  pushed")

    print("\nAll images pushed. The EC2 instance can now pull them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
