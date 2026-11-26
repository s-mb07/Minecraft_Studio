#!/usr/bin/env python3
"""Copy / adapt a reference asset or class into the target mod, and log the provenance.

  reuse_apply.py <ref-id> (--asset <path> | --class <Name>) --target <path-in-mod> --transform <t>
                 [--root .] [--color "#a050ff"] [--size 32] [--rename old=new ...] [--package com.x.y]
                 [--directive "user words"]

transforms: copy, copy_and_rename, recolour, resize, edit_model, adapt_code, port_code, extract_pattern,
            convert_format (.bbmodel -> Java block model json)
--asset is a path inside the reference (substring match: "textures/block/cog.png"); --target is relative to --root.
Namespaces <refmodid>: are rewritten to the target modid in JSON and code. An existing target is backed up to
.studio-backup/<time>/ first. Every action is appended to studio/reuse-log.jsonl (and the reference's log).
adapt_code / port_code copy and rename only: Claude then ports the API calls and builds.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402
import _ref  # noqa: E402

TRANSFORMS = ["copy", "copy_and_rename", "recolour", "resize", "edit_model", "adapt_code", "port_code",
              "extract_pattern", "convert_format"]


def target_modid(root: Path) -> str | None:
    from mod_check import find_modid
    return find_modid(root)[0]


def target_package(root: Path) -> str | None:
    for p in sorted((root / "src/main/java").rglob("*.java")) if (root / "src/main/java").exists() else []:
        m = re.search(r"^package\s+([\w.]+);", p.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return None


def find_src(ref: Path, asset: str | None, cls: str | None) -> Path:
    if cls:
        hits = [c for c in _ref.load_index(ref)["classes"] if c["name"] == cls or f"{c['pkg']}.{c['name']}" == cls]
        if not hits:
            raise SystemExit(f"error: class {cls} not in reference index")
        return ref / hits[0]["file"]
    cands = []
    for base in _ref.res_roots(ref) + [ref / "source", ref]:
        if base.exists():
            exact = base / asset
            if exact.is_file():
                return exact
            cands += [p for p in base.rglob("*") if p.is_file() and asset in p.as_posix()]
    if not cands:
        raise SystemExit(f"error: asset {asset} not found in reference")
    return sorted(cands, key=lambda p: len(p.as_posix()))[0]


def backup(root: Path, tgt: Path):
    if tgt.exists():
        b = root / ".studio-backup" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S") / tgt.relative_to(root)
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tgt, b)
        return b.relative_to(root).as_posix()
    return None


def rewrite_text(t: str, ns_from: str | None, ns_to: str | None, renames: list[tuple[str, str]]) -> str:
    if ns_from and ns_to and ns_from != ns_to:
        t = re.sub(rf"\b{re.escape(ns_from)}:", f"{ns_to}:", t)
        t = re.sub(rf'"{re.escape(ns_from)}"', f'"{ns_to}"', t)
    for a, b in renames:
        t = t.replace(a, b)
    return t


def bbmodel_to_java(j: dict, ns: str, name: str) -> dict:
    tex = {str(i): f"{ns}:block/{Path(t.get('name', name)).stem}" for i, t in enumerate(j.get("textures", []))}
    els = []
    for e in j.get("elements", []):
        if e.get("type", "cube") != "cube":
            continue
        el = {"from": e["from"], "to": e["to"], "faces": {}}
        if any(e.get("rotation", [0, 0, 0])):
            ax = max(range(3), key=lambda i: abs(e["rotation"][i]))
            el["rotation"] = {"angle": e["rotation"][ax], "axis": "xyz"[ax], "origin": e.get("origin", [8, 8, 8])}
        for f, d in e.get("faces", {}).items():
            if d.get("texture") is not None:
                el["faces"][f] = {"uv": d.get("uv", [0, 0, 16, 16]), "texture": f"#{d['texture']}"}
        els.append(el)
    if tex:
        tex["particle"] = tex["0"]
    return {"parent": "block/block", "textures": tex, "elements": els}


def pattern_note(src: Path, ref_id: str) -> str:
    t = src.read_text(encoding="utf-8", errors="replace")
    c = _ref.index_file(src, src.parent) or {}
    sig = re.findall(r"^\s*((?:public|protected|private)[^=;{]*\([^)]*\))\s*\{", t, re.M)
    return (f"# Pattern: {c.get('name', src.stem)} (from reference {ref_id})\n\n"
            f"- kind: {c.get('kind')} extends {c.get('extends') or '-'} implements {c.get('implements') or '-'}\n"
            f"- systems: {', '.join(c.get('systems', []))}\n- persisted (NBT): {', '.join(c.get('nbt', [])) or '-'}\n"
            f"- events: {', '.join(c.get('events', [])) or '-'}\n\n## Signatures\n```java\n" + "\n".join(sig[:40]) + "\n```\n")


def apply(root: Path, ref_id: str, asset: str | None, cls: str | None, target: str, transform: str,
          color: str | None = None, size: int | None = None, renames=(), package: str | None = None,
          directive: str | None = None) -> dict:
    ref = _ref.need(root, ref_id)
    src = find_src(ref, asset, cls)
    m = _ref.meta(ref)
    ns_from, ns_to = m.get("modid"), target_modid(root)
    tgt = root / target
    if transform == "extract_pattern" and tgt.suffix != ".md":
        tgt = root / "studio" / "patterns" / f"{src.stem}.md"
    bk = backup(root, tgt)
    tgt.parent.mkdir(parents=True, exist_ok=True)
    renames = list(renames)
    if transform in ("recolour", "resize"):
        img = _png.load(src)
        if transform == "recolour":
            if not color:
                raise SystemExit("error: --color needed for recolour")
            from texture import hex2rgb, recolor
            img = recolor(img, hex2rgb(color))
        else:
            n = size or img.w * 2
            out = _png.Image(n, n * img.h // img.w)
            for y in range(out.h):
                for x in range(out.w):
                    out.set(x, y, img.get(x * img.w // out.w, y * img.h // out.h))
            img = out
        img.save(tgt)
    elif transform == "convert_format":
        if src.suffix != ".bbmodel":
            raise SystemExit("error: convert_format supports .bbmodel -> java json")
        j = json.loads(src.read_text(encoding="utf-8"))
        tgt.write_text(json.dumps(bbmodel_to_java(j, ns_to or "minecraft", tgt.stem), indent=2) + "\n", encoding="utf-8")
    elif transform == "extract_pattern":
        tgt.write_text(pattern_note(src, ref_id), encoding="utf-8")
    elif transform == "copy" or src.suffix not in (".json", ".java", ".mcmeta", ".txt", ".toml", ".fsh", ".vsh", ".glsl"):
        shutil.copy2(src, tgt)
    else:
        t = src.read_text(encoding="utf-8", errors="replace")
        if src.suffix == ".java":
            pkg = package or target_package(root)
            if pkg:
                t = re.sub(r"^package\s+[\w.]+;", f"package {pkg};", t, count=1, flags=re.M)
            if tgt.stem != src.stem:
                renames.append((src.stem, tgt.stem))
            lic = m.get("licence", "unknown")
            t = f"// {'Ported' if transform == 'port_code' else 'Adapted'} from {m.get('source')} ({src.stem}), licence: {lic}\n" + t
        t = rewrite_text(t, ns_from, ns_to, renames)
        tgt.write_text(t, encoding="utf-8")
    entry = {"action": transform, "source": src.relative_to(root).as_posix() if src.is_relative_to(root) else str(src),
             "target": tgt.relative_to(root).as_posix(), "transform": transform + (f" {color}" if color else "")
             + (f" {size}px" if size else ""), "licence": m.get("licence", "unknown"),
             "user_directive": directive or "", "backup": bk}
    _ref.log_reuse(root, ref_id, entry)
    return entry


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--asset"); g.add_argument("--class", dest="cls")
    ap.add_argument("--target", required=True); ap.add_argument("--transform", required=True, choices=TRANSFORMS)
    ap.add_argument("--root", default="."); ap.add_argument("--color"); ap.add_argument("--size", type=int)
    ap.add_argument("--rename", action="append", default=[]); ap.add_argument("--package")
    ap.add_argument("--directive")
    a = ap.parse_args()
    ren = [tuple(r.split("=", 1)) for r in a.rename if "=" in r]
    e = apply(Path(a.root), a.id, a.asset, a.cls, a.target, a.transform, a.color, a.size, ren, a.package, a.directive)
    print(f"REUSED {e['action']}: {e['source']} -> {e['target']} · licence {e['licence']}"
          + (f" · backup {e['backup']}" if e["backup"] else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
