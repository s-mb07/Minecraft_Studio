#!/usr/bin/env python3
"""Modrinth tooling for Minecraft Studio.

Commands
  search   <query> --mc 1.21.1 --loader fabric [--type mod|resourcepack|shader|datapack] [--limit 10]
  info     <slug>  --mc 1.21.1 --loader fabric
  resolve  [slug ...] [--file mods.txt] --mc 1.21.1 --loader fabric --out pack.lock.json [--name NAME]
  audit    pack.lock.json [--json]
  download pack.lock.json --dest DIR [--side client|server]
  loader-version --mc 1.21.1 --loader neoforge

mods.txt format: one slug per line; '# comment' allowed; 'slug@version_number' pins a version;
a line starting with 'rp:' / 'shader:' / 'dp:' is a resource pack / shaderpack / datapack.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (LOADERS, MODRINTH_API, Report, die, download, file_hashes, http_json,  # noqa: E402
                     java_for, load_json, save_json)

TYPE_FOLDER = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks", "datapack": "datapacks"}
TYPE_PREFIX = {"rp:": "resourcepack", "shader:": "shader", "dp:": "datapack"}

# Groups of mods that usually overlap. Two entries from the same group => LOOK (not FAIL: sometimes intended).
OVERLAP_GROUPS = {
    "renderer": {"sodium", "embeddium", "rubidium", "optifine", "magnesium"},
    "minimap": {"xaeros-minimap", "journeymap", "voxelmap-updated", "ftb-chunks"},
    "recipe-viewer": {"jei", "rei", "emi"},
    "shader-loader": {"iris", "oculus", "optifine"},
    "inventory-sort": {"inventory-profiles-next", "mouse-tweaks-inventory-sort", "inventorysorter"},
}


def loader_filter(ptype: str, loader: str) -> list[str]:
    if ptype == "mod":
        return [loader]
    if ptype == "shader":
        return ["iris", "optifine", "canvas"]
    if ptype == "resourcepack":
        return ["minecraft"]
    if ptype == "datapack":
        return ["datapack"]
    return [loader]


# ---------------- search / info ----------------

def cmd_search(a):
    facets = [[f"project_type:{a.type}"], [f"versions:{a.mc}"]]
    if a.type == "mod":
        facets.append([f"categories:{a.loader}"])
    res = http_json(f"{MODRINTH_API}/search", {"query": a.query, "facets": facets,
                                               "limit": a.limit, "index": "relevance"})
    for h in (res or {}).get("hits", []):
        print(f"{h['slug']:<32} {h['downloads']:>11,} dl  client={h.get('client_side')} "
              f"server={h.get('server_side')}  {h.get('license', '?')}\n    {h['title']}: {h['description'][:110]}")
    if not (res or {}).get("hits"):
        print("no results (try fewer words, or check the version/loader)")


def best_version(project: str, ptype: str, mc: str, loader: str, pin: str | None = None):
    versions = http_json(f"{MODRINTH_API}/project/{project}/version",
                         {"game_versions": [mc], "loaders": loader_filter(ptype, loader)})
    if not versions:
        return None
    if pin:
        for v in versions:
            if v["version_number"] == pin:
                return v
        return None
    for channel in ("release", "beta", "alpha"):
        for v in versions:  # API returns newest first
            if v["version_type"] == channel:
                return v
    return None


def cmd_info(a):
    p = http_json(f"{MODRINTH_API}/project/{a.slug}")
    if not p:
        die(f"project '{a.slug}' not found on Modrinth")
    v = best_version(p["id"], p["project_type"], a.mc, a.loader)
    print(f"{p['title']} ({p['slug']}) — {p['project_type']}, license {p['license']['id']}")
    print(f"  client={p['client_side']} server={p['server_side']}  https://modrinth.com/{p['project_type']}/{p['slug']}")
    if not v:
        print(f"  NO version for MC {a.mc} / {a.loader}. Available game versions (last 8): {p['game_versions'][-8:]}")
        return
    print(f"  best: {v['version_number']} ({v['version_type']}) loaders={v['loaders']}")
    for d in v["dependencies"]:
        dp = http_json(f"{MODRINTH_API}/project/{d['project_id']}") if d.get("project_id") else None
        print(f"    {d['dependency_type']:<12} {dp['slug'] if dp else d.get('file_name') or d.get('project_id')}")


# ---------------- resolve ----------------

def parse_list(lines):
    out = []
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        ptype = None
        for pre, t in TYPE_PREFIX.items():
            if line.startswith(pre):
                ptype, line = t, line[len(pre):].strip()
        slug, _, pin = line.partition("@")
        out.append((slug.strip(), ptype, pin.strip() or None))
    return out


def env_of(project) -> dict:
    def norm(v):
        return v if v in ("required", "optional", "unsupported") else "required"
    return {"client": norm(project.get("client_side")), "server": norm(project.get("server_side"))}


def cmd_resolve(a):
    wanted = parse_list(a.slugs)
    if a.file:
        wanted += parse_list(Path(a.file).read_text(encoding="utf-8").splitlines())
    if not wanted:
        die("give slugs or --file")
    entries, by_pid, problems = [], {}, []
    queue = [(slug, ptype, pin, "user") for slug, ptype, pin in wanted]
    while queue:
        ref, ptype, pin, reason = queue.pop(0)
        p = http_json(f"{MODRINTH_API}/project/{ref}")
        if not p:
            hint = " (FTB mods are CurseForge-only: see the plugin docs/platforms.md)" if ref.startswith("ftb") else \
                " (may be CurseForge-only, or a wrong slug: try `search`)"
            problems.append(f"'{ref}': not found on Modrinth{hint}")
            continue
        if p["id"] in by_pid:
            continue
        ptype = ptype or p["project_type"]
        v = best_version(p["id"], ptype, a.mc, a.loader, pin)
        if not v:
            problems.append(f"{p['slug']}: no {ptype} version for MC {a.mc} / {a.loader}" + (f" matching {pin}" if pin else ""))
            by_pid[p["id"]] = None
            continue
        f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
        entry = {
            "slug": p["slug"], "project_id": p["id"], "title": p["title"], "type": ptype,
            "license": p["license"]["id"], "version_id": v["id"], "version_number": v["version_number"],
            "version_type": v["version_type"], "loaders": v["loaders"], "game_versions": v["game_versions"],
            "path": f"{TYPE_FOLDER.get(ptype, 'mods')}/{f['filename']}",
            "file": {"url": f["url"], "size": f["size"], "sha1": f["hashes"]["sha1"], "sha512": f["hashes"]["sha512"]},
            "env": env_of(p), "reason": reason,
            "dependencies": [{"project_id": d.get("project_id"), "type": d["dependency_type"]}
                             for d in v["dependencies"] if d.get("project_id")],
        }
        by_pid[p["id"]] = entry
        entries.append(entry)
        print(f"  + {p['slug']} {v['version_number']} ({reason})")
        for d in v["dependencies"]:
            if d["dependency_type"] == "required" and d.get("project_id") and d["project_id"] not in by_pid:
                queue.append((d["project_id"], None, None, f"dependency of {p['slug']}"))
    lock = {
        "name": a.name or Path(a.out).parent.name or "modpack", "version": "0.1.0",
        "minecraft": a.mc, "loader": a.loader, "loader_version": a.loader_version or latest_loader(a.mc, a.loader),
        "java": java_for(a.mc), "generated_by": "minecraft-studio/modrinth.py resolve",
        "entries": entries, "unresolved": problems,
    }
    save_json(Path(a.out), lock)
    print(f"wrote {a.out}: {len(entries)} entries, {len(problems)} unresolved")
    for pr in problems:
        print(f"  ! {pr}")
    return 1 if problems else 0


# ---------------- loader version ----------------

def latest_loader(mc: str, loader: str):
    try:
        if loader == "fabric":
            r = http_json(f"https://meta.fabricmc.net/v2/versions/loader/{mc}")
            return r[0]["loader"]["version"] if r else None
        if loader == "quilt":
            r = http_json(f"https://meta.quiltmc.org/v3/versions/loader/{mc}")
            return r[0]["loader"]["version"] if r else None
        if loader == "neoforge":
            parts = mc.split(".")
            if parts[0] != "1" or len(parts) < 2:
                return None  # new version scheme: ask the user / check neoforged.net
            prefix = f"{parts[1]}.{parts[2] if len(parts) > 2 else 0}."
            r = http_json("https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge")
            vs = [v for v in (r or {}).get("versions", []) if v.startswith(prefix) and "beta" not in v]
            return vs[-1] if vs else None
        if loader == "forge":
            r = http_json("https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json")
            promos = (r or {}).get("promos", {})
            return promos.get(f"{mc}-recommended") or promos.get(f"{mc}-latest")
    except Exception as e:  # network or format change: never guess
        print(f"  ! could not fetch {loader} loader version: {e}", file=sys.stderr)
    return None


def cmd_loader_version(a):
    v = latest_loader(a.mc, a.loader)
    print(v or f"unknown — check the {a.loader} website for MC {a.mc}")


# ---------------- audit ----------------

def audit(lock: dict) -> Report:
    r = Report(f"dependency audit — {lock.get('name')} (MC {lock.get('minecraft')}, {lock.get('loader')})")
    mc, loader = lock.get("minecraft"), lock.get("loader")
    if loader not in LOADERS:
        r.fail("lock", f"unknown loader '{loader}' (expected one of {', '.join(LOADERS)})")
    if lock.get("loader_version"):
        r.ok("lock", f"loader version pinned: {lock['loader_version']}")
    else:
        r.look("lock", "loader_version is empty: pin it before export (modrinth.py loader-version)")
    for u in lock.get("unresolved", []):
        r.fail("resolve", u)
    entries = lock.get("entries", [])
    by_pid = {e["project_id"]: e for e in entries}
    seen_slugs = {}
    for e in entries:
        where = e["slug"]
        if e["slug"] in seen_slugs:
            r.fail(where, "duplicate entry")
        seen_slugs[e["slug"]] = e
        if mc not in e.get("game_versions", [mc]):
            r.fail(where, f"version {e['version_number']} does not list MC {mc}")
        if e["type"] == "mod" and loader not in e.get("loaders", [loader]):
            r.fail(where, f"version {e['version_number']} is for {e.get('loaders')}, not {loader}")
        if e.get("version_type") != "release":
            r.look(where, f"uses a {e.get('version_type')} version ({e['version_number']})")
        for d in e.get("dependencies", []):
            if d["type"] == "required" and d["project_id"] not in by_pid:
                r.fail(where, f"required dependency {d['project_id']} missing from the lock")
            if d["type"] == "incompatible" and d["project_id"] in by_pid:
                r.fail(where, f"declared INCOMPATIBLE with {by_pid[d['project_id']]['slug']}")
        if e["env"]["client"] == "unsupported" and e["env"]["server"] == "unsupported":
            r.fail(where, "unsupported on both client and server")
        if e.get("license") in (None, "", "LicenseRef-All-Rights-Reserved", "ARR"):
            r.look(where, f"license '{e.get('license')}': check redistribution before shipping overrides")
    for group, members in OVERLAP_GROUPS.items():
        hit = sorted(members & set(seen_slugs))
        if len(hit) > 1:
            r.look(group, f"overlapping mods: {', '.join(hit)} (keep one unless intended)")
    client_only = [e["slug"] for e in entries if e["env"]["server"] == "unsupported"]
    server_only = [e["slug"] for e in entries if e["env"]["client"] == "unsupported"]
    if client_only:
        r.ok("sides", f"client-only (excluded from server pack): {', '.join(client_only)}")
    if server_only:
        r.ok("sides", f"server-only: {', '.join(server_only)}")
    if entries and not any(i[0] == "FAIL" for i in r.items):
        r.ok("deps", f"{len(entries)} entries, all required dependencies present")
    r.look("runtime", "not measured here: the game must still be launched (mc-test-loop)")
    return r


def cmd_audit(a):
    rep = audit(load_json(Path(a.lock)))
    rep.print(as_json=a.json)
    return rep.exit_code()


# ---------------- download ----------------

def cmd_download(a):
    lock = load_json(Path(a.lock))
    dest = Path(a.dest)
    n = 0
    for e in lock["entries"]:
        if a.side and e["env"][a.side] == "unsupported":
            continue
        target = dest / e["path"]
        if target.exists() and file_hashes(target)["sha512"] == e["file"]["sha512"]:
            continue
        print(f"  downloading {e['path']}")
        download(e["file"]["url"], target)
        if file_hashes(target)["sha512"] != e["file"]["sha512"]:
            target.unlink()
            die(f"hash mismatch for {e['path']} — file deleted")
        n += 1
    print(f"{n} files downloaded to {dest} (hashes verified)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def vl(p, required=True):
        p.add_argument("--mc", required=required, help="Minecraft version, e.g. 1.21.1")
        p.add_argument("--loader", required=required, choices=list(LOADERS))

    s = sub.add_parser("search"); s.add_argument("query"); vl(s)
    s.add_argument("--type", default="mod", choices=list(TYPE_FOLDER)); s.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("info"); s.add_argument("slug"); vl(s)
    s = sub.add_parser("resolve"); s.add_argument("slugs", nargs="*"); s.add_argument("--file"); vl(s)
    s.add_argument("--out", required=True); s.add_argument("--name"); s.add_argument("--loader-version")
    s = sub.add_parser("audit"); s.add_argument("lock"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("download"); s.add_argument("lock"); s.add_argument("--dest", required=True)
    s.add_argument("--side", choices=["client", "server"])
    s = sub.add_parser("loader-version"); vl(s)
    a = ap.parse_args()
    fn = {"search": cmd_search, "info": cmd_info, "resolve": cmd_resolve, "audit": cmd_audit,
          "download": cmd_download, "loader-version": cmd_loader_version}[a.cmd]
    sys.exit(fn(a) or 0)


if __name__ == "__main__":
    main()
