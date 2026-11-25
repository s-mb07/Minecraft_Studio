#!/usr/bin/env python3
"""Triage Minecraft logs / crash reports: find the failure, the suspect mod and a suggested fix.

  log_scan.py <latest.log | crash-report.txt | instance-or-server-dir> [--json] [--history studio/fix-history.json]

Prints a 'signature' (short hash of the normalized failure). The test loop stores signatures in
--history: if the same signature comes back after a fix, the loop must STOP and ask the user.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_json, save_json  # noqa: E402

# (id, regex, explanation, suggested fix). Group 'mod' / 'dep' are used when present.
RULES = [
    ("wrong-java", r"UnsupportedClassVersionError.*class file version (?P<v>\d+)",
     "A mod or the game was compiled for a newer Java than the one running.",
     "Use the Java version required by this Minecraft version (see lock 'java'). Class file 65 = Java 21, 69 = Java 25."),
    ("fabric-missing-dep", r"Mod '[^']+' \((?P<mod>[^)]+)\) [^\n]* requires (?:any version|version [^\n]*?) of (?:mod )?'?(?P<dep>[\w\-. ]+?)'?(?:,| which| \(|$)",
     "A Fabric/Quilt mod needs a dependency that is missing or the wrong version.",
     "Add/adjust the dependency (modrinth.py info <mod>) or remove the mod, then re-run resolve + audit."),
    ("fabric-incompatible", r"Incompatible mods? found!",
     "Fabric refused to start: incompatible set of mods.",
     "Read the lines just below in the log: they list each mod and what it needs. Fix versions or drop one mod."),
    ("neoforge-missing-dep", r"(?:Missing or unsupported mandatory dependencies|Mod (?P<mod>\S+) requires (?P<dep>\S+))",
     "NeoForge/Forge: a mandatory dependency is missing or out of range.",
     "Install the listed dependency in a compatible version, or remove the mod that needs it."),
    ("duplicate-mod", r"(?:Found duplicate mods|Duplicate mods? found|Mod ID '?(?P<mod>[\w-]+)'? .*duplicate)",
     "The same mod is installed twice (often two versions of one jar).",
     "Keep one jar. Check mods/ for leftovers that are not in pack.lock.json."),
    ("mixin-failure", r"Mixin apply (?:for mod (?P<mod>[\w-]+) )?failed|MixinApplyError|InvalidMixinException.*?(?P<cfg>[\w.\-]+\.mixins\.json)",
     "A mod's mixin could not patch the game: usually a mod made for another MC/loader version, or two mods patching the same code.",
     "Check the suspect mod's version vs MC version; try removing it or the mod it conflicts with (bisect)."),
    ("class-not-found", r"(?:ClassNotFoundException|NoClassDefFoundError):? (?P<cls>[\w.$/]+)",
     "Code refers to a class that is not present: missing library/dependency or wrong version.",
     "Find which mod provides that package (the package name usually contains the mod id) and add/update it."),
    ("no-such-method", r"NoSuchMethodError:? (?P<cls>[\w.$/:'() ]+)",
     "Two mods disagree on an API version.",
     "Update the dependency or the mod calling it so they match; check the mod's required version range."),
    ("out-of-memory", r"java\.lang\.OutOfMemoryError",
     "The JVM ran out of memory.",
     "Raise -Xmx (6-8 GB for big packs), or remove heavy mods; check for memory leak mods."),
    ("config-error", r"(?:Failed loading config file|ParsingException|Configuration file .* is not correct)\s*(?P<file>\S+)?",
     "A config file is malformed.",
     "Fix or delete the listed config (it will be regenerated). Validate overrides with validate.py."),
    ("kubejs-error", r"\[KubeJS[^\]]*\].*?(?:Error|error)[^\n]*?(?P<file>[\w/\-]+\.js)(?:#(?P<line>\d+))?",
     "A KubeJS script failed.",
     "Open the script at the given line; check recipe/item IDs exist (/kubejs hand, or the mod's lang/registry)."),
    ("missing-registry", r"(?:Unknown (?:item|block|recipe serializer|registry key)|Unknown registry entry|Couldn't parse .*?Unknown).*?(?P<id>[a-z0-9_.-]+:[a-z0-9_/.-]+)",
     "A datapack/recipe/quest references an ID that does not exist.",
     "Correct the ID or add the mod that provides it. Search the ID in overrides/ and quests."),
    ("port-in-use", r"FAILED TO BIND TO PORT",
     "Server port already in use.",
     "Stop the other server or change server-port in server.properties."),
]

SUSPECT_RE = re.compile(r"Suspected Mods?:\s*(?P<s>[^\n]+(?:\n\t[^\n]+)*)", re.I)
DESC_RE = re.compile(r"^Description: (?P<d>.+)$", re.M)


def pick_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    out = []
    for base in (target, target / "minecraft", target / ".minecraft"):
        crashes = sorted((base / "crash-reports").glob("crash-*.txt"), key=lambda p: p.stat().st_mtime)
        if crashes:
            out.append(crashes[-1])
        if (base / "logs" / "latest.log").exists():
            out.append(base / "logs" / "latest.log")
    return out


def normalize(text: str) -> str:
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}[^\]]*\]", "", text)
    text = re.sub(r"\b0x[0-9a-f]+\b|\b\d+\b", "N", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:400]


def scan(text: str) -> dict:
    findings = []
    for rid, rx, why, fix in RULES:
        matches = list(re.finditer(rx, text))[:50]
        if matches:
            # first occurrence, unless a later one names the mod (more useful for triage)
            m = max(matches, key=lambda x: (len([v for v in x.groupdict().values() if v]), -x.start()))
            line_no = text.count("\n", 0, m.start()) + 1
            g = {k: v for k, v in m.groupdict().items() if v}
            findings.append({"rule": rid, "line": line_no, "match": m.group(0)[:300], "groups": g,
                             "why": why, "fix": fix})
    suspects = []
    m = SUSPECT_RE.search(text)
    if m:
        for s in re.split(r",|\n\t", m.group("s")):
            s = s.strip()
            if s and s != "NONE":
                mid = re.search(r"\(([\w-]+)\)\s*$", s)  # "Cool Mod (coolmod)" -> coolmod
                suspects.append(mid.group(1) if mid else s)
    for f in findings:
        for k in ("mod", "dep"):
            if f["groups"].get(k):
                suspects.append(f["groups"][k].strip())
    desc = DESC_RE.search(text)
    first = findings[0] if findings else None
    basis = (first["rule"] + normalize(first["match"])) if first else normalize(desc.group("d") if desc else text[-400:])
    return {
        "description": desc.group("d") if desc else None,
        "findings": findings,
        "suspects": sorted(set(suspects)),
        "signature": hashlib.sha1(basis.encode()).hexdigest()[:12],
        "clean": not findings and not desc,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--history", help="JSON file storing previous signatures (bounded fix loop)")
    a = ap.parse_args()
    files = pick_files(Path(a.target))
    if not files:
        print("LOOK: no crash report or latest.log found — was the game launched?")
        sys.exit(0)
    results = {}
    for f in files:
        results[str(f)] = scan(f.read_text(encoding="utf-8", errors="replace"))
    repeat = False
    if a.history:
        hp = Path(a.history)
        hist = load_json(hp) if hp.exists() else {"signatures": []}
        for r in results.values():
            if not r["clean"]:
                if r["signature"] in hist["signatures"]:
                    repeat = True
                hist["signatures"].append(r["signature"])
        save_json(hp, hist)
    if a.json:
        print(json.dumps({"files": results, "repeat": repeat}, indent=2, ensure_ascii=False))
    else:
        for path, r in results.items():
            print(f"== {path}")
            if r["clean"]:
                print("  no known failure pattern (LOOK: read the end of the log yourself)")
            if r["description"]:
                print(f"  crash: {r['description']}")
            for fd in r["findings"]:
                print(f"  [{fd['rule']}] line {fd['line']}: {fd['match'][:160]}")
                print(f"     why: {fd['why']}\n     fix: {fd['fix']}")
            if r["suspects"]:
                print(f"  suspects: {', '.join(r['suspects'])}")
            print(f"  signature: {r['signature']}")
        if repeat:
            print("STOP: this failure signature already happened after a previous fix. Ask the user before trying again.")
    sys.exit(3 if repeat else 0)


if __name__ == "__main__":
    main()
