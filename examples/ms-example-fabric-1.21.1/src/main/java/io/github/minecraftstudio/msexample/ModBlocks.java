package io.github.minecraftstudio.msexample;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;

public final class ModBlocks {
    public static final Block CRYSTAL_BLOCK = register("crystal_block",
            new CrystalBlock(BlockBehaviour.Properties.of().strength(1.5f).sound(SoundType.AMETHYST).noOcclusion().lightLevel(s -> 7)));

    /** Registers the block and its block item under the same id. */
    private static Block register(String name, Block block) {
        Registry.register(BuiltInRegistries.BLOCK, Msexample.id(name), block);
        Registry.register(BuiltInRegistries.ITEM, Msexample.id(name), new BlockItem(block, new Item.Properties()));
        return block;
    }

    public static void init() {
    }

    private ModBlocks() {
    }
}
