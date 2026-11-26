#!/usr/bin/env python3
"""Generate a GeckoLib entity from a compact spec: geometry, box-UV atlas, pixel-art texture, glowmask, animations.

  entity_gen.py <spec.json> --out <mod>/src/main/resources/assets/<modid> [--pose anim@t --pose-out f.geo.json]

Writes geo/entity/<id>.geo.json, animations/entity/<id>.animation.json, textures/entity/<id>.png
(+ <id>_glowmask.png when a material is emissive). Paths match GeckoLib 4 DefaultedEntityGeoModel.

Spec (see templates/entity/cave_crawler.json):
  id, texture [w,h], light "top-front-left", materials {name: {color, pattern?: plates|scales|smooth, emissive?}},
  bones [{name, parent?, pivot, rotation?, role?, side?: -1|1, phase?: 0..1, cubes: [{origin, size, mat, inflate?}]}],
  details [{bone, face, px: [[x,y,shade|"emit"|"#hex"],...]}], animations {name: {length, loop, kind}} kinds:
  idle, walk, attack, hurt, death. Roles drive motion: body, head, jaw, antenna, tail, leg (upper), leg_lower.

Painting = method of the reference study: 4-shade hue-shifted ramps per material, light from top, rim highlight
on top edges, contact shadow on bottom rows, material pattern, sparse 2-px clusters (no single-pixel noise),
details last. Bake real ambient occlusion afterwards in Blockbench (Baked AO plugin, see mc-entity-art).
Animations are baked at 20 fps with linear keys, like the best reference rigs.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402

FPS = 20


# ---------------------------------------------------------------- colour
def hexrgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ramp(hexcol: str, n: int = 4) -> list[tuple]:
    """Dark -> light, hue-shifted: shadows drift to blue/purple, highlights to warm yellow (colour gradient method)."""
    r, g, b = [v / 255 for v in hexrgb(hexcol)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    out = []
    steps = [-0.19, -0.09, 0.0, 0.11, 0.2][:n] if n <= 5 else [i * 0.08 - 0.2 for i in range(n)]
    base_i = steps.index(0.0)
    for k, dl in enumerate(steps):
        t = (k - base_i)
        # shadows: cool materials drift to blue/purple, warm ones (skin, ivory, gold, leather) to deep red-brown;
        # violet shadows on warm colours look dirty/pink
        # never purple: cool materials keep their own hue in the shadows, warm ones drift slightly to red-brown
        warm = h < 0.17 or h > 0.92
        target = (0.02 if warm else h) if t < 0 else 0.13
        hh = h + ((target - h + 0.5) % 1 - 0.5) * min(0.25, 0.08 * abs(t))
        ss = min(1, s * (1 + 0.12 * abs(t))) if t < 0 else s * (1 - 0.08 * t)
        rr, gg, bb = colorsys.hls_to_rgb(hh % 1, max(0.02, min(0.96, l + dl)), max(0, min(1, ss)))
        out.append((round(rr * 255), round(gg * 255), round(bb * 255), 255))
    return out


def hsh(*a) -> float:
    x = 0
    for v in a:
        x = (x * 1000003 ^ int(v * 7919)) & 0xFFFFFFFF
    x = (x ^ (x >> 15)) * 2246822519 & 0xFFFFFFFF
    return ((x ^ (x >> 13)) & 0xFFFF) / 0xFFFF


# ---------------------------------------------------------------- UV
def box(size):
    dx, dy, dz = [max(1, math.ceil(v)) for v in size]
    return dx, dy, dz


def faces_of(u, v, size):
    """Blockbench/Bedrock box-UV layout -> {face: (x, y, w, h)}."""
    dx, dy, dz = box(size)
    return {"up": (u + dz, v, dx, dz), "down": (u + dz + dx, v, dx, dz),
            "east": (u, v + dz, dz, dy), "north": (u + dz, v + dz, dx, dy),
            "west": (u + dz + dx, v + dz, dz, dy), "south": (u + 2 * dz + dx, v + dz, dx, dy)}


def pack(cubes, tw, th):
    """Shelf packing of box-UV footprints, biggest first. Mirrored pairs (same size+mat, mirror=True) share a slot."""
    items = sorted(cubes, key=lambda c: -(box(c["size"])[1] + box(c["size"])[2]) * 100 - 2 * (box(c["size"])[0] + box(c["size"])[2]))
    x = y = row_h = 0
    shared = {}
    for c in items:
        dx, dy, dz = box(c["size"])
        w, h = 2 * (dx + dz), dz + dy
        key = c.get("share")
        if key and key in shared:
            c["uv"] = shared[key]; continue
        if x + w > tw:
            x, y, row_h = 0, y + row_h, 0
        if y + h > th:
            raise SystemExit(f"error: texture {tw}x{th} too small for the cubes (increase texture size)")
        c["uv"] = [x, y]
        if key:
            shared[key] = c["uv"]
        x, row_h = x + w, max(row_h, h)
    return y + row_h


# ---------------------------------------------------------------- painting
# 5-shade ramp per material: 0 deep shadow / outline, 1 shadow, 2 base, 3 light, 4 highlight.
LIGHT = {"up": 3, "north": 2, "east": 2, "west": 2, "south": 1, "down": 1}


def paint_face(img, rect, face, mat, rmp, seed, n=1, lit=False):
    """Method taken from the reference rigs (troll, golem, chest):
    - every face is framed: a 1-px darker outline, with the top edge of side faces lit (rim light);
    - broad light: lit top band, base, shadow on the lower third (no per-pixel noise);
    - material motifs are coherent shapes in model units: panel (bevelled inset), trim (bright rims),
      plates/ridges (seam + catch-light bands), grain (big low-contrast patches, never isolated dots).
    n = pixels per model unit."""
    x0, y0, w, h = [v * n for v in rect]
    pat = mat.get("pattern", "smooth")
    # Animated entities are UNLIT: the game lights the model, and light painted into the texture (bright tops,
    # dark bottoms, AO) turns wrong as soon as a limb rotates. Only static props (blocks, items) use lit=True.
    base = LIGHT[face] if lit else 2
    side = face not in ("up", "down") and lit
    for j in range(h):
        for i in range(w):
            s = base
            u, v = i // n, j // n
            wu, hu = w // n, h // n
            if side:
                if j < max(1, n // 2):
                    s = base + 1                       # rim light
                elif j >= h * 0.66:
                    s = base - 1                       # shadow on the lower third
            if pat == "panel" and wu >= 4 and hu >= 4:
                if (u == 1 and 1 <= v <= hu - 2) or (v == 1 and 1 <= u <= wu - 2):
                    s -= 1                             # groove (top/left of the inset)
                elif (u == wu - 2 and 1 <= v <= hu - 2) or (v == hu - 2 and 1 <= u <= wu - 2):
                    s += 1                             # bevel catch-light (bottom/right)
            elif pat == "trim":
                if v == 0 or v == hu - 1:
                    s += 1
                elif v == 1 or v == hu - 2:
                    s -= 1
            elif pat == "plates":
                along = v if hu >= wu else u           # ridges across the long axis (horns, tails)
                if along % 3 == 0 and along > 0:
                    s -= 1                             # ridge seam every 3 units (closer = zebra stripes)
            elif pat == "grain" and 0 < i < w - 1 and 0 < j < h - 1:
                if hsh(seed, (x0 + i) // n, (y0 + j) // n) < 0.1 and s == base:
                    s -= 1                             # sparse 1-unit cells, only on the flat base area
            # frame: 1-px outline (keeps the lit top edge on side faces)
            if w > 2 and h > 2 and (i in (0, w - 1) or j == h - 1 or (j == 0 and not side)):
                s = min(s, base - 1)
            img.set(x0 + i, y0 + j, rmp[max(0, min(4, s))])


def build(spec: dict, root: Path):
    tw, th = spec.get("texture", [64, 64])
    n = int(spec.get("density", 1))
    mats = spec["materials"]
    ramps = {k: ramp(v["color"], 5) for k, v in mats.items()}
    cubes = [dict(c, bone=b["name"], idx=i) for b in spec["bones"] for i, c in enumerate(b.get("cubes", []))]
    # Box UV needs whole-number sizes: a 2.5-wide face gets a 3-px UV strip, so Blockbench/GeckoLib show seams
    # and see-through slivers. Round each size (min 1) and keep the cube centred where it was.
    for c in cubes:
        size = [max(1, round(v)) for v in c["size"]]
        if size != list(c["size"]):
            c["origin"] = [c["origin"][k] + (c["size"][k] - size[k]) / 2 for k in range(3)]
            c["size"] = size
    while True:  # grow the atlas (height, then width) until every box-UV footprint fits
        try:
            used = pack(cubes, tw, th)
            break
        except SystemExit:
            if tw >= 1024:
                raise
            tw, th = (tw, th * 2) if th <= tw else (tw * 2, th)
    spec["texture"] = [tw, th]
    img, glow = _png.Image(tw * n, th * n), _png.Image(tw * n, th * n)
    glow_used = False
    for c in cubes:
        rect = faces_of(*c["uv"], c["size"])
        group = spec.get("paint_group")
        for f, r in rect.items():
            if group and c["mat"] not in group:   # texture group by group: the rest stays neutral grey
                for j in range(r[3] * n):
                    for i in range(r[2] * n):
                        img.set(r[0] * n + i, r[1] * n + j, (128, 128, 128, 255))
                continue
            paint_face(img, r, f, mats[c["mat"]], ramps[c["mat"]], sum(map(ord, c["bone"])) % 997 + c["idx"], n,
                       lit=spec.get("lighting") == "lit")
            if mats[c["mat"]].get("emissive"):
                glow_used = True
                for j in range(r[3] * n):
                    for i in range(r[2] * n):
                        glow.set(r[0] * n + i, r[1] * n + j, img.get(r[0] * n + i, r[1] * n + j))
    by_bone = {}
    for c in cubes:
        by_bone.setdefault(c["bone"], c)
    for d in spec.get("details", []):
        c = next(x for x in cubes if x["bone"] == d["bone"] and x["idx"] == d.get("cube", 0))
        fx, fy, fw, fh = faces_of(*c["uv"], c["size"])[d["face"]]
        rm = ramps[d.get("mat", c["mat"])]
        for px in d["px"]:
            x, y, s = px
            if not (0 <= x < fw and 0 <= y < fh):
                continue
            emit = s == "emit"
            col = (*hexrgb(mats[d.get("emit_mat", "eye")]["color"] if emit else s), 255) if emit or str(s).startswith("#") else rm[int(s)]
            for yy in range(n):           # a detail pixel = one model unit, whatever the density
                for xx in range(n):
                    X, Y = (fx + x) * n + xx, (fy + y) * n + yy
                    c2 = col
                    if emit and n > 1 and (xx in (0, n - 1) or yy in (0, n - 1)):
                        c2 = tuple(int(v * 0.8) for v in col[:3]) + (255,)  # soft glow edge at high density
                    img.set(X, Y, c2)
                    if emit:
                        glow.set(X, Y, c2); glow_used = True
    # geometry
    bones = []
    parent = {b["name"]: b.get("parent") for b in spec["bones"]}

    def depth(n):
        d = 0
        while parent.get(n):
            n, d = parent[n], d + 1
        return d
    for b in spec["bones"]:
        gb = {"name": b["name"], "pivot": b.get("pivot", [0, 0, 0])}
        if b.get("parent"):
            gb["parent"] = b["parent"]
        if b.get("rotation"):
            gb["rotation"] = b["rotation"]
        cs = [c for c in cubes if c["bone"] == b["name"]]
        if cs:
            gb["cubes"] = []
            for c in sorted(cs, key=lambda c: c["idx"]):
                gc = {"origin": c["origin"], "size": c["size"], "uv": c["uv"]}
                # Anti-overlap: chained segments (upper/lower limb, body/plate) share face planes at the joints
                # and z-fight. Each hierarchy level is 0.01 thinner and each extra cube of a bone 0.005 larger,
                # so no two touching faces are coplanar. Invisible, and inflate leaves the UVs untouched.
                auto = round(-0.01 * depth(b["name"]) + 0.005 * c["idx"], 3)
                if "inflate" not in c and auto:
                    c["inflate"] = auto
                for k in ("inflate", "mirror", "rotation", "pivot"):
                    if c.get(k):
                        gc[k] = c[k]
                gb["cubes"].append(gc)
        bones.append(gb)
    xs = [abs(v) for c in cubes for v in (c["origin"][0], c["origin"][0] + c["size"][0], c["origin"][2], c["origin"][2] + c["size"][2])]
    ys = [c["origin"][1] + c["size"][1] for c in cubes]
    geo = {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": f"geometry.{spec['id']}", "texture_width": tw, "texture_height": th,
                        "visible_bounds_width": math.ceil(max(xs) * 2 / 16) + 1, "visible_bounds_height": math.ceil(max(ys) / 16) + 1,
                        "visible_bounds_offset": [0, math.ceil(max(ys) / 32), 0]},
        "bones": bones}]}
    return geo, img, (glow if glow_used else None), used


# ---------------------------------------------------------------- animation
def smooth(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t * t * (3 - 2 * t)


def env(t, keys):
    """Piecewise smoothstep through [(time, value), ...]."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return smooth(v0, v1, (t - t0) / (t1 - t0 or 1))
    return keys[-1][1]


def motion(kind: str, b: dict, t: float, L: float, spec: dict):
    """(rotation [x,y,z] deg, position [x,y,z] px) of a bone at time t."""
    role, s, ph = b.get("role"), b.get("side", 1), b.get("phase", 0.0)
    p = 2 * math.pi * (t / L + ph)
    w = 2 * math.pi * t / L
    rot, pos = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    drag = b.get("drag", 0.0)  # seconds of lag behind the parent motion (overlap)
    if kind == "walk":
        if role == "leg":
            rot[1] = 22 * math.sin(p) * s
            rot[2] = s * 16 * max(0.0, math.cos(p))          # lift during the forward swing
        elif role == "leg_lower":
            rot[2] = -s * 9 * max(0.0, math.cos(p))
        elif role == "body":
            pos[1] = 0.35 * math.sin(2 * w)                  # bob at twice the step frequency
            rot[2] = 1.5 * math.sin(w)
        elif role == "head":
            rot[1] = -2.5 * math.sin(w)
        elif role in ("antenna", "tail"):
            rot[0] = 7 * math.sin(w - 2 * math.pi * drag / L * 4)
            rot[1] = 4 * math.sin(w - 0.8) * s
        elif role == "jaw":
            rot[1] = s * 3 * max(0.0, math.sin(2 * w))
    elif kind == "idle":
        if role == "body":
            pos[1] = 0.25 * math.sin(w)
            rot[0] = 0.8 * math.sin(w)
        elif role == "head":
            rot[1] = 6 * math.sin(w + 0.5) * math.sin(w * 0.5) ** 2
            rot[0] = 2 * math.sin(2 * w)
        elif role in ("antenna", "tail"):
            rot[0] = 9 * math.sin(2 * w + (0 if s > 0 else 1.3) - drag * 6)
            rot[1] = 6 * math.sin(w + (0.7 if s > 0 else 0)) * s
        elif role == "jaw":
            pulse = max(0.0, math.sin(4 * w)) ** 8 + max(0.0, math.sin(4 * w + 0.6)) ** 8
            rot[1] = -s * 12 * pulse
        elif role == "leg":
            rot[1] = 2 * math.sin(w + ph * 6) * s
    elif kind == "attack":
        if role == "body":
            rot[0] = env(t, [(0, 0), (0.3 * L, -13), (0.45 * L, 9), (0.75 * L, 2), (L, 0)])
            pos[2] = env(t, [(0, 0), (0.3 * L, 1.5), (0.45 * L, -2.5), (L, 0)])
            pos[1] = env(t, [(0, 0), (0.3 * L, 1.0), (0.45 * L, -0.5), (L, 0)])
        elif role == "head":
            rot[0] = env(t, [(0, 0), (0.3 * L, -10), (0.45 * L, 16), (0.8 * L, 0)])
        elif role == "jaw":
            rot[1] = -s * env(t, [(0, 0), (0.3 * L, 28), (0.42 * L, 30), (0.47 * L, -6), (0.7 * L, 0)])
        elif role in ("antenna", "tail"):
            rot[0] = env(t, [(0, 0), (0.33 * L, -18), (0.5 * L, 14), (0.85 * L, 0)])
        elif role == "leg" and b.get("front"):
            rot[2] = s * env(t, [(0, 0), (0.3 * L, 30), (0.45 * L, -10), (L, 0)])
            rot[1] = s * env(t, [(0, 0), (0.3 * L, 15), (0.45 * L, -12), (L, 0)])
    elif kind == "hurt":
        decay = math.exp(-5 * t / L)
        if role == "body":
            rot[2] = 9 * math.sin(28 * t) * decay
            pos[1] = 0.8 * decay * (1 - math.exp(-30 * t))
        elif role == "leg":
            rot[2] = s * 14 * decay * (1 - math.exp(-30 * t))
        elif role == "head":
            rot[0] = -12 * decay * (1 - math.exp(-30 * t))
        elif role == "jaw":
            rot[1] = -s * 20 * decay
    elif kind == "death":
        h = spec.get("height", 8)
        if role == "root":
            rot[2] = env(t, [(0, 0), (0.25 * L, 12), (0.6 * L, 180), (0.7 * L, 172), (0.8 * L, 180)])
            pos[1] = env(t, [(0, 0), (0.25 * L, 0), (0.6 * L, h), (L, h)])
        elif role == "leg":
            curl = env(t, [(0, 0), (0.5 * L, -35), (L, -45)])
            twitch = 6 * math.sin(30 * t) * max(0.0, (t - 0.6 * L) / (0.4 * L)) * math.exp(-4 * max(0.0, t - 0.6 * L))
            rot[2] = s * (curl + twitch)
        elif role == "leg_lower":
            rot[2] = s * env(t, [(0, 0), (0.6 * L, -40), (L, -50)])
        elif role in ("antenna", "jaw"):
            rot[0] = env(t, [(0, 0), (0.6 * L, -20), (L, -25)])
    k = b.get("_amp", {}).get(kind, 1.0)  # damping set by fix_collisions
    if role != "root":
        rot = [v * k for v in rot]
        pos = [v * k for v in pos]
    return rot, pos


def animations(spec: dict) -> dict:
    out = {}
    for name, a in spec.get("animations", {}).items():
        L, kind = a["length"], a.get("kind", name)
        loop = {"loop": True, "once": False, "hold": "hold_on_last_frame"}[a.get("loop", "loop")]
        bones = {}
        n = max(2, round(L * FPS))
        for b in spec["bones"]:
            if not b.get("role"):
                continue
            rk, pk = {}, {}
            for i in range(n + 1):
                t = round(i * L / n, 4)
                r, p = motion(kind, b, t, L, spec)
                rk[f"{t:g}"] = [round(v, 2) for v in r]
                pk[f"{t:g}"] = [round(v, 3) for v in p]
            ch = {}
            if any(any(v) for v in rk.values()):
                ch["rotation"] = rk
            if any(any(v) for v in pk.values()):
                ch["position"] = pk
            if ch:
                bones[b["name"]] = ch
        out[f"animation.{spec['id']}.{name}"] = {"loop": loop, "animation_length": L, "bones": bones}
    return {"format_version": "1.8.0", "animations": out, "geckolib_format_version": 2}


# ---------------------------------------------------------------- orientation: never write raw rotation signs
# Conventions MEASURED in Blockbench for .geo.json (GeckoLib) - see mc-entity-art "Orientation":
#   the entity faces -Z (front); geo +X is the CHARACTER'S LEFT (shown on the viewer's right in a front view);
#   +rot Z lowers the outer end of a part pointing to +X; +rot X lowers the front end (raises the back end);
#   +rot Y swings a +X part towards the front.
# Write specs with these helpers and declare intent with "expect"; check_orientation() verifies it.
LEFT, RIGHT = "left", "right"


def out_x(side: str) -> int:
    """Sign of X pointing outwards on the character's side."""
    return 1 if side == LEFT else -1


def raise_outer(side: str, deg: float) -> list:
    """Z rotation lifting the outer end of a sideways part (brow outer end up = angry, horn tips up)."""
    return [0, 0, -deg * out_x(side)]


def tip_front_down(deg: float) -> list:
    """X rotation: positive lowers parts pointing to the front and raises parts pointing back."""
    return [deg, 0, 0]


def swing_forward(side: str, deg: float) -> list:
    """Y rotation sending the outer end of a sideways part towards the front (negative = towards the back)."""
    return [0, deg * out_x(side), 0]


def combine(*rots) -> list:
    return [round(sum(r[i] for r in rots), 3) for i in range(3)]


def mirror_cube(c: dict) -> dict:
    """The same cube on the other side (x -> -x). Rotations about Y and Z flip sign, X does not."""
    o, s = c["origin"], c["size"]
    m = dict(c, origin=[-(o[0] + s[0]), o[1], o[2]])
    if c.get("rotation"):
        r, p = c["rotation"], c.get("pivot", [0, 0, 0])
        m["rotation"], m["pivot"] = [r[0], -r[1], -r[2]], [-p[0], p[1], p[2]]
    return m


def check_orientation(spec: dict, geo: dict) -> list:
    """FAIL lines for bones whose declared "expect": {"tip": [...]} (out, in, up, down, front, back, left, right)
    does not match the rest pose: tip = cube corner farthest from the bone pivot, computed with the measured FK."""
    want = {b["name"]: b["expect"] for b in spec["bones"] if b.get("expect")}
    if not want:
        return []
    R = {}
    for bn, ctr, ax, h in boxes(geo):
        if bn in want:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        R.setdefault(bn, []).append([ctr[i] + ax[0][i] * h[0] * sx + ax[1][i] * h[1] * sy + ax[2][i] * h[2] * sz for i in range(3)])
    piv = {}
    for b in geo["minecraft:geometry"][0]["bones"]:
        piv[b["name"]] = b.get("pivot", [0, 0, 0])
    # world pivot of each bone = its pivot transformed by the parent chain
    tf_bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}

    def world(name, p):
        b = tf_bones[name]
        while b.get("parent"):
            par = tf_bones[b["parent"]]
            Rm = _rot(*par.get("rotation", [0, 0, 0]))
            pv = par.get("pivot", [0, 0, 0])
            q = _mv(Rm, [p[i] - pv[i] for i in range(3)])
            p = [q[i] + pv[i] for i in range(3)]
            b = par
        return p
    fails = []
    for bn, exp in want.items():
        if bn not in R:
            continue
        pw = world(bn, piv[bn])
        tip = max(R[bn], key=lambda c: sum((c[i] - pw[i]) ** 2 for i in range(3)))
        d = [tip[i] - pw[i] for i in range(3)]
        L = max(1e-6, max(abs(v) for v in d))
        side = 1 if pw[0] > 0.01 else -1 if pw[0] < -0.01 else (1 if d[0] > 0 else -1)
        ok = {"up": d[1] > 0.2 * L, "down": d[1] < -0.2 * L, "front": d[2] < -0.2 * L, "back": d[2] > 0.2 * L,
              "out": d[0] * side > 0.2 * L, "in": d[0] * side < -0.2 * L,
              "left": d[0] > 0.2 * L, "right": d[0] < -0.2 * L}
        bad = [e for e in exp.get("tip", []) if not ok[e]]
        if bad:
            fails.append(f"{bn}: tip should point {'+'.join(exp['tip'])}, it doesn't ({', '.join(bad)}); "
                         f"tip offset x{d[0]:+.1f} y{d[1]:+.1f} z{d[2]:+.1f} (front=-z, character left=+x)")
    return fails


# ---------------------------------------------------------------- collisions during animation
def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def _rot(rx, ry, rz):
    """Rotation matrix of a Bedrock/GeckoLib geo rotation, in geo coordinates (order Z, Y, X).
    MEASURED in Blockbench (probe cubes): geo X is mirrored vs Blockbench and X/Y rotations are negated on import,
    so in geo space a rotation acts as the standard right-handed one with angles (-rx, +ry, -rz)."""
    rx, rz = -rx, -rz

    def m(a, axis):
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        return {"x": [[1, 0, 0], [0, c, -s_], [0, s_, c]], "y": [[c, 0, s_], [0, 1, 0], [-s_, 0, c]],
                "z": [[c, -s_, 0], [s_, c, 0], [0, 0, 1]]}[axis]
    return _mm(_mm(m(rz, "z"), m(ry, "y")), m(rx, "x"))


def boxes(geo: dict, frame: dict | None = None) -> list:
    """World oriented boxes (bone, centre, axes, half sizes) for a frame {bone: (rot, pos)}."""
    frame = frame or {}
    bones = geo["minecraft:geometry"][0]["bones"]
    by = {b["name"]: b for b in bones}
    tf = {}

    def T(name):
        if name in tf:
            return tf[name]
        b = by[name]
        r0 = b.get("rotation", [0, 0, 0])
        ar, ap = frame.get(name, ([0, 0, 0], [0, 0, 0]))
        R = _rot(*(r0[i] + ar[i] for i in range(3)))
        pv = b.get("pivot", [0, 0, 0])
        PR, PT = T(b["parent"]) if b.get("parent") else ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
        WR = _mm(PR, R)   # x' = PR (R (x - pv) + pv + pos) + PT
        off = _mv(PR, [pv[i] + ap[i] for i in range(3)])
        rp = _mv(WR, pv)
        tf[name] = (WR, [off[i] + PT[i] - rp[i] for i in range(3)])
        return tf[name]
    out = []
    for b, c, M, ctr in world_cubes(geo, T):
        inf = c.get("inflate", 0)
        out.append((b["name"], ctr, [[M[r][k] for r in range(3)] for k in range(3)],
                    [max(0.01, c["size"][i] / 2 + inf) for i in range(3)]))
    return out


def world_cubes(geo: dict, T=None):
    """(bone, cube, world rotation matrix, world centre) for every cube, including cube-level rotations."""
    bones = geo["minecraft:geometry"][0]["bones"]
    if T is None:
        by = {b["name"]: b for b in bones}
        tf = {}

        def T(name):  # noqa: F811 - rest pose transform
            if name in tf:
                return tf[name]
            b = by[name]
            R = _rot(*b.get("rotation", [0, 0, 0]))
            pv = b.get("pivot", [0, 0, 0])
            PR, PT = T(b["parent"]) if b.get("parent") else ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
            WR = _mm(PR, R)
            off = _mv(PR, pv)
            rp = _mv(WR, pv)
            tf[name] = (WR, [off[i] + PT[i] - rp[i] for i in range(3)])
            return tf[name]
    for b in bones:
        WR, WT = T(b["name"])
        for c in b.get("cubes", []):
            lc = [c["origin"][i] + c["size"][i] / 2 for i in range(3)]
            M = WR
            if c.get("rotation") and any(c["rotation"]):
                Rc, pc = _rot(*c["rotation"]), c.get("pivot", [0, 0, 0])
                q = _mv(Rc, [lc[i] - pc[i] for i in range(3)])
                lc = [q[i] + pc[i] for i in range(3)]
                M = _mm(WR, Rc)
            w = _mv(WR, lc)
            yield b, c, M, [w[i] + WT[i] for i in range(3)]


def _euler_geo(M) -> list:
    """Inverse of _rot: world matrix -> geo rotation [x, y, z] (degrees)."""
    ry = math.degrees(math.asin(max(-1.0, min(1.0, -M[2][0]))))
    rx = math.degrees(math.atan2(M[2][1], M[2][2]))
    rz = math.degrees(math.atan2(M[1][0], M[0][0]))
    return [round(-rx, 4), round(ry, 4), round(-rz, 4)]


def rigid_clusters(spec: dict) -> dict:
    """bone -> cluster name. A bone that animates (has a role) starts its own rigid block; decorative children
    (horns, brows, armour pieces without a role) belong to the block of their nearest animated ancestor."""
    by = {b["name"]: b for b in spec["bones"]}
    out = {}
    for b in spec["bones"]:
        n = b["name"]
        while n and not (by[n].get("role") or by[n].get("animated")):
            n = by[n].get("parent")
        out[b["name"]] = n or "root"
    return out


def explode_geo(geo: dict, spec: dict, gap: float = 48) -> dict:
    """Same cubes and UVs, every rigid block moved far from the others (for AO without cross-part shadows).
    Each cube becomes a top-level bone carrying its world rotation, so parent rotations can't pull blocks back."""
    cl = rigid_clusters(spec)
    names = sorted(set(cl.values()), key=list(cl.values()).index)
    offset = {n: [(k % 5) * gap, 0, (k // 5) * gap] for k, n in enumerate(names)}
    g = json.loads(json.dumps(geo))
    desc = g["minecraft:geometry"][0]
    bones = []
    for k, (b, c, M, ctr) in enumerate(world_cubes(geo)):
        o = offset[cl.get(b["name"], "root")]
        p = [ctr[i] + o[i] for i in range(3)]
        cube = {"origin": [p[i] - c["size"][i] / 2 for i in range(3)], "size": c["size"], "uv": c["uv"]}
        if c.get("inflate"):
            cube["inflate"] = c["inflate"]
        if c.get("mirror"):
            cube["mirror"] = True
        bones.append({"name": f"{b['name']}__{k}", "pivot": p, "rotation": _euler_geo(M), "cubes": [cube]})
    desc["bones"] = bones
    desc["description"]["visible_bounds_width"] = 64
    return g


def _sat(a, b, margin=0.05) -> bool:
    """Oriented-box overlap (separating axis theorem); the margin ignores grazing contact."""
    _, ca, A, ea = a
    _, cb, B, eb = b
    d = [cb[i] - ca[i] for i in range(3)]
    axes = A + B + [[u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]] for u in A for v in B]
    for ax in axes:
        n = math.sqrt(sum(x * x for x in ax))
        if n < 1e-6:
            continue
        ax = [x / n for x in ax]
        ra = sum(ea[i] * abs(sum(A[i][k] * ax[k] for k in range(3))) for i in range(3))
        rb = sum(eb[i] * abs(sum(B[i][k] * ax[k] for k in range(3))) for i in range(3))
        if abs(sum(d[k] * ax[k] for k in range(3))) > ra + rb - margin:
            return False
    return True


def collisions(spec: dict, geo: dict, anim: dict, step: int = 2) -> list:
    """(animation, time, boneA, boneB) for parts that pass through each other during an animation although they
    don't touch at rest (touching at rest = attached by design). Parent/child joints are ignored."""
    parent = {b["name"]: b.get("parent") for b in spec["bones"]}
    rest = boxes(geo)
    attached = {frozenset((a[0], b[0])) for i, a in enumerate(rest) for b in rest[i + 1:] if _sat(a, b)}
    hits = []
    for name, a in anim["animations"].items():
        keys = []
        for ch in a["bones"].values():
            keys = sorted((ch.get("rotation") or ch.get("position")).keys(), key=float)
            break
        for t in keys[::step]:
            frame = {bn: (ch.get("rotation", {}).get(t, [0, 0, 0]), ch.get("position", {}).get(t, [0, 0, 0]))
                     for bn, ch in a["bones"].items()}
            bx = boxes(geo, frame)
            for i, p in enumerate(bx):
                for q in bx[i + 1:]:
                    if p[0] == q[0] or parent.get(p[0]) == q[0] or parent.get(q[0]) == p[0]:
                        continue
                    if frozenset((p[0], q[0])) in attached:
                        continue
                    if _sat(p, q):
                        hits.append((name.split(".")[-1], float(t), p[0], q[0]))
    return hits


def fix_collisions(spec: dict, geo: dict, rounds: int = 5):
    """Damp the colliding bones' motion (x0.8 per round, per animation) until no part passes through another.
    Returns (animations, remaining hits). The root's death roll is never damped."""
    anim = animations(spec)
    by = {b["name"]: b for b in spec["bones"]}
    for _ in range(rounds):
        hits = collisions(spec, geo, anim)
        if not hits:
            return anim, []
        changed = False
        for kind, _t, a, b in hits:
            for n in (a, b):
                if by[n].get("role") and by[n]["role"] not in ("root", "body"):
                    amp = by[n].setdefault("_amp", {})
                    new = max(0.5, round(amp.get(kind, 1.0) * 0.85, 3))  # floor: never kill the motion
                    changed |= new != amp.get(kind, 1.0)
                    amp[kind] = new
        if not changed:
            break  # what is left needs a spec change (spacing between limbs, phase, rest pose)
        anim = animations(spec)
    return anim, collisions(spec, geo, anim)


def pose(geo: dict, anim: dict, name: str, t: float) -> dict:
    """Geometry with an animation frame baked into bone rotations (for static renders of key poses)."""
    g = json.loads(json.dumps(geo))
    a = next(v for k, v in anim["animations"].items() if k.endswith("." + name))
    for b in g["minecraft:geometry"][0]["bones"]:
        ch = a["bones"].get(b["name"], {})
        for kind in ("rotation", "position"):
            if kind in ch:
                keys = sorted(ch[kind], key=float)
                k = min(keys, key=lambda x: abs(float(x) - t))
                v = ch[kind][k]
                if kind == "rotation":
                    b["rotation"] = [round(b.get("rotation", [0, 0, 0])[i] + v[i], 2) for i in range(3)]
                elif any(v):
                    b["pivot"] = [b["pivot"][i] + v[i] for i in range(3)]
                    for c in b.get("cubes", []):
                        c["origin"] = [c["origin"][i] + v[i] for i in range(3)]
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("--out", required=True)
    ap.add_argument("--pose", action="append", default=[], help="anim@time, e.g. walk@0.25 (writes posed geo files)")
    ap.add_argument("--pose-dir")
    ap.add_argument("--group", help="texture only these materials (comma list); others stay flat grey for review")
    ap.add_argument("--density", type=int, help="pixels per model unit (1 = vanilla look; 2-4 = room for real shading/AO)")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    if a.density:
        spec["density"] = a.density
    if a.group:
        spec["paint_group"] = a.group.split(",")
    out = Path(a.out)
    geo, img, glow, used = build(spec, out)
    for msg in check_orientation(spec, geo):
        print(f"  [FAIL] orientation {msg}")
    anim, left = fix_collisions(spec, geo)
    damped = {b["name"]: b["_amp"] for b in spec["bones"] if b.get("_amp")}
    i = spec["id"]
    (out / "geo/entity").mkdir(parents=True, exist_ok=True)
    (out / "animations/entity").mkdir(parents=True, exist_ok=True)
    (out / f"geo/entity/{i}.geo.json").write_text(json.dumps(geo, indent=1) + "\n", encoding="utf-8")
    (out / f"animations/entity/{i}.animation.json").write_text(json.dumps(anim, separators=(",", ":")) + "\n", encoding="utf-8")
    img.save(out / f"textures/entity/{i}.png")
    if glow:
        glow.save(out / f"textures/entity/{i}_glowmask.png")
    for pz in a.pose:
        name, t = pz.split("@")
        d = Path(a.pose_dir or out / "_poses")
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{i}_{name}_{t}.geo.json").write_text(json.dumps(pose(geo, anim, name, float(t))), encoding="utf-8")
    nb = sum(1 for b in geo["minecraft:geometry"][0]["bones"])
    nc = sum(len(b.get("cubes", [])) for b in geo["minecraft:geometry"][0]["bones"])
    print(f"ENTITY {i}: {nc} cubes, {nb} bones, texture {img.w}x{img.h} ({used}px rows used), "
          f"{len(anim['animations'])} animations{', glowmask' if glow else ''}")
    if damped:
        print("  collisions fixed by damping: " + ", ".join(f"{k} {v}" for k, v in damped.items()))
    for kind, t, a_, b_ in left[:5]:
        print(f"  [LOOK] {kind} @ {t}s: {a_} passes through {b_} (change phase or rest pose in the spec)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
