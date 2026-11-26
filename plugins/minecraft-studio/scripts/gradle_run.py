#!/usr/bin/env python3
"""Run a Gradle task of a mod with the right JDK, a timeout, and a short result.

  gradle_run.py <mod-folder> build|server|gametest|client|data|<any gradle task> [--timeout 1200]
                [--java PATH] [--accept-eula] [--verbose]

  build     gradlew build            -> jar in build/libs/
  server    runServer, waits for "Done", sends stop      (EULA: --accept-eula once, remembered in studio/dossier.md)
  gametest  Fabric runGametest / NeoForge runGameTestServer (exit code = result)
  client    runClient (needs a desktop; offline dev account). Failure here is LOOK, never blocking.
  data      Fabric runDatagen / NeoForge runData

Full output goes to studio/logs/<task>.log; only the result (and on failure the log_scan summary + last lines)
is printed. Results are written to studio/test-status.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import log_scan  # noqa: E402
from _common import load_json, save_json  # noqa: E402


def loader_of(root: Path) -> str:
    if (root / "src/main/resources/fabric.mod.json").exists():
        return "fabric"
    t = (root / "build.gradle").read_text(encoding="utf-8", errors="ignore") if (root / "build.gradle").exists() else ""
    return "neoforge" if "neoforged" in t else "forge" if "minecraftforge" in t else "unknown"


def java_major_needed(root: Path) -> int:
    t = (root / "build.gradle").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"JavaLanguageVersion\.of\((\d+)\)|options\.release\s*=\s*(\d+)", t)
    return int(next(g for g in m.groups() if g)) if m else 21


def find_java_home(major: int, explicit: str | None) -> str | None:
    """Newest installed JDK >= major (Gradle may run on a newer JVM than the mod's release target:
    e.g. Fabric Loom 1.19 needs Java 25 to run while mods still target Java 21)."""
    if explicit:
        p = Path(explicit)
        return str(p.parent.parent if p.name.startswith("java") else p)
    cands = []
    if os.environ.get("JAVA_HOME"):
        cands.append(Path(os.environ["JAVA_HOME"]))
    for base in (Path("C:/Java"), Path("C:/Program Files/Java"), Path("C:/Program Files/Eclipse Adoptium"),
                 Path("C:/Program Files/Microsoft"), Path("/usr/lib/jvm"), Path("/Library/Java/JavaVirtualMachines")):
        if base.exists():
            cands += sorted(base.iterdir())
    found = []
    for c in cands:
        home = c / "Contents/Home" if (c / "Contents/Home").exists() else c
        rel = home / "release"
        if rel.exists():
            mv = re.search(r'JAVA_VERSION="(\d+)', rel.read_text(errors="ignore"))
            if mv and int(mv.group(1)) >= major:
                found.append((int(mv.group(1)), str(home)))
    return max(found)[1] if found else os.environ.get("JAVA_HOME")


TASKS = {
    "fabric": {"server": "runServer", "gametest": "runGametest", "client": "runClient", "data": "runDatagen"},
    "neoforge": {"server": "runServer", "gametest": "runGameTestServer", "client": "runClient", "data": "runData"},
    "forge": {"server": "runServer", "gametest": "runGameTestServer", "client": "runClient", "data": "runData"},
}
RUN_DIRS = ["run", "runs/server", "run/server"]


def eula_ok(root: Path, accept: bool) -> bool:
    dossier = root / "studio" / "dossier.md"
    text = dossier.read_text(encoding="utf-8") if dossier.exists() else ""
    if re.search(r"EULA accepted \(dev server\) \| yes", text):
        return True
    if not accept:
        return False
    stamp = dt.date.today().isoformat()
    if "EULA accepted (dev server)" in text:
        text = re.sub(r"\| EULA accepted \(dev server\) \|[^\n]*", f"| EULA accepted (dev server) | yes | user, {stamp} |", text)
    else:
        text += f"| EULA accepted (dev server) | yes | user, {stamp} |\n"
    dossier.parent.mkdir(parents=True, exist_ok=True)
    dossier.write_text(text, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("task")
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--java")
    ap.add_argument("--accept-eula", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    root = Path(a.folder).resolve()
    loader = loader_of(root)
    task = TASKS.get(loader, {}).get(a.task, a.task)
    env = dict(os.environ)
    major = java_major_needed(root)
    jh = find_java_home(major, a.java)
    if jh:
        env["JAVA_HOME"] = jh
        env["PATH"] = str(Path(jh) / "bin") + os.pathsep + env.get("PATH", "")
    else:
        print(f"LOOK: no JDK {major} found (set JAVA_HOME or --java); Gradle may try its toolchain download")
    if a.task == "server":
        if not eula_ok(root, a.accept_eula):
            print("NEED: the dev server requires accepting the Minecraft EULA (https://aka.ms/MinecraftEULA). "
                  "Ask the user once, then re-run with --accept-eula (remembered in studio/dossier.md).")
            sys.exit(4)
        for d in RUN_DIRS:
            (root / d).mkdir(parents=True, exist_ok=True)
            (root / d / "eula.txt").write_text("eula=true\n")
    gradlew = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradlew.exists():
        print("FAIL: no gradlew in the project")
        sys.exit(1)
    if os.name != "nt":
        gradlew.chmod(0o755)
    # no --args=nogui: Loom and the NeoForge MDK already run dev servers without GUI, and NeoForge's
    # launcher treats an extra arg as a main class (ClassNotFoundException: nogui).
    cmd = [str(gradlew), task, "--console=plain"]
    logs = root / "studio" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"{a.task}.log"
    t0 = time.time()
    state = {"done": False}
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        p = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

        def reader():
            for line in p.stdout:
                log.write(line)
                if a.verbose:
                    print(line, end="")
                if a.task == "server" and "Done (" in line and "For help" in line:
                    state["done"] = True
                    try:
                        p.stdin.write("stop\n")
                        p.stdin.flush()
                    except OSError:
                        pass
        th = threading.Thread(target=reader, daemon=True)
        th.start()
        def kill_tree():
            # kill the whole tree FIRST (gradlew -> Gradle -> game JVM); killing the wrapper alone leaves the
            # game server running and holding port 25565
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            p.kill()
        done_at = None
        while p.poll() is None:
            time.sleep(1)
            if state["done"] and done_at is None:
                done_at = time.time()
            # "stop" on stdin does not always reach the game through Gradle: give it 45 s, then kill the tree
            if (done_at and time.time() - done_at > 45) or time.time() - t0 > a.timeout:
                kill_tree()
                break
        th.join(10)
    secs = round(time.time() - t0)
    ok = state["done"] if a.task == "server" else p.returncode == 0
    status_p = root / "studio" / "test-status.json"
    st = load_json(status_p) if status_p.exists() else {}
    st[a.task] = ok
    st[f"{a.task}_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_json(status_p, st)
    if ok:
        extra = ""
        if a.task == "build":
            jars = [j.name for j in (root / "build/libs").glob("*.jar") if "sources" not in j.name]
            extra = f" -> build/libs/{', '.join(jars)}"
        print(f"PASS: {task} in {secs}s{extra}")
        sys.exit(0)
    level = "LOOK" if a.task == "client" else "FAIL"
    print(f"{level}: {task} after {secs}s (exit {p.returncode}) — log: {log_path}")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    scan = log_scan.scan(text)
    for f in scan["findings"][:3]:
        print(f"  [{f['rule']}] {f['match'][:150]}\n     fix: {f['fix']}")
    errs = [l for l in text.splitlines() if re.search(r"error:|ERROR|FAILED|Exception|What went wrong", l)][:8]
    for l in errs:
        print("  | " + l.strip()[:200])
    sys.exit(0 if level == "LOOK" else 1)


if __name__ == "__main__":
    main()
