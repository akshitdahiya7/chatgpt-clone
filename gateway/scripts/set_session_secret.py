"""Generate a SESSION_SECRET and write it into the gateway config.

Run from the gateway directory:
    uv run python scripts/set_session_secret.py

The value is written straight to the file and never printed, so it does not end
up in a terminal transcript or scrollback. Pass --force to replace an existing
one; changing it signs every visitor out, which is the correct response if it
ever leaks.
"""
import secrets
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / ".env"
KEY = "SESSION_SECRET"


def main():
    force = "--force" in sys.argv

    if not CONFIG.exists():
        sys.exit(
            f"{CONFIG.name} not found in {CONFIG.parent}.\n"
            "Copy the example file first."
        )

    lines = CONFIG.read_text(encoding="utf-8").splitlines()

    existing = [
        line for line in lines
        if line.strip().startswith(f"{KEY}=")
    ]

    if existing and not force:
        current = existing[0].partition("=")[2].strip()

        if current and current != "change-me":
            print(f"{KEY} is already set ({len(current)} characters).")
            print("Pass --force to replace it. Doing so signs every visitor out.")
            return 0

    secret = secrets.token_urlsafe(32)
    replacement = f"{KEY}={secret}"

    if existing:
        lines = [
            replacement if line.strip().startswith(f"{KEY}=") else line
            for line in lines
        ]
    else:
        lines.append(replacement)

    CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{KEY} written to gateway config ({len(secret)} characters).")
    print("The value was not printed. Copy the file to the server with:")
    print("  .\\scripts\\copy-env-to-ec2.ps1 -HostIp 34.235.183.74")
    return 0


if __name__ == "__main__":
    sys.exit(main())
