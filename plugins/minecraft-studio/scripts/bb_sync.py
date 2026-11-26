#!/usr/bin/env python3
"""Bring manual Blockbench edits back into an entity_gen spec, so regenerating never loses the user's fixes.

  bb_sync.py <spec.json> <edited.bbmodel> --out <spec_new.json> [--bones regex] [--dry-run]

For every bone of the spec that also exists (same name) in the .bbmodel, copies pivot, rotation and cube
geometry (origin, size, rotation, pivot). Materials, roles, expects and details stay as in the spec.
Frame conversion (measured, see mc-entity-art "Orientation"): Blockbench shows geo X mirrored and X/Y rotations
negated, so geo = (-x, y, z) for points and (-rx, -ry, rz) for rotations; a cube's geo origin x = -to_x.
Prints one line per changed bone.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def r3(v):
    return [round(float(x), 4) for x in v]


def to_geo_point(p):
    return r3([-p[0], p[1], p[2]])


def to_geo_rot(r):
    return r3([-r[0], -r[1], r[2]])


def load_bb(path: Path) -> dict:
    """{bone name: {"pivot", "rotation", "cubes": [geo cube dicts in outliner order]}}"""
    j = json.loads(path.read_text(encoding="utf-8"))
    groups = {g["uuid"]: g for g in j.get("groups", []) if isinstance(g, dict)}
    els = {e["uuid"]: e for e in j.get("elements", [])}
    out = {}

    def walk(node):
        if isinstance(node, str):
            return
        g = groups.get(node.get("uuid"), node)
        cubes = []
        for ch in node.get("children", []):
            if isinstance(ch, str) and ch in els and els[ch].get("type", "cube") == "cube":
                e = els[ch]
                f, t = e["from"], e["to"]
                c = {"origin": r3([-t[0], f[1], f[2]]), "size": r3([t[i] - f[i] for i in range(3)])}
                if any(e.get("rotation", [0, 0, 0])):
                    c["rotation"], c["pivot"] = to_geo_rot(e["rotation"]), to_geo_point(e.get("origin", [0, 0, 0]))
                if e.get("inflate"):
                    c["inflate"] = e["inflate"]
                cubes.append(c)
        out[g.get("name")] = {"pivot": to_geo_point(g.get("origin", [0, 0, 0])),
                              "rotation": to_geo_rot(g.get("rotation", [0, 0, 0])), "cubes": cubes}
        for ch in node.get("children", []):
            walk(ch)
    for n in j.get("outliner", []):
        walk(n)
    return out


def sync(spec: dict, bb: dict, pattern: str | None = None) -> list[str]:
    changed = []
    rx = re.compile(pattern) if pattern else None
    for b in spec["bones"]:
        e = bb.get(b["name"])
        if not e or (rx and not rx.search(b["name"])):
            continue
        def sig(b=b):  # numeric signature (2 == 2.0, tolerance 1e-3)
            vals = list(b.get("pivot", [0, 0, 0])) + list(b.get("rotation", [0, 0, 0]))
            for c in b.get("cubes", []):
                vals += list(c["origin"]) + list(c["size"]) + list(c.get("rotation", [0, 0, 0]))
            return [round(float(v), 3) for v in vals]
        before = sig()
        b["pivot"] = e["pivot"]
        if any(e["rotation"]):
            b["rotation"] = e["rotation"]
        else:
            b.pop("rotation", None)
        for i, c in enumerate(b.get("cubes", [])):
            if i < len(e["cubes"]):
                ec = e["cubes"][i]
                c["origin"], c["size"] = ec["origin"], ec["size"]
                for k in ("rotation", "pivot", "inflate"):
                    if k in ec:
                        c[k] = ec[k]
                    elif k in ("rotation", "pivot"):
                        c.pop(k, None)
        if sig() != before:
            changed.append(f"{b['name']}: pivot {b['pivot']} rot {b.get('rotation', [0, 0, 0])}")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("bbmodel"); ap.add_argument("--out")
    ap.add_argument("--bones", help="only bones matching this regex"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    changed = sync(spec, load_bb(Path(a.bbmodel)), a.bones)
    for c in changed:
        print("SYNC", c)
    print(f"{len(changed)} bones updated from {Path(a.bbmodel).name}")
    if not a.dry_run:
        Path(a.out or a.spec).write_text(json.dumps(spec, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
