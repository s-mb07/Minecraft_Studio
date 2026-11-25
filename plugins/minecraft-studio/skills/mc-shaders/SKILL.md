---
name: mc-shaders
description: >-
  Stage 6b of a Minecraft modpack: choose and configure existing shaderpacks (Iris/OptiFine format) that match
  the visual direction and performance target, ship presets legally, and know when vanilla core shaders are the
  right tool instead. Use for shaders, Iris, Complementary, BSL, shader presets, visual mood.
---

# Shaders

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`).

## Decision
| Want | Do |
|---|---|
| Better lighting/sky/water for players who want it | Iris (+ Sodium) in the pack, shaderpack **optional**, off by default |
| A signature look for the pack | an existing shaderpack + a tuned preset file, still optional |
| Small vanilla-style effects (HUD, tint, vignette) without Iris | vanilla core shaders inside the resource pack → `minecraft-core-shaders` skill (`/mc-setup`) |
| Write a full shaderpack | out of scope for v1 |

Iris runs on Fabric and NeoForge; on old Forge, Oculus. Always add the shader loader to `mods.txt` (client-only).

## Pick a shaderpack
```
python <scripts>/modrinth.py search "<mood words>" --type shader --mc 1.21.1 --loader fabric
python <scripts>/modrinth.py info <slug> --mc 1.21.1 --loader fabric
```
Match the design brief: warm/soft (Complementary, BSL), stylised/toon, dark/horror, low-end (Sildur's Vibrant
Lite, MakeUp Ultra Fast). Note the performance cost: low / medium / high, vs the brief's hardware target.

## Ship it
- Add as `shader:<slug>` in `mods.txt` → it's referenced by URL in the .mrpack (no redistribution).
- Many shaderpacks forbid redistribution: **never** copy the zip into overrides unless the licence allows it.
- A preset: the `<shaderpack>.zip.txt` settings file goes in `client-overrides/shaderpacks/`. Iris reads it.
- Enabling by default: `client-overrides/config/iris.properties` with `enableShaders=false` (recommended) or
  `true` + `shaderPack=<file>.zip`. Default to off; say how to turn it on in the README.

## Gate
LOOK until the user (or a screenshot from the test loop) has seen it in game at the target settings, with FPS
noted in `studio/test-log.md`. Static validation can't judge visuals.
