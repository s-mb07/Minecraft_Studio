package __PKG__;

import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;

public final class ModItems {
//EX{
    public static final Item CRYSTAL_SHARD = register("crystal_shard", new Item(new Item.Properties()));
//EX}

    private static Item register(String name, Item item) {
        return Registry.register(BuiltInRegistries.ITEM, __CLASS__.id(name), item);
    }

    public static void init() {
        ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.INGREDIENTS).register(entries -> {
//EX{
            entries.accept(CRYSTAL_SHARD);
            entries.accept(ModBlocks.CRYSTAL_BLOCK);
//EX}
        });
    }

    private ModItems() {
    }
}
