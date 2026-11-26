---
name: mc-mod-build-test
description: >-
  Build and test a Minecraft mod automatically: mod_check, Gradle build with the right JDK, headless GameTests,
  dev server boot, optional dev client, crash/compile triage and a bounded repair loop. Use for "build", "compile",
  "test my mod", "it crashes", Gradle errors.
---

# Build & test (automatic)

```
python <scripts>/mod_check.py  <mod> --fix          # always first; repairs mechanical issues
python <scripts>/gradle_run.py <mod> build          # jar in build/libs
python <scripts>/gradle_run.py <mod> gametest       # headless GameTests, exits with the result
python <scripts>/gradle_run.py <mod> server --accept-eula   # dev server until "Done", then stop
python <scripts>/gradle_run.py <mod> client         # optional, LOOK on failure
```
`gradle_run.py` picks the JDK the build asks for (JAVA_HOME, `C:\Java\*`, standard folders), writes the full log to
`studio/logs/<task>.log`, prints only PASS/FAIL + a short diagnosis, and records `studio/test-status.json`.
First build downloads Minecraft + mappings (5-15 min); later builds are fast.

## Repair loop (no user prompts)
1. `mod_check.py --fix` until no FAIL (it never deletes; it adds lang keys, item models, namespaces texture refs).
2. Build. On FAIL read the printed lines (compiler `error:` lines with file:line). Typical causes: wrong import/class name
   for the MC version, method renamed, missing dependency in `build.gradle`. Fix the code, rebuild.
3. GameTest / server FAIL: the summary shows `log_scan` rules (mixin, missing dependency, registry, client class on server).
4. Max **3 attempts or 10 minutes per failing check**. If still failing: stop, summarise what was tried, ask the user one
   precise question. Same error twice in a row = try a different approach, not the same fix.

## EULA (once per project)
`server` needs the Minecraft EULA. If `studio/dossier.md` doesn't say `EULA accepted (dev server) | yes`, ask once:
"The dev server needs the Minecraft EULA (https://aka.ms/MinecraftEULA) — accept for this project?" then pass
`--accept-eula` (it's remembered). GameTests don't need it. User can revoke by editing the dossier line.

## Client check (optional, never blocking)
`client` starts the dev client with an offline dev account. If it fails (no display, auth, GPU), record the reason as
LOOK and rely on gametest + server. Never require TLauncher or any unofficial launcher.

## Checks summary to report
`mod_check` · `build` · `gametest` · `server` · `client` — each PASS / FAIL / LOOK (+ reason) / not run.
