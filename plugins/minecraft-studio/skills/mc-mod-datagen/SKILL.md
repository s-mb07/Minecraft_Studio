---
name: mc-mod-datagen
description: >-
  Generate a mod's JSON (models, blockstates, lang, recipes, loot tables, tags) with the loader's data generators
  instead of writing it by hand, for mods with more than a handful of items/blocks. Use when a mod grows, when JSON
  keeps drifting from Java ids, or the user asks for datagen.
---

# Data generation

Rule of thumb: ≤ 10 items/blocks → hand-written JSON + `mod_check.py --fix` is faster. More → datagen.
Status: patterns below are documented, not yet validated by the repo examples. Compile errors → check the loader docs
for the exact 1.21.1 signatures, fix, rebuild.

## NeoForge (already wired in the MDK: `runData` → `src/generated/resources`)
```java
@EventBusSubscriber(modid = Main.MOD_ID, bus = EventBusSubscriber.Bus.MOD)
public class ModDataGen {
    @SubscribeEvent
    public static void gather(GatherDataEvent event) {
        var gen = event.getGenerator(); var out = gen.getPackOutput();
        var lookup = event.getLookupProvider(); var efh = event.getExistingFileHelper();
        gen.addProvider(event.includeClient(), new ModBlockStates(out, efh));      // extends BlockStateProvider
        gen.addProvider(event.includeClient(), new ModItemModels(out, efh));       // extends ItemModelProvider
        gen.addProvider(event.includeClient(), new ModLang(out));                  // extends LanguageProvider
        gen.addProvider(event.includeServer(), new ModRecipes(out, lookup));       // extends RecipeProvider
        gen.addProvider(event.includeServer(), new LootTableProvider(out, Set.of(),
            List.of(new LootTableProvider.SubProviderEntry(ModBlockLoot::new, LootContextParamSets.BLOCK)), lookup));
    }
}
```
Run: `gradle_run.py <mod> data`. `mod_check.py` reads `src/generated/resources` too.

## Fabric
1. In `build.gradle`: `fabricApi { configureDataGeneration { client = true } }` → task `runDatagen`, output `src/main/generated`.
2. Entrypoint `"fabric-datagen": ["<pkg>.ModDataGen"]` in `fabric.mod.json`; class implements `DataGeneratorEntrypoint`:
```java
public void onInitializeDataGenerator(FabricDataGenerator gen) {
    var pack = gen.createPack();
    pack.addProvider(ModModelProvider::new);   // extends FabricModelProvider
    pack.addProvider(ModLangProvider::new);    // extends FabricLanguageProvider
    pack.addProvider(ModRecipeProvider::new);  // extends FabricRecipeProvider
    pack.addProvider(ModBlockLoot::new);       // extends FabricBlockLootTableProvider
    pack.addProvider(ModTags::new);            // extends FabricTagProvider.BlockTagProvider
}
```
3. Add `src/main/generated` to resources (`sourceSets.main.resources.srcDir 'src/main/generated'`).

## Rules
- Generated files are outputs: never hand-edit them; change the provider and re-run.
- Keep Blockbench custom models hand-made (exported JSON in `src/main/resources`), and let datagen reference them
  (`models().getExistingFile(...)` / `Models` with a parent) instead of overwriting them.
- Commit generated resources (the build doesn't run datagen), re-run after content changes, then `mod_check.py`.
