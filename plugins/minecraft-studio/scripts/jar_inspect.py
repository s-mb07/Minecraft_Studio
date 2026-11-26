#!/usr/bin/env python3
"""Inspect a mod jar: metadata, loader, dependencies, mixins, registered content (from lang), asset counts.

  jar_inspect.py <mod.jar | mods-folder> [--ids] [--json] [--sheet out.md]

Works for your own builds AND for third-party mods in a modpack: --ids lists real item/block ids
(useful for FTB Quests tasks and KubeJS recipes), --sheet writes a mod sheet (templates/mod-sheet.md style).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


def read_toml_basic(text: str) -> dict:
    """Very small TOML subset reader for mods.toml / neoforge.mods.toml (keys we need)."""
    out = {"mods": [], "dependencies": []}
    cur = None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[[mods]]"):
            cur = {}
            out["mods"].append(cur)
        elif line.startswith("[[dependencies"):
            cur = {}
            out["dependencies"].append(cur)
        elif "=" in line:
            k, v = [x.strip() for x in line.split("=", 1)]
            v = v.strip('"\'')
            (cur if cur is not None else out)[k] = v
    return out


def inspect(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        info = {"file": path.name, "loader": None, "id": None, "version": None, "name": None,
                "depends": {}, "mixins": [], "ids": {"item": [], "block": [], "entity": [], "other": []},
                "assets": {}, "data": {}}
        if "fabric.mod.json" in names:
            m = json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
            info.update(loader="fabric", id=m.get("id"), version=m.get("version"), name=m.get("name"),
                        depends=m.get("depends", {}))
            info["mixins"] = [x if isinstance(x, str) else x.get("config") for x in m.get("mixins", [])]
        else:
            for meta in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
                if meta in names:
                    t = read_toml_basic(z.read(meta).decode("utf-8", "replace"))
                    mod = (t["mods"] or [{}])[0]
                    info.update(loader="neoforge" if "neoforge" in meta else "forge", id=mod.get("modId"),
                                version=mod.get("version"), name=mod.get("displayName"),
                                depends={d.get("modId"): d.get("versionRange") for d in t["dependencies"] if d.get("modId")})
                    break
        for n in names:
            mm = re.match(r"(assets|data)/([^/]+)/([^/]+)/", n)
            if mm:
                bucket = info[mm.group(1)].setdefault(mm.group(2), {})
                bucket[mm.group(3)] = bucket.get(mm.group(3), 0) + 1
        for n in names:
            if re.match(r"assets/[^/]+/lang/en_us\.json$", n):
                try:
                    lang = json.loads(z.read(n).decode("utf-8", "replace"), strict=False)
                except ValueError:
                    continue
                for k in lang:
                    p = k.split(".")
                    if len(p) == 3 and p[0] in ("item", "block", "entity"):
                        info["ids"][p[0]].append(f"{p[1]}:{p[2]}")
    return info


def sheet(info: dict) -> str:
    items = ", ".join(info["ids"]["item"][:30]) or "(none found in lang)"
    blocks = ", ".join(info["ids"]["block"][:30]) or "(none)"
    return (f"---\nmod: {info['id']}\nversion: {info['version']}\nstatus: candidate\nside: both\n---\n"
            f"# {info['name'] or info['id']}\n\n- **Loader:** {info['loader']}\n- **Depends on:** "
            f"{', '.join(k for k in info['depends'] if k not in ('minecraft', 'java', 'fabricloader'))}\n"
            f"- **Key items:** {items}\n- **Blocks:** {blocks}\n- **Why it's in the pack:**\n- **Recipes to rebalance:**\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--ids", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    t = Path(a.target)
    jars = sorted(t.glob("*.jar")) if t.is_dir() else [t]
    jars = [j for j in jars if "-sources" not in j.name]
    results = [inspect(j) for j in jars]
    if a.json:
        print(json.dumps(results if len(results) > 1 else results[0], indent=2))
        return
    for r in results:
        own = r["assets"].get(r["id"], {})
        print(f"{r['file']}: {r['id']} {r['version']} ({r['loader']}) — items {len(r['ids']['item'])}, "
              f"blocks {len(r['ids']['block'])}, entities {len(r['ids']['entity'])}, mixin configs {len(r['mixins'])}, "
              f"assets {sum(own.values())} {dict(own)}")
        if a.ids:
            for k in ("item", "block", "entity"):
                if r["ids"][k]:
                    print(f"  {k}: {' '.join(r['ids'][k])}")
    if a.sheet and results:
        Path(a.sheet).write_text(sheet(results[0]), encoding="utf-8")
        print(f"wrote {a.sheet}")


if __name__ == "__main__":
    main()
