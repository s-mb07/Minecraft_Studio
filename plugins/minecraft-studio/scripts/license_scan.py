#!/usr/bin/env python3
"""Detect a reference's licence: LICENSE/COPYING/NOTICE files, SPDX headers, mod metadata, Modrinth.

  license_scan.py <ref-id> [--root .]

Result known | unknown | mixed, written to licence.json and meta.json. One line of output.
Informational only: it never blocks anything.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import save_json  # noqa: E402
import _ref  # noqa: E402

TEXT_RULES = [  # (spdx, regex on licence text) - most specific first
    ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE[\s\S]{0,200}Version 3"),
    ("LGPL-2.1", r"GNU LESSER GENERAL PUBLIC LICENSE[\s\S]{0,200}Version 2\.1"),
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE[\s\S]{0,200}Version 3"),
    ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE[\s\S]{0,200}Version 2"),
    ("Apache-2.0", r"Apache License[\s\S]{0,100}Version 2\.0"),
    ("MPL-2.0", r"Mozilla Public License[\s\S]{0,50}2\.0"),
    ("CC0-1.0", r"CC0 1\.0|Creative Commons Zero|No Copyright"),
    ("CC-BY-NC-SA-4.0", r"Attribution-NonCommercial-ShareAlike 4\.0"),
    ("CC-BY-NC-4.0", r"Attribution-NonCommercial 4\.0"),
    ("CC-BY-SA-4.0", r"Attribution-ShareAlike 4\.0"),
    ("CC-BY-4.0", r"Attribution 4\.0 International"),
    ("Unlicense", r"This is free and unencumbered software"),
    ("BSD-3-Clause", r"Neither the name of[\s\S]{0,200}endorse or promote"),
    ("MIT", r"Permission is hereby granted, free of charge"),
    ("ARR", r"All Rights Reserved"),
]
ALIASES = {"mit": "MIT", "apache 2.0": "Apache-2.0", "apache-2.0": "Apache-2.0", "apache2": "Apache-2.0",
           "gpl-3.0": "GPL-3.0", "gplv3": "GPL-3.0", "gpl3": "GPL-3.0", "lgpl-3.0": "LGPL-3.0", "lgplv3": "LGPL-3.0",
           "lgpl-2.1": "LGPL-2.1", "mpl-2.0": "MPL-2.0", "cc0": "CC0-1.0", "cc0-1.0": "CC0-1.0", "cc-by-4.0": "CC-BY-4.0",
           "all rights reserved": "ARR", "arr": "ARR", "unlicense": "Unlicense", "lgpl-3.0-only": "LGPL-3.0",
           "gpl-3.0-only": "GPL-3.0", "gpl-3.0-or-later": "GPL-3.0", "lgpl-3.0-or-later": "LGPL-3.0"}
NOTES = {"MIT": "attribution (keep notice)", "Apache-2.0": "attribution + NOTICE", "BSD-3-Clause": "attribution",
         "CC-BY-4.0": "attribution", "CC-BY-SA-4.0": "attribution, share-alike", "GPL-3.0": "copyleft (GPL)",
         "GPL-2.0": "copyleft (GPL)", "LGPL-3.0": "weak copyleft", "LGPL-2.1": "weak copyleft", "AGPL-3.0": "copyleft",
         "MPL-2.0": "file-level copyleft", "CC0-1.0": "public domain", "Unlicense": "public domain",
         "ARR": "all rights reserved", "CC-BY-NC-4.0": "non-commercial", "CC-BY-NC-SA-4.0": "non-commercial"}


def norm(s: str | None) -> str | None:
    if not s or not isinstance(s, str) or "${" in s:
        return None
    k = s.strip().lower()
    return ALIASES.get(k) or (s.strip() if re.match(r"^[A-Za-z0-9.+-]+$", s.strip()) else s.strip()[:40])


def from_text(t: str) -> str | None:
    for spdx, rx in TEXT_RULES:
        if re.search(rx, t, re.I if spdx != "ARR" else 0):
            return spdx
    return None


def scan(ref: Path) -> dict:
    found: dict[str, list[str]] = {}

    def hit(spdx, where):
        if spdx and spdx.upper() not in ("LICENSEREF-CUSTOM", "UNKNOWN"):
            found.setdefault(spdx, []).append(where)

    import mod_inventory
    m = _ref.meta(ref)
    hit(norm(m.get("modrinth_licence")), "modrinth")
    hit(norm(mod_inventory.read_meta(ref).get("licence_field")), "mod metadata")
    for p in _ref.meta_files(ref):
        if re.match(r"(LICEN[CS]E|COPYING|NOTICE)", p.name, re.I):
            hit(from_text(p.read_text(encoding="utf-8", errors="replace")[:20000]), p.name)
    for f in _ref.java_files(ref)[:300]:
        h = re.search(r"SPDX-License-Identifier:\s*([\w.+-]+)", f.read_text(encoding="utf-8", errors="replace")[:600])
        if h:
            hit(norm(h.group(1)), "SPDX header")
    names = sorted(found, key=lambda k: -len(found[k]))
    # same family (e.g. GPL-3.0 text + "GPL-3.0-or-later" field) counts as one
    fam = {re.sub(r"-(only|or-later)$", "", n) for n in names}
    status = "unknown" if not names else "known" if len(fam) == 1 else "mixed"
    res = {"licence": " + ".join(names) if names else "unknown", "status": status, "sources": found,
           "note": "; ".join(NOTES[n] for n in names if n in NOTES), "scanned": _ref.now()}
    save_json(ref / "licence.json", res)
    m["licence"], m["licence_status"] = res["licence"], status
    _ref.save_meta(ref, m)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id"); ap.add_argument("--root", default=".")
    a = ap.parse_args()
    r = scan(_ref.need(Path(a.root), a.id))
    src = ", ".join(sorted({w for v in r["sources"].values() for w in v})) or "nothing found"
    print(f"LICENCE: {r['licence']} ({r['status']}){' · ' + r['note'] if r['note'] else ''} · from {src}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
