package io.github.minecraftstudio.mscrawler.client;

import io.github.minecraftstudio.mscrawler.ModEntities;
import io.github.minecraftstudio.mscrawler.Mscrawler;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.neoforge.client.event.EntityRenderersEvent;

@EventBusSubscriber(modid = Mscrawler.MOD_ID, bus = EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class ClientEvents {
    @SubscribeEvent
    public static void registerRenderers(EntityRenderersEvent.RegisterRenderers event) {
        event.registerEntityRenderer(ModEntities.CAVE_CRAWLER.get(), CaveCrawlerRenderer::new);
    }

    private ClientEvents() {
    }
}
