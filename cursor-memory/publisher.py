"""Publish only marked local ClaudeMem notes to the private cloud snapshot."""
import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from publication import Publications, canonical


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def write_json(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".publication-")
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(value, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def remote(config, method, body=None):
    data = None if body is None else canonical(body)
    request = Request(config["endpoint"], data=data, method=method, headers={
        "Authorization": "Bearer " + config["token"],
        "Content-Type": "application/json",
    })
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(4097)
    if len(raw) > 4096:
        raise ValueError("Unexpected publication receipt.")
    receipt = json.loads(raw)
    if (
        not isinstance(receipt.get("generation"), str) or not receipt["generation"].isdecimal()
        or not isinstance(receipt.get("digest"), str) or len(receipt["digest"]) != 64
    ):
        raise ValueError("Invalid publication receipt.")
    return receipt


def synchronize(config, publications):
    snapshot = publications.snapshot()
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    current = remote(config, "GET")
    if current["digest"] != digest:
        current = remote(config, "PUT", {"generation": current["generation"], "snapshot": snapshot})
    if current["digest"] != digest:
        raise ValueError("Publication readback digest did not match.")
    return {"generation": current["generation"], "notes": sum(map(len, snapshot.values())), "digest": digest}


def load_config(path):
    if path.stat().st_mode & 0o077:
        raise ValueError("Publication configuration must be readable only by its owner.")
    config = json.loads(path.read_text())
    endpoint = urlsplit(config["endpoint"])
    if (
        endpoint.scheme != "https" or not endpoint.hostname or not endpoint.hostname.endswith(".run.app")
        or endpoint.path != "/publication" or endpoint.query or endpoint.fragment
        or endpoint.username or endpoint.password or endpoint.port
        or not isinstance(config["token"], str) or len(config["token"]) < 32
    ):
        raise ValueError("Expected a dedicated HTTPS publication endpoint and credential.")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/claudemem-cursor/publisher.json")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("mark", "unpublish"):
        command = commands.add_parser(name)
        command.add_argument("id", type=int)
        command.add_argument("--repo", required=True)
    commands.add_parser("sync")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        publications = Publications(Path(config["source"]), Path(config["registry"]), config["projects"])
        if args.command == "mark":
            publications.mark(args.id, args.repo)
            print(f"Marked observation {args.id} for {args.repo}; the background publisher will deliver it.")
            return 0
        if args.command == "unpublish":
            publications.unmark(args.id, args.repo)
            print(f"Unmarked observation {args.id} for {args.repo}; the background publisher will withdraw it.")
            return 0
        health_path = args.config.with_name("sync-health.json")
        with args.config.with_name("sync.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            try:
                receipt = synchronize(config, publications)
            except Exception as error:
                try:
                    health = json.loads(health_path.read_text())
                except (OSError, ValueError):
                    health = {}
                health["last_error"] = type(error).__name__
                write_json(health_path, health)
                raise
            write_json(health_path, {**receipt, "last_success": datetime.now(timezone.utc).isoformat(), "last_error": None})
            print(f"Published {receipt['notes']} notes; cloud generation {receipt['generation']}.")
        return 0
    except Exception as error:
        print(f"Publication operation failed ({type(error).__name__}); existing marks are preserved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
