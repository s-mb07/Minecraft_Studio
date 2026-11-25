---
name: mc-quests-ftb
description: >-
  Stage 4 of a Minecraft modpack: design a quest progression (chapters, dependencies, tasks, rewards) and
  generate FTB Quests SNBT files from a readable JSON design, or vanilla advancements when the pack has no quest
  mod. Use for "add quests", "quest book", "progression", "chapters", FTB Quests, .snbt files.
---

# Quests (FTB Quests, vanilla fallback)

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Principle: the design file is the source
Write and edit `quests/design.json` (readable, diffable), then generate SNBT. Never hand-edit generated chapter
files: they are overwritten on the next build. IDs are derived from quest keys, so regenerating keeps player
progress as long as keys don't change. **Never rename a key in a released pack** — add a new quest instead.
Schema: see `templates/quest-design.example.json` and `quests.py -h`.

## 1. Design the progression first (no files yet)
Give the user a chapter outline for approval:
- 1 chapter = 1 phase of play (e.g. First night → Tools → Exploration → Boss → Endgame). 5-15 quests each.
- Every chapter has one entry quest. Every quest has a purpose: teach a mod, gate a resource, or reward a milestone.
- Use the mod sheets (stage 2) to anchor quests on real items from mods that are in the lock.
- Branching: main line + optional side quests (`"optional": true`). Avoid > 3 dependencies per quest.
- Show the tree: `python <scripts>/quests.py mermaid quests/design.json`.

## 2. Tasks and rewards that make sense
| Phase | Typical tasks | Reward scale |
|---|---|---|
| Early | gather (16-64 basic items), craft first tool, checkmark tutorial | food, a few torches, 50-100 xp |
| Mid | craft a machine, visit a dimension, kill N mobs, reach a biome/structure | components that save 10-20 min, 1-3 levels |
| Late | multi-step builds, boss kills, rare items | choice rewards, loot crates, cosmetic items |
Rules: rewards never skip the thing the next quest teaches; don't reward items the quest consumed; ≤ 1 reward
that gives a big shortcut per chapter; prefer `consume: false` unless it's a sink on purpose.

## 3. Write text with mc-writing-voice
Title ≤ 4 words, subtitle ≤ 1 line, description ≤ 3 short lines, follow `studio/style-guide.md`. Don't repeat
what the task already says.

## 4. Check, build, validate
```
python <scripts>/quests.py check quests/design.json
python <scripts>/quests.py build quests/design.json --out pack/overrides --format 1.21   # 1.20 for MC 1.20.1
python <scripts>/validate.py pack/overrides
```
Output goes to `pack/overrides/config/ftbquests/quests/` (chapters/, chapter_groups.snbt, lang/en_us.snbt,
data.snbt created only if missing). The pack needs FTB Quests + FTB Library + FTB Teams.

**Platform warning:** FTB mods are published on **CurseForge only** (not Modrinth) and have no open licence, so
they can't be referenced in a Modrinth `.mrpack` or copied into overrides. Tell the user before stage 4:
- CurseForge pack → FTB Quests is fine (the SNBT files ship in overrides on any platform).
- Modrinth pack → use the vanilla advancements fallback below, or a quest mod that is on Modrinth
  (check with `modrinth.py search "quests"`), or accept a manual install step.
Details: `docs/platforms.md` in this plugin (`${CLAUDE_PLUGIN_ROOT}/docs/`).

Gate: `check` PASS + `validate` no FAIL. In-game layout and item IDs are LOOK until the test loop opens the
book (stage 7): item IDs from mods can only be confirmed in game (`/kubejs hand` or F3+H tooltips).

## Reward types not covered by the generator
`choice`, `loot`, `random`, `all_table` need reward tables; KubeJS custom rewards use `FTBQuestsEvents.customReward`.
For these, install the `ftb-quests` reference skill (`/mc-setup`) and add them in the design as raw objects
(extra fields are passed through).

## Vanilla fallback (no quest mod)
Use advancements as quests: `data/<namespace>/advancement/<chapter>/<quest>.json` (folder is `advancements/`
before 1.21), parent = dependency, criteria = task, rewards = function/loot/xp. Package as a datapack with
`pack.mcmeta` and validate with `validate.py --mc <ver>`. The `minecraft-datapack` skill (`/mc-setup`) has the
full syntax.
