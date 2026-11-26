#!/usr/bin/env python3
"""Layout of a reference GUI (Screen + Menu classes, or a GUI texture), plus an original-design variant.

  gui_study.py <ref-id> --screen <class name or png path substring> [--root .] [--json]

Reads imageWidth/imageHeight, slots (addSlot(new Slot(..., x, y))), blit() regions (bars/arrows), buttons,
input handlers and translation keys. Fabric intermediary code is read the same way (names may be obfuscated).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ref  # noqa: E402

RX_SIZE = re.compile(r"(?:imageWidth|imageHeight|backgroundWidth|backgroundHeight|field_2792|field_2779)\s*=\s*(\d+)")
RX_SLOT = re.compile(r"addSlot\(\s*new\s+(\w+)\(([^;]*?)\)\s*\)")
RX_BLIT = re.compile(r"\.(?:blit|drawTexture|method_25302|blitSprite)\(([^;]*?)\);")
HANDLERS = ["mouseClicked", "mouseDragged", "mouseScrolled", "keyPressed", "charTyped", "mouseReleased"]


def find(ref: Path, name: str) -> list[Path]:
    idx = _ref.load_index(ref)
    base = name.replace("Screen", "").replace("Menu", "").replace("ScreenHandler", "").replace("Container", "")
    hits = [c for c in idx["classes"] if c["name"] == name or (base and c["name"].startswith(base)
            and re.search(r"(Screen|Menu|Container|Handler)$", c["name"]))]
    return [ref / c["file"] for c in hits]


def study(ref: Path, screen: str) -> dict:
    if screen.endswith(".png"):
        import asset_study
        return {"texture": asset_study.study(ref, "gui", screen, 5)}
    out = {"screen": screen, "classes": [], "size": [], "slots": [], "player_inventory": False, "regions": [],
           "buttons": 0, "interaction": [], "lang": []}
    for p in find(ref, screen):
        t = p.read_text(encoding="utf-8", errors="replace")
        out["classes"].append(p.name)
        out["size"] += [int(x) for x in RX_SIZE.findall(t)]
        for kind, args in RX_SLOT.findall(t):
            nums = re.findall(r"(?<![\w.])(\d+)(?![\w.])", args)
            if re.search(r"\d+\s*\+\s*\w+\s*\*\s*18", args):
                out["player_inventory"] = True
            elif len(nums) >= 2:
                out["slots"].append({"type": kind, "x": int(nums[-2]), "y": int(nums[-1])})
        for args in RX_BLIT.findall(t):
            nums = [int(n) for n in re.findall(r"(?<![\w.])(\d+)(?![\w.])", args)]
            if len(nums) >= 2 and nums[-2] and nums[-1] and nums[-2] < 176:
                w, h = nums[-2], nums[-1]
                shape = "horizontal bar/arrow" if w >= 1.3 * h else "vertical bar/gauge" if h >= 1.3 * w else "icon"
                out["regions"].append(f"{w}x{h} {shape}")
        out["buttons"] += len(re.findall(r"Button\.builder|new \w*Button\(|addRenderableWidget|method_37063", t))
        out["interaction"] += [h for h in HANDLERS if re.search(rf"\b{h}\(", t)]
        out["lang"] += re.findall(r'(?:translatable|literal)\(\s*"([^"]+)"', t)
    out["size"] = out["size"][:2] or ["176?", "166?"]
    out["interaction"] = sorted(set(out["interaction"]))
    out["regions"] = list(dict.fromkeys(out["regions"]))[:10]
    out["original_design"] = original(out)
    return out


def original(o: dict) -> list[str]:
    n = len(o["slots"])
    ideas = [f"{max(1, n - 1)} input(s) + 1 catalyst + 1 output (reference has {n} machine slots)" if n else
             "start from the function, not the layout: list inputs/outputs first"]
    if any("horizontal" in r for r in o["regions"]):
        ideas.append("progress as a vertical fill or a ring instead of a horizontal arrow")
    if any("vertical" in r for r in o["regions"]):
        ideas.append("energy/fluid as a segmented horizontal gauge, different side")
    ideas += ["own colour language and frame from the mod's palette (texture.py), new modid textures",
              "own translation keys under <modid>.screen.*"]
    return ideas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("--screen", required=True); ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = study(_ref.need(Path(a.root), a.id), a.screen)
    if a.json or "texture" in r:
        print(json.dumps(r, indent=2, ensure_ascii=False)); return
    sl = ", ".join(f"{s['x']},{s['y']}" for s in r["slots"])
    print(f"SCREEN: {r['screen']} ({', '.join(r['classes']) or 'not found'})")
    print(f"LAYOUT: {'x'.join(map(str, r['size']))}")
    print(f"SLOTS: {len(r['slots'])} [{sl}]" + (" + player inventory" if r["player_inventory"] else ""))
    if r["regions"]:
        print(f"WIDGETS: {' | '.join(r['regions'])}" + (f" | {r['buttons']} buttons" if r["buttons"] else ""))
    if r["interaction"]:
        print(f"INTERACTION: {', '.join(r['interaction'])}")
    if r["lang"]:
        print(f"LANG: {', '.join(r['lang'][:6])}")
    print("ORIGINAL DESIGN:\n- " + "\n- ".join(r["original_design"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
