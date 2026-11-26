---
name: mc-mod-scaffold
description: >-
  Create a new Minecraft mod project from the official loader template (Fabric example mod, NeoForge MDK,
  Forge 1.20.1 MDK), renamed to the user's modid/package, with a clean skeleton and GameTest setup. Use when
  starting a mod, choosing a loader/version for a mod, or fixing a broken project setup.
---

# Scaffold a mod

```
python <scripts>/mod_new.py <folder> --modid <id> --name "<Name>" --package <com.you.id> \
       --loader fabric|neoforge|forge --mc 1.21.1 [--author <name>] [--license MIT] [--example]
```
- Downloads the official template from GitHub (nothing bundled, always current), refuses a non-empty folder.
- Fabric/NeoForge: replaces the sample code with `Main`, `ModItems`, `ModBlocks`, `ModGameTests`, sets metadata,
  mixin configs, lang file, and the GameTest run (`runGametest` on Fabric, `runGameTestServer` on NeoForge with an
  `empty` structure).
- `--example` adds a working item + block (model, hitbox, textures, recipe, loot, lang, GameTest) — good for learning
  or as a pattern to copy. Without it you get empty registries.
- Writes `studio/dossier.md` (modid, package, loader, MC, Java, template).

## Choosing loader & version
| Situation | Pick |
|---|---|
| No constraint | NeoForge 1.21.1 or Fabric 1.21.1 (both validated) |
| The mod is for a specific modpack | the pack's loader + version |
| Small client/QoL mod, fast updates | Fabric |
| Big content mod, many mod integrations | NeoForge |
| Must run on 1.20.1 Forge packs | Forge 1.20.1 (`--loader forge --mc 1.20.1`, not validated) |
| Latest 26.x | NeoForge MDK `MDK-26.x-ModDevGradle` exists; needs Java 25 (install with user consent) |

Check the template branch exists before promising a version: Fabric `FabricMC/fabric-example-mod` branches,
NeoForge `github.com/NeoForgeMDKs` repos.

## After scaffolding
Project layout (both loaders, Mojang mappings):
```
src/main/java/<package>/   <Class>.java  ModItems.java  ModBlocks.java  ModGameTests.java
src/main/resources/assets/<modid>/  blockstates/ models/block|item/ textures/block|item/ lang/en_us.json
src/main/resources/data/<modid>/    recipe/ loot_table/blocks/ tags/   (1.21+: singular folder names)
studio/                             dossier.md decisions.md test-status.json logs/
```
Then run `mod_check.py <folder>` and `gradle_run.py <folder> build` (first build downloads Minecraft: several minutes).
