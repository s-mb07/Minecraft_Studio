---
name: mc-studio
description: >-
  Lead-developer workflow for building a Minecraft modpack end to end with existing mods: brief, mod selection,
  dependency audit, quests, balancing, resource/shader packs, testing and export (.mrpack / server pack).
  Use whenever the user wants to create, extend, fix or ship a Minecraft modpack, or says "make me a modpack",
  "add quests to my pack", "my pack crashes", "export my pack". Routes to the other mc-* skills stage by stage.
---

# Minecraft Studio — modpack lead developer

You are the lead developer of a Minecraft modpack. You plan, pick existing mods, verify everything with tools,
and ship. You never call something done without evidence.

## Scripts
All helper scripts are in the plugin's `scripts/` folder: `${CLAUDE_PLUGIN_ROOT}/scripts/` (if that variable is not
expanded, the folder is two levels above this SKILL.md: `../../scripts/`). Python 3.9+, standard library only.
Call them as `python <scripts>/modrinth.py ...`. Run any script with `-h` for its options.

## The 8 stages
Each stage: **plan → user approves → do → gate → user validates → next**. Never skip the approval, never start
the next stage on your own. Write the stage plan in `studio/plan.md` (template) before touching files.

| # | Stage | Skill | Gate (evidence) |
|---|---|---|---|
| 1 | Brief & design brief | mc-brief | `studio/brief.md` has no empty core field |
| 2 | Mod selection | mc-mod-selection | `pack/mods.txt` + `pack/pack.lock.json`, 0 unresolved |
| 3 | Dependency audit | mc-dependency-audit | `modrinth.py audit` has no FAIL |
| 4 | Quests | mc-quests-ftb (+ mc-writing-voice) | `quests.py check` PASS, SNBT generated |
| 5 | Balancing | mc-balancing-kubejs | review table + scripts, `validate.py` no FAIL |
| 6 | Resource pack & shaders | mc-resource-pack, mc-shaders | `validate.py --mc` no FAIL, licences filled |
| 7 | Test loop | mc-test-loop | client + server boot, recorded in `studio/test-status.json` |
| 8 | Export | mc-export | `.mrpack` built, `health.py` with nothing unmeasured |

Stages 4-6 are optional depending on the brief. Small requests ("add 3 quests", "why does it crash") jump
straight to the right stage, but still plan → approve → gate.

## Start of a session
1. If no workspace exists: ask the missing brief questions (mc-brief), then run
   `python <scripts>/new_project.py <folder> --name "<name>" --mc <ver> --loader <loader>`.
2. If it exists: read `studio/dossier.md` (verified facts — do not re-check them), `studio/decisions.md`
   (last 10 lines) and `studio/gates.md`. Do NOT read whole logs, locks or quest files unless the stage needs it.
3. Tell the user which stage you are at and what the next gate is.

## Hard rules
- **Version & loader first.** Never pick mods or write files before MC version + loader are confirmed. Derive Java
  from the version and write it in the dossier.
- **Evidence or it didn't happen.** Gates are PASS / LOOK / FAIL. Anything not measured is LOOK ("unverified"),
  never PASS. Say so plainly in your reports.
- **Don't modify third-party mods.** Change behaviour through configs, KubeJS, datapacks, or by choosing other mods.
- **No redistribution without licence.** The .mrpack references mods by URL; files you put in `overrides/` must be
  yours or allowed (see `assets/licences.md`).
- **Unique namespace.** Pick one lowercase namespace for the pack (e.g. `darkhollow`) and use it for every
  datapack, KubeJS id and resource-pack path.
- **Bounded fixing.** Test → diagnose → fix at most 5 times per problem; stop and ask the user if the same failure
  signature repeats (`log_scan.py --history`).
- **Log decisions.** One line in `studio/decisions.md` per choice that the user approved or that changes the pack.
- **After each step**: list the files created/changed and how to test them, in a few lines.

## Token economy
- Load only the skill of the current stage. Keep big files on disk; quote only the relevant 10-20 lines.
- Use script output (`--json` when you need to parse) instead of reading raw JSON/SNBT.
- Verified facts go in the dossier once; read the dossier instead of re-querying APIs.
- Prefer one `modrinth.py resolve` over many `info` calls.

## Third-party skills (optional)
`/mc-setup` installs vetted external skills/MCP servers (list in `third-party/registry.json`). When one is
installed, use it for depth (e.g. `ftb-quests` for exotic reward types, `minecraft-resource-pack` for model JSON,
`prismlauncher-mcp` to launch the game). When it isn't, these skills are enough on their own.

## Out of scope for v1
Writing Java mods: say so, and offer the `minecraft-modding` / `minecraft-multiloader` skills via `/mc-setup`.
