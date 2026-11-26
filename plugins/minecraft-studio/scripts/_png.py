"""Minimal PNG read/write (RGBA 8-bit), standard library only."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

Pixel = tuple  # (r, g, b, a)


class Image:
    def __init__(self, w: int, h: int, fill: Pixel = (0, 0, 0, 0)):
        self.w, self.h = w, h
        self.px = [list(fill) for _ in range(w * h)]

    def get(self, x, y):
        return tuple(self.px[y * self.w + x])

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = list(c) if len(c) == 4 else [*c, 255]

    def save(self, path):
        raw = b"".join(b"\x00" + bytes(v for p in self.px[y * self.w:(y + 1) * self.w] for v in p)
                       for y in range(self.h))

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                               + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def load(path) -> Image:
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, plte, trns = 8, b"", None, None
    w = h = depth = ctype = 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        t, d = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if t == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", d)
            if depth != 8 or inter:
                raise ValueError("only 8-bit non-interlaced PNG supported")
        elif t == b"PLTE":
            plte = [tuple(d[i:i + 3]) for i in range(0, len(d), 3)]
        elif t == b"tRNS":
            trns = d
        elif t == b"IDAT":
            idat += d
    bpp = {6: 4, 2: 3, 0: 1, 4: 2, 3: 1}[ctype]
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    img = Image(w, h)
    for y, line in enumerate(rows):
        for x in range(w):
            s = line[x * bpp:(x + 1) * bpp]
            if ctype == 6:
                c = tuple(s)
            elif ctype == 2:
                c = (*s, 255)
            elif ctype == 0:
                c = (s[0], s[0], s[0], 255)
            elif ctype == 4:
                c = (s[0], s[0], s[0], s[1])
            else:
                r, g, b = plte[s[0]]
                c = (r, g, b, trns[s[0]] if trns and s[0] < len(trns) else 255)
            img.set(x, y, c)
    return img
