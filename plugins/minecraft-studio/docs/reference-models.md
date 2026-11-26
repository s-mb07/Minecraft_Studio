# What good entity rigs have in common

These are measurements of 11 community Blockbench entity models (pets, skeleton, golem, humanoids, minotaur,
giant spider, T-rex, boss, cave troll, animated chest), taken with `bbmodel_study.py`. The models themselves are
not redistributed; only the numbers are kept, in `reference-models-profile.json`.

| Metric | Median | Range seen | Takeaway |
|---|---|---|---|
| cubes | 39 | 12-332 | 20-60 is plenty for a medium mob; 300+ is boss territory |
| bones | 20 | 8-86 | one bone per moving part, segmented limbs (`legR0a/b`) |
| hierarchy depth | 6 | 2-10 | depth > 6 makes rigs hard to animate |
| texel density | 1 px/unit | 1-3.3 | constant density; mixed density shows as blurry/sharp patches |
| density spread | 0% | 0-39% | the two worst models (spread 28-39%) are the ones with per-face UV |
| animations | 7 | 2-11 | idle + walk always; attack, hurt, death on mobs |
| keyframes/bone | 4-50 | | top rigs bake dense linear keys (~20 fps) |
| reference score | 77 | 43-88 | Minecraft Studio's test entity: 95 |

The skills built from this:
- `mc-entity-art`: modelling, texturing, AO, render.
- `mc-animation`: timing, gaits, overlap.
- `mc-geckolib`: integration.

Methods also adapted from Blockbench Workshop tutorials. These are our own summaries; read the originals for the
details:
- Creature Animation Workflow (@sylvain_35)
- Pixel Art Shading: Light Logic (@capu0410)
- How to draw a Pixel Art (@capu0410)
- Brick block texturing (@monkus)
- Seamless textures (@voxelated)
- Outlines (@legoego19)
- Z-fighting (@zombiemastera)
- Armature basics (@legoego19)
- Character design (@sylvain_35)
- GeckoLib with NeoForge (@monkus)

All on https://blockbenchworkshop.com.
