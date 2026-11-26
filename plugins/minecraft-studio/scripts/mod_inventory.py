#!/usr/bin/env python3
"""Compact inventory of a reference: loader, MC versions, entrypoints, mixins, registries, assets, data.

  mod_inventory.py <ref-id> [--root .] [--json]

Writes analysis/inventory.json. Default output is 3 lines.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import save_json  # noqa: E402
import _ref  # noqa: E402

ASSET_KINDS = {"models": "models", "textures": "textures", "sounds": "sounds", "shaders": "shaders",
               "particles": "particles", "lang": "lang", "blockstates": "blockstates"}
REG_RX = {"items": r'(?:ITEMS\.register\w*|Registries?\.ITEM\s*,\s*[\w.]*\()\s*\(?\s*"([a-z0-9_/]+)"',
          "blocks": r'(?:BLOCKS\.register\w*|Registries?\.BLOCK\s*,\s*[\w.]*\()\s*\(?\s*"([a-z0-9_/]+)"',
          "entities": r'(?:ENTITY_TYPES?\.register\w*|Registries?\.ENTITY_TYPE\s*,\s*[\w.]*\()\s*\(?\s*"([a-z0-9_/]+)"'}


def read_meta(ref: Path) -> dict:
    out = {"loader": None, "modid": None, "version": None, "minecraft": [], "entrypoints": [], "mixin_configs": [],
           "licence_field": None}
    for p in _ref.meta_files(ref):
        t = p.read_text(encoding="utf-8", errors="replace")
        if p.name == "fabric.mod.json":
            try:
                j = json.loads(t, strict=False)
            except ValueError:
                continue
            mc = (j.get("depends") or {}).get("minecraft")
            out.update(loader="fabric", modid=j.get("id"), version=j.get("version"),
                       minecraft=mc if isinstance(mc, list) else [mc] if mc else [],
                       licence_field=j.get("license"))
            out["entrypoints"] = [f"{k}: {v if isinstance(v, str) else v.get('value')}"
                                  for k, vs in (j.get("entrypoints") or {}).items() for v in vs]
            out["mixin_configs"] = [x if isinstance(x, str) else x.get("config") for x in j.get("mixins", [])]
        elif p.name.endswith("mods.toml"):
            out["loader"] = out["loader"] or ("neoforge" if p.name.startswith("neoforge") else "forge")
            g = lambda k: (re.search(rf'^\s*{k}\s*=\s*"([^"]*)"', t, re.M) or [None, None])[1]  # noqa: E731
            out.update(modid=out["modid"] or g("modId"), version=out["version"] or g("version"),
                       licence_field=out["licence_field"] or g("license"))
            mc = re.search(r'modId\s*=\s*"minecraft"[\s\S]*?versionRange\s*=\s*"([^"]+)"', t)
            if mc:
                out["minecraft"] = [mc.group(1)]
            out["mixin_configs"] += re.findall(r'^\s*config\s*=\s*"([^"]+)"', t, re.M)
        elif p.name.endswith(".mixins.json") and p.name not in out["mixin_configs"]:
            out["mixin_configs"].append(p.name)
    return out


def count_res(ref: Path) -> tuple[dict, dict, dict]:
    assets, data, regs = {k: 0 for k in ASSET_KINDS}, {}, {k: set() for k in REG_RX}
    assets.update(gui=0, geo=0, bbmodel=0)
    for base in _ref.res_roots(ref):
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            parts = p.relative_to(base).parts
            if parts[0] == "assets" and len(parts) > 2:
                k = parts[2]
                if k in assets:
                    assets[k] += 1
                if k == "textures" and len(parts) > 3 and parts[3] == "gui":
                    assets["gui"] += 1
                if p.name.endswith(".geo.json"):
                    assets["geo"] += 1
            elif parts[0] == "data" and len(parts) > 2:
                k = parts[2].rstrip("s") if parts[2] in ("recipes", "loot_tables", "structures") else parts[2]
                data[k] = data.get(k, 0) + 1
            if p.suffix == ".bbmodel":
                assets["bbmodel"] += 1
            if p.name == "en_us.json":
                try:
                    for key in json.loads(p.read_text(encoding="utf-8", errors="replace"), strict=False):
                        s = key.split(".")
                        if len(s) == 3 and s[0] in ("item", "block", "entity"):
                            regs[{"item": "items", "block": "blocks", "entity": "entities"}[s[0]]].add(s[2])
                except ValueError:
                    pass
    for f in _ref.java_files(ref):
        t = f.read_text(encoding="utf-8", errors="replace")
        for k, rx in REG_RX.items():
            regs[k].update(re.findall(rx, t))
    return {k: v for k, v in assets.items() if v}, data, {k: len(v) for k, v in regs.items()}


def inventory(ref: Path) -> dict:
    inv = read_meta(ref)
    idx = _ref.load_index(ref)
    inv["assets"], inv["data"], inv["registries"] = count_res(ref)
    inv["mixins"] = sorted({t for c in idx["classes"] for t in c.get("mixin", [])})[:50]
    inv["mixin_classes"] = sum(1 for c in idx["classes"] if c.get("mixin"))
    if not inv["entrypoints"]:
        inv["entrypoints"] = [f"@Mod {c['pkg']}.{c['name']}" for c in idx["classes"] if "Mod" in c.get("annotations", [])][:5]
    inv["classes"] = len(idx["classes"])
    inv["systems"] = {k: v for k, v in idx["systems"].items() if v}
    save_json(ref / "analysis/inventory.json", inv)
    m = _ref.meta(ref)
    m.update(loader=inv["loader"], modid=inv["modid"], version=inv["version"]); _ref.save_meta(ref, m)
    return inv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("--root", default="."); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    inv = inventory(_ref.need(Path(a.root), a.id))
    if a.json:
        print(json.dumps(inv, indent=2, ensure_ascii=False)); return
    fmt = lambda d: ", ".join(f"{k} {v}" for k, v in d.items()) or "-"  # noqa: E731
    print(f"{inv['modid']} {inv['version']} · {inv['loader']} · MC {', '.join(inv['minecraft']) or '?'} · "
          f"{inv['classes']} classes · {inv['mixin_classes']} mixins")
    print(f"  registries: {fmt(inv['registries'])} | systems: {fmt(inv['systems'])}")
    print(f"  assets: {fmt(inv['assets'])} | data: {fmt(inv['data'])}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
