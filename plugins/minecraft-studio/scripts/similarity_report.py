#!/usr/bin/env python3
"""How close is the target mod to a reference? Informational, never blocking.

  similarity_report.py --target <mod-root> --reference <ref-id> [--json]

Compares ids/names, textures (identical pixels, recolours = same alpha mask), models (element boxes),
classes (same names + reuse log) and systems. Output: SIMILARITY low|medium|high + counts + licence + provenance.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402
import _ref  # noqa: E402


def res_files(bases: list[Path], sub: str, suffix: str) -> list[Path]:
    return [p for b in bases if (b / "assets").exists() for p in (b / "assets").rglob(f"*{suffix}") if f"/{sub}/" in p.as_posix()]


def tex_sig(p: Path):
    try:
        img = _png.load(p)
    except Exception:  # noqa: BLE001
        return None
    raw = bytes(v for px in img.px for v in px)
    mask = bytes(1 if px[3] > 0 else 0 for px in img.px)
    return (img.w, img.h), hashlib.sha1(raw).hexdigest(), hashlib.sha1(mask).hexdigest()


def model_sig(p: Path):
    try:
        j = json.loads(p.read_text(encoding="utf-8", errors="replace"), strict=False)
    except ValueError:
        return None
    els = j.get("elements") or []
    return tuple(sorted(tuple(e.get("from", []) + e.get("to", [])) for e in els)) if els else None


def report(target: Path, ref_id: str) -> dict:
    ref = _ref.need(target, ref_id)
    rb, tb = _ref.res_roots(ref), [target / "src/main/resources"]
    out = {"ids_same": [], "ids_close": [], "textures_identical": [], "textures_recolour": [], "models_identical": [],
           "classes_same_name": [], "reused": 0, "systems_shared": []}
    names = lambda bases: {p.stem for p in res_files(bases, "models", ".json")}  # noqa: E731
    rn, tn = names(rb), names(tb)
    out["ids_same"] = sorted(rn & tn)
    out["ids_close"] = sorted(f"{t}~{difflib.get_close_matches(t, list(rn - tn), 1, 0.85)[0]}"
                              for t in tn - rn if difflib.get_close_matches(t, list(rn - tn), 1, 0.85))[:20]
    rsig = {}
    for p in res_files(rb, "textures", ".png"):
        s = tex_sig(p)
        if s:
            rsig.setdefault((s[0], s[1]), p); rsig.setdefault((s[0], "m" + s[2]), p)
    for p in res_files(tb, "textures", ".png"):
        s = tex_sig(p)
        if not s:
            continue
        if (s[0], s[1]) in rsig:
            out["textures_identical"].append(p.name)
        elif (s[0], "m" + s[2]) in rsig and s[0][0] * s[0][1] >= 64:
            out["textures_recolour"].append(f"{p.name}~{rsig[(s[0], 'm' + s[2])].name}")
    rm = {model_sig(p): p.name for p in res_files(rb, "models", ".json")}
    rm.pop(None, None)
    out["models_identical"] = [f"{p.name}~{rm[s]}" for p in res_files(tb, "models", ".json") if (s := model_sig(p)) in rm]
    idx = _ref.load_index(ref)
    tcls = {p.stem for p in (target / "src").rglob("*.java")} if (target / "src").exists() else set()
    out["classes_same_name"] = sorted(tcls & {c["name"] for c in idx["classes"]})
    log = [e for e in _ref.read_log(target / "studio/reuse-log.jsonl") if e.get("reference") == ref_id]
    out["reused"] = len(log)
    out["reused_by_kind"] = {}
    for e in log:
        k = "class" if e["target"].endswith(".java") else "texture" if e["target"].endswith(".png") else \
            "model" if "/models/" in e["target"] else "other"
        out["reused_by_kind"][k] = out["reused_by_kind"].get(k, 0) + 1
    tidx = {"classes": [c for c in (_ref.index_file(p, target) for p in (target / "src").rglob("*.java")) if c]} \
        if (target / "src").exists() else {"classes": []}
    ts = {s for c in tidx["classes"] for s in c["systems"]}
    out["systems_shared"] = sorted(ts & {k for k, v in idx["systems"].items() if v})
    direct = len(out["textures_identical"]) + len(out["models_identical"]) + len(out["classes_same_name"])
    near = len(out["textures_recolour"]) + len(out["ids_same"]) + len(out["ids_close"])
    out["similarity"] = "high" if direct >= 5 or out["reused"] >= 5 else "medium" if direct or near or out["reused"] else "low"
    m = _ref.meta(ref)
    out["licence"] = m.get("licence", "unknown")
    out["provenance"] = "studio/reuse-log.jsonl" if log else "none logged"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default="."); ap.add_argument("--reference", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = report(Path(a.target), a.reference)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False)); return
    kinds = ", ".join(f"{v} {k}{'s' if v > 1 else ''}" for k, v in r["reused_by_kind"].items()) or "nothing"
    print(f"SIMILARITY: {r['similarity']}")
    print(f"REUSED: {kinds} · identical textures {len(r['textures_identical'])} · recolours {len(r['textures_recolour'])}"
          f" · identical models {len(r['models_identical'])} · same-name classes {len(r['classes_same_name'])}"
          f" · same ids {len(r['ids_same'])}")
    if r["systems_shared"]:
        print(f"SHARED SYSTEMS: {', '.join(r['systems_shared'])}")
    print(f"LICENCE: {r['licence']}")
    print(f"PROVENANCE: {r['provenance']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
