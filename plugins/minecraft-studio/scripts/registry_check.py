#!/usr/bin/env python3
"""Re-check the third-party registry against GitHub (exists, licence, archived, last push).

  registry_check.py [--registry ../third-party/registry.json] [--stale-days 365]

Uses the public GitHub API without a token (60 requests/hour). Set GITHUB_TOKEN to raise the limit.
Exit code 1 if an entry disappeared, got archived, or changed licence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import USER_AGENT, Report, load_json  # noqa: E402


def gh(repo: str):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={"User-Agent": USER_AGENT})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return None if e.code == 404 else {"_error": e.code}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=str(Path(__file__).resolve().parent.parent / "third-party" / "registry.json"))
    ap.add_argument("--stale-days", type=int, default=365)
    a = ap.parse_args()
    reg = load_json(Path(a.registry))
    r = Report("third-party registry")
    seen = {}
    for e in reg["entries"]:
        repo = e["repo"]
        info = seen.get(repo) or gh(repo)
        seen[repo] = info
        if info is None:
            r.fail(e["id"], f"{repo} no longer exists")
            continue
        if "_error" in info:
            r.look(e["id"], f"GitHub API error {info['_error']} (rate limit?)")
            continue
        lic = (info.get("license") or {}).get("spdx_id")
        if info.get("archived"):
            r.fail(e["id"], f"{repo} is archived")
        elif lic != e["license"]:
            r.fail(e["id"], f"licence changed: registry says {e['license']}, GitHub says {lic}")
        else:
            pushed = dt.datetime.fromisoformat(info["pushed_at"].replace("Z", "+00:00"))
            age = (dt.datetime.now(dt.timezone.utc) - pushed).days
            if age > a.stale_days:
                r.look(e["id"], f"{repo}: no push for {age} days")
            else:
                r.ok(e["id"], f"{repo} ({lic}, pushed {age}d ago, {info.get('stargazers_count')} stars)")
    r.print()
    sys.exit(r.exit_code())


if __name__ == "__main__":
    main()
