#!/usr/bin/env python3
"""Static checks for a modpack workspace, resource pack or datapack. Gates: PASS / LOOK / FAIL.

  validate.py <dir> [--mc 1.21.1] [--json] [--quiet]

Checks
  *.json / *.mcmeta     parse errors with file:line
  pack.mcmeta           pack_format matches --mc (resource pack vs datapack auto-detected)
  assets/ data/         resource locations must be lowercase [a-z0-9_.-/]
  *.png textures        size sanity (multiple of 16 or animated strip with .mcmeta)
  *.snbt (FTB Quests)   brackets/quotes balanced, 16-hex ids, duplicate ids, dangling dependencies
  kubejs/**/*.js        brackets balanced
  secrets               API keys / tokens accidentally left in files

Anything this script cannot verify (runtime behaviour, visuals, balance) is NOT reported as PASS.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_PACK_FORMAT, RESOURCE_PACK_FORMAT, Report  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", ".venv"}
HEX16 = re.compile(r"^[0-9A-F]{16}$")
SECRET_RX = re.compile(r"(sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|"
                       r"(?:api[_-]?key|secret|token)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"'])", re.I)
RESLOC_RX = re.compile(r"^[a-z0-9_.\-/]+$")


def files(root: Path, *exts):
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS) and p.suffix.lower() in exts:
            yield p


def rel(root, p):
    return p.relative_to(root).as_posix()


def check_json(root: Path, r: Report):
    n = 0
    for p in files(root, ".json", ".mcmeta"):
        try:
            json.loads(p.read_text(encoding="utf-8-sig"))
            n += 1
        except json.JSONDecodeError as e:
            r.fail(f"{rel(root, p)}:{e.lineno}", f"invalid JSON: {e.msg}")
        except UnicodeDecodeError:
            r.fail(rel(root, p), "not UTF-8")
    if n:
        r.ok("json", f"{n} JSON/mcmeta files parse")


def check_mcmeta(root: Path, r: Report, mc: str | None):
    for p in files(root, ".mcmeta"):
        if p.name != "pack.mcmeta":
            continue
        where = rel(root, p)
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue  # already reported by check_json
        pack = data.get("pack")
        if not isinstance(pack, dict):
            r.fail(where, "missing top-level 'pack' object")
            continue
        if "description" not in pack:
            r.fail(where, "pack.description missing")
        kind = "datapack" if (p.parent / "data").is_dir() and not (p.parent / "assets").is_dir() else "resourcepack"
        fmt = pack.get("pack_format")
        has_range = "min_format" in pack or "max_format" in pack
        if fmt is None and not has_range:
            r.fail(where, "pack_format (or min_format/max_format) missing")
            continue
        if fmt is not None and not isinstance(fmt, int):
            r.fail(where, f"pack_format must be an integer, got {fmt!r}")
            continue
        if not mc:
            r.look(where, f"{kind} pack_format={fmt}: pass --mc to check it against the target version")
            continue
        table = DATA_PACK_FORMAT if kind == "datapack" else RESOURCE_PACK_FORMAT
        expected = table.get(mc)
        if expected is None:
            r.look(where, f"no verified {kind} format for MC {mc} in our table: check the Minecraft Wiki 'Pack format'")
        elif has_range:
            r.look(where, f"uses min/max_format: confirm the range covers {expected} (MC {mc})")
        elif fmt != expected:
            r.fail(where, f"{kind} pack_format={fmt} but MC {mc} expects {expected}")
        else:
            r.ok(where, f"{kind} pack_format {fmt} matches MC {mc}")


def check_reslocs(root: Path, r: Report):
    bad = 0
    for top in ("assets", "data"):
        for base in root.rglob(top):
            if not base.is_dir() or set(base.relative_to(root).parts) & SKIP_DIRS:
                continue
            for p in base.rglob("*"):
                if p.is_file() and not RESLOC_RX.match(p.relative_to(base).as_posix()):
                    if bad < 20:
                        r.fail(rel(root, p), "resource paths must be lowercase a-z 0-9 _ . - / (game ignores this file)")
                    bad += 1
    if bad > 20:
        r.fail("assets", f"... and {bad - 20} more invalid resource paths")


def png_size(p: Path):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def check_textures(root: Path, r: Report):
    n = 0
    for p in files(root, ".png"):
        if "textures" not in p.parts:
            continue
        size = png_size(p)
        where = rel(root, p)
        if not size:
            r.fail(where, "not a valid PNG")
            continue
        w, h = size
        n += 1
        animated = p.with_suffix(".png.mcmeta").exists()
        if animated and h % w:
            r.fail(where, f"animated texture {w}x{h}: height must be a multiple of width")
        elif not animated and "gui" not in p.parts and "font" not in p.parts and (w % 16 or h % 16):
            r.look(where, f"{w}x{h} is not a multiple of 16 (fine for GUI/fonts, unusual for blocks/items)")
        elif not animated and w != h and ("block" in p.parts or "item" in p.parts) and "entity" not in p.parts:
            r.look(where, f"{w}x{h} non-square block/item texture without .mcmeta (animation?)")
    if n:
        r.ok("textures", f"{n} PNG textures read")


def strip_strings(text: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', text)


def balanced(text: str):
    pairs, stack = {"}": "{", "]": "[", ")": "("}, []
    for i, ch in enumerate(text):
        if ch in "{[(":
            stack.append((ch, i))
        elif ch in "}])":
            if not stack or stack[-1][0] != pairs[ch]:
                return text.count("\n", 0, i) + 1
            stack.pop()
    return (text.count("\n", 0, stack[-1][1]) + 1) if stack else None


def check_snbt(root: Path, r: Report):
    ids, deps, n = {}, [], 0
    for p in files(root, ".snbt"):
        where = rel(root, p)
        text = p.read_text(encoding="utf-8", errors="replace")
        if text.count('"') - len(re.findall(r'\\"', text)) & 1:
            r.fail(where, "odd number of quotes (unclosed string)")
            continue
        line = balanced(strip_strings(text))
        if line:
            r.fail(f"{where}:{line}", "unbalanced brackets")
            continue
        n += 1
        if "ftbquests" not in p.parts:
            continue
        for m in re.finditer(r'^\s*id:\s*"([^"]+)"', text, re.M):
            v, ln = m.group(1), text.count("\n", 0, m.start()) + 1
            if not HEX16.match(v):
                r.fail(f"{where}:{ln}", f"id {v} is not 16 uppercase hex chars")
            elif v in ids:
                r.fail(f"{where}:{ln}", f"duplicate id {v} (also in {ids[v]})")
            else:
                ids[v] = f"{where}:{ln}"
        for m in re.finditer(r"dependencies:\s*\[([^\]]*)\]", text):
            for d in re.findall(r'"([0-9A-Fa-f]{16})"', m.group(1)):
                deps.append((d, f"{where}:{text.count(chr(10), 0, m.start()) + 1}"))
        fm = re.search(r'^\s*filename:\s*"([^"]+)"', text, re.M)
        if fm and "chapters" in p.parts and fm.group(1) != p.stem:
            r.fail(where, f"filename field '{fm.group(1)}' must match the file name '{p.stem}'")
    for d, where in deps:
        if d not in ids:
            r.fail(where, f"dependency {d} points to no known quest")
    if n:
        r.ok("snbt", f"{n} SNBT files balanced; {len(ids)} FTB Quests ids checked")


def check_js(root: Path, r: Report):
    n = 0
    for p in files(root, ".js"):
        if "kubejs" not in p.parts:
            continue
        text = re.sub(r"//[^\n]*|/\*.*?\*/", "", p.read_text(encoding="utf-8", errors="replace"), flags=re.S)
        text = re.sub(r"'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`", "''", strip_strings(text))
        line = balanced(text)
        if line:
            r.fail(f"{rel(root, p)}:{line}", "unbalanced brackets")
        n += 1
    if n:
        r.ok("kubejs", f"{n} scripts bracket-balanced")
        r.look("kubejs", "syntax only: recipe/item ids are checked when the game loads (mc-test-loop)")


def check_secrets(root: Path, r: Report):
    for p in files(root, ".json", ".js", ".toml", ".txt", ".cfg", ".properties", ".snbt", ".md", ".yml", ".yaml", ".env"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = SECRET_RX.search(text)
        if m:
            r.fail(f"{rel(root, p)}:{text.count(chr(10), 0, m.start()) + 1}", "looks like a secret/API key — remove it")


def run(root: Path, mc: str | None) -> Report:
    r = Report(f"validate {root}")
    check_json(root, r)
    check_mcmeta(root, r, mc)
    check_reslocs(root, r)
    check_textures(root, r)
    check_snbt(root, r)
    check_js(root, r)
    check_secrets(root, r)
    if not r.items:
        r.look(str(root), "nothing to check here")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--mc")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="hide PASS lines")
    a = ap.parse_args()
    rep = run(Path(a.dir), a.mc)
    rep.print(as_json=a.json, quiet_pass=a.quiet)
    sys.exit(rep.exit_code())


if __name__ == "__main__":
    main()
