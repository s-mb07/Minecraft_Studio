#!/usr/bin/env python3
"""Generate FTB Quests SNBT files from a readable quest design (JSON).

  quests.py build quests/design.json --out pack/overrides [--format 1.21|1.20]
  quests.py check quests/design.json            # graph checks only (cycles, dangling deps, reachability)
  quests.py mermaid quests/design.json          # quest tree as a Mermaid diagram (for docs / the vault)

IDs are derived from each quest's key, so regenerating keeps the same IDs (player progress survives).
Never hand-edit generated chapter files AND the design at the same time: the design is the source.

--format 1.21 (default, FTB Quests for MC 1.21+): item objects { id, count }, text in lang/<lang>.snbt.
--format 1.20 (MC 1.20.1): item ids as strings, titles/descriptions inline in the chapter file.
Always open the quest book in game once to confirm (the script cannot see the game: that is a LOOK).

Design schema (see templates/quest-design.example.json):
{ "lang": "en_us",
  "groups":   [ { "key": "main", "title": "Main story" } ],
  "chapters": [ { "key": "first_night", "title": "...", "icon": "minecraft:torch", "group": "main",
                  "quests": [ { "key": "wood", "title": "...", "subtitle": "...", "description": ["..."],
                                "icon": "minecraft:oak_log", "deps": ["other_key" | "chapter/key"],
                                "x": 0, "y": 0, "optional": false, "shape": "circle",
                                "tasks":   [ {"type": "item", "item": "minecraft:oak_log", "count": 16, "consume": false},
                                             {"type": "kill", "entity": "minecraft:zombie", "value": 5},
                                             {"type": "checkmark"}, {"type": "advancement", "advancement": "minecraft:story/mine_stone"},
                                             {"type": "dimension", "dimension": "minecraft:the_nether"} ],
                                "rewards": [ {"type": "item", "item": "minecraft:bread", "count": 4},
                                             {"type": "xp", "xp": 100}, {"type": "xp_levels", "xp_levels": 2},
                                             {"type": "command", "command": "/say hi"}, {"type": "custom"} ] } ] } ] }
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, load_json  # noqa: E402


def hex_id(*parts: str) -> str:
    h = hashlib.sha256("/".join(parts).encode()).hexdigest().upper()[:16]
    return h if h != "0" * 16 else "0000000000000001"


def q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------------- SNBT writer ----------------

class Raw(str):
    """Already-formatted SNBT literal (e.g. 16L, 0.5d)."""


def snbt(v, indent=0) -> str:
    t = "\t"
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v}d"
    if isinstance(v, str):
        return q(v)
    if isinstance(v, list):
        if not v:
            return "[ ]"
        if all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in v):
            return "[" + ", ".join(snbt(x) for x in v) + "]"
        inner = "\n".join(t * (indent + 1) + snbt(x, indent + 1) for x in v)
        return "[\n" + inner + "\n" + t * indent + "]"
    if isinstance(v, dict):
        if not v:
            return "{ }"
        if all(not isinstance(x, (dict, list)) for x in v.values()) and len(v) <= 3 and indent > 0:
            return "{ " + ", ".join(f"{key(k)}: {snbt(x)}" for k, x in v.items()) + " }"
        inner = "\n".join(f"{t * (indent + 1)}{key(k)}: {snbt(x, indent + 1)}" for k, x in v.items())
        return "{\n" + inner + "\n" + t * indent + "}"
    raise TypeError(type(v))


def key(k: str) -> str:
    return k if all(c.isalnum() or c in "_.-" for c in k) else q(k)


# ---------------- design model ----------------

def index_design(d: dict) -> dict:
    """Return {full_key: (chapter, quest)} and validate keys."""
    idx = {}
    if not d.get("chapters"):
        die("design has no chapters")
    for ch in d["chapters"]:
        for qu in ch.get("quests", []):
            fk = f"{ch['key']}/{qu['key']}"
            if fk in idx:
                die(f"duplicate quest key {fk}")
            idx[fk] = (ch, qu)
    return idx


def resolve_dep(dep: str, ch_key: str, idx: dict) -> str | None:
    fk = dep if "/" in dep else f"{ch_key}/{dep}"
    return fk if fk in idx else None


def check(d: dict) -> list[str]:
    idx = index_design(d)
    errors, edges = [], {}
    group_keys = {g["key"] for g in d.get("groups", [])}
    for ch in d["chapters"]:
        if ch.get("group") and ch["group"] not in group_keys:
            errors.append(f"chapter {ch['key']}: unknown group '{ch['group']}'")
    for fk, (ch, qu) in idx.items():
        edges[fk] = []
        if not qu.get("tasks"):
            errors.append(f"{fk}: no tasks (add at least a checkmark)")
        for t in qu.get("tasks", []):
            if t.get("type") in ("item", "kill") and ":" not in str(t.get("item") or t.get("entity") or ""):
                errors.append(f"{fk}: task {t} needs a namespaced id like minecraft:oak_log")
        for dep in qu.get("deps", []):
            r = resolve_dep(dep, ch["key"], idx)
            if not r:
                errors.append(f"{fk}: dependency '{dep}' does not exist")
            else:
                edges[fk].append(r)
    # cycles
    state = {}

    def dfs(n, path):
        state[n] = 1
        for m in edges.get(n, []):
            if state.get(m) == 1:
                errors.append("cycle: " + " -> ".join(path + [m]))
            elif not state.get(m):
                dfs(m, path + [m])
        state[n] = 2
    for n in edges:
        if not state.get(n):
            dfs(n, [n])
    roots = [k for k, v in edges.items() if not v]
    if not roots:
        errors.append("no starting quest (every quest has a dependency)")
    return errors


def depth_layout(ch: dict, idx: dict) -> dict:
    """Auto x/y for quests missing coordinates: x = dependency depth, y = order within that depth."""
    memo = {}

    def depth(fk):
        if fk in memo:
            return memo[fk]
        c, qu = idx[fk]
        ds = [resolve_dep(x, c["key"], idx) for x in qu.get("deps", [])]
        ds = [x for x in ds if x and x.startswith(ch["key"] + "/")]
        memo[fk] = 0 if not ds else 1 + max(depth(x) for x in ds)
        return memo[fk]
    rows, pos = {}, {}
    for qu in ch.get("quests", []):
        fk = f"{ch['key']}/{qu['key']}"
        dx = depth(fk)
        rows[dx] = rows.get(dx, 0) + 1
        pos[fk] = (dx * 1.5, (rows[dx] - 1) * 1.5)
    return pos


def item_obj(item: str, count: int | None, fmt: str):
    if fmt == "1.20":
        return item
    o = {"id": item}
    if count and count != 1:
        o = {"count": count, "id": item}
    return o


def build_task(t: dict, tid: str, fmt: str) -> dict:
    typ = t["type"]
    o = {"id": tid, "type": typ}
    if typ == "item":
        o["item"] = item_obj(t["item"], 1, fmt)
        if t.get("count", 1) != 1:
            o["count"] = Raw(f"{int(t['count'])}L")
        if "consume" in t:
            o["consume_items"] = bool(t["consume"])
    elif typ == "kill":
        o["entity"] = t["entity"]
        o["value"] = Raw(f"{int(t.get('value', 1))}L")
    elif typ in ("advancement", "dimension", "biome", "structure", "stage"):
        o[typ] = t[typ]
    elif typ == "checkmark":
        pass
    else:
        o.update({k: v for k, v in t.items() if k != "type"})
    return o


def build_reward(r: dict, rid: str, fmt: str) -> dict:
    typ = r["type"]
    o = {"id": rid, "type": typ}
    if typ == "item":
        o["item"] = item_obj(r["item"], 1, fmt)
        if r.get("count", 1) != 1:
            o["count"] = int(r["count"])
    elif typ == "xp":
        o["xp"] = int(r["xp"])
    elif typ == "xp_levels":
        o["xp_levels"] = int(r["xp_levels"])
    elif typ == "command":
        o["command"] = r["command"]
        o["permission_level"] = int(r.get("permission_level", 2))
    elif typ == "custom":
        pass
    else:
        o.update({k: v for k, v in r.items() if k != "type"})
    return o


def build(d: dict, out: Path, fmt: str):
    errs = check(d)
    if errs:
        for e in errs:
            print(f"  FAIL {e}")
        die("fix the design first (quests.py check)")
    idx = index_design(d)
    base = out / "config" / "ftbquests" / "quests"
    (base / "chapters").mkdir(parents=True, exist_ok=True)
    lang: dict[str, object] = {}
    inline = fmt == "1.20"

    def text(obj: dict, lang_key: str, field: str, value):
        if value in (None, "", []):
            return
        if inline:
            obj[{"quest_desc": "description", "quest_subtitle": "subtitle"}.get(field, field)] = value
        else:
            lang[f"{lang_key}.{field}"] = value

    groups = []
    for g in d.get("groups", []):
        gid = hex_id("group", g["key"])
        go = {"id": gid}
        text(go, f"chapter_group.{gid}", "title", g.get("title"))
        groups.append(go)
    (base / "chapter_groups.snbt").write_text("{\n\tchapter_groups: " + snbt(groups, 1) + "\n}\n",
                                              encoding="utf-8", newline="\n")
    for order, ch in enumerate(d["chapters"]):
        cid = hex_id("chapter", ch["key"])
        auto = depth_layout(ch, idx)
        quests = []
        for qu in ch.get("quests", []):
            fk = f"{ch['key']}/{qu['key']}"
            qid = hex_id("quest", fk)
            x, y = (float(qu["x"]), float(qu["y"])) if "x" in qu and "y" in qu else auto[fk]
            qo = {"id": qid}
            text(qo, f"quest.{qid}", "title", qu.get("title"))
            text(qo, f"quest.{qid}", "quest_subtitle", qu.get("subtitle"))
            text(qo, f"quest.{qid}", "quest_desc", qu.get("description"))
            deps = [hex_id("quest", resolve_dep(x_, ch["key"], idx)) for x_ in qu.get("deps", [])]
            if deps:
                qo["dependencies"] = deps
            if qu.get("icon"):
                qo["icon"] = item_obj(qu["icon"], 1, fmt)
            if qu.get("shape"):
                qo["shape"] = qu["shape"]
            if qu.get("optional"):
                qo["optional"] = True
            qo["x"] = Raw(f"{x}d")
            qo["y"] = Raw(f"{y}d")
            qo["tasks"] = [build_task(t, hex_id("task", fk, str(i)), fmt) for i, t in enumerate(qu.get("tasks", []))]
            qo["rewards"] = [build_reward(r, hex_id("reward", fk, str(i)), fmt) for i, r in enumerate(qu.get("rewards", []))]
            quests.append(qo)
        co = {
            "default_hide_dependency_lines": False,
            "default_quest_shape": "",
            "filename": cid,
            "group": hex_id("group", ch["group"]) if ch.get("group") else "",
        }
        if ch.get("icon"):
            co["icon"] = item_obj(ch["icon"], 1, fmt)
        co["id"] = cid
        co["order_index"] = order
        co["quest_links"] = []
        co["quests"] = quests
        text(co, f"chapter.{cid}", "title", ch.get("title"))
        (base / "chapters" / f"{cid}.snbt").write_text(snbt(co) + "\n", encoding="utf-8", newline="\n")
        print(f"  chapter {ch['key']} -> chapters/{cid}.snbt ({len(quests)} quests)")
    if not inline:
        (base / "lang").mkdir(exist_ok=True)
        lines = "\n".join(f"\t{k}: {snbt(v, 1)}" for k, v in lang.items())
        lp = base / "lang" / f"{d.get('lang', 'en_us')}.snbt"
        lp.write_text("{\n" + lines + "\n}\n", encoding="utf-8", newline="\n")
        print(f"  lang -> {lp.relative_to(out)} ({len(lang)} keys)")
    data = base / "data.snbt"
    if not data.exists():
        data.write_text(snbt({"default_quest_shape": "circle", "progression_mode": "linear",
                              "grid_scale": Raw("0.5d"), "show_lock_icons": True}) + "\n",
                        encoding="utf-8", newline="\n")
        print("  data.snbt created with minimal defaults (FTB Quests fills in the rest on first load)")
    print("LOOK: open the quest book in game once — layout and item ids can only be confirmed there.")


def mermaid(d: dict) -> str:
    idx = index_design(d)
    out = ["flowchart LR"]
    for ch in d["chapters"]:
        out.append(f"  subgraph {ch['key']}[\"{ch.get('title', ch['key'])}\"]")
        for qu in ch.get("quests", []):
            out.append(f"    {ch['key']}__{qu['key']}[\"{qu.get('title', qu['key'])}\"]")
        out.append("  end")
    for fk, (ch, qu) in idx.items():
        for dep in qu.get("deps", []):
            r = resolve_dep(dep, ch["key"], idx)
            if r:
                out.append(f"  {r.replace('/', '__')} --> {fk.replace('/', '__')}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("design"); b.add_argument("--out", required=True)
    b.add_argument("--format", choices=["1.21", "1.20"], default="1.21")
    c = sub.add_parser("check"); c.add_argument("design")
    m = sub.add_parser("mermaid"); m.add_argument("design")
    a = ap.parse_args()
    d = load_json(Path(a.design))
    if a.cmd == "check":
        errs = check(d)
        for e in errs:
            print(f"  [FAIL] {e}")
        n = len(index_design(d))
        print(f"== quest design: {'FAIL' if errs else 'PASS'} ({n} quests, {len(d['chapters'])} chapters)")
        sys.exit(1 if errs else 0)
    if a.cmd == "mermaid":
        print(mermaid(d))
        return
    build(d, Path(a.out), a.format)


if __name__ == "__main__":
    main()
