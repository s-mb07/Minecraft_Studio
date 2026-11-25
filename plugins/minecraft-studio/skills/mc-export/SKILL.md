---
name: mc-export
description: >-
  Stage 8 of a Minecraft modpack: package and release — Modrinth .mrpack, server pack, CurseForge route,
  README, credits and licences, changelog, version bump, final health score. Use for "export", "release",
  "make a .mrpack", "server pack", "publish my modpack".
---

# Export & release

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Pre-flight (all must hold, else stop and say what's missing)
- `modrinth.py audit pack/pack.lock.json` → no FAIL, `loader_version` pinned
- `validate.py pack --mc <ver>` → no FAIL
- `studio/test-status.json` → `server_boot` and `client_boot` true, dated after the last lock change
- `health.py <workspace>` → nothing listed as NOT MEASURED (or the user explicitly accepts the gap)

## Build
```
python <scripts>/build_mrpack.py pack/pack.lock.json --out dist --version 1.0.0
python <scripts>/build_mrpack.py pack/pack.lock.json --out dist --version 1.0.0 --server-pack
```
- `.mrpack`: mods referenced by URL + hash, `overrides/`, `client-overrides/`, `server-overrides/` included.
  Import test: Prism Launcher → Add instance → Import → the .mrpack. Do it once before publishing.
- Server pack: downloads server-side files and zips them with overrides + a README-SERVER.txt.
  **Publishing a server pack redistributes mod jars**: only do it if every included mod's licence allows it
  (check the audit's licence lines); otherwise publish the .mrpack only and point server owners to it
  (tools like mrpack-install can build the server from the .mrpack).
- **CurseForge**: a .mrpack can't be uploaded to CurseForge. Options: import the .mrpack in Prism and export as
  CurseForge (needs all mods to exist on CurseForge), or rebuild the list with packwiz. Tell the user plainly.

## Docs to ship (generate, then let the user edit)
- `README.md` (template): pitch, versions, RAM, install steps, features, known issues (beta mods, shader cost).
- `CREDITS.md`: one row per lock entry — title, licence, Modrinth link. Generate it from the lock; don't write by hand.
- `assets/licences.md`: every non-Modrinth asset in overrides. No TODO left.
- `CHANGELOG.md`: added / removed / updated mods since the last version (diff the old and new lock), balance changes,
  quest changes. Players care about "will my world break?": say it when keys/IDs changed.

## Versioning
`MAJOR.MINOR.PATCH`: MAJOR = MC version or world-breaking change, MINOR = content added, PATCH = fixes/config.
Bump `version` in the lock, tag the git commit `v1.0.0`, attach `dist/*` to the release.

## Final report to the user
Health score with measured weight, gates table (`studio/gates.md` updated), file list in `dist/`, and what was
not verified. Never claim "ready to publish" while something is unmeasured.
