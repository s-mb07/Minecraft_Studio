#!/usr/bin/env python3
"""Pixel-art textures for mods and resource packs (16x16 by default). Deterministic (seeded).

  texture.py gen <kind> <out.png> --color "#7a4fd6" [--size 16] [--seed 1]
       kinds: block (noisy full block), ore (stone + ore specks), gem, shard, ingot, dust, rod, plank
  texture.py ramp "#7a4fd6" [--steps 5]                 # print a dark->light palette (hex)
  texture.py recolor <in.png> <out.png> --color "#d64f4f" # keep shading, change hue/saturation
  texture.py preview <in.png> <out.png> [--scale 8]      # nearest-neighbour upscale to look at
  texture.py strip <out.png> <frame1.png> <frame2.png> ... # vertical animation strip (+ .mcmeta)

Pixel-art rules applied: hard edges, a 4-5 colour ramp per material, light from top-left, dark outline on items.
These are starting points: refine in Blockbench (paint mode) or your editor.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _png import Image, load  # noqa: E402


def hex2rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(c[:3])


def ramp(base, steps=5):
    """Dark -> light ramp with a hue shift (shadows cooler, highlights warmer): classic pixel-art palette."""
    r, g, b = [v / 255 for v in base]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    out = []
    for i in range(steps):
        t = i / (steps - 1) - 0.5           # -0.5 .. 0.5
        hh = (h - t * 0.06) % 1.0
        ll = min(0.92, max(0.08, l + t * 0.55))
        ss = min(1.0, max(0.0, s * (1 - abs(t) * 0.35)))
        out.append(tuple(round(v * 255) for v in colorsys.hls_to_rgb(hh, ll, ss)) + (255,))
    return out


def gen(kind: str, color, size=16, seed=1) -> Image:
    rnd = random.Random(f"{kind}{seed}{color}")
    pal = ramp(color)
    img = Image(size, size)
    s = size / 16

    def shade_at(x, y):  # light from top-left
        v = 2 + (1 if x + y < size * 0.6 else 0) - (1 if x + y > size * 1.4 else 0)
        return max(0, min(4, v + rnd.choice((-1, 0, 0, 0, 1))))

    if kind in ("block", "plank", "ore"):
        base = pal if kind != "ore" else ramp((125, 125, 125))
        for y in range(size):
            for x in range(size):
                v = shade_at(x, y)
                if kind == "plank" and y % max(1, int(4 * s)) == 0:
                    v = 0
                img.set(x, y, base[v])
        if kind == "ore":
            for _ in range(int(5 * s * s)):
                cx, cy = rnd.randrange(1, size - 2), rnd.randrange(1, size - 2)
                for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    if rnd.random() < 0.8:
                        img.set(cx + dx, cy + dy, pal[3 if dy == 0 else 1])
                img.set(cx, cy, pal[4])
        return img

    # items: build a mask, then shade + outline
    mask = set()
    c = size / 2
    if kind == "gem":
        for y in range(size):
            for x in range(size):
                if abs(x - c + 0.5) + abs(y - c + 0.5) * 1.1 < c * 0.8:
                    mask.add((x, y))
    elif kind == "shard":
        for y in range(size):
            for x in range(size):
                d = abs((x - y)) * 1.0
                if d < 2.2 * s and 2 * s <= x + y <= 28 * s:
                    mask.add((x, y))
    elif kind == "ingot":
        top, bottom = int(6 * s), int(11 * s)
        for y in range(top, bottom):
            inset = (bottom - 1 - y) // 2  # trapezoid: narrower on top
            for x in range(int(2 * s) + inset, int(14 * s) - inset):
                mask.add((x, y))
    elif kind == "dust":
        for _ in range(int(40 * s * s)):
            x = int(c + rnd.gauss(0, size / 6))
            y = int(c + 2 * s + rnd.gauss(0, size / 9))
            if 0 < x < size - 1 and 0 < y < size - 1:
                mask.add((x, y))
    elif kind == "rod":
        for i in range(int(2 * s), int(14 * s)):
            mask.add((i, size - 1 - i))
            mask.add((i + 1, size - 1 - i))
    else:
        raise SystemExit(f"unknown kind {kind}")
    for (x, y) in mask:
        edge_light = (x - 1, y) not in mask or (x, y - 1) not in mask
        edge_dark = (x + 1, y) not in mask or (x, y + 1) not in mask
        v = 4 if edge_light else 1 if edge_dark else shade_at(x, y)
        img.set(x, y, pal[v])
    outline = ramp(color)[0]
    outline = tuple(max(0, int(v * 0.45)) for v in outline[:3]) + (255,)
    for (x, y) in list(mask):
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in mask and img.get(nx, ny)[3] == 0 if 0 <= nx < size and 0 <= ny < size else False:
                img.set(nx, ny, outline)
    return img


def recolor(img: Image, color) -> Image:
    th, _, ts = colorsys.rgb_to_hls(*[v / 255 for v in color])
    out = Image(img.w, img.h)
    for y in range(img.h):
        for x in range(img.w):
            r, g, b, a = img.get(x, y)
            _, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            nr, ng, nb = colorsys.hls_to_rgb(th, l, max(s, ts * 0.85))
            out.set(x, y, (round(nr * 255), round(ng * 255), round(nb * 255), a))
    return out


def preview(img: Image, scale: int) -> Image:
    out = Image(img.w * scale, img.h * scale)
    for y in range(out.h):
        for x in range(out.w):
            out.set(x, y, img.get(x // scale, y // scale))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("kind"); g.add_argument("out"); g.add_argument("--color", required=True)
    g.add_argument("--size", type=int, default=16); g.add_argument("--seed", type=int, default=1)
    r = sub.add_parser("ramp"); r.add_argument("color"); r.add_argument("--steps", type=int, default=5)
    rc = sub.add_parser("recolor"); rc.add_argument("inp"); rc.add_argument("out"); rc.add_argument("--color", required=True)
    p = sub.add_parser("preview"); p.add_argument("inp"); p.add_argument("out"); p.add_argument("--scale", type=int, default=8)
    st = sub.add_parser("strip"); st.add_argument("out"); st.add_argument("frames", nargs="+")
    st.add_argument("--frametime", type=int, default=2)
    a = ap.parse_args()
    if a.cmd == "gen":
        gen(a.kind, hex2rgb(a.color), a.size, a.seed).save(a.out)
        print(f"wrote {a.out}")
    elif a.cmd == "ramp":
        print(" ".join(rgb2hex(c) for c in ramp(hex2rgb(a.color), a.steps)))
    elif a.cmd == "recolor":
        recolor(load(a.inp), hex2rgb(a.color)).save(a.out)
        print(f"wrote {a.out}")
    elif a.cmd == "preview":
        preview(load(a.inp), a.scale).save(a.out)
        print(f"wrote {a.out}")
    elif a.cmd == "strip":
        frames = [load(f) for f in a.frames]
        w = frames[0].w
        out = Image(w, w * len(frames))
        for i, f in enumerate(frames):
            for y in range(w):
                for x in range(w):
                    out.set(x, i * w + y, f.get(x, y))
        out.save(a.out)
        Path(a.out + ".mcmeta").write_text(json.dumps({"animation": {"frametime": a.frametime}}) + "\n")
        print(f"wrote {a.out} (+.mcmeta, {len(frames)} frames)")


if __name__ == "__main__":
    main()
