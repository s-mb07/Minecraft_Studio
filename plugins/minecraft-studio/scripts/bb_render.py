#!/usr/bin/env python3
"""Render an entity (geo.json + png) in Blockbench through its MCP plugin into ONE contact sheet.

  bb_render.py <model.geo.json> --texture <png> --out sheet.png [--poses dir] [--size 384] [--ao]
               [--url http://localhost:3000/bb-mcp]

4 views (front 3/4, side, back 3/4, top-front) + one tile per posed geo in --poses (entity_gen --pose).
Off-screen view: the user's camera is never moved. --ao bakes ambient occlusion with Mr Salmon's Baked AO
plugin on a mesh copy and writes <texture>_ao.png (see mc-entity-art). Blockbench closed -> LOOK, exit 0.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _png  # noqa: E402

H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


class MCP:
    def __init__(self, url):
        self.url, self.sid, self.n = url, None, 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "minecraft-studio", "version": "0.3"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, payload):
        h = dict(H)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), h)
        with urllib.request.urlopen(req, timeout=300) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            body = r.read().decode("utf-8", "replace")
        for line in body.splitlines():
            if line.startswith("data:"):
                body = line[5:]
        return json.loads(body) if body.strip() else {}

    def _rpc(self, method, params):
        self.n += 1
        res = self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        if "error" in res:
            raise RuntimeError(f"{method}: {res['error']}")
        return res.get("result", {})

    def call(self, tool, **args):
        res = self._rpc("tools/call", {"name": tool, "arguments": args})
        if res.get("isError"):
            raise RuntimeError(f"{tool}: {json.dumps(res)[:300]}")
        return res

    def image(self, res):
        for c in res.get("content", []):
            if c.get("type") == "image":
                return _png.loads(base64.b64decode(c["data"]))
        raise RuntimeError("no image in result")

    def js(self, code):
        res = self.call("risky_eval", code=code)
        return " ".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")


VIEWS = {  # camera position relative to the model centre (model faces -Z)
    "front34": [-1.0, 0.55, -1.25], "side": [-1.6, 0.25, 0.0], "back34": [1.1, 0.6, 1.2], "top": [-0.4, 1.5, -0.9]}


def load_model(m: MCP, geo: Path, tex: Path, name: str):
    m.call("create_project", name=name, format="geckolib_model")
    m.call("from_geo_json", geojson=str(geo.resolve()))
    m.call("create_texture", name=tex.stem, data=str(tex.resolve()))
    # apply the texture to every cube face (single-texture entity)
    m.js("const t=Texture.all[0]; Cube.all.forEach(c=>{for(const f in c.faces){c.faces[f].texture=t.uuid}}); Canvas.updateAll(); 'ok'")


AO_SETTINGS = {"shadow_alpha": 0.85, "shadow_gamma": 0.8, "ao_shadow_size": 6, "highlight_alpha": 0.35,
               "highlight_gamma": 1.4, "ao_highlight_size": 2, "samples": 400, "sample_method": "uniform",
               "simulate_ground_plane": True, "retain_texture_transparency": True}


def bake_ao(m: MCP, geo: Path, tex: Path, out_png: Path, timeout: int = 240, per_mesh: bool = False,
            settings: dict | None = None) -> bool:
    """Mr Salmon's Baked AO bakes ONE selected mesh, and GeckoLib projects forbid meshes. So: temporary Generic
    project -> import geo -> texture on every face -> cubes to meshes -> merge into one mesh (parts occlude each
    other) -> bake with the plugin's remembered settings -> read the texture back."""
    import time
    m.call("create_project", name="ms_ao_bake", format="free")
    m.call("from_geo_json", geojson=str(geo.resolve()))
    m.call("create_texture", name=tex.stem, data=str(tex.resolve()))
    m.js("const t=Texture.all[0]; Cube.all.forEach((c,i)=>{for(const f in c.faces){c.faces[f].texture=t.uuid}; c.select({ctrlOrCmd:i>0})}); 'ok'")
    m.call("trigger_action", action="convert_to_mesh", confirmDialog=True)
    if not per_mesh:
        m.js("Mesh.all.forEach((x,i)=>x.select({ctrlOrCmd:i>0})); 'ok'")
        m.call("trigger_action", action="merge_meshes", confirmDialog=True)
    form = json.dumps(settings or AO_SETTINGS)
    n = int(m.js("Mesh.all.length"))
    changed = False
    for i in range(n):  # one mesh per bake (the plugin's rule); merged = 1 pass with cross-part occlusion
        before = m.js(f"Mesh.all[{i}].select(); Texture.all[0].getDataURL().length")
        m.js("BarItems.bake_ambient_occlusion.click(); setTimeout(()=>{ if(Dialog.open){ "
             f"try{{Dialog.open.setFormValues({form})}}catch(e){{}}; Dialog.open.confirm() }} }}, 400); 'ok'")
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(2)
            if m.js("Texture.all[0].getDataURL().length") != before:
                changed = True
                time.sleep(1)
                break
    if changed:
        data = m.js("Texture.all[0].getDataURL()").strip().strip('"')
        out_png.write_bytes(base64.b64decode(data.split(",", 1)[1]))
    return changed


def snap_palette(src: Path, ao: Path):
    """Keep the AO light/shadow shape but stay pixel-art: every pixel snaps to the nearest colour of the original
    palette or one deeper shadow step of it (no new in-between shades)."""
    o, a = _png.load(src), _png.load(ao)
    pal = {o.get(x, y)[:3] for y in range(o.h) for x in range(o.w) if o.get(x, y)[3]}
    pal |= {tuple(int(v * 0.78) for v in c) for c in pal}
    pal = list(pal)
    for y in range(a.h):
        for x in range(a.w):
            r, g, b, al = a.get(x, y)
            if al:
                c = min(pal, key=lambda p: (p[0] - r) ** 2 * 3 + (p[1] - g) ** 2 * 4 + (p[2] - b) ** 2 * 2)
                a.set(x, y, (*c, al))
    a.save(ao)


def tile(m: MCP, view: str, center, radius, size):
    d = VIEWS[view]
    pos = [center[i] + d[i] * radius for i in range(3)]
    return m.image(m.call("set_camera_angle", view=m.view, position=pos, target=center, projection="perspective"))


def drop(m: MCP):
    try:  # plugin 1.10 may throw on dispose; the view is freed with the project anyway
        m.call("delete_offscreen_view", view=m.view)
    except RuntimeError:
        pass


def sheet(tiles, size, cols):
    rows = (len(tiles) + cols - 1) // cols
    out = _png.Image(cols * size, rows * size, (38, 40, 46, 255))
    for k, im in enumerate(tiles):
        ox, oy = (k % cols) * size, (k // cols) * size
        sx, sy = im.w / size, im.h / size
        s = max(sx, sy)
        for y in range(size):
            for x in range(size):
                px, py = int(x * s), int(y * s)
                if px < im.w and py < im.h:
                    c = im.get(px, py)
                    if c[3] > 0:
                        out.set(ox + x, oy + y, c)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geo"); ap.add_argument("--texture", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--poses"); ap.add_argument("--size", type=int, default=384); ap.add_argument("--ao", action="store_true")
    ap.add_argument("--per-mesh", action="store_true", help="bake each part alone (no cross-part occlusion)")
    ap.add_argument("--snap", action="store_true", help="snap AO colours back to the palette (stricter pixel art, weaker AO)")
    ap.add_argument("--url", default="http://localhost:3000/bb-mcp")
    a = ap.parse_args()
    try:
        m = MCP(a.url)
    except Exception as e:  # noqa: BLE001
        print(f"LOOK: Blockbench MCP not reachable ({e.__class__.__name__}); open Blockbench with the MCP plugin")
        return
    geo, tex = Path(a.geo), Path(a.texture)
    g = json.loads(geo.read_text(encoding="utf-8"))["minecraft:geometry"][0]
    ys = [c["origin"][1] + c["size"][1] for b in g["bones"] for c in b.get("cubes", [])]
    xs = [abs(c["origin"][0]) + c["size"][0] for b in g["bones"] for c in b.get("cubes", [])]
    center, radius = [0, max(ys) * 0.45, 0], max(max(ys), max(xs)) * 1.35
    if a.ao:
        ok = bake_ao(m, geo, tex, tex.with_name(tex.stem + "_ao.png"), per_mesh=a.per_mesh)
        if ok and a.snap:
            snap_palette(tex, tex.with_name(tex.stem + "_ao.png"))
        print(f"AO -> {tex.with_name(tex.stem + '_ao.png')}" if ok else "LOOK: AO bake timed out (texture unchanged)")
        if not ok:
            a.ao = False
    load_model(m, geo, tex.with_name(tex.stem + "_ao.png") if a.ao else tex, geo.stem)
    m.view = "ms_r0"
    m.call("create_offscreen_view", id=m.view, width=a.size, height=a.size, antialias=False, copy_view="none")
    tiles = [tile(m, v, center, radius, a.size) for v in VIEWS]
    for p in sorted(Path(a.poses).glob("*.geo.json")) if a.poses else []:
        drop(m)
        load_model(m, p, tex.with_name(tex.stem + "_ao.png") if a.ao else tex, p.stem)
        m.view = f"ms_r{len(tiles)}"
        m.call("create_offscreen_view", id=m.view, width=a.size, height=a.size, antialias=False, copy_view="none")
        tiles.append(tile(m, "front34", center, radius, a.size))
    drop(m)
    prefix = geo.name.split(".")[0]
    m.js("ModelProject.all.filter(p=>p.name.startsWith('ms_ao_bake')||p.name.startsWith('" + prefix + "')).forEach(p=>{p.saved=true; p.close(true)}); 'ok'")
    sheet(tiles, a.size, 4).save(a.out)
    print(f"PASS: contact sheet {a.out} ({len(tiles)} tiles)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
