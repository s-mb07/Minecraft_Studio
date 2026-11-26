#!/usr/bin/env python3
"""Create a mod project from the OFFICIAL template of a loader, renamed to your mod.

  mod_new.py <folder> --modid crystalcraft --name "Crystal Craft" --package com.you.crystalcraft
             --loader fabric|neoforge|forge --mc 1.21.1 [--author you] [--license MIT] [--example]

Templates (downloaded from GitHub, nothing bundled):
  fabric    FabricMC/fabric-example-mod, branch = MC version          (validated: 1.21.1)
  neoforge  NeoForgeMDKs/MDK-<mc>-ModDevGradle                         (validated: 1.21.1)
  forge     NeoForgeMDKs/MDK-Forge-<mc>-ModDevGradle (1.20.1)          (not validated: ids renamed only)

Fabric/NeoForge get a clean Minecraft Studio skeleton (Main, ModItems, ModBlocks, ModGameTests) instead of the
template's sample code, plus a `runGametest` (Fabric) / `runGameTestServer` (NeoForge) setup.
--example adds a working item + block (Blockbench-style model, hitbox, textures, recipe, loot, lang, GameTest).
Refuses to write into a non-empty folder (never overwrites existing work).
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import USER_AGENT, die, java_for  # noqa: E402
import texture  # noqa: E402

TPL = HERE.parent / "templates" / "mod"
TEXT_EXT = {".java", ".json", ".gradle", ".properties", ".toml", ".md", ".txt", ".kts", ".mcmeta"}
DATA_VERSION = {"1.21.1": 3955, "1.21": 3953, "1.20.1": 3465}


def template_url(loader: str, mc: str) -> tuple[str, str]:
    if loader == "fabric":
        return f"https://codeload.github.com/FabricMC/fabric-example-mod/zip/refs/heads/{mc}", "FabricMC/fabric-example-mod@" + mc
    if loader == "neoforge":
        repo = f"NeoForgeMDKs/MDK-{mc}-ModDevGradle"
    elif loader == "forge":
        repo = f"NeoForgeMDKs/MDK-Forge-{mc}-ModDevGradle"
    else:
        die(f"unknown loader {loader}")
    return f"https://codeload.github.com/{repo}/zip/refs/heads/main", repo


def fetch(url: str, dest: Path):
    import urllib.request
    import subprocess
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        data = urllib.request.urlopen(req, timeout=60).read()
    except Exception:
        data = subprocess.run(["curl", "-fsSL", url], check=True, capture_output=True).stdout
    with zipfile.ZipFile(io.BytesIO(data)) as z, tempfile.TemporaryDirectory() as tmp:
        z.extractall(tmp)
        root = next(Path(tmp).iterdir())
        shutil.copytree(root, dest, dirs_exist_ok=True)


def sub_text(root: Path, pairs: list[tuple[str, str]]):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in TEXT_EXT and ".git" not in p.parts:
            t = p.read_text(encoding="utf-8", errors="ignore")
            n = t
            for a, b in pairs:
                n = re.sub(a, b, n)
            if n != t:
                p.write_text(n, encoding="utf-8", newline="\n")


def set_props(path: Path, values: dict):
    lines, seen = path.read_text(encoding="utf-8").splitlines(), set()
    for i, l in enumerate(lines):
        k = l.split("=", 1)[0].strip()
        if k in values and not l.lstrip().startswith("#"):
            lines[i] = f"{k}={values[k]}"
            seen.add(k)
    for k, v in values.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def render(name: str, loader: str, subs: dict, example: bool) -> str:
    f = TPL / loader / name if (TPL / loader / name).exists() else TPL / "common" / name
    text = f.read_text(encoding="utf-8")
    out, skip = [], False
    for line in text.splitlines():
        if line.strip() == "//EX{":
            skip = not example
            continue
        if line.strip() == "//EX}":
            skip = False
            continue
        if not skip:
            out.append(line)
    text = "\n".join(out) + "\n"
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def write(path: Path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, (dict, list)):
        text = json.dumps(text, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


# ---- tiny NBT writer (empty GameTest structure) ----
def nbt_empty_structure(size=(3, 3, 3), data_version=3955) -> bytes:
    def s(x):
        b = x.encode()
        return struct.pack(">H", len(b)) + b

    def tag(t, name, payload):
        return bytes([t]) + s(name) + payload
    empty_list = bytes([0]) + struct.pack(">i", 0)
    body = (tag(3, "DataVersion", struct.pack(">i", data_version))
            + tag(9, "size", bytes([3]) + struct.pack(">i", 3) + b"".join(struct.pack(">i", v) for v in size))
            + tag(9, "palette", empty_list) + tag(9, "blocks", empty_list) + tag(9, "entities", empty_list) + b"\x00")
    return gzip.compress(tag(10, "", body))


def folder(name: str, mc: str) -> str:
    """1.21 renamed data folders to singular."""
    plural = tuple(int(x) for x in mc.split(".")[:2]) < (1, 21)
    return {"recipe": "recipes", "loot_table": "loot_tables", "structure": "structures"}[name] if plural else name


def example_resources(res: Path, m: str, mc: str):
    a, d = res / "assets" / m, res / "data" / m
    write(a / "blockstates" / "crystal_block.json", {"variants": {"": {"model": f"{m}:block/crystal_block"}}})
    write(a / "models" / "block" / "crystal_block.json", {
        "textures": {"0": f"{m}:block/crystal_block", "particle": f"{m}:block/crystal_block"},
        "elements": [
            {"name": "base", "from": [0, 0, 0], "to": [16, 4, 16],
             "faces": {f: {"uv": [0, 0, 16, 4] if f not in ("up", "down") else [0, 0, 16, 16], "texture": "#0"}
                       for f in ("north", "east", "south", "west", "up", "down")}},
            {"name": "spike", "from": [5, 4, 5], "to": [11, 14, 11],
             "faces": {f: {"uv": [5, 2, 11, 12] if f not in ("up", "down") else [5, 5, 11, 11], "texture": "#0"}
                       for f in ("north", "east", "south", "west", "up", "down")}}]})
    write(a / "models" / "item" / "crystal_block.json", {"parent": f"{m}:block/crystal_block"})
    write(a / "models" / "item" / "crystal_shard.json",
          {"parent": "minecraft:item/generated", "textures": {"layer0": f"{m}:item/crystal_shard"}})
    texture.gen("block", texture.hex2rgb("#7a4fd6")).save(a / "textures" / "block" / "crystal_block.png")
    texture.gen("shard", texture.hex2rgb("#9b6ff0")).save(a / "textures" / "item" / "crystal_shard.png")
    write(d / folder("recipe", mc) / "crystal_block.json", {
        "type": "minecraft:crafting_shaped", "pattern": ["##", "##"],
        "key": {"#": {"item": f"{m}:crystal_shard"}}, "result": {"id": f"{m}:crystal_block", "count": 1}})
    write(d / folder("loot_table", mc) / "blocks" / "crystal_block.json", {
        "type": "minecraft:block", "pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": f"{m}:crystal_block"}],
                                              "conditions": [{"condition": "minecraft:survives_explosion"}]}]})
    return {f"item.{m}.crystal_shard": "Crystal Shard", f"block.{m}.crystal_block": "Crystal Block"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--modid", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--loader", required=True, choices=["fabric", "neoforge", "forge"])
    ap.add_argument("--mc", default="1.21.1")
    ap.add_argument("--author", default="")
    ap.add_argument("--license", default="MIT")
    ap.add_argument("--description", default="")
    ap.add_argument("--example", action="store_true")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", a.modid):
        die("modid must be lowercase letters, digits, underscore (2-64 chars), starting with a letter")
    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", a.package):
        die("package must look like com.you.modid (lowercase)")
    root = Path(a.folder)
    if root.exists() and any(root.iterdir()):
        die(f"{root} is not empty — choose a new folder (existing work is never overwritten)")
    url, src = template_url(a.loader, a.mc)
    print(f"  template: {src}")
    fetch(url, root)
    m, pkg = a.modid, a.package
    cls = "".join(w.capitalize() for w in re.split(r"[_\W]+", m)) or "Mod"
    pkg_path = pkg.replace(".", "/")
    subs = {"__PKG__": pkg, "__MODID__": m, "__CLASS__": cls}
    desc = a.description or f"{a.name}, made with Minecraft Studio."
    lang = {}

    if a.loader == "fabric":
        for d in ("src/main/java/com/example", "src/client/java/com/example"):
            shutil.rmtree(root / d, ignore_errors=True)
        java = root / "src/main/java" / pkg_path
        for f, out in (("Main.java", f"{cls}.java"), ("ModItems.java", None), ("ModBlocks.java", None), ("ModGameTests.java", None)):
            write(java / (out or f), render(f, "fabric", subs, a.example))
        if a.example:
            write(java / "CrystalBlock.java", render("CrystalBlock.java", "fabric", subs, True))
        write(root / f"src/client/java/{pkg_path}/client/{cls}Client.java",
              f"package {pkg}.client;\n\nimport net.fabricmc.api.ClientModInitializer;\n\n"
              f"public class {cls}Client implements ClientModInitializer {{\n    @Override\n"
              f"    public void onInitializeClient() {{\n    }}\n}}\n")
        res, cres = root / "src/main/resources", root / "src/client/resources"
        (res / "modid.mixins.json").unlink(missing_ok=True)
        (cres / "modid.client.mixins.json").unlink(missing_ok=True)
        mix = {"required": True, "minVersion": "0.8", "compatibilityLevel": "JAVA_21", "mixins": [],
               "injectors": {"defaultRequire": 1}}
        write(res / f"{m}.mixins.json", {**mix, "package": f"{pkg}.mixin"})
        write(cres / f"{m}.client.mixins.json", {**{k: v for k, v in mix.items() if k != "mixins"},
                                                  "package": f"{pkg}.client.mixin", "client": []})
        if (res / "assets/modid").exists():
            shutil.move(str(res / "assets/modid"), str(res / "assets" / m))
        fmj = json.loads((res / "fabric.mod.json").read_text(encoding="utf-8"))
        fmj.update({"id": m, "name": a.name, "description": desc, "authors": [a.author] if a.author else [],
                    "license": a.license, "icon": f"assets/{m}/icon.png", "contact": {}})
        fmj["entrypoints"] = {"main": [f"{pkg}.{cls}"], "client": [f"{pkg}.client.{cls}Client"],
                              "fabric-gametest": [f"{pkg}.ModGameTests"]}
        fmj["mixins"] = [f"{m}.mixins.json", {"config": f"{m}.client.mixins.json", "environment": "client"}]
        write(res / "fabric.mod.json", fmj)
        sub_text(root, [(r"rootProject\.name = '.*'", f"rootProject.name = '{m}'")])
        set_props(root / "gradle.properties", {"group": pkg})
        with open(root / "build.gradle", "a", encoding="utf-8", newline="\n") as f:
            f.write((TPL / "fabric" / "gametest.gradle").read_text(encoding="utf-8"))
    elif a.loader == "neoforge":
        shutil.rmtree(root / "src/main/java/com/example", ignore_errors=True)
        java = root / "src/main/java" / pkg_path
        for f, out in (("Main.java", f"{cls}.java"), ("ModItems.java", None), ("ModBlocks.java", None), ("ModGameTests.java", None)):
            write(java / (out or f), render(f, "neoforge", subs, a.example))
        if a.example:
            write(java / "CrystalBlock.java", render("CrystalBlock.java", "neoforge", subs, True))
        res = root / "src/main/resources"
        shutil.rmtree(res / "assets/examplemod", ignore_errors=True)
        set_props(root / "gradle.properties", {"mod_id": m, "mod_name": a.name, "mod_license": a.license,
                                               "mod_group_id": pkg})
        toml = root / "src/main/templates/META-INF/neoforge.mods.toml"
        if toml.exists():  # the MDK only expands a fixed set of ${...} keys: write these literally
            t = toml.read_text(encoding="utf-8")
            t = re.sub(r"description='''.*?'''", lambda _: f"description='''{desc.replace(chr(39) * 3, '')}'''", t, flags=re.S)
            if a.author:
                t = re.sub(r'^#?\s*authors\s*=.*$', lambda _: f'authors="{a.author}"', t, count=1, flags=re.M)
            toml.write_text(t, encoding="utf-8", newline="\n")
        (res / "data" / m / folder("structure", a.mc)).mkdir(parents=True, exist_ok=True)
        (res / "data" / m / folder("structure", a.mc) / "empty.nbt").write_bytes(
            nbt_empty_structure(data_version=DATA_VERSION.get(a.mc, 3955)))
    else:  # forge: keep template code, rename ids only (not validated)
        sub_text(root, [(r"\bexamplemod\b", m), (r"com\.example\.examplemod", pkg)])
        old = root / "src/main/java/com/example/examplemod"
        if old.exists():
            (root / "src/main/java" / pkg_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(root / "src/main/java" / pkg_path))
        set_props(root / "gradle.properties", {"mod_id": m, "mod_name": a.name, "mod_license": a.license,
                                               "mod_group_id": pkg, "mod_authors": a.author})
        print("  NOTE: forge templates are not validated by Minecraft Studio; template sample code kept.")
        res = root / "src/main/resources"

    if a.loader in ("fabric", "neoforge"):
        if a.example:
            lang.update(example_resources(res, m, a.mc))
        write(res / "assets" / m / "lang" / "en_us.json", lang)

    st = root / "studio"
    write(st / "dossier.md", f"# Dossier — {a.name}\n\n| Fact | Value | Source |\n|---|---|---|\n"
          f"| modid | {m} | mod_new |\n| package | {pkg} | mod_new |\n| loader | {a.loader} | mod_new |\n"
          f"| Minecraft | {a.mc} | mod_new |\n| Java | {java_for(a.mc)} | _common.java_for |\n"
          f"| template | {src} | GitHub |\n| EULA accepted (dev server) | no | ask once |\n")
    write(st / "decisions.md", "# Decisions\n\n| Date | Decision | Why |\n|---|---|---|\n")
    gi = root / ".gitignore"
    with open(gi, "a", encoding="utf-8") as f:
        f.write("\n# Minecraft Studio\n.studio-backup/\nstudio/logs/\n")
    print(f"created {a.loader} mod '{m}' ({cls}) in {root}{' with example content' if a.example else ''}")
    print(f"  next: python {HERE / 'mod_check.py'} {root}  then  python {HERE / 'gradle_run.py'} {root} build")


if __name__ == "__main__":
    main()
