#!/usr/bin/env python3
"""Study a reference's assets: models, textures, sounds, GUI, shaders, VFX.

  asset_study.py <ref-id> --kind model|texture|sound|gui|shader|vfx [filter] [--root .] [--limit 10] [--json]

filter = substring of the path (e.g. "block/cog"). Without a filter: a summary + the first items.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402
import _ref  # noqa: E402


def files(ref: Path, pred) -> list[tuple[str, Path]]:
    out = []
    for base in _ref.res_roots(ref) + ([ref / "source"] if (ref / "source").exists() else []):
        for p in base.rglob("*"):
            rel = p.relative_to(base).as_posix()
            if p.is_file() and pred(rel, p) and "/build/" not in rel:
                out.append((rel, p))
    return list({r: (r, p) for r, p in out}.values())


def palette(img, n=8) -> list[str]:
    c = Counter((r, g, b) for r, g, b, a in (img.get(x, y) for y in range(img.h) for x in range(img.w)) if a > 0)
    return ["#%02x%02x%02x" % k for k, _ in c.most_common(n)]


def study_texture(rel, p) -> dict:
    try:
        img = _png.load(p)
    except Exception as e:  # noqa: BLE001
        return {"path": rel, "error": str(e)}
    alphas = {img.get(x, y)[3] for y in range(img.h) for x in range(img.w)}
    d = {"path": rel, "size": f"{img.w}x{img.h}", "palette": palette(img),
         "colors": len({img.get(x, y) for y in range(img.h) for x in range(img.w)}),
         "alpha": "opaque" if alphas == {255} else "cutout" if alphas <= {0, 255} else "translucent"}
    mc = p.with_name(p.name + ".mcmeta")
    if mc.exists() or (img.h > img.w and img.h % img.w == 0):
        d["animation"] = f"{img.h // img.w} frames" + (" (mcmeta)" if mc.exists() else " (strip?)")
    return d


def study_model(rel, p) -> dict:
    try:
        j = json.loads(p.read_text(encoding="utf-8", errors="replace"), strict=False)
    except ValueError as e:
        return {"path": rel, "error": str(e)[:80]}
    if p.name.endswith(".geo.json") or "minecraft:geometry" in j:
        geo = (j.get("minecraft:geometry") or [{}])[0]
        bones = geo.get("bones", [])
        desc = geo.get("description", {})
        return {"path": rel, "format": "bedrock geo (GeckoLib)", "bones": len(bones),
                "cubes": sum(len(b.get("cubes", [])) for b in bones),
                "texture": f"{desc.get('texture_width')}x{desc.get('texture_height')}",
                "bone_names": [b.get("name") for b in bones][:15]}
    if p.suffix == ".bbmodel":
        return {"path": rel, "format": f"bbmodel {j.get('meta', {}).get('model_format')}",
                "elements": len(j.get("elements", [])), "groups": len(j.get("groups", j.get("outliner", []))),
                "textures": len(j.get("textures", [])), "animations": len(j.get("animations", []))}
    els = j.get("elements", [])
    xs = [v for e in els for v in (e.get("from", []) + e.get("to", []))]
    pattern = ("parent-only" if not els else "full cube" if len(els) == 1 and xs and min(xs) == 0 and max(xs) == 16
               else "multi-part" if len(els) > 8 else "simple shape")
    return {"path": rel, "format": "java " + ("block" if "/block/" in rel else "item" if "/item/" in rel else "model"),
            "parent": j.get("parent"), "elements": len(els), "rotated": sum(1 for e in els if e.get("rotation")),
            "bounds": f"{min(xs):g}..{max(xs):g}" if xs else None, "textures": j.get("textures", {}),
            "display": sorted(j.get("display", {}))[:8], "pattern": pattern}


def study_shader(rel, p) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".json":
        try:
            j = json.loads(t, strict=False)
        except ValueError:
            return {"path": rel}
        return {"path": rel, "vertex": j.get("vertex"), "fragment": j.get("fragment"),
                "samplers": [s.get("name") for s in j.get("samplers", []) if isinstance(s, dict)],
                "uniforms": [u.get("name") for u in j.get("uniforms", []) if isinstance(u, dict)],
                "passes": len(j.get("passes", [])) or None}
    return {"path": rel, "uniforms": re.findall(r"uniform\s+\w+\s+(\w+)", t)[:20],
            "inputs": re.findall(r"\bin\s+\w+\s+(\w+)", t)[:12], "lines": t.count("\n")}


KINDS = {
    "texture": (lambda r, p: "/textures/" in r and p.suffix == ".png", study_texture),
    "model": (lambda r, p: ("/models/" in r and p.suffix == ".json") or r.endswith(".geo.json") or p.suffix == ".bbmodel", study_model),
    "shader": (lambda r, p: "/shaders/" in r or p.suffix in (".vsh", ".fsh", ".glsl"), study_shader),
    "gui": (lambda r, p: "/textures/gui/" in r and p.suffix == ".png", study_texture),
}


def sounds(ref: Path, flt: str | None, limit: int) -> dict:
    ev, oggs = {}, files(ref, lambda r, p: p.suffix == ".ogg")
    for rel, p in files(ref, lambda r, p: r.endswith("sounds.json")):
        try:
            for k, v in json.loads(p.read_text(encoding="utf-8"), strict=False).items():
                if not flt or flt in k:
                    ev[k] = {"sounds": len(v.get("sounds", [])), "subtitle": v.get("subtitle")}
        except ValueError:
            pass
    return {"events": len(ev), "ogg_files": len(oggs), "items": dict(list(ev.items())[:limit])}


def study(ref: Path, kind: str, flt: str | None = None, limit: int = 10) -> dict:
    if kind == "sound":
        return sounds(ref, flt, limit)
    if kind == "vfx":
        idx = _ref.load_index(ref)
        return {"particles": [r for r, _ in files(ref, lambda r, p: "/particles/" in r)][:limit],
                "shaders": len(files(ref, KINDS["shader"][0])), "sounds": sounds(ref, None, 0)["events"],
                "particle_code": [c["file"] for c in idx["classes"] if "particles" in c.get("systems", [])][:limit],
                "render_code": [c["file"] for c in idx["classes"] if "render" in c.get("systems", [])][:limit]}
    pred, fn = KINDS[kind]
    fs = [(r, p) for r, p in files(ref, pred) if not flt or flt in r]
    out = {"count": len(fs), "items": [fn(r, p) for r, p in fs[:limit]]}
    if kind == "texture":
        out["sizes"] = dict(Counter(i.get("size") for i in out["items"]))
    if kind == "gui":
        idx = _ref.load_index(ref)
        out["screens"] = [c["name"] for c in idx["classes"] if "gui" in c.get("systems", [])][:limit]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("filter", nargs="?")
    ap.add_argument("--kind", required=True, choices=["model", "texture", "sound", "gui", "shader", "vfx"])
    ap.add_argument("--root", default="."); ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = study(_ref.need(Path(a.root), a.id), a.kind, a.filter, a.limit)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False)); return
    for k, v in r.items():
        if k == "items":
            for it in (v.values() if isinstance(v, dict) else v):
                print("  - " + " · ".join(f"{x}={y}" for x, y in it.items() if y not in (None, [], {})))
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
