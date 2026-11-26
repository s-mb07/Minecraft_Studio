---
name: mc-geckolib
description: >-
  Optional: animated entities, items, armor or blocks with GeckoLib (Blockbench GeckoLib plugin + GeckoLib
  dependency). Use only when the user wants real animations (walk cycles, idle, attacks, animated armor);
  simple items/blocks don't need it.
---

# GeckoLib (optional dependency)

Adds a library dependency players must install: confirm the user wants animation before adding it.

## Setup
1. Check the GeckoLib version for the loader/MC: `python <scripts>/modrinth.py info geckolib --mc 1.21.1 --loader <loader>`.
2. Add the maven + dependency from GeckoLib's wiki for that version (github.com/bernie-g/geckolib/wiki) to `build.gradle`;
   declare the dependency in `fabric.mod.json` / `neoforge.mods.toml`. Build to confirm.

## Model & animations (Blockbench, GeckoLib plugin installed)
1. `create_project {format: "geckolib_model"}` (Blockbench MCP) — bones with unique names (`bbmodel_check.py` checks).
2. Animate in Blockbench; `geckolib_list_easings` lists allowed easings.
3. Export: `assets/<modid>/geo/<name>.geo.json`, `assets/<modid>/animations/<name>.animation.json`,
   texture `assets/<modid>/textures/entity/<name>.png`. (GeckoLib 4 paths; check the wiki for your version.)

## Code (shape of it)
- Entity implements `GeoEntity`; `registerControllers` adds an `AnimationController` choosing `RawAnimation` by state
  (`isMoving` → walk, else idle); `getAnimatableInstanceCache` returns `GeckoLibUtil.createInstanceCache(this)`.
- Client: `GeoEntityRenderer<MyEntity>` with a `DefaultedEntityGeoModel<>(Main.id("<name>"))`, registered in the client
  initializer / `EntityRenderersEvent.RegisterRenderers`.
- Attributes + spawn egg like any entity (`mc-mod-content`).

Test: build + server (no client needed to load). Visual check is LOOK unless the dev client runs.
