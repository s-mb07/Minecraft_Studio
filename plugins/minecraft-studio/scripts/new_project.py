#!/usr/bin/env python3
"""Create a modpack workspace from the Minecraft Studio templates.

  new_project.py <folder> --name "My Pack" [--mc 1.21.1] [--loader neoforge]

Never overwrites an existing file. Layout:
  <folder>/
    studio/   brief.md, dossier.md, plan.md, decisions.md, test-log.md, gates.md, style-guide.md
    pack/     mods.txt, (pack.lock.json), overrides/{config,kubejs,defaultconfigs}, client-overrides/, server-overrides/
    quests/   design.json
    assets/   resourcepack/ (your own resource pack sources), licences.md
    dist/     build output (git-ignored)
    README.md, CREDITS.md, .gitignore
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"

FILES = {
    "studio/brief.md": "brief.md",
    "studio/dossier.md": "dossier.md",
    "studio/plan.md": "plan.md",
    "studio/decisions.md": "decisions.md",
    "studio/test-log.md": "test-log.md",
    "studio/gates.md": "gates.md",
    "studio/style-guide.md": "style-guide.md",
    "quests/design.json": "quest-design.example.json",
    "assets/licences.md": "licences.md",
    "README.md": "pack-readme.md",
    "CREDITS.md": "credits.md",
}
DIRS = ["pack/overrides/config", "pack/overrides/kubejs/server_scripts", "pack/overrides/kubejs/startup_scripts",
        "pack/overrides/kubejs/client_scripts", "pack/overrides/defaultconfigs", "pack/client-overrides",
        "pack/server-overrides", "assets/resourcepack", "dist"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--name", required=True)
    ap.add_argument("--mc", default="TBD")
    ap.add_argument("--loader", default="TBD")
    a = ap.parse_args()
    root = Path(a.folder)
    subs = {"{{PACK_NAME}}": a.name, "{{MC_VERSION}}": a.mc, "{{LOADER}}": a.loader,
            "{{DATE}}": dt.date.today().isoformat()}
    created = []
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    for dest, tpl in FILES.items():
        target = root / dest
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (TEMPLATES / tpl).read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        target.write_text(text, encoding="utf-8", newline="\n")
        created.append(dest)
    mods = root / "pack" / "mods.txt"
    if not mods.exists():
        mods.write_text("# One Modrinth slug per line. slug@version pins a version.\n"
                        "# Prefixes: rp: resource pack, shader: shaderpack, dp: datapack\n", encoding="utf-8")
        created.append("pack/mods.txt")
    gi = root / ".gitignore"
    if not gi.exists():
        shutil.copyfile(TEMPLATES / "pack.gitignore", gi)
        created.append(".gitignore")
    print(f"workspace ready in {root} ({len(created)} files created)")
    for c in created:
        print(f"  + {c}")


if __name__ == "__main__":
    sys.exit(main())
