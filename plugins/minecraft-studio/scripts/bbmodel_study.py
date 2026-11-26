#!/usr/bin/env python3
"""Quality profile of entity models: .bbmodel, or .geo.json (+ .animation.json + .png next to it).

  bbmodel_study.py <file|folder>... [--profile out.json] [--against profile.json] [--json]

Measures (all computed, no GUI):
  structure   cubes, bones, hierarchy depth, roots, orphan cubes, inflate use, mirror error of left/right pairs
  density     texture pixels per model unit, per face (box UV = uniform); spread = share of faces off the median by >15%
  texture     size, colours, shades per hue ramp (median/max), alpha
  animation   names, lengths, loop, keyframes, easings, Molang use, coverage of idle/walk/attack/hurt/death, errors
Gates: density spread >15% LOOK, >50% FAIL; >5 shades in a ramp LOOK; missing idle/walk LOOK; orphan cubes LOOK;
bad keyframes FAIL. --profile writes the medians of a reference set; --against compares a model to it.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402

STANDARD = ["idle", "walk", "attack", "hurt", "death"]
FACE_DIMS = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2)}


def ramps(img) -> dict:
    """Shades per hue ramp: opaque colours grouped in 12 hue bins (+ greys), counting colours with >=0.5% share."""
    px = Counter(img.get(x, y)[:3] for y in range(img.h) for x in range(img.w) if img.get(x, y)[3] > 0)
    total = sum(px.values()) or 1
    bins: dict[str, int] = Counter()
    for (r, g, b), n in px.items():
        if n / total < 0.005:
            continue
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        bins["grey" if s < 0.15 or l < 0.06 else f"h{int(h * 12) % 12}"] += 1
    sizes = sorted(bins.values()) or [0]
    alphas = {img.get(x, y)[3] for y in range(img.h) for x in range(img.w)}
    return {"colors": len(px), "ramps": len(bins), "shades_median": st.median(sizes), "shades_max": max(sizes),
            "alpha": "opaque" if alphas == {255} else "cutout" if alphas <= {0, 255} else "translucent"}


# ---------------------------------------------------------------- loaders -> common form
def from_bbmodel(j: dict) -> dict:
    res = j.get("resolution", {"width": 16, "height": 16})
    tex = []
    for t in j.get("textures", []):
        tw, th = t.get("width") or 0, t.get("height") or 0
        img = None
        if str(t.get("source", "")).startswith("data:image/png"):
            try:
                img = _png.loads(t["source"].encode())
                tw, th = img.w, img.h
            except Exception:  # noqa: BLE001
                img = None
        tex.append({"w": tw, "h": th, "uvw": t.get("uv_width") or res["width"], "uvh": t.get("uv_height") or res["height"], "img": img})
    box_default = j.get("meta", {}).get("box_uv", False)
    cubes = []
    for e in j.get("elements", []):
        if e.get("type", "cube") != "cube":
            continue
        cubes.append({"name": e.get("name", ""), "uuid": e.get("uuid"), "from": e["from"], "to": e["to"],
                      "inflate": e.get("inflate", 0), "box": e.get("box_uv", box_default), "faces": e.get("faces", {})})
    groups = {g["uuid"]: g for g in j.get("groups", []) if isinstance(g, dict) and "uuid" in g}

    def walk(node, depth):
        if isinstance(node, str):
            return depth - 1, 0
        best, n = depth, 1
        for c in node.get("children", []):
            d, k = walk(c, depth + 1)
            best, n = max(best, d), n + k
        return best, n
    outl = j.get("outliner", [])
    depth = max((walk(n, 1)[0] for n in outl if not isinstance(n, str)), default=0)
    bones = sum(walk(n, 1)[1] for n in outl if not isinstance(n, str))
    names = [g.get("name", "") for g in groups.values()] or \
        [n.get("name", "") for n in outl if isinstance(n, dict)]
    anims = []
    for a in j.get("animations", []):
        kfs = []
        for an in (a.get("animators") or {}).values():
            for k in an.get("keyframes", []):
                vals = [v for dp in k.get("data_points", []) for v in dp.values()] if k.get("data_points") else []
                kfs.append({"time": k.get("time", 0), "easing": k.get("easing") or k.get("interpolation", "linear"),
                            "vals": vals, "bone": an.get("name")})
        anims.append({"name": a.get("name", ""), "length": a.get("length", 0), "loop": a.get("loop", "once"),
                      "bones": len(a.get("animators") or {}), "kfs": kfs})
    return {"format": j.get("meta", {}).get("model_format"), "cubes": cubes, "bones": bones, "depth": depth,
            "roots": sum(1 for n in outl if not isinstance(n, str)), "orphans": sum(1 for n in outl if isinstance(n, str)),
            "bone_names": names, "textures": tex, "anims": anims}


def from_geo(p: Path) -> dict:
    j = json.loads(p.read_text(encoding="utf-8"))
    g = j["minecraft:geometry"][0]
    d = g.get("description", {})
    tw, th = d.get("texture_width", 16), d.get("texture_height", 16)
    bones = g.get("bones", [])
    parent = {b["name"]: b.get("parent") for b in bones}

    def depth(n):
        k = 1
        while parent.get(n):
            n, k = parent[n], k + 1
        return k
    cubes = [{"name": b["name"], "from": c["origin"], "to": [c["origin"][i] + c["size"][i] for i in range(3)],
              "inflate": c.get("inflate", 0), "box": isinstance(c.get("uv"), list), "faces": c.get("uv") if isinstance(c.get("uv"), dict) else {}}
             for b in bones for c in b.get("cubes", [])]
    stem = p.name[:-len(".geo.json")]
    img = None
    for cand in [p.parent / f"{stem}.png", p.parent.parent.parent / "textures/entity" / f"{stem}.png"]:
        if cand.exists():
            img = _png.load(cand); break
    tex = [{"w": img.w if img else tw, "h": img.h if img else th, "uvw": tw, "uvh": th, "img": img}]
    anims = []
    for cand in [p.parent / f"{stem}.animation.json", p.parent.parent / "animations" / f"{stem}.animation.json",
                 p.parent.parent.parent / "animations" / f"{stem}.animation.json",
                 p.parent.parent.parent / "animations/entity" / f"{stem}.animation.json"]:
        if cand.exists():
            for name, a in json.loads(cand.read_text(encoding="utf-8")).get("animations", {}).items():
                kfs = []
                for bone, chans in a.get("bones", {}).items():
                    for ch in chans.values():
                        items = ch.items() if isinstance(ch, dict) and not {"vector", "easing"} & set(ch) else [("0", ch)]
                        for t, v in items:
                            vec = v.get("vector") if isinstance(v, dict) else v
                            kfs.append({"time": float(t), "easing": v.get("easing", "linear") if isinstance(v, dict) else "linear",
                                        "vals": vec if isinstance(vec, list) else [vec], "bone": bone})
                anims.append({"name": name, "length": a.get("animation_length", 0), "loop": a.get("loop", False),
                              "bones": len(a.get("bones", {})), "kfs": kfs})
            break
    return {"format": "geckolib geo", "cubes": cubes, "bones": len(bones), "depth": max((depth(b["name"]) for b in bones), default=0),
            "roots": sum(1 for b in bones if not b.get("parent")), "orphans": 0, "bone_names": [b["name"] for b in bones],
            "textures": tex, "anims": anims}


# ---------------------------------------------------------------- metrics
def density(m: dict) -> list[float]:
    out = []
    t0 = m["textures"][0] if m["textures"] else {"w": 16, "uvw": 16}
    scale = (t0["w"] / t0["uvw"]) if t0.get("uvw") else 1
    for c in m["cubes"]:
        size = [abs(c["to"][i] - c["from"][i]) for i in range(3)]
        if c["box"]:
            out.append(scale)
            continue
        for f, d in (c["faces"] or {}).items():
            uv = d.get("uv") if isinstance(d, dict) else None
            if not uv or f not in FACE_DIMS or d.get("texture") is None and "texture" in d:
                continue
            a, b = FACE_DIMS[f]
            fw, fh = size[a], size[b]
            uw, uh = (abs(uv[2] - uv[0]), abs(uv[3] - uv[1])) if len(uv) == 4 else (abs(d.get("uv_size", [0, 0])[0]), abs(d.get("uv_size", [0, 0])[1]))
            for u, s in ((uw, fw), (uh, fh)):
                if s >= 1 and u > 0:
                    out.append(u / s * scale)
    return out


def mirror_error(m: dict) -> float | None:
    by = {c["name"].lower(): c for c in m["cubes"]}
    errs = []
    for n, c in by.items():
        for a, b in (("left", "right"), ("_l", "_r"), ("l_", "r_")):
            if a in n:
                o = by.get(n.replace(a, b))
                if o:
                    errs.append(abs((c["from"][0] + c["to"][0]) + (o["from"][0] + o["to"][0])) / 2
                                + sum(abs(abs(c["to"][i] - c["from"][i]) - abs(o["to"][i] - o["from"][i])) for i in range(3)))
    return round(max(errs), 3) if errs else None


def study(m: dict) -> dict:
    dens = density(m)
    med = st.median(dens) if dens else 0
    spread = (sum(1 for d in dens if med and abs(d - med) / med > 0.15) / len(dens)) if dens else 0
    tex = [ramps(t["img"]) | {"size": f"{t['w']}x{t['h']}"} for t in m["textures"] if t.get("img")]
    names = [a["name"].lower() for a in m["anims"]]
    cover = [s for s in STANDARD if any(s in n for n in names)]
    bad, molang, easings = [], 0, Counter()
    for a in m["anims"]:
        for k in a["kfs"]:
            easings[str(k["easing"])] += 1
            for v in k["vals"]:
                if isinstance(v, str) and re.search(r"[a-z]", v.replace("e", "")):
                    molang += 1
                elif isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
                    bad.append(f"{a['name']}: NaN")
            if a["length"] and k["time"] > a["length"] + 1e-3:
                bad.append(f"{a['name']}: keyframe at {k['time']} > length {a['length']}")
    return {
        "format": m["format"], "cubes": len(m["cubes"]), "bones": m["bones"], "depth": m["depth"], "roots": m["roots"],
        "orphans": m["orphans"], "inflated": sum(1 for c in m["cubes"] if c["inflate"]),
        "density_px_per_unit": round(med, 2), "density_spread": round(spread, 2), "mirror_error": mirror_error(m),
        "textures": tex, "animations": [f"{a['name']} {a['length']}s {a['bones']}b {len(a['kfs'])}k" for a in m["anims"]],
        "anim_count": len(m["anims"]), "coverage": cover,
        "keyframes_per_bone": round(st.median([len(a["kfs"]) / a["bones"] for a in m["anims"] if a["bones"]]), 1) if m["anims"] else 0,
        "easings": dict(easings.most_common(4)), "molang_values": molang, "errors": bad[:5],
    }


def gates(s: dict) -> list[tuple[str, str]]:
    g = []
    if s["density_spread"] > 0.5:
        g.append(("FAIL", f"mixed texel density ({int(s['density_spread'] * 100)}% of faces off the median)"))
    elif s["density_spread"] > 0.15:
        g.append(("LOOK", f"texel density spread {int(s['density_spread'] * 100)}%"))
    for t in s["textures"]:
        if t["shades_max"] > 5:
            g.append(("LOOK", f"texture {t['size']}: a ramp has {t['shades_max']} shades (aim <= 4-5)"))
    if s["orphans"]:
        g.append(("LOOK", f"{s['orphans']} cubes outside any bone"))
    if s["roots"] > 1:
        g.append(("LOOK", f"{s['roots']} root bones (aim 1)"))
    if s["depth"] > 6:
        g.append(("LOOK", f"hierarchy depth {s['depth']} (> 6)"))
    if s["mirror_error"] and s["mirror_error"] > 0.01:
        g.append(("LOOK", f"left/right mirror error {s['mirror_error']}"))
    for need in ("idle", "walk"):
        if need not in s["coverage"]:
            g.append(("LOOK", f"no {need} animation"))
    g += [("FAIL", e) for e in s["errors"]]
    return g


def score(s: dict) -> int:
    pts = 100
    pts -= min(30, int(s["density_spread"] * 60))
    pts -= 5 * sum(1 for t in s["textures"] if t["shades_max"] > 5)
    pts -= 10 * (s["orphans"] > 0) + 5 * (s["roots"] > 1) + 5 * (s["depth"] > 6)
    pts -= 4 * (len(STANDARD) - len(s["coverage"]))
    pts -= 15 * bool(s["errors"])
    return max(0, pts)


def load(p: Path) -> dict:
    if p.name.endswith(".geo.json"):
        return from_geo(p)
    return from_bbmodel(json.loads(p.read_text(encoding="utf-8")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+"); ap.add_argument("--profile"); ap.add_argument("--against")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    files = []
    for p in map(Path, a.paths):
        files += sorted(list(p.rglob("*.bbmodel")) + list(p.rglob("*.geo.json"))) if p.is_dir() else [p]
    results = {}
    worst = 0
    for f in files:
        s = study(load(f)); s["score"] = score(s); g = gates(s)
        results[f.name] = s
        if a.json:
            continue
        t = s["textures"][0] if s["textures"] else {}
        print(f"{f.name}: score {s['score']} · {s['cubes']} cubes {s['bones']} bones d{s['depth']} · "
              f"{s['density_px_per_unit']} px/u (spread {int(s['density_spread'] * 100)}%) · "
              f"tex {t.get('size', '-')} {t.get('colors', '-')} col, {t.get('ramps', '-')} ramps x{t.get('shades_median', '-')} · "
              f"anims {s['anim_count']} [{','.join(s['coverage'])}] {s['keyframes_per_bone']} k/bone")
        for lvl, msg in g:
            print(f"  [{lvl}] {msg}")
            worst = max(worst, 2 if lvl == "FAIL" else 1)
    if a.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    if a.profile:
        num = lambda k: round(st.median([r[k] for r in results.values() if isinstance(r[k], (int, float))]), 2)  # noqa: E731
        prof = {"models": len(results), **{k: num(k) for k in ("cubes", "bones", "depth", "density_spread", "anim_count",
                                                                  "keyframes_per_bone", "score")},
                "shades_median": round(st.median([t["shades_median"] for r in results.values() for t in r["textures"]] or [0]), 1),
                "colors_median": round(st.median([t["colors"] for r in results.values() for t in r["textures"]] or [0])),
                "coverage": dict(Counter(c for r in results.values() for c in r["coverage"]))}
        Path(a.profile).write_text(json.dumps(prof, indent=2) + "\n", encoding="utf-8")
        print(f"profile -> {a.profile}: {prof}")
    if a.against:
        prof = json.loads(Path(a.against).read_text(encoding="utf-8"))
        for name, s in results.items():
            verdict = "PASS" if s["score"] >= prof["score"] else "LOOK"
            print(f"{verdict}: {name} score {s['score']} vs reference median {prof['score']}")
    sys.exit(1 if worst == 2 else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
