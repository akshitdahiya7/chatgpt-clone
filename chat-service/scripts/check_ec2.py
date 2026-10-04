"""Report the EC2 instance state and its security group rules.

Run from the chat-service directory:
    uv run python scripts/check_ec2.py
"""
import sys
import urllib.request
from pathlib import Path

import boto3

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


def my_ip():
    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def main():
    env = load_env(ENV)
    ec2 = boto3.client(
        "ec2",
        region_name=env["AWS_REGION"],
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )

    current = my_ip()
    print(f"this machine's public IP : {current or 'could not determine'}")
    print()

    reservations = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "stopped"]}]
    )["Reservations"]

    instances = [i for r in reservations for i in r["Instances"]]
    if not instances:
        print("No instances found.")
        return 1

    for inst in instances:
        name = next(
            (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
            "<unnamed>",
        )
        print(f"instance : {name}  ({inst['InstanceId']})")
        print(f"  state      : {inst['State']['Name']}")
        print(f"  type       : {inst['InstanceType']}")
        print(f"  public IP  : {inst.get('PublicIpAddress', '<none>')}")
        profile = inst.get("IamInstanceProfile", {}).get("Arn", "<NONE ATTACHED>")
        print(f"  IAM profile: {profile.split('/')[-1] if '/' in profile else profile}")

        for group in inst.get("SecurityGroups", []):
            detail = ec2.describe_security_groups(GroupIds=[group["GroupId"]])[
                "SecurityGroups"
            ][0]
            print(f"  security group: {detail['GroupName']} ({group['GroupId']})")

            if not detail["IpPermissions"]:
                print("    (no inbound rules at all)")

            for perm in detail["IpPermissions"]:
                proto = perm.get("IpProtocol")
                lo, hi = perm.get("FromPort"), perm.get("ToPort")
                port = proto if lo is None else (str(lo) if lo == hi else f"{lo}-{hi}")
                for rng in perm.get("IpRanges", []):
                    cidr = rng["CidrIp"]
                    note = ""
                    if current and cidr != "0.0.0.0/0":
                        allowed = cidr.split("/")[0]
                        note = (
                            "  <-- matches this machine"
                            if allowed == current
                            else f"  <-- does NOT match this machine ({current})"
                        )
                    print(f"    inbound {port:9} from {cidr}{note}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
