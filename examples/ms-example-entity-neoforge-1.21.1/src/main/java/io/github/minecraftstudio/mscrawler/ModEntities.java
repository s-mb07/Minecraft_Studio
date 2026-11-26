package io.github.minecraftstudio.mscrawler;

import net.minecraft.core.registries.Registries;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent;
import net.neoforged.neoforge.registries.DeferredHolder;
import net.neoforged.neoforge.registries.DeferredRegister;

public final class ModEntities {
    public static final DeferredRegister<EntityType<?>> ENTITIES = DeferredRegister.create(Registries.ENTITY_TYPE, Mscrawler.MOD_ID);

    public static final DeferredHolder<EntityType<?>, EntityType<CaveCrawler>> CAVE_CRAWLER = ENTITIES.register("cave_crawler",
            () -> EntityType.Builder.of(CaveCrawler::new, MobCategory.MONSTER).sized(1.4F, 0.8F).clientTrackingRange(8)
                    .build(Mscrawler.MOD_ID + ":cave_crawler"));

    static void registerAttributes(EntityAttributeCreationEvent event) {
        event.put(CAVE_CRAWLER.get(), CaveCrawler.createAttributes().build());
    }

    private ModEntities() {
    }
}
