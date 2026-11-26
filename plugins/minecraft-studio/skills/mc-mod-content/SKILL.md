---
name: mc-mod-content
description: >-
  Java patterns for Minecraft mod content on Fabric and NeoForge 1.21.1 (Mojang mappings): registering items,
  blocks, block items, tools/armor/food, creative tabs, block entities, entities, sounds, recipes, loot, tags,
  worldgen, keybinds, networking, configs, and when to use mixins. Use when adding or changing mod content.
---

# Mod content patterns (1.21.1, Mojang mappings)

Validated in the repo examples: items, blocks with custom shape, block items, creative tab, recipe, loot, GameTest.
Everything else below is a pattern: build + `mod_check.py` will tell you if a name is off — fix and rebuild.
APIs change between versions: if a symbol doesn't compile, search the loader docs for that version
(docs.fabricmc.net / docs.neoforged.net) instead of guessing repeatedly.

## Registration
| | Fabric | NeoForge |
|---|---|---|
| Item | `Registry.register(BuiltInRegistries.ITEM, Main.id("x"), new Item(new Item.Properties()))` | `ITEMS.registerSimpleItem("x")` / `ITEMS.registerItem("x", Item::new, new Item.Properties())` |
| Block | `ModBlocks.register("x", new Block(Properties.of()...))` (helper also registers the BlockItem) | `BLOCKS.registerBlock("x", Block::new, Properties.of()...)` + `ITEMS.registerSimpleBlockItem(X)` |
| Creative tab | `ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.X).register(e -> e.accept(...))` | `BuildCreativeModeTabContentsEvent` listener on the mod bus |
| Own tab | `FabricItemGroup.builder()` + `Registry.register(BuiltInRegistries.CREATIVE_MODE_TAB, ...)` | `DeferredRegister.create(Registries.CREATIVE_MODE_TAB, MOD_ID)` + `CreativeModeTab.builder()` |
| Block entity | `BlockEntityType.Builder.of(MyBE::new, BLOCK).build(null)` | `DeferredRegister.create(Registries.BLOCK_ENTITY_TYPE, MOD_ID)` same builder |
| Entity | `EntityType.Builder.of(MyEntity::new, MobCategory.CREATURE).sized(w, h).build("id")` + `FabricDefaultAttributeRegistry` | `DeferredRegister.create(Registries.ENTITY_TYPE, ...)` + `EntityAttributeCreationEvent` |
| Sound | `Registry.register(BuiltInRegistries.SOUND_EVENT, id, SoundEvent.createVariableRangeEvent(id))` + `sounds.json` | `DeferredRegister.create(Registries.SOUND_EVENT, ...)` |

Ids: lowercase `[a-z0-9_/]`. Every id needs assets: run `mod_check.py --fix` after adding content — it adds lang keys and
block-item models, and lists what's missing (model, blockstate, texture, loot).

## Common content
- **Tools**: `new SwordItem(Tiers.DIAMOND, new Item.Properties().attributes(SwordItem.createAttributes(Tiers.DIAMOND, 3, -2.4f)))`;
  custom tier = implement `Tier` (incorrect-blocks tag, uses, speed, damage, enchant value, repair ingredient).
- **Armor (1.21)**: register an `ArmorMaterial` (Holder) then `new ArmorItem(material, ArmorItem.Type.CHESTPLATE, props)`; armor
  textures at `textures/models/armor/<material>_layer_1.png`.
- **Food**: `new Item.Properties().food(new FoodProperties.Builder().nutrition(4).saturationModifier(0.3f).build())`.
- **Block shapes**: override `getShape` with `Shapes.or(Block.box(...))` in pixel units matching the Blockbench elements
  (example: `CrystalBlock`). Non-full blocks: `.noOcclusion()`.
- **Directional block**: `HorizontalDirectionalBlock` + `FACING` in `createBlockStateDefinition` + blockstate variants with `y` rotation.
- **Data (no Java)**: recipes `data/<modid>/recipe/`, loot `data/<modid>/loot_table/blocks/`, tags `data/<ns>/tags/block|item/`
  (1.21 singular folders; 1.20.1 plural). Mining: add blocks to `minecraft:mineable/pickaxe` + a tool tag.
- **Worldgen ore**: configured_feature + placed_feature JSON + biome modifier (NeoForge `data/<modid>/neoforge/biome_modifier/`)
  or Fabric `BiomeModifications.addFeature(...)` in Java.

## Client-only code
Fabric: `src/client/java` + `ClientModInitializer` (renderers, keybinds `KeyBindingHelper`, screens). NeoForge: classes
annotated `@EventBusSubscriber(value = Dist.CLIENT)` or a `@Mod(value = MOD_ID, dist = Dist.CLIENT)` class.
Never reference client classes from common code (crashes dedicated servers — the server test catches it).

## Networking & config
- Payloads (1.20.5+): a `record` implementing `CustomPacketPayload` with a `StreamCodec`. Fabric `PayloadTypeRegistry` +
  `ServerPlayNetworking`; NeoForge `RegisterPayloadHandlersEvent`.
- Config: NeoForge `ModConfigSpec` (`container.registerConfig(ModConfig.Type.COMMON, SPEC)`); Fabric: a small JSON file in
  `FabricLoader.getInstance().getConfigDir()` or a config library (ask before adding a dependency).

## Mixins: last resort
Prefer events/APIs. If needed: add the class to `<modid>.mixins.json` (`mixins` common, `client` client-only), target the
narrowest method, use `@Inject` over `@Overwrite`, and expect breakage on MC updates. `mod_check.py` verifies listed mixin
classes exist.

## Tests
Add one GameTest per mechanic in `ModGameTests` (setBlock / assertBlockPresent / spawn + assertEntityPresent / succeedWhen).
They run headless with `gradle_run.py <mod> gametest`.
