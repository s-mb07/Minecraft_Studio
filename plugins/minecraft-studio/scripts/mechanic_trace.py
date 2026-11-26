#!/usr/bin/env python3
"""Targeted map of one mechanic in a reference: which classes, flow, state, NBT, packets, events, files to read.

  mechanic_trace.py <ref-id> --question "how does its energy cable work?" [--root .] [--top 8] [--json]

Claude reads only the files listed under READ instead of the whole mod.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ref  # noqa: E402

SYN = {
    "energy": ["energy", "power", "fe", "rf", "charge", "battery", "capacitor", "generator", "storage"],
    "cable": ["cable", "wire", "pipe", "conduit", "network", "duct", "transfer", "connect"],
    "fluid": ["fluid", "tank", "liquid", "bucket"],
    "gui": ["screen", "menu", "container", "handler", "gui", "slot", "widget"],
    "machine": ["machine", "block", "entity", "tick", "process", "recipe", "progress"],
    "kinetic": ["kinetic", "rotation", "rpm", "speed", "stress", "shaft", "gear", "cog"],
    "worldgen": ["feature", "biome", "structure", "ore", "placed", "configured", "worldgen"],
    "entity": ["entity", "mob", "goal", "ai", "attribute", "renderer", "model"],
    "network": ["packet", "payload", "sync", "network", "codec"],
    "render": ["render", "renderer", "shader", "model", "baked", "vertex"],
    "config": ["config", "spec", "option"],
    "item": ["item", "tool", "sword", "armor", "use"],
}
ENTRY_METHODS = {"tick", "servertick", "clienttick", "use", "useon", "onuse", "useitemon", "onplace", "setplacedby",
                 "neighborchanged", "onremove", "entityinside", "stepon", "hurtenemy", "inventorytick", "finishusingitem",
                 "onblockentityuse", "handle", "receive", "oninitialize", "render", "init"}


def terms(question: str) -> list[str]:
    ws = [w for w in _ref.words(question) if w not in _ref.STOP and len(w) > 1]
    out = list(ws)
    for w in ws:
        for k, syn in SYN.items():
            if w == k or w in syn:
                out += syn
    return list(dict.fromkeys(out))


def score(c: dict, ts: list[str], primary: set[str]) -> float:
    name = set(_ref.words(c["name"]))
    meth = {x for m in c.get("methods", []) for x in _ref.words(m)}
    flds = {x for f in c.get("fields", []) for x in _ref.words(f)}
    strs = {x for s in c.get("strings", []) for x in _ref.words(s)}
    s = 0.0
    for t in ts:
        w = 3 if t in primary else 1
        s += w * (5 * (t in name) + 2 * (t in meth) + 1.5 * (t in flds) + 1 * (t in strs) + 1 * (t in c.get("systems", [])))
    return s


def trace(ref: Path, question: str, top: int = 8) -> dict:
    idx = _ref.load_index(ref)
    cls = idx["classes"]
    primary = {w for w in _ref.words(question) if w not in _ref.STOP}
    ts = terms(question)
    ranked = sorted(((score(c, ts, primary), c) for c in cls), key=lambda x: -x[0])
    hits = [c for s, c in ranked[:top] if s > 0]
    by = {c["name"]: c for c in cls}
    names = {c["name"] for c in hits}
    # one hop: classes the hits reference a lot
    hop = Counter(r for c in hits for r in c.get("refs", []) if r not in names)
    for n, _ in hop.most_common(3):
        if n in by:
            hits.append(by[n]); names.add(n)
    flow = [f"{c['name']} -> {r}" for c in hits for r in c.get("refs", []) if r in names][:12]
    sysc = Counter(s for c in hits for s in c.get("systems", []))
    risk = []
    if not idx.get("decompiled"):
        risk.append("no decompiled sources (names only)")
    if any(c.get("intermediary") for c in hits):
        risk.append("Fabric intermediary names (class_/method_NNNN) - Minecraft calls are obfuscated, mod code is readable")
    if not hits:
        risk.append("no class matched - try other words or mod_inventory.py")
    return {
        "question": question,
        "system": ", ".join(k for k, _ in sysc.most_common(3)) or "?",
        "classes": [f"{c['pkg']}.{c['name']}" + (f" extends {c['extends']}" if c.get("extends") else "") for c in hits],
        "entry": [f"{c['name']}.{m}()" for c in hits for m in c.get("methods", []) if m.lower() in ENTRY_METHODS][:10],
        "flow": flow,
        "state": [f"{c['name']}.{f}" for c in hits[:5] for f in c.get("fields", [])[:6] if not f.isupper()][:15],
        "persisted": sorted({k for c in hits for k in c.get("nbt", [])})[:20],
        "network": [c["name"] for c in hits if c.get("packet")][:8],
        "events": sorted({e for c in hits for e in c.get("events", [])})[:10],
        "mixins": [f"{c['name']} -> {', '.join(c['mixin'])}" for c in hits if c.get("mixin")][:8],
        "read": [c["file"] for c in hits[:5]],
        "risk": risk,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("--question", "-q", required=True); ap.add_argument("--root", default=".")
    ap.add_argument("--top", type=int, default=8); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = trace(_ref.need(Path(a.root), a.id), a.question, a.top)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False)); return
    for k in ("system", "classes", "entry", "flow", "state", "persisted", "network", "events", "mixins", "read", "risk"):
        v = r[k]
        if v:
            print(f"{k.upper()}: {v if isinstance(v, str) else ' | '.join(v)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
