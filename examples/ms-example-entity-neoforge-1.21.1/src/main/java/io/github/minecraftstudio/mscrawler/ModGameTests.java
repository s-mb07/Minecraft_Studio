package io.github.minecraftstudio.mscrawler;

import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

// Template "empty" = data/mscrawler/structure/empty.nbt (written by mod_new.py).
@GameTestHolder(Mscrawler.MOD_ID)
@PrefixGameTestTemplate(false)
public class ModGameTests {
    @GameTest(template = "empty")
    public static void caveCrawlerSpawns(GameTestHelper helper) {
        CaveCrawler mob = helper.spawn(ModEntities.CAVE_CRAWLER.get(), new BlockPos(1, 1, 1));
        helper.assertTrue(mob.isAlive(), "cave crawler should be alive");
        helper.assertTrue(mob.getMaxHealth() == 14.0F, "max health should be 14");
        helper.succeed();
    }
}
