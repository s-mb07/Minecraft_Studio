package io.github.minecraftstudio.mscrawler.client;

import io.github.minecraftstudio.mscrawler.CaveCrawler;
import io.github.minecraftstudio.mscrawler.Mscrawler;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import software.bernie.geckolib.model.DefaultedEntityGeoModel;
import software.bernie.geckolib.renderer.GeoEntityRenderer;
import software.bernie.geckolib.renderer.layer.AutoGlowingGeoLayer;

/** geo/entity/cave_crawler.geo.json + animations/entity/cave_crawler.animation.json + textures/entity/cave_crawler.png */
public class CaveCrawlerRenderer extends GeoEntityRenderer<CaveCrawler> {
    public CaveCrawlerRenderer(EntityRendererProvider.Context context) {
        super(context, new DefaultedEntityGeoModel<>(Mscrawler.id("cave_crawler")));
        addRenderLayer(new AutoGlowingGeoLayer<>(this)); // cave_crawler_glowmask.png -> glowing eyes
        this.shadowRadius = 0.6F;
    }

    @Override
    protected float getDeathMaxRotation(CaveCrawler animatable) {
        return 0; // the death animation rolls the body itself
    }
}
