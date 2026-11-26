---
name: mc-mod-textures
description: >-
  Make pixel-art textures for Minecraft mods and resource packs (16x16 items/blocks, ores, ingots, gems, animated
  textures) with a consistent palette, using texture.py for first drafts and Blockbench/editors to refine. Use for
  textures, sprites, icons, recolours, "make it look Minecraft-like".
---

# Textures

```
python <scripts>/texture.py ramp "#7a4fd6"                                  # 5-colour palette (shadow cool -> light warm)
python <scripts>/texture.py gen gem   <mod>/.../textures/item/ruby.png --color "#d63a4f"
python <scripts>/texture.py gen ore   .../textures/block/ruby_ore.png   --color "#d63a4f"
python <scripts>/texture.py recolor iron_like.png copper_like.png --color "#c8743a"
python <scripts>/texture.py preview ruby.png ruby_x8.png --scale 8           # look at it (Read the PNG)
python <scripts>/texture.py strip anim.png f1.png f2.png f3.png               # animated strip + .mcmeta
```
Kinds: `block`, `ore`, `plank`, `gem`, `shard`, `ingot`, `dust`, `rod`. Deterministic (`--seed` for variants).

## Rules that make it read as Minecraft
- 16x16 (one pixel density per pack), hard pixels, no anti-aliasing, no gradients smoother than the 4-5 colour ramp.
- Light from top-left; items have a dark outline (darkest ramp colour, not black); blocks tile seamlessly.
- Materials of one mod share hue families from the design brief; a "tier" upgrade = same shape, new ramp.
- Ores: vanilla-like stone base + specks of the material ramp. Don't copy vanilla textures (Mojang copyright):
  draw/generate your own, or recolour your own.
- Look at the 8x preview once; adjust; move on. Fine detail in Blockbench paint mode (with Baked Ambient Occlusion
  and Colour Gradient Generator plugins) when the user wants polish.

## Paths
`assets/<modid>/textures/item/<id>.png` (item models `layer0`), `textures/block/<id>.png` (block models),
`textures/entity/...`, `textures/models/armor/<material>_layer_1.png`. Then `mod_check.py <mod>` confirms every
model's texture exists.

## Pixel-art method (block/item textures; entities: see mc-entity-art)
1. **Silhouette and outline:** a black outline pops; a darker local colour blends. Mixing them highlights the subject.
2. **Base colours in a side palette**, then **ramps of at most 4 shades** per colour (highlight, base, shadow,
   deep shadow). Hue-shift them (`entity_gen.ramp()` / the Colour Gradient Generator plugin).
3. **One light direction** (top-left). Highlights on lit edges, shadows opposite. **No pillow shading** (darkening
   every edge around a bright centre).
4. **Details last, sparingly.** Zoom out often: textures are seen small.
5. **Worked example (brick):** fill `#B96946`; mortar `#C1B9A7` in 4-px rows with 1-px joints every 8 px,
   offset by 4 px on alternate rows. Each brick gets a top-edge highlight `#DF965D` and a bottom-edge shadow
   `#8B493D`. Add two chipped edges and a few mortar streaks.
6. **Seamless:** paint across a 2×2 group of duplicated cubes so the pattern crosses the edges, and clean up the
   corner pixels.
