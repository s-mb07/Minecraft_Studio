---
name: mc-mod-dev
description: >-
  Build a Minecraft Java mod end to end (Fabric or NeoForge; Forge 1.20.1 documented): concept, scaffold from the
  official template, items/blocks/entities, textures, Blockbench models, datagen, build, tests, jar. Use whenever
  the user wants to create or extend a mod ("make a mod with an obsidian sword", "add a block to my mod",
  "my mod doesn't compile"). Routes to the other mc-mod-* skills.
---

# Mod development — lead developer

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/` from this file). Python 3.9+, stdlib only.

## Autonomy policy (read first)
- **Default: Fast mode.** Do all local, reversible work yourself: scaffold, code, assets, models, datagen,
  fixes, builds, tests, packaging. Never ask "can I create/add/build/fix/retry?".
- **FAIL = repair and rerun** (max 3 attempts or 10 min per failing check), then continue. **LOOK = keep going**,
  mention it in the final summary.
- **Ask (one short line) only for:** publishing (Modrinth, git push, release), deleting/overwriting work that can't
  be recovered, secrets/tokens, installs or settings outside the project, the Minecraft EULA (once per project,
  stored in `studio/dossier.md`), or a request that is genuinely ambiguous. Batch questions into one round.
- **Modes** (user can say it any time): *Fast* (default, report at the end) · *Balanced* (show a 5-line plan, then run)
  · *Guided* (ask the key design questions once: theme, style, content list — then run without routine prompts).
- **Protect existing work:** before overwriting a file the user made, copy it to `.studio-backup/<date>/` or write a
  new path. Never silently destroy user content.
- **Optional integrations never block:** Blockbench MCP, client launch, screenshots, GeckoLib, TLauncher.
- **Tokens:** scripts print only FAIL/LOOK by default; read logs through `log_scan`/`gradle_run` summaries, not in full.

## Reference mods (study / reuse)
- "study this mod", "how does X work?", "make something similar" → **mc-mod-study** (analysis, then an original build).
- "copy this model and change it", "reuse this texture recoloured", "take this system and adapt/port it" →
  **mc-mod-study** (`reuse_apply.py`), then this pipeline from step 3.
- Follow the *Reference analysis and reuse policy* in mc-mod-study: analysis is automatic, reuse happens when the
  user asks, the licence is shown in one line and logged, and nothing blocks on an unknown licence.

## Pipeline (runs end to end in Fast mode)
| Step | Skill | Automatic check |
|---|---|---|
| 1 Concept | (this) | loader + MC version known (default **NeoForge or Fabric 1.21.1**), content list, modid |
| 2 Scaffold | mc-mod-scaffold | `mod_new.py` succeeded |
| 3 Content (Java) | mc-mod-content | `mod_check.py --fix` no FAIL |
| 4 Textures | mc-mod-textures | `validate.py` on resources |
| 5 Models | mc-blockbench (optional: mc-geckolib) | `bbmodel_check.py` + `mod_check.py` |
| 6 Data | mc-mod-datagen or hand-written JSON | `mod_check.py` |
| 7 Build & test | mc-mod-build-test | build PASS, gametest PASS, server boots |
| 8 Package | mc-mod-release | jar inspected; publish only after confirmation |

Loop for steps 3-7: write → `mod_check.py <mod> --fix` → fix the remaining FAILs → `gradle_run.py <mod> build` → on FAIL
read the printed summary, fix, rebuild. Then `gametest`, then `server` (EULA asked once).

## Concept (keep it short)
From the request, derive: modid (lowercase, 2-64 chars, `[a-z0-9_]`), display name, package (`io.github.<user>.<modid>`
if unknown), loader + version, and a content list (items, blocks, entities, recipes, worldgen...). Only ask if the
loader matters to the user (e.g. they want it in a specific modpack) or the idea is unclear. One mod = one loader;
multiloader only on explicit request, after a single-loader version works.

## Final summary (≤ 10 lines)
What was built (content list), jar path, checks (build/gametest/server/client: PASS/LOOK + reason), what's not
verified, and the one next step. Offer publishing; don't do it unasked.

## Scope notes
- Validated end to end by Minecraft Studio: Fabric 1.21.1, NeoForge 1.21.1 (examples in the repo: `examples/`).
- Documented, not validated: Forge 1.20.1 (`mod_new.py --loader forge`), 26.x (Java 25), multiloader
  (Architectury / MultiLoader-Template — see the `minecraft-multiloader` skill via `/mc-setup`).
- Adding the mod to a modpack: drop the jar into the pack's `overrides/mods/` (own work, so redistribution is fine).
