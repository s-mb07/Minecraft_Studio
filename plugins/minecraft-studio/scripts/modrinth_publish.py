#!/usr/bin/env python3
"""Publish a mod version to Modrinth. DRY RUN unless --yes (publishing is public: confirm with the user first).

  modrinth_publish.py <mod.jar> --project <slug-or-id> --version 1.0.0 --mc 1.21.1 --loader fabric
                      [--changelog CHANGELOG.md] [--type release|beta|alpha] [--dep slug:required ...] [--yes]

Token: environment variable MODRINTH_TOKEN (scope: create versions). Never pass it on the command line
or write it to a file in the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODRINTH_API, USER_AGENT, die, http_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jar")
    ap.add_argument("--project", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--mc", required=True, nargs="+")
    ap.add_argument("--loader", required=True, nargs="+")
    ap.add_argument("--changelog")
    ap.add_argument("--type", default="release", choices=["release", "beta", "alpha"])
    ap.add_argument("--dep", nargs="*", default=[], help="slug:required|optional|incompatible")
    ap.add_argument("--yes", action="store_true", help="actually publish (default: dry run)")
    a = ap.parse_args()
    jar = Path(a.jar)
    if not jar.exists():
        die(f"{jar} not found")
    proj = http_json(f"{MODRINTH_API}/project/{a.project}")
    if not proj:
        die(f"Modrinth project '{a.project}' not found — create it on modrinth.com first")
    deps = []
    for d in a.dep:
        slug, _, kind = d.partition(":")
        dp = http_json(f"{MODRINTH_API}/project/{slug}")
        if not dp:
            die(f"dependency '{slug}' not found on Modrinth")
        deps.append({"project_id": dp["id"], "dependency_type": kind or "required"})
    data = {
        "project_id": proj["id"], "name": f"{proj['title']} {a.version}", "version_number": a.version,
        "changelog": Path(a.changelog).read_text(encoding="utf-8") if a.changelog else "",
        "dependencies": deps, "game_versions": a.mc, "version_type": a.type, "loaders": a.loader,
        "featured": False, "file_parts": ["file"], "primary_file": "file",
    }
    print(f"version {a.version} of {proj['slug']} — {a.type}, MC {a.mc}, {a.loader}, file {jar.name} "
          f"({jar.stat().st_size // 1024} KB), {len(deps)} deps")
    if not a.yes:
        print("DRY RUN: nothing sent. Re-run with --yes after the user confirms.")
        return
    token = os.environ.get("MODRINTH_TOKEN")
    if not token:
        die("MODRINTH_TOKEN is not set")
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"data\"\r\nContent-Type: application/json\r\n\r\n"
            f"{json.dumps(data)}\r\n--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{jar.name}\"\r\n"
            f"Content-Type: application/java-archive\r\n\r\n").encode() + jar.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"{MODRINTH_API}/version", data=body, method="POST", headers={
        "Authorization": token, "User-Agent": USER_AGENT, "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    print(f"published: https://modrinth.com/{proj['project_type']}/{proj['slug']}/version/{res['id']}")


if __name__ == "__main__":
    main()
