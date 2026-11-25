#!/usr/bin/env python3
"""Pack health score (0-100) from evidence only. Unmeasured areas are listed, not scored as passing.

  health.py <workspace> [--mc 1.21.1] [--json]

Areas and weights (fixed so scores are comparable between packs):
  compatibility 30  modrinth.py audit on pack/pack.lock.json
  files         20  validate.py on pack/
  quests        15  quests.py check on quests/design.json
  runtime       25  studio/test-status.json written by the test loop: {"client_boot": bool, "server_boot": bool, "quest_walkthrough": bool}
  docs          10  README.md, CREDITS.md, assets/licences.md filled in (no TODO left)

Score = earned / measured weight * 100, and the report always prints the measured weight.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modrinth  # noqa: E402
import quests as questmod  # noqa: E402
import validate  # noqa: E402
from _common import load_json  # noqa: E402

WEIGHTS = {"compatibility": 30, "files": 20, "quests": 15, "runtime": 25, "docs": 10}
LEVEL_SCORE = {"PASS": 1.0, "LOOK": 0.6, "FAIL": 0.0}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--mc")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ws = Path(a.workspace)
    areas, unmeasured = {}, []

    lock_p = ws / "pack" / "pack.lock.json"
    lock = load_json(lock_p) if lock_p.exists() else None
    mc = a.mc or (lock or {}).get("minecraft")
    if lock:
        rep = modrinth.audit(lock)
        fails = sum(1 for i in rep.items if i[0] == "FAIL")
        areas["compatibility"] = (max(0.0, 1 - 0.25 * fails) if fails else LEVEL_SCORE["PASS"],
                                  f"{rep.verdict}, {fails} fail")
    else:
        unmeasured.append("compatibility (no pack/pack.lock.json — run modrinth.py resolve)")

    if (ws / "pack").is_dir():
        rep = validate.run(ws / "pack", mc)
        fails = sum(1 for i in rep.items if i[0] == "FAIL")
        areas["files"] = (max(0.0, 1 - 0.2 * fails), f"{rep.verdict}, {fails} fail")
    else:
        unmeasured.append("files (no pack/ folder)")

    design = ws / "quests" / "design.json"
    if design.exists():
        errs = questmod.check(load_json(design))
        areas["quests"] = (max(0.0, 1 - 0.2 * len(errs)), f"{len(errs)} design errors")
    else:
        unmeasured.append("quests (no quests/design.json)")

    status_p = ws / "studio" / "test-status.json"
    if status_p.exists():
        st = load_json(status_p)
        keys = ["client_boot", "server_boot", "quest_walkthrough"]
        known = [k for k in keys if isinstance(st.get(k), bool)]
        if known:
            areas["runtime"] = (sum(1 for k in known if st[k]) / len(keys),
                                ", ".join(f"{k}={st.get(k, 'not tested')}" for k in keys))
        else:
            unmeasured.append("runtime (test-status.json has no results)")
    else:
        unmeasured.append("runtime (game never launched by the test loop)")

    docs = [ws / "README.md", ws / "CREDITS.md", ws / "assets" / "licences.md"]
    present = [d for d in docs if d.exists()]
    if present:
        filled = [d for d in present if "TODO" not in d.read_text(encoding="utf-8", errors="ignore")]
        areas["docs"] = (len(filled) / len(docs), f"{len(filled)}/{len(docs)} complete")
    else:
        unmeasured.append("docs")

    measured = sum(WEIGHTS[k] for k in areas)
    earned = sum(WEIGHTS[k] * v[0] for k, v in areas.items())
    score = round(100 * earned / measured) if measured else None
    if a.json:
        print(json.dumps({"score": score, "measured_weight": measured, "areas":
                          {k: {"score": round(v[0], 2), "weight": WEIGHTS[k], "detail": v[1]} for k, v in areas.items()},
                          "unmeasured": unmeasured}, indent=2))
        return
    print(f"== pack health: {score if score is not None else 'n/a'}/100 (based on {measured}/100 of the weight)")
    for k, (v, detail) in areas.items():
        print(f"  {k:<14} {round(v * WEIGHTS[k]):>3}/{WEIGHTS[k]:<3} {detail}")
    for u in unmeasured:
        print(f"  NOT MEASURED   {u}")
    if unmeasured:
        print("  A pack is not release-ready while anything is unmeasured.")


if __name__ == "__main__":
    main()
