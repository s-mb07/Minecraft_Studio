package io.github.minecraftstudio.mscrawler;

import com.mojang.logging.LogUtils;
import net.minecraft.resources.ResourceLocation;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import org.slf4j.Logger;

@Mod(Mscrawler.MOD_ID)
public class Mscrawler {
    public static final String MOD_ID = "mscrawler";
    public static final Logger LOGGER = LogUtils.getLogger();

    public Mscrawler(IEventBus modBus, ModContainer container) {
        ModEntities.ENTITIES.register(modBus);
        modBus.addListener(ModEntities::registerAttributes);
        ModItems.ITEMS.register(modBus);
        modBus.addListener(ModItems::addToCreativeTabs);
    }

    public static ResourceLocation id(String path) {
        return ResourceLocation.fromNamespaceAndPath(MOD_ID, path);
    }
}
