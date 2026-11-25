---
name: mc-dependency-audit
description: >-
  Stage 3 of a Minecraft modpack: verify the pinned mod list before anyone launches the game — loader and version
  match, required dependencies present, declared incompatibilities, duplicates, overlapping mods, client/server
  sides, beta versions and licences. Use after changing pack.lock.json, before testing, or when the user asks
  "is my mod list compatible?". Also handles migrating a pack to another MC version or loader.
---

# Dependency audit

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Run
```
python <scripts>/modrinth.py audit pack/pack.lock.json          # human report
python <scripts>/modrinth.py audit pack/pack.lock.json --json   # to parse
```
Gate: no FAIL. LOOK items must each get a decision (keep / replace / accept) written in `studio/decisions.md`.

## What each finding means and what to do
| Finding | Action |
|---|---|
| unresolved / not found | wrong slug or no version: search again or replace |
| version does not list MC X / is for loader Y | re-resolve; if no build exists, replace the mod |
| required dependency missing | re-run `resolve` (it pulls deps), never add jars by hand |
| declared INCOMPATIBLE with ... | remove one of the two; tell the user which and why |
| overlapping mods (renderer, minimap ...) | keep one unless the user wants both on purpose |
| beta/alpha version | accept only if no release exists; note it in the README "Known issues" |
| licence ARR/unknown | fine in .mrpack (download by URL), NOT fine to copy into overrides or a server pack you publish |
| client-only / server-only | expected; just make sure server-only mods are not needed on the client |
| loader_version empty | `modrinth.py loader-version --mc X --loader Y`, then write it in the lock |

The script also always reports `runtime: not measured` — static checks can't prove the game boots. That is
stage 7 (mc-test-loop).

## Things the script can't see (check by reading mod pages / changelogs when relevant)
- Mods that need a specific *version range* of another mod (only visible at launch → test loop).
- Mixin-heavy mods known to clash (e.g. two mods that both rewrite rendering or chunk loading).
- Mods whose features are already covered by a mod in the pack (content duplication: two copper ores, two backpacks).
- Config-driven conflicts (two world-gen mods spawning the same structures).
Write what you find in the mod sheets / decisions log.

## Migration (change MC version or loader)
1. Copy the workspace to a new branch/folder. Never migrate in place.
2. `resolve` the same `mods.txt` with the new `--mc/--loader` into a new lock.
3. Classify every mod: keep (same mod exists) / replace (equivalent mod) / drop (nothing) — table for the user.
4. Port configs, KubeJS scripts, quests: item IDs may have changed; FTB Quests item format changed in 1.21
   (`quests.py build --format 1.21`). Pack formats changed: `validate.py --mc <new>`.
5. Re-audit, then full test loop. Quests and KubeJS must be re-validated in game — say so.

For deeper migration tooling, `/mc-setup` can install the `choice21hax/MinecraftSkills` skills (review first).
