package __PKG__;

import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.neoforged.neoforge.registries.DeferredBlock;
import net.neoforged.neoforge.registries.DeferredRegister;

public final class ModBlocks {
    public static final DeferredRegister.Blocks BLOCKS = DeferredRegister.createBlocks(__CLASS__.MOD_ID);

//EX{
    public static final DeferredBlock<CrystalBlock> CRYSTAL_BLOCK = BLOCKS.registerBlock("crystal_block", CrystalBlock::new,
            BlockBehaviour.Properties.of().strength(1.5f).sound(SoundType.AMETHYST).noOcclusion().lightLevel(s -> 7));
//EX}

    private ModBlocks() {
    }
}
