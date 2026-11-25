#!/usr/bin/env python3
"""Release documents generated from pack locks.

  release_docs.py credits pack/pack.lock.json [--out CREDITS.md]
  release_docs.py changelog old.lock.json new.lock.json [--version 1.1.0]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_json  # noqa: E402

TYPE_URL = {"mod": "mod", "resourcepack": "resourcepack", "shader": "shader", "datapack": "datapack"}


def credits(lock: dict) -> str:
    rows = [f"# Credits — {lock['name']}\n",
            f"Minecraft {lock['minecraft']} · {lock['loader']} {lock.get('loader_version') or ''}\n",
            "Every file below is downloaded from its official Modrinth page; this pack does not redistribute it.\n",
            "| Name | Type | Version | Licence | Link |", "|---|---|---|---|---|"]
    for e in sorted(lock["entries"], key=lambda x: (x["type"], x["title"].lower())):
        rows.append(f"| {e['title']} | {e['type']} | {e['version_number']} | {e.get('license') or '?'} | "
                    f"https://modrinth.com/{TYPE_URL.get(e['type'], 'mod')}/{e['slug']} |")
    return "\n".join(rows) + "\n"


def changelog(old: dict, new: dict, version: str | None) -> str:
    o = {e["slug"]: e for e in old["entries"]}
    n = {e["slug"]: e for e in new["entries"]}
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    updated = sorted(s for s in set(o) & set(n) if o[s]["version_number"] != n[s]["version_number"])
    out = [f"## {version or new.get('version', '?')} — {dt.date.today()}"]
    if old["minecraft"] != new["minecraft"] or old["loader"] != new["loader"]:
        out.append(f"\n**Platform change:** {old['minecraft']}/{old['loader']} → {new['minecraft']}/{new['loader']}. "
                   "Back up worlds before updating.")
    if old.get("loader_version") != new.get("loader_version"):
        out.append(f"\n- Loader {old.get('loader_version')} → {new.get('loader_version')}")
    for title, items, fmt in (("Added", added, lambda s: f"{n[s]['title']} {n[s]['version_number']}"),
                              ("Removed", removed, lambda s: f"{o[s]['title']}"),
                              ("Updated", updated, lambda s: f"{n[s]['title']} {o[s]['version_number']} → {n[s]['version_number']}")):
        if items:
            out.append(f"\n### {title}")
            out += [f"- {fmt(s)}" for s in items]
    if removed:
        out.append("\n> Removed mods can delete blocks/items from existing worlds. Say it in the release notes.")
    out.append("\n### Balance / quests / configs\n- TODO: summarise from studio/decisions.md")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("credits"); c.add_argument("lock"); c.add_argument("--out")
    ch = sub.add_parser("changelog"); ch.add_argument("old"); ch.add_argument("new"); ch.add_argument("--version")
    a = ap.parse_args()
    if a.cmd == "credits":
        text = credits(load_json(Path(a.lock)))
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {a.out}")
        else:
            print(text)
    else:
        print(changelog(load_json(Path(a.old)), load_json(Path(a.new)), a.version))


if __name__ == "__main__":
    main()
