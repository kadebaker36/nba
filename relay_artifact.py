#!/usr/bin/env python3
"""Create immutable UTF-8 reference artifacts or verify an exact envelope. No sends."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def fingerprint(raw):
    raw.decode("utf-8", errors="strict")
    return {"utf8_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify(path, byte_count, sha256):
    raw = Path(path).read_bytes()
    actual = fingerprint(raw)
    if type(byte_count) is not int or byte_count < 0 or actual != dict(utf8_bytes=byte_count, sha256=sha256):
        raise ValueError("Artifact byte count/SHA256 mismatch")
    return raw


def create(path, raw):
    receipt = fingerprint(raw)
    # Private from creation, then read-only once complete. These are guards,
    # not irreversible OS immutability or durable off-host storage.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o400)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("create")
    make.add_argument("path", type=Path)
    make.add_argument("--from-file", type=Path, required=True, help="Read raw bytes; no newline conversion")
    check = commands.add_parser("verify")
    check.add_argument("path", type=Path)
    check.add_argument("--bytes", type=int, required=True)
    check.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            receipt = create(args.path, args.from_file.read_bytes())
        else:
            raw = verify(args.path, args.bytes, args.sha256)
            receipt = fingerprint(raw)
        print(json.dumps(dict(state="verified", artifact_path=str(args.path), **receipt)))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps(dict(state="error", error=str(exc))))
        return 2


if __name__ == "__main__":
    sys.exit(main())
