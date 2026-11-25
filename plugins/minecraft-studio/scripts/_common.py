"""Shared helpers for Minecraft Studio scripts (Python 3.9+, standard library only)."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Minecraft-Studio/0.1 (+https://github.com/s-mb07/Minecraft_Studio)"
MODRINTH_API = "https://api.modrinth.com/v2"

for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Loader ids as used by Modrinth and by modrinth.index.json "dependencies".
LOADERS = {
    "fabric": "fabric-loader",
    "quilt": "quilt-loader",
    "neoforge": "neoforge",
    "forge": "forge",
}

# Resource / data pack formats. Sources: Minecraft Wiki "Pack format".
# Keep this table small and verified; unknown versions are reported as LOOK, never guessed.
RESOURCE_PACK_FORMAT = {
    "1.20.1": 15, "1.20.2": 18, "1.20.3": 22, "1.20.4": 22, "1.20.5": 32, "1.20.6": 32,
    "1.21": 34, "1.21.1": 34, "1.21.2": 42, "1.21.3": 42, "1.21.4": 46, "1.21.5": 55,
    "1.21.6": 63, "1.21.7": 64, "1.21.8": 64,
}
DATA_PACK_FORMAT = {
    "1.20.1": 15, "1.20.2": 18, "1.20.3": 26, "1.20.4": 26, "1.20.5": 41, "1.20.6": 41,
    "1.21": 48, "1.21.1": 48, "1.21.2": 57, "1.21.3": 57, "1.21.4": 61, "1.21.5": 71,
    "1.21.6": 80, "1.21.7": 81, "1.21.8": 81,
}


def java_for(mc_version: str) -> str:
    """Minimum Java for a Minecraft version (Java Edition)."""
    parts = [int(p) for p in mc_version.split(".")[:3] if p.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts
    if major >= 26:
        return "25 (verify on the Minecraft Wiki)"
    if (minor, patch) >= (20, 5):
        return "21"
    if minor >= 18:
        return "17"
    if minor == 17:
        return "16"
    return "8"


# ---------- HTTP ----------

def http_json(url: str, params: dict | None = None, retries: int = 3):
    if params:
        enc = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in params.items()}
        url = f"{url}?{urllib.parse.urlencode(enc)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and attempt < retries - 1:
                time.sleep(int(e.headers.get("X-Ratelimit-Reset", "5")))
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    return dest


def file_hashes(path: Path) -> dict:
    sha1, sha512 = hashlib.sha1(), hashlib.sha512()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            sha1.update(chunk)
            sha512.update(chunk)
    return {"sha1": sha1.hexdigest(), "sha512": sha512.hexdigest()}


# ---------- Gate reporting (PASS / LOOK / FAIL) ----------
# Rule: anything we could not measure is LOOK ("unverified"), never PASS.

class Report:
    def __init__(self, title: str):
        self.title = title
        self.items: list[tuple[str, str, str]] = []  # (level, where, message)

    def add(self, level: str, where: str, msg: str):
        assert level in ("PASS", "LOOK", "FAIL")
        self.items.append((level, where, msg))

    def ok(self, where, msg): self.add("PASS", where, msg)
    def look(self, where, msg): self.add("LOOK", where, msg)
    def fail(self, where, msg): self.add("FAIL", where, msg)

    @property
    def verdict(self) -> str:
        levels = {i[0] for i in self.items}
        if "FAIL" in levels:
            return "FAIL"
        if "LOOK" in levels or not self.items:
            return "LOOK"
        return "PASS"

    def print(self, as_json: bool = False, quiet_pass: bool = False):
        if as_json:
            print(json.dumps({"title": self.title, "verdict": self.verdict,
                              "items": [{"level": l, "where": w, "message": m} for l, w, m in self.items]},
                             indent=2, ensure_ascii=False))
            return
        print(f"== {self.title}: {self.verdict}")
        for level, where, msg in self.items:
            if quiet_pass and level == "PASS":
                continue
            print(f"  [{level}] {where}: {msg}")
        counts = {k: sum(1 for i in self.items if i[0] == k) for k in ("PASS", "LOOK", "FAIL")}
        print(f"  -- {counts['PASS']} pass, {counts['LOOK']} look, {counts['FAIL']} fail")

    def exit_code(self) -> int:
        return {"PASS": 0, "LOOK": 0, "FAIL": 1}[self.verdict]


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def die(msg: str, code: int = 2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)
