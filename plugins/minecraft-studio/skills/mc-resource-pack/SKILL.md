---
name: mc-resource-pack
description: >-
  Stage 6a of a Minecraft modpack: pick existing resource packs or build the pack's own resource pack
  (pack.mcmeta, textures, models, lang, sounds, menu/branding) consistent with the design brief, with a licence
  table for every asset. Use for texture packs, resource packs, retexturing mod items, custom menu, pack icon.
---

# Resource packs

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Choose: existing pack, own pack, or both
- **Existing** (Faithful, Fresh Animations, Stay True ...): add with `rp:<slug>` in `mods.txt` and resolve. Nothing
  to redistribute. Check its version covers the MC version.
- **Own pack** for branding (title screen, pack icon, menu background), retextures of a few mod items, quest
  icons, lang overrides (rename items to fit the theme). Source lives in `assets/resourcepack/`, the built zip is
  shipped through `pack/overrides/resourcepacks/` (or `client-overrides/`).

## pack.mcmeta
```json
{ "pack": { "pack_format": 34, "description": "§6Dark Hollow§r resources" } }
```
`pack_format` depends on the MC version: the table is in `scripts/_common.py` (verified values). Unknown version
→ check the Minecraft Wiki "Pack format" page and add the value to the table in a PR. Newer versions can use
`min_format` / `max_format`. Always run `validate.py --mc <ver>`.

## Layout
```
assets/resourcepack/
  pack.mcmeta  pack.png (128x128 recommended)
  assets/<namespace or modid>/
    textures/item/*.png  textures/block/*.png  textures/gui/...
    models/item/*.json   blockstates/*.json
    lang/en_us.json      sounds.json  sounds/*.ogg
```
- To retexture a mod item, use the **mod's** namespace and the same path as in its jar (open the jar as a zip and
  look under `assets/<modid>/textures/`). Don't ship the mod's original textures.
- All paths lowercase `[a-z0-9_.-/]`.
- Textures 16x16 (or 32x32 for an HD pack, consistently). Animated textures: vertical strip + `.png.mcmeta`.
- Item models (1.21.4+) moved to `assets/<ns>/items/*.json` definitions: check the version before writing models.
  For complex model JSON, the `minecraft-resource-pack` skill (`/mc-setup`) has the details.

## Art direction
Follow the design brief palette and mood words. Keep one pixel density. Write a short asset list first
(file, purpose, size) and get approval. For concepts/icons/banners, the `minecraft-imagegen` skill can help;
for 3D models, Blockbench (BlockBenchMCP via `/mc-setup`).

## Licences (mandatory)
Every asset not made by the user goes into `assets/licences.md` with source, author, licence and class:
COPY (redistribution allowed) / INSPIRE (look only, redraw) / REFERENCE (never ship). Vanilla Mojang textures are
not redistributable: edit-and-ship of vanilla textures is a grey zone — prefer your own art or packs that allow it.

## Build & validate
Zip the **content** of `assets/resourcepack/` (pack.mcmeta at the root of the zip, not inside a folder) into
`pack/overrides/resourcepacks/<namespace>-resources.zip`. Then:
```
python <scripts>/validate.py assets/resourcepack --mc 1.21.1
```
Gate: no FAIL, licences filled, user saw screenshots in game (LOOK until then). To enable it by default, add it to
`options.txt` `resourcePacks:[...]` in `client-overrides/` — only on first install, never overwrite player options.
