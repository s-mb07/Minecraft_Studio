#!/usr/bin/env python3
"""Headless server boot test: the cheapest real proof that a modpack loads.

  server_test.py <workspace> --accept-eula [--timeout 900] [--java java] [--xmx 4G] [--keep]

Steps: install the loader server in <workspace>/.run/server, download server-side files from pack.lock.json
(hash-checked), copy pack/overrides + pack/server-overrides, write eula.txt, start with nogui, wait for
"Done (" -> send "stop". Result goes to studio/test-status.json (server_boot) and studio/test-log.md.
On failure, run log_scan.py on .run/server.

--accept-eula: you (the user) accept the Minecraft EULA https://aka.ms/MinecraftEULA . Claude must ask you.
Supported loaders: fabric, neoforge, forge. Quilt: install the server manually, then use log_scan.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, download, file_hashes, http_json, load_json, save_json  # noqa: E402


def install_server(lock: dict, run: Path, java: str) -> list[str]:
    mc, loader, lv = lock["minecraft"], lock["loader"], lock.get("loader_version")
    if not lv:
        die("lock has no loader_version")
    run.mkdir(parents=True, exist_ok=True)
    if loader == "fabric":
        inst = http_json("https://meta.fabricmc.net/v2/versions/installer")[0]["version"]
        jar = run / "fabric-server-launch.jar"
        if not jar.exists():
            download(f"https://meta.fabricmc.net/v2/versions/loader/{mc}/{lv}/{inst}/server/jar", jar)
        return [java, "-jar", jar.name, "nogui"]
    if loader in ("neoforge", "forge"):
        if loader == "neoforge":
            url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{lv}/neoforge-{lv}-installer.jar"
            args_dir = run / "libraries" / "net" / "neoforged" / "neoforge" / lv
        else:
            full = lv if lv.startswith(mc) else f"{mc}-{lv}"
            url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full}/forge-{full}-installer.jar"
            args_dir = run / "libraries" / "net" / "minecraftforge" / "forge" / full
        args_file = args_dir / ("win_args.txt" if os.name == "nt" else "unix_args.txt")
        if not args_file.exists():
            inst = download(url, run / "installer.jar")
            print("  installing loader server (can take a few minutes)...")
            subprocess.run([java, "-jar", inst.name, "--installServer"], cwd=run, check=True,
                           stdout=subprocess.DEVNULL)
        if not args_file.exists():
            die(f"installer finished but {args_file} is missing — check the loader version")
        jvm = run / "user_jvm_args.txt"
        return [java, f"@{jvm.name}", f"@{args_file.relative_to(run).as_posix()}", "nogui"]
    die(f"loader {loader} not supported by server_test.py")


def copy_tree(src: Path, dst: Path):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--accept-eula", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--java", default="java")
    ap.add_argument("--xmx", default="4G")
    ap.add_argument("--keep", action="store_true", help="keep the world between runs")
    a = ap.parse_args()
    if not a.accept_eula:
        die("you must accept the Minecraft EULA (https://aka.ms/MinecraftEULA): re-run with --accept-eula")
    if not shutil.which(a.java):
        die(f"java not found ('{a.java}'). Install Java {load_json(Path(a.workspace) / 'pack' / 'pack.lock.json').get('java')}")
    ws = Path(a.workspace)
    lock = load_json(ws / "pack" / "pack.lock.json")
    run = ws / ".run" / "server"
    cmd = install_server(lock, run, a.java)

    # mods: remove jars not in the lock (stale versions are a classic crash cause)
    wanted = {}
    for e in lock["entries"]:
        if e["env"]["server"] == "unsupported" or e["type"] in ("resourcepack", "shader"):
            continue
        wanted[e["path"]] = e
    mods = run / "mods"
    mods.mkdir(exist_ok=True)
    for f in mods.glob("*.jar"):
        if f"mods/{f.name}" not in wanted:
            f.unlink()
    for path, e in wanted.items():
        t = run / path
        if not (t.exists() and file_hashes(t)["sha512"] == e["file"]["sha512"]):
            print(f"  downloading {path}")
            download(e["file"]["url"], t)
            if file_hashes(t)["sha512"] != e["file"]["sha512"]:
                die(f"hash mismatch {path}")
    copy_tree(ws / "pack" / "overrides", run)
    copy_tree(ws / "pack" / "server-overrides", run)
    (run / "eula.txt").write_text("eula=true\n")
    props = run / "server.properties"
    if not props.exists():
        props.write_text("online-mode=false\nserver-port=25599\nspawn-protection=0\nmotd=minecraft-studio test\n")
    if not a.keep:
        shutil.rmtree(run / "world", ignore_errors=True)
    if cmd[1].startswith("@"):
        (run / "user_jvm_args.txt").write_text(f"-Xmx{a.xmx}\n")
    else:
        cmd.insert(1, f"-Xmx{a.xmx}")

    print(f"  starting: {' '.join(cmd)} (timeout {a.timeout}s)")
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=run, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    result = {"ok": False, "reason": "timeout"}

    def reader():
        for line in p.stdout:
            if "Done (" in line and "For help" in line:
                result.update(ok=True, reason="Done")
                try:
                    p.stdin.write("stop\n")
                    p.stdin.flush()
                except OSError:
                    pass
            elif "Exception" in line or "ERROR" in line:
                result.setdefault("first_error", line.strip()[:300])
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    try:
        p.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        p.kill()
    th.join(5)
    if not result["ok"] and p.returncode not in (None, 0):
        result["reason"] = f"exited with code {p.returncode}"
    secs = round(time.time() - t0)

    status_p = ws / "studio" / "test-status.json"
    status = load_json(status_p) if status_p.exists() else {}
    status["server_boot"] = result["ok"]
    status["server_boot_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_json(status_p, status)
    log = ws / "studio" / "test-log.md"
    if log.exists():
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"| auto | {dt.date.today()} | server | {'PASS' if result['ok'] else 'FAIL'} ({secs}s) | "
                    f"| | {result.get('first_error', '')[:80].replace('|', '/')} |\n")
    if result["ok"]:
        print(f"PASS: server reached 'Done' in {secs}s ({len(wanted)} server-side files)")
        return 0
    print(f"FAIL: {result['reason']} after {secs}s")
    print(f"  next: python {Path(__file__).parent / 'log_scan.py'} {run} --history {ws / 'studio' / 'fix-history.json'}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
