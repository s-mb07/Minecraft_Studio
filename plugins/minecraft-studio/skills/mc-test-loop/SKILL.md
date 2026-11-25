---
name: mc-test-loop
description: >-
  Stage 7 of a Minecraft modpack: launch the pack (headless server and/or client), read latest.log and crash
  reports, identify the guilty mod, apply a fix and retest — in a bounded loop that stops when the same failure
  repeats. Use when the user says "test my pack", "it crashes", "won't start", pastes a crash report, or before export.
---

# Test & fix loop

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Order of tests (cheapest proof first)
1. **Static**: `modrinth.py audit` + `validate.py` must already be clean (stages 3-6).
2. **Server boot** (automated, no account needed):
   ```
   python <scripts>/server_test.py <workspace> --accept-eula
   ```
   Ask the user first: "This accepts the Minecraft EULA (https://aka.ms/MinecraftEULA) for a local test server — OK?"
   Needs Java (version in the dossier). Writes `studio/test-status.json` → `server_boot`.
3. **Client boot to title screen + world load**:
   - with **prismlauncher-mcp** installed (`/mc-setup`): create/update an instance from the .mrpack, launch, wait,
     read `latest.log`, take a screenshot.
   - otherwise: build the .mrpack (`build_mrpack.py`), ask the user to import it in Prism Launcher / Modrinth App,
     launch, create a world, then give you the instance folder path.
   Record `client_boot: true/false` in `studio/test-status.json`.
4. **Quest walkthrough** (first chapter at least): user or bot plays it; record `quest_walkthrough`.

## The loop (max 5 attempts per problem)
```
python <scripts>/log_scan.py <instance-or-server-dir> --history <workspace>/studio/fix-history.json
```
1. Read the scan: rule, line, suspects, suggested fix. Quote only the relevant log lines to the user.
2. Propose ONE fix (smallest change): update/pin a version, add a dependency, remove a mod, fix a config or a KubeJS
   line. Explain why in one sentence. Apply after the user OKs it (or directly if they said "fix it yourself").
3. Change the source of truth (`mods.txt` → re-`resolve`, overrides, design.json), never the test copy.
4. Retest the same way. Log the attempt in `studio/test-log.md` (# · side · result · signature · suspect · fix).
5. **Stop** when: it passes; OR `log_scan` exits with code 3 / prints STOP (same signature as a previous attempt);
   OR 5 attempts. On stop, summarise what was tried and ask the user how to proceed.

## Diagnosis tips
- No pattern matched → read the last 60 lines of `latest.log` and the `Caused by:` chain of the crash report.
- Many suspects → **bisect**: disable half of the non-core mods (keep dependencies together), retest, repeat.
- Works on server, crashes on client → client-only mod (renderer, shader, UI) or a resource pack.
- Crash only when joining a world → world-gen / structure mods, or a datapack; test in a fresh world.
- `UnsupportedClassVersionError` → wrong Java, not a mod bug.
- Very slow boot (> 5 min) or OOM → raise `--xmx`, check for heavy mods, note it in the README.

## Gate
`server_boot: true` and `client_boot: true` with dates, no KubeJS errors in `logs/kubejs/`, and the user saw the
title screen / a world. Anything not run is reported as "not tested", never as passed.
