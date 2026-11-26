package io.github.minecraftstudio.msexample;

import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;

public final class ModItems {
    public static final Item CRYSTAL_SHARD = register("crystal_shard", new Item(new Item.Properties()));

    private static Item register(String name, Item item) {
        return Registry.register(BuiltInRegistries.ITEM, Msexample.id(name), item);
    }

    public static void init() {
        ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.INGREDIENTS).register(entries -> {
            entries.accept(CRYSTAL_SHARD);
            entries.accept(ModBlocks.CRYSTAL_BLOCK);
        });
    }

    private ModItems() {
    }
}
