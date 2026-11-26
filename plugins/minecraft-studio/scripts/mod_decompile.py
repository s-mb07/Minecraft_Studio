#!/usr/bin/env python3
"""Decompile a reference's classes to Java and (re)build its index.

  mod_decompile.py <ref-id> [--root .] [--engine vineflower|cfr] [--java PATH]

Engines are downloaded once from Maven Central into ~/.minecraft-studio/tools/ (a user cache, no system change):
Vineflower (Apache-2.0, default) or CFR (MIT). Needs a JDK 17+ (newest one found is used).
Writes decompiled/java/ and analysis/index.json. Failure -> index from class names only (LOOK), never blocking.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import download  # noqa: E402
import _ref  # noqa: E402

ENGINES = {
    "vineflower": ("https://repo1.maven.org/maven2/org/vineflower/vineflower/1.10.1/vineflower-1.10.1.jar", "vineflower-1.10.1.jar"),
    "cfr": ("https://repo1.maven.org/maven2/org/benf/cfr/0.152/cfr-0.152.jar", "cfr-0.152.jar"),
}
TOOLS = Path.home() / ".minecraft-studio" / "tools"


def engine_jar(engine: str) -> Path:
    url, name = ENGINES[engine]
    p = TOOLS / name
    if not p.exists() or p.stat().st_size < 10000:
        download(url, p)
    return p


def java_bin(explicit: str | None) -> str:
    from gradle_run import find_java_home
    home = find_java_home(17, explicit)
    if home:
        exe = Path(home) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        if exe.exists():
            return str(exe)
    return "java"


def run(ref: Path, engine: str = "vineflower", java: str | None = None) -> str:
    classes = ref / "extracted/classes"
    out = ref / "decompiled/java"
    if not classes.exists():
        _ref.build_index(ref)
        return "no-classes"
    out.mkdir(parents=True, exist_ok=True)
    try:
        jar = engine_jar(engine)
        if engine == "vineflower":
            cmd = [java_bin(java), "-jar", str(jar), "-dgs=1", "-log=WARN", str(classes), str(out)]
        else:
            cmd = [java_bin(java), "-jar", str(jar), str(classes), "--outputdir", str(out), "--silent", "true"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        (ref / "analysis").mkdir(exist_ok=True)
        (ref / "analysis/decompile.log").write_text((p.stdout + p.stderr)[-20000:], encoding="utf-8")
        ok = any(out.rglob("*.java"))
    except Exception as e:  # noqa: BLE001 - never block on decompiler issues
        (ref / "analysis").mkdir(exist_ok=True)
        (ref / "analysis/decompile.log").write_text(str(e), encoding="utf-8")
        ok = False
    idx = _ref.build_index(ref)
    m = _ref.meta(ref); m["decompiler"] = engine if ok else None; _ref.save_meta(ref, m)
    return f"{engine} PASS ({len(idx['classes'])} classes)" if ok else "LOOK (names only, see analysis/decompile.log)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("--root", default=".")
    ap.add_argument("--engine", choices=list(ENGINES), default="vineflower"); ap.add_argument("--java")
    a = ap.parse_args()
    print("DECOMPILE", run(_ref.need(Path(a.root), a.id), a.engine, a.java))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
