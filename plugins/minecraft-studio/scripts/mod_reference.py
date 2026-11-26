#!/usr/bin/env python3
"""Import a reference mod for study: local jar/folder, GitHub repo, Modrinth page or direct jar URL.

  mod_reference.py add <jar|folder|url> --id <ref-id> [--root .] [--loader fabric] [--mc 1.21.1] [--no-decompile]
  mod_reference.py list [--root .]
  mod_reference.py remove <ref-id> [--root .]        (study copy only; never touches the target mod)

Creates studio/references/<id>/ (meta.json, original.jar, extracted/, source/), then runs decompile,
inventory and licence scan. Output: one line. Local and reversible, no confirmation needed.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODRINTH_API, download, http_json  # noqa: E402
import _ref  # noqa: E402

IGNORE = shutil.ignore_patterns(".git", ".gradle", "build", "run", "runs", "out", ".idea", "*.jar")


def safe_extract(z: zipfile.ZipFile, name: str, dest: Path):
    if name.startswith("/") or ".." in Path(name).parts:
        return
    out = dest / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(z.read(name))


def extract_jar(jar: Path, ref: Path) -> int:
    ex = ref / "extracted"
    n = 0
    with zipfile.ZipFile(jar) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            if name.endswith(".class"):
                safe_extract(z, name, ex / "classes"); n += 1
            elif name.startswith(("assets/", "data/")):
                safe_extract(z, name, ex)
            elif "/" not in name or name.startswith("META-INF/") and name.endswith(".toml"):
                if not name.startswith("META-INF/jars"):
                    safe_extract(z, name, ex / "meta")
    return n


def fetch(src: str, ref: Path, args) -> tuple[str, Path, dict]:
    """Returns (type, local path, extra meta)."""
    p = Path(src)
    if p.exists():
        return ("folder" if p.is_dir() else "jar"), p, {}
    tmp = ref / "_download"
    m = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+?)(?:\.git)?(?:/tree/([^?#]+))?/?$", src)
    if m:
        url = f"https://github.com/{m.group(1)}/{m.group(2)}/archive/{m.group(3) or 'HEAD'}.zip"
        return "github", download(url, tmp / "src.zip"), {"archive": url}
    m = re.match(r"https?://(?:www\.)?modrinth\.com/(?:mod|plugin|datapack|resourcepack|shader)/([^/?#]+)(?:/version/([^/?#]+))?", src)
    if m:
        proj = http_json(f"{MODRINTH_API}/project/{m.group(1)}") or {}
        params = {}
        if args.loader:
            params["loaders"] = [args.loader]
        if args.mc:
            params["game_versions"] = [args.mc]
        vers = http_json(f"{MODRINTH_API}/project/{m.group(1)}/version", params) or []
        if m.group(2):
            vers = [v for v in vers if m.group(2) in (v["id"], v["version_number"])] or vers
        if not vers:
            raise SystemExit("error: no Modrinth version matches")
        f = next((x for x in vers[0]["files"] if x.get("primary")), vers[0]["files"][0])
        lic = proj.get("license") or {}
        return "modrinth", download(f["url"], tmp / f["filename"]), {
            "modrinth": {"slug": m.group(1), "version": vers[0]["version_number"], "source_url": proj.get("source_url")},
            "modrinth_licence": lic.get("id")}
    if src.startswith("http"):
        return "url", download(src, tmp / (src.rsplit("/", 1)[-1].split("?")[0] or "mod.jar")), {}
    raise SystemExit(f"error: not found: {src}")


def add(args):
    root = Path(args.root)
    ref = _ref.ref_dir(root, args.id)
    if ref.exists():
        shutil.rmtree(ref)  # a study copy, regenerated from its source
    ref.mkdir(parents=True)
    kind, path, extra = fetch(args.source, ref, args)
    info = {"id": args.id, "source": args.source, "type": kind, "added": _ref.now(), **extra}
    classes = 0
    if path.is_dir():
        shutil.copytree(path, ref / "source", ignore=IGNORE)
    elif zipfile.is_zipfile(path) and any(n.endswith(".class") for n in zipfile.ZipFile(path).namelist()):
        shutil.copy2(path, ref / "original.jar")
        info["sha1"] = hashlib.sha1(path.read_bytes()).hexdigest()
        classes = extract_jar(ref / "original.jar", ref)
    elif zipfile.is_zipfile(path):  # source archive
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if not n.endswith("/") and not re.search(r"/(build|\.gradle|run)/|\.jar$", n):
                    safe_extract(z, n, ref / "source")
    else:
        raise SystemExit("error: not a jar, zip or folder")
    shutil.rmtree(ref / "_download", ignore_errors=True)
    _ref.save_meta(ref, info)

    import license_scan, mod_inventory, mod_decompile  # noqa: E401
    dec = "skipped"
    if classes and not args.no_decompile:
        dec = mod_decompile.run(ref, "vineflower")
    else:
        _ref.build_index(ref)
    inv = mod_inventory.inventory(ref)
    lic = license_scan.scan(ref)
    a = inv["assets"]
    print(f"ADDED {args.id} ({kind}) · loader {inv['loader'] or '?'} · {classes or len(_ref.java_files(ref))} classes · "
          f"decompile {dec} · {sum(a.values())} assets · licence {lic['licence']} ({lic['status']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("source"); a.add_argument("--id", required=True)
    a.add_argument("--root", default="."); a.add_argument("--loader"); a.add_argument("--mc")
    a.add_argument("--no-decompile", action="store_true")
    l = sub.add_parser("list"); l.add_argument("--root", default=".")
    r = sub.add_parser("remove"); r.add_argument("id"); r.add_argument("--root", default=".")
    args = ap.parse_args()
    if args.cmd == "add":
        add(args)
    elif args.cmd == "list":
        base = Path(args.root) / "studio/references"
        for d in sorted(base.iterdir()) if base.exists() else []:
            m = _ref.meta(d)
            print(f"{d.name}: {m.get('type')} {m.get('source')} licence={m.get('licence', '?')}")
    else:
        shutil.rmtree(_ref.need(Path(args.root), args.id)); print(f"REMOVED {args.id}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
