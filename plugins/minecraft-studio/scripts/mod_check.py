#!/usr/bin/env python3
"""Static consistency check for a Fabric / NeoForge mod source tree. Run before every build.

  mod_check.py <mod-folder> [--fix] [--verbose] [--json]

Finds registered ids in Java (Registry.register / DeferredRegister calls) and checks that each has:
  blocks: blockstate, block model, item model (block item), lang key, loot table (LOOK if missing)
  items:  item model, lang key
  models: every own-namespace texture exists; parent models exist
  recipes / loot: own-namespace item ids are registered
  metadata: modid in fabric.mod.json / gradle.properties == MOD_ID in Java; mixin classes exist
Plus validate.py on src/main/resources (JSON, pack.mcmeta, lowercase paths, PNGs).

--fix repairs what is mechanical (never deletes anything):
  - model texture refs without namespace ("crystal" from a Blockbench export) -> "<modid>:block/crystal"
  - missing lang keys -> Title Case name
  - missing item model for a block item -> {"parent": "<modid>:block/<id>"}
Output is short by default (FAIL/LOOK only); --verbose shows PASS lines.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402
from _common import Report  # noqa: E402

BLOCK_RX = [r'BLOCKS\.register\w*\(\s*"([a-z0-9_/.]+)"', r'Registries?\.BLOCK\s*,\s*\w*\.?id\(\s*"([a-z0-9_/.]+)"',
            r'ModBlocks\.\w*\s*=\s*register\w*\(\s*"([a-z0-9_/.]+)"']
ITEM_RX = [r'ITEMS\.register(?!SimpleBlockItem)\w*\(\s*"([a-z0-9_/.]+)"', r'Registries?\.ITEM\s*,\s*\w*\.?id\(\s*"([a-z0-9_/.]+)"']
BLOCK_ITEM_RX = r'registerSimpleBlockItem\(\s*(?:ModBlocks\.)?(\w+)'


def title(s):
    return " ".join(w.capitalize() for w in s.replace("/", " ").split("_"))


def find_modid(root: Path):
    fmj = root / "src/main/resources/fabric.mod.json"
    if fmj.exists():
        return json.loads(fmj.read_text(encoding="utf-8"))["id"], "fabric"
    gp = root / "gradle.properties"
    if gp.exists():
        m = re.search(r"^mod_id=(\S+)", gp.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1), "neoforge"
    return None, None


def scan_ids(root: Path, modid: str, r: Report):
    blocks, items, consts = {}, {}, {}
    java = [p for d in ("src/main/java", "src/client/java") for p in (root / d).rglob("*.java")]
    texts = {p: p.read_text(encoding="utf-8", errors="ignore") for p in java}
    reg_rx = re.compile(r'\bregister\w*\(\s*"([a-z0-9_/.]+)"')
    for p, t in texts.items():
        file_kind = "block" if re.search(r"Registries\.BLOCK\b|createBlocks|DeferredRegister\.Blocks", t) else \
            "item" if re.search(r"Registries\.ITEM\b|createItems|DeferredRegister\.Items", t) else None
        for line_no, line in enumerate(t.splitlines(), 1):
            where = f"{p.relative_to(root).as_posix()}:{line_no}"
            hit = False
            for rx in BLOCK_RX:
                for m in re.finditer(rx, line):
                    blocks[m.group(1)] = where
                    hit = True
            for rx in ITEM_RX:
                for m in re.finditer(rx, line):
                    items[m.group(1)] = where
                    hit = True
            if not hit and file_kind and "static" in line:
                for m in reg_rx.finditer(line):
                    (blocks if file_kind == "block" else items)[m.group(1)] = where
            for bid in [b for b, w in blocks.items() if w == where]:
                c = re.search(r"(\w+)\s*=", line)
                if c:
                    consts[c.group(1)] = bid
    # Fabric helper register(name, block) also registers the block item; NeoForge needs registerSimpleBlockItem
    for t in texts.values():
        for m in re.finditer(BLOCK_ITEM_RX, t):
            bid = consts.get(m.group(1))
            if bid:
                items.setdefault(bid, blocks.get(bid))
    fabric_helper = any("new BlockItem(block" in t for t in texts.values())
    if fabric_helper:
        for b, w in blocks.items():
            items.setdefault(b, w)
    mods = [re.search(r'MOD_?ID\s*=\s*"([^"]+)"', t) for t in texts.values()]
    java_ids = {m.group(1) for m in mods if m}
    if java_ids and modid not in java_ids:
        r.fail("metadata", f"MOD_ID in Java {sorted(java_ids)} != modid '{modid}' in metadata")
    return blocks, items


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None  # validate.py reports parse errors


def res_path(res: Path, ref: str, kind: str, default_ns: str) -> Path:
    ns, _, path = ref.partition(":") if ":" in ref else (default_ns, "", ref)
    base = res / "assets" / ns
    return base / ("textures" if kind == "texture" else "models") / f"{path}.{'png' if kind == 'texture' else 'json'}"


def check(root: Path, fix: bool) -> Report:
    r = Report(f"mod check {root.name}")
    modid, loader = find_modid(root)
    if not modid:
        r.fail("metadata", "no fabric.mod.json or gradle.properties mod_id found")
        return r
    res = root / "src/main/resources"
    gen = root / "src/generated/resources"  # NeoForge datagen output
    roots = [res] + ([gen] if gen.exists() else [])
    a = lambda *p: next((x / "assets" / modid / Path(*p) for x in roots if (x / "assets" / modid / Path(*p)).exists()),
                        res / "assets" / modid / Path(*p))
    blocks, items = scan_ids(root, modid, r)
    lang_p = res / "assets" / modid / "lang" / "en_us.json"
    lang = load_json(lang_p) or {}
    for x in roots[1:]:
        lang.update(load_json(x / "assets" / modid / "lang" / "en_us.json") or {})
    lang_added = {}

    for b, where in blocks.items():
        if not a("blockstates", f"{b}.json").exists():
            r.fail(where, f"block '{b}': missing assets/{modid}/blockstates/{b}.json")
        if not a("models", "block", f"{b}.json").exists() and not a("blockstates", f"{b}.json").exists():
            r.fail(where, f"block '{b}': missing block model")
        key = f"block.{modid}.{b}"
        if key not in lang:
            if fix:
                lang_added[key] = title(b)
            else:
                r.fail(where, f"missing lang key {key}")
        lt = [x / "data" / modid / d / "blocks" / f"{b}.json" for x in roots for d in ("loot_table", "loot_tables")]
        if not any(p.exists() for p in lt):
            r.look(where, f"block '{b}' has no loot table (drops nothing)")
    for i, where in items.items():
        im = a("models", "item", f"{i}.json")
        if not im.exists() and not a("items", f"{i}.json").exists():
            if fix and i in blocks:
                im.parent.mkdir(parents=True, exist_ok=True)
                im.write_text(json.dumps({"parent": f"{modid}:block/{i}"}, indent=2) + "\n", encoding="utf-8")
                r.ok(where, f"created item model for block item '{i}'")
            else:
                r.fail(where, f"item '{i}': missing assets/{modid}/models/item/{i}.json")
        if i not in blocks:
            key = f"item.{modid}.{i}"
            if key not in lang:
                if fix:
                    lang_added[key] = title(i)
                else:
                    r.fail(where, f"missing lang key {key}")
    if lang_added:
        lang.update(lang_added)
        lang_p.parent.mkdir(parents=True, exist_ok=True)
        lang_p.write_text(json.dumps(dict(sorted(lang.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        r.ok("lang", f"added {len(lang_added)} lang keys")

    # models: textures + parents (+ blockstate model refs)
    for x in roots:
        for mp in (x / "assets" / modid / "models").rglob("*.json") if (x / "assets" / modid / "models").exists() else []:
            data = load_json(mp)
            if not isinstance(data, dict):
                continue
            where = mp.relative_to(root).as_posix()
            changed = False
            for k, ref in list((data.get("textures") or {}).items()):
                if not isinstance(ref, str) or ref.startswith("#"):
                    continue
                if ":" not in ref and fix:
                    sub = "item" if "/item/" in mp.as_posix() else "block"
                    ref = data["textures"][k] = f"{modid}:{ref if '/' in ref else sub + '/' + ref}"
                    changed = True
                ns = ref.split(":")[0] if ":" in ref else "minecraft"
                if ns == modid and not any(res_path(y, ref, "texture", modid).exists() for y in roots) and fix:
                    sub = "item" if "/item/" in mp.as_posix() else "block"
                    alt = f"{modid}:{sub}/{mp.stem}"  # Blockbench texture name != file name: use <model>.png
                    if any(res_path(y, alt, "texture", modid).exists() for y in roots):
                        ref = data["textures"][k] = alt
                        changed = True
                if ns == modid and not any(res_path(y, ref, "texture", modid).exists() for y in roots):
                    r.fail(where, f"texture '{ref}' not found")
                elif ":" not in ref:
                    r.look(where, f"texture '{ref}' has no namespace (means minecraft:) — run with --fix if it's yours")
            tex = data.get("textures") or {}
            if fix and data.get("elements") and tex and "particle" not in tex:
                first = next((v for v in tex.values() if isinstance(v, str) and not v.startswith("#")), None)
                if first:
                    tex["particle"] = first
                    changed = True
            par = data.get("parent")
            if isinstance(par, str) and par.startswith(modid + ":") and not any(res_path(y, par, "model", modid).exists() for y in roots):
                r.fail(where, f"parent model '{par}' not found")
            if changed:
                mp.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
                r.ok(where, "namespaced texture refs (Blockbench export fix)")
        bs_dir = x / "assets" / modid / "blockstates"
        for bp in bs_dir.rglob("*.json") if bs_dir.exists() else []:
            for ref in re.findall(r'"model"\s*:\s*"([^"]+)"', bp.read_text(encoding="utf-8")):
                if ref.startswith(modid + ":") and not any(res_path(y, ref, "model", modid).exists() for y in roots):
                    r.fail(bp.relative_to(root).as_posix(), f"model '{ref}' not found")

    # data: own ids referenced in recipes / loot tables must be registered
    known = set(blocks) | set(items)
    for x in roots:
        for jp in (x / "data" / modid).rglob("*.json") if (x / "data" / modid).exists() else []:
            text = jp.read_text(encoding="utf-8", errors="ignore")
            for ref in set(re.findall(rf'"{modid}:([a-z0-9_/]+)"', text)):
                if ref not in known and "/" not in ref and ("recipe" in jp.parts[-2] or "loot" in jp.as_posix()):
                    r.fail(jp.relative_to(root).as_posix(), f"'{modid}:{ref}' is not a registered item/block")

    # mixins
    for mj in list(res.glob("*.mixins.json")) + list((root / "src/client/resources").glob("*.mixins.json")):
        data = load_json(mj) or {}
        pkg = data.get("package", "")
        for key in ("mixins", "client", "server"):
            for c in data.get(key, []) or []:
                rel = (pkg + "." + c).replace(".", "/") + ".java"
                if not any((root / d / rel).exists() for d in ("src/main/java", "src/client/java")):
                    r.fail(mj.name, f"mixin class {pkg}.{c} not found")

    v = validate.run(res, None)
    for level, where, msg in v.items:
        if level != "PASS" and "pack_format" not in msg:
            r.add(level, f"resources/{where}", msg)
    if not any(i[0] == "FAIL" for i in r.items):
        r.ok("summary", f"{len(blocks)} blocks, {len(items)} items consistent ({loader})")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = check(Path(a.folder), a.fix)
    rep.print(as_json=a.json, quiet_pass=not a.verbose)
    sys.exit(rep.exit_code())


if __name__ == "__main__":
    main()
