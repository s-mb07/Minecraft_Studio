#!/usr/bin/env python3
"""Build a Modrinth .mrpack (and optionally a server pack) from a pack.lock.json.

  build_mrpack.py pack/pack.lock.json --pack-dir pack --out dist [--server-pack] [--version 1.0.0]

Expected layout under --pack-dir (all optional):
  overrides/          -> copied to the instance root on both sides (config/, kubejs/, defaultconfigs/ ...)
  client-overrides/   -> client only (options.txt, client resourcepacks you made yourself ...)
  server-overrides/   -> server only (server.properties defaults ...)

The .mrpack only references files by URL + hash (nothing is redistributed).
The server pack DOWNLOADS server-side files and zips them with overrides: check licences before
publishing it (mc-export skill).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import LOADERS, die, download, file_hashes, load_json  # noqa: E402

ALLOWED_HOSTS = ("https://cdn.modrinth.com/", "https://github.com/", "https://raw.githubusercontent.com/",
                 "https://gitlab.com/")


def index_from_lock(lock: dict, version: str) -> dict:
    if not lock.get("loader_version"):
        die("lock has no loader_version: run `modrinth.py loader-version` and set it")
    if lock.get("unresolved"):
        die("lock has unresolved entries — fix them first (modrinth.py audit):\n  " + "\n  ".join(lock["unresolved"]))
    files = []
    for e in lock["entries"]:
        url = e["file"]["url"]
        if not url.startswith(ALLOWED_HOSTS):
            die(f"{e['slug']}: download host not allowed in .mrpack: {url}")
        files.append({
            "path": e["path"],
            "hashes": {"sha1": e["file"]["sha1"], "sha512": e["file"]["sha512"]},
            "env": e["env"],
            "downloads": [url],
            "fileSize": e["file"]["size"],
        })
    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": version,
        "name": lock["name"],
        "summary": lock.get("summary", ""),
        "files": files,
        "dependencies": {"minecraft": lock["minecraft"], LOADERS[lock["loader"]]: lock["loader_version"]},
    }


def add_tree(z: zipfile.ZipFile, src: Path, prefix: str) -> int:
    n = 0
    if src.is_dir():
        for f in sorted(src.rglob("*")):
            if f.is_file() and f.name not in (".DS_Store", "Thumbs.db") and ".git" not in f.parts:
                z.write(f, f"{prefix}/{f.relative_to(src).as_posix()}" if prefix else f.relative_to(src).as_posix())
                n += 1
    return n


def build_mrpack(lock: dict, pack_dir: Path, out: Path, version: str) -> Path:
    idx = index_from_lock(lock, version)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{slugify(lock['name'])}-{version}.mrpack"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("modrinth.index.json", json.dumps(idx, indent=2, ensure_ascii=False))
        counts = {d: add_tree(z, pack_dir / d, d) for d in ("overrides", "client-overrides", "server-overrides")}
    print(f"wrote {target}: {len(idx['files'])} referenced files, overrides {counts}")
    return target


def build_server_pack(lock: dict, pack_dir: Path, out: Path, version: str) -> Path:
    target = out / f"{slugify(lock['name'])}-{version}-server.zip"
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for e in lock["entries"]:
            if e["env"]["server"] == "unsupported" or e["type"] in ("resourcepack", "shader"):
                continue
            f = download(e["file"]["url"], Path(tmp) / e["path"])
            if file_hashes(f)["sha512"] != e["file"]["sha512"]:
                die(f"hash mismatch for {e['path']}")
            z.write(f, e["path"])
        add_tree(z, pack_dir / "overrides", "")
        add_tree(z, pack_dir / "server-overrides", "")
        z.writestr("README-SERVER.txt", server_readme(lock))
    print(f"wrote {target}")
    return target


def server_readme(lock: dict) -> str:
    loader = lock["loader"]
    install = {
        "fabric": "https://fabricmc.net/use/server/",
        "quilt": "https://quiltmc.org/install/server/",
        "neoforge": "https://neoforged.net/ (run the installer with --installServer)",
        "forge": "https://files.minecraftforge.net/ (run the installer with --installServer)",
    }[loader]
    return (f"{lock['name']} server pack\n\nMinecraft {lock['minecraft']} / {loader} {lock['loader_version']}\n"
            f"Java {lock.get('java', '?')}\n\n1. Install the {loader} server: {install}\n"
            "2. Unzip this archive into the server folder (mods/, config/ ...).\n"
            "3. Accept the EULA (eula.txt) and start the server.\n")


def slugify(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-") or "modpack"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lock")
    ap.add_argument("--pack-dir", help="folder holding overrides/ (default: the lock's folder)")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--version", help="pack version (default: lock 'version')")
    ap.add_argument("--server-pack", action="store_true")
    a = ap.parse_args()
    lock = load_json(Path(a.lock))
    pack_dir = Path(a.pack_dir) if a.pack_dir else Path(a.lock).parent
    version = a.version or lock.get("version", "0.1.0")
    out = Path(a.out)
    build_mrpack(lock, pack_dir, out, version)
    if a.server_pack:
        build_server_pack(lock, pack_dir, out, version)


if __name__ == "__main__":
    main()
