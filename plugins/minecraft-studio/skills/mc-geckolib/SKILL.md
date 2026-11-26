---
name: mc-geckolib
description: >-
  Animated entities (and items/armor/blocks) with GeckoLib: dependency, entity + controllers, renderer, glowmask,
  spawn egg, asset paths, tests. Verified for NeoForge 1.21.1 + GeckoLib 4.9.4. Use when a mob or object needs
  real animations; simple items/blocks don't need it.
---

# GeckoLib

GeckoLib is a library dependency players must install too. The art comes from **mc-entity-art** and **mc-animation**.
Worked example (build + GameTest + server PASS): `examples/ms-example-entity-neoforge-1.21.1`.

## Versions (check again for other MC versions: `modrinth.py info geckolib --mc <v> --loader <l>`)
- NeoForge **1.21.1** → GeckoLib **4.9.4**, package `software.bernie.geckolib`.
  Checked on Modrinth and against the Cloudsmith `maven-metadata.xml`. 5.x is for newer Minecraft versions;
  don't assume it works on 1.21.1.
- GeckoLib 5 (MC 26.x) uses package `com.geckolib`, render states, and `geckolib/models` / `geckolib/animations`
  paths. It has a different API, so don't mix 4 and 5 code.

## Setup (NeoForge 1.21.1)
`build.gradle`:
```gradle
repositories { maven { url = 'https://dl.cloudsmith.io/public/geckolib3/geckolib/maven/' } }
dependencies { implementation "software.bernie.geckolib:geckolib-neoforge-${minecraft_version}:4.9.4" }
```
`src/main/templates/META-INF/neoforge.mods.toml`:
```toml
[[dependencies.${mod_id}]]
    modId="geckolib"
    type="required"
    versionRange="[4.9,5)"
    ordering="AFTER"
    side="BOTH"
```

## Assets (GeckoLib 4 `DefaultedEntityGeoModel`, read from the jar)
```
assets/<modid>/geo/entity/<id>.geo.json
assets/<modid>/animations/entity/<id>.animation.json      animation.<id>.idle / walk / ...
assets/<modid>/textures/entity/<id>.png                    any multiple of the geo texture size (HD ok)
assets/<modid>/textures/entity/<id>_glowmask.png           optional, with AutoGlowingGeoLayer
```

## Code (copy from the example; all names checked against 4.9.4)
- Entity `extends Monster implements GeoEntity`.
  - Cache: `GeckoLibUtil.createInstanceCache(this)`.
  - `registerControllers`: `new AnimationController<>(this, "movement", 5, state -> isDeadOrDying() ? DEATH :
    state.isMoving() ? WALK : IDLE)` using `state.setAndContinue(...)`.
  - A second controller `"action"` returns `PlayState.STOP`, with `.triggerableAnim("attack", ATTACK)` and
    `.triggerableAnim("hurt", HURT)`.
  - `triggerAnim("action", "attack")` from `doHurtTarget`, and `"hurt"` from `hurt()` on the server.
  - `RawAnimation.begin().thenLoop(...)`, `.thenPlay(...)`, `.thenPlayAndHold(...)` for death.
- Registry: `DeferredRegister.create(Registries.ENTITY_TYPE, MODID)`, then
  `EntityType.Builder.of(Ctor, MobCategory.MONSTER).sized(w, h).build(id)`.
  Attributes go in `EntityAttributeCreationEvent`.
- Spawn egg: `new DeferredSpawnEggItem(ENTITY, bg, fg, new Item.Properties())` in `CreativeModeTabs.SPAWN_EGGS`.
  The item model has parent `minecraft:item/template_spawn_egg`.
- Renderer: `GeoEntityRenderer<T>` with `new DefaultedEntityGeoModel<>(id("<id>"))`, plus
  `addRenderLayer(new AutoGlowingGeoLayer<>(this))`. Override `getDeathMaxRotation` → 0 if the animation handles
  the death. Register it in `EntityRenderersEvent.RegisterRenderers` (`@EventBusSubscriber(value = Dist.CLIENT, bus = MOD)`).
- GameTest: `helper.spawn(ENTITY.get(), pos)`, then assert it's alive and its max health.

## Test
`gradle_run.py <mod> build` → `gametest` (spawns the mob) → `server`. The in-game look is LOOK until someone runs
`runClient` and uses `/summon <modid>:<id>`. `bb_render.py` is the visual proof without a client.
If the mob is invisible, check the asset paths. If it's frozen, check that the animation names match. If it's
missing its texture, check the PNG name.
