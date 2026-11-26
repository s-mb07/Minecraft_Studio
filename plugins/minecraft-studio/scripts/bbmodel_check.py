#!/usr/bin/env python3
"""Check Blockbench files and exported Java models before they go into a mod.

  bbmodel_check.py <file.bbmodel | model.json | folder> [--modid msexample] [--verbose]

.bbmodel   format, texture resolution, textures without a source, Java Block limits, duplicate GeckoLib bones
model.json (exported java_block): elements within -16..32, rotation angles allowed by vanilla
           (-45/-22.5/0/22.5/45, one axis), face texture refs defined, texture refs namespaced (--modid)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report  # noqa: E402

ANGLES = {-45, -22.5, 0, 22.5, 45}


def check_elements(elements, where, r: Report):
    for i, e in enumerate(elements or []):
        name = e.get("name", f"#{i}")
        for k in ("from", "to"):
            v = e.get(k)
            if v and any(c < -16 or c > 32 for c in v):
                r.fail(where, f"element '{name}' {k}={v} outside -16..32 (Java block/item limit)")
        rot = e.get("rotation")
        if isinstance(rot, dict) and rot.get("angle", 0) not in ANGLES:
            r.fail(where, f"element '{name}' rotation {rot.get('angle')} not allowed (use -45/-22.5/0/22.5/45)")
        if isinstance(rot, list):
            nz = [x for x in rot if x]
            if len(nz) > 1:
                r.fail(where, f"element '{name}' rotated on {len(nz)} axes (Java models allow one)")
            elif nz and nz[0] not in ANGLES:
                r.fail(where, f"element '{name}' rotation {nz[0]} not allowed (use -45/-22.5/0/22.5/45)")


def check_json_model(p: Path, modid: str | None, r: Report):
    m = json.loads(p.read_text(encoding="utf-8"))
    where = p.name
    check_elements(m.get("elements"), where, r)
    tex = m.get("textures", {})
    for e in m.get("elements", []) or []:
        for f, face in (e.get("faces") or {}).items():
            ref = face.get("texture", "")
            if ref.startswith("#") and ref[1:] not in tex:
                r.fail(where, f"face {f} of '{e.get('name')}' uses {ref} which is not in textures")
    for k, ref in tex.items():
        if isinstance(ref, str) and not ref.startswith("#") and ":" not in ref:
            r.fail(where, f"texture '{k}': '{ref}' has no namespace — run mod_check.py --fix (or set {modid or '<modid>'}:block/{ref})")
    if "particle" not in tex and m.get("elements"):
        r.look(where, "no 'particle' texture (breaking particles will be missing)")
    if not any(i[1] == where and i[0] == "FAIL" for i in r.items):
        r.ok(where, f"{len(m.get('elements') or [])} elements OK")


def check_bbmodel(p: Path, r: Report):
    m = json.loads(p.read_text(encoding="utf-8"))
    where = p.name
    fmt = (m.get("meta") or {}).get("model_format")
    res = m.get("resolution", {})
    if fmt == "java_block":
        check_elements(m.get("elements"), where, r)
    for t in m.get("textures", []):
        if not t.get("source") and not t.get("path"):
            r.fail(where, f"texture '{t.get('name')}' has no image data or path")
        w, h = t.get("width") or res.get("width"), t.get("height") or res.get("height")
        if w and h and (w % 16 or h % 16):
            r.look(where, f"texture '{t.get('name')}' is {w}x{h}, not a multiple of 16")
    if fmt in ("geckolib_model", "modded_entity", "bedrock"):
        names = []

        def walk(nodes):
            for n in nodes:
                if isinstance(n, dict):
                    names.append(n.get("name"))
                    walk(n.get("children", []))
        walk(m.get("outliner", []))
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            r.fail(where, f"duplicate bone names {sorted(dup)} (animations target bones by name)")
    if not any(i[1] == where and i[0] == "FAIL" for i in r.items):
        r.ok(where, f"{fmt}, {len(m.get('elements', []))} elements, {len(m.get('textures', []))} textures")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--modid")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    t = Path(a.target)
    files = [t] if t.is_file() else sorted(list(t.rglob("*.bbmodel")) + list(t.rglob("models/**/*.json")))
    r = Report(f"blockbench check {t.name}")
    for f in files:
        try:
            (check_bbmodel if f.suffix == ".bbmodel" else check_json_model)(f, *([] if f.suffix == ".bbmodel" else [a.modid]), r)
        except (ValueError, KeyError) as e:
            r.fail(f.name, f"unreadable: {e}")
    if not files:
        r.look(str(t), "no .bbmodel or model json found")
    r.print(quiet_pass=not a.verbose)
    sys.exit(r.exit_code())


if __name__ == "__main__":
    main()
