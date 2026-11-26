package io.github.minecraftstudio.mscrawler;

import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.neoforged.neoforge.common.DeferredSpawnEggItem;
import net.neoforged.neoforge.event.BuildCreativeModeTabContentsEvent;
import net.neoforged.neoforge.registries.DeferredItem;
import net.neoforged.neoforge.registries.DeferredRegister;

public final class ModItems {
    public static final DeferredRegister.Items ITEMS = DeferredRegister.createItems(Mscrawler.MOD_ID);

    public static final DeferredItem<DeferredSpawnEggItem> CAVE_CRAWLER_SPAWN_EGG = ITEMS.register("cave_crawler_spawn_egg",
            () -> new DeferredSpawnEggItem(ModEntities.CAVE_CRAWLER, 0x3E5566, 0x8FF5D2, new Item.Properties()));

    static void addToCreativeTabs(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.SPAWN_EGGS) {
            event.accept(CAVE_CRAWLER_SPAWN_EGG);
        }
    }

    private ModItems() {
    }
}
