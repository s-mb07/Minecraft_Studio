---
name: mc-balancing-kubejs
description: >-
  Stage 5 of a Minecraft modpack: review progression and economy across mods (recipe costs, duplicate
  content, shortcuts, bottlenecks, loot, quest rewards) and fix it with KubeJS scripts, datapacks or configs —
  never by editing mods. Use for "balance my pack", "this recipe is too cheap", "remove duplicate ores",
  "gate this item", KubeJS, recipe changes.
---

# Balancing with KubeJS / datapacks / configs

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## 1. Review before changing (write it down)
Create `studio/balancing.md` with one table per pillar mod:

| Item / mechanic | Unlock phase | Cost now | Problem | Proposed fix | Tool |
|---|---|---|---|---|---|

Look for:
- **Shortcuts**: an early item that makes a whole chapter pointless (e.g. a cheap teleporter, infinite-power block).
- **Duplicates**: same material from 2+ mods (copper, tin, steel), two backpacks, two ways to make the same machine.
  → unify with tags, hide extras, keep one recipe.
- **Bottlenecks**: one rare resource gating too much, or a grind > 30 min with no automation option.
- **Cross-mod exploits**: duplication loops, free energy, item-to-item conversion that creates value.
- **Quest rewards** that skip what the next quest teaches.
Apply clear fixes (exploits, duplicates, obvious shortcuts) directly. Taste calls (making the pack harder/easier) follow the brief; if the brief is silent, list them in the summary as suggestions.

**KubeJS availability depends on the loader** (checked on Modrinth, 2026-11): on 1.21.1 it's **NeoForge only**;
on 1.20.1 it exists for Forge, Fabric and Quilt. Always run `modrinth.py info kubejs --mc <v> --loader <l>`
before planning KubeJS work. No KubeJS → use datapacks (recipes, tags, loot) and mod configs.

## 2. Pick the lightest tool
| Need | Tool |
|---|---|
| Change a number the mod exposes (ore rate, energy, durability) | the mod's config in `pack/overrides/config/` or `defaultconfigs/` |
| Add / remove / replace recipes, unify tags, hide items | KubeJS `server_scripts` (`kubejs` mod; `resolve` pulls `rhino` etc.) |
| Loot tables, vanilla recipes, tags without KubeJS | datapack in `pack/overrides/` (via a global datapack mod or the world) |
| Gate items behind quest progress | KubeJS + FTB Quests stages, or recipe removal + quest reward |

## 3. KubeJS patterns (KubeJS 6+ / 7 syntax, check the version in the lock)
```js
// pack/overrides/kubejs/server_scripts/<namespace>_balance.js
ServerEvents.recipes(event => {
  // remove a too-cheap recipe and replace it
  event.remove({ output: 'somemod:teleporter' })
  event.shaped('somemod:teleporter', ['EDE', 'DXD', 'EDE'], {
    E: 'minecraft:ender_pearl', D: 'minecraft:diamond', X: 'minecraft:nether_star'
  }).id('<namespace>:teleporter')

  // unify a duplicate material: every recipe that outputs mod_b copper -> mod_a copper
  event.replaceOutput({}, 'mod_b:copper_ingot', 'mod_a:copper_ingot')
  event.replaceInput({}, 'mod_b:copper_ingot', '#c:ingots/copper')
})

ServerEvents.tags('item', event => {
  event.add('c:ingots/copper', 'mod_a:copper_ingot')
})
```
Rules: every new recipe gets an explicit `.id('<namespace>:...')`; one file per topic; comment the "why" with a
link to the row in `studio/balancing.md`; use tags (`#c:...` on 1.21, `#forge:...` on 1.20.1 Forge) over hard IDs.
Hide removed items in the recipe viewer (EMI/JEI) with a client script so players don't hunt for them.

KubeJS syntax differs between versions (6 on 1.20.1, 7 on 1.21.1). If unsure, check the KubeJS wiki for the
version in the lock — never guess method names.

## 4. Validate
```
python <scripts>/validate.py pack/overrides
```
Syntax only. Item IDs and recipe types are checked when the game loads: KubeJS errors show in
`logs/kubejs/server.log` and are triaged by `log_scan.py` (stage 7). Gate: validate no FAIL + server boots with no
KubeJS error; the balancing table is in `studio/balancing.md`.
