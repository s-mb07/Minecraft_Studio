package io.github.minecraftstudio.msexample;

import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

// Template "empty" = data/msexample/structure/empty.nbt (written by mod_new.py).
@GameTestHolder(Msexample.MOD_ID)
@PrefixGameTestTemplate(false)
public class ModGameTests {
    @GameTest(template = "empty")
    public static void modLoads(GameTestHelper helper) {
        helper.setBlock(1, 1, 1, ModBlocks.CRYSTAL_BLOCK.get());
        helper.assertBlockPresent(ModBlocks.CRYSTAL_BLOCK.get(), 1, 1, 1);
        helper.succeed();
    }
}
