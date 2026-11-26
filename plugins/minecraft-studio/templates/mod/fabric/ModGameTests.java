package __PKG__;

import net.fabricmc.fabric.api.gametest.v1.FabricGameTest;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;

public class ModGameTests implements FabricGameTest {
    @GameTest(template = EMPTY_STRUCTURE)
    public void modLoads(GameTestHelper helper) {
//EX{
        helper.setBlock(1, 1, 1, ModBlocks.CRYSTAL_BLOCK);
        helper.assertBlockPresent(ModBlocks.CRYSTAL_BLOCK, 1, 1, 1);
//EX}
        helper.succeed();
    }
}
