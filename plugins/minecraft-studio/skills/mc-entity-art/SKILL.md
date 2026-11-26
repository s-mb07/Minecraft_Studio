---
name: mc-entity-art
description: >-
  Create a Minecraft entity's art end to end: design brief, silhouette, cube model and bones, box-UV pixel-art
  texture, ambient occlusion baked with the user's Blockbench plugin, animations, contact-sheet render, GeckoLib
  export. Use for "make a mob", "model a creature", "texture my entity", "make it look better", or a photo reference.
---

# Entity art pipeline (model → texture → AO → animation → render)

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/`. Worked example: `examples/ms-example-entity-neoforge-1.21.1`
(spec: `templates/entity/cave_crawler.json`). Animation details: **mc-animation**. Java side: **mc-geckolib**.

## Validation gates (art is the exception to Fast mode)
Stop and show the user the result at each gate. Go on only after they approve, unless they explicitly asked
for everything in one go.
1. **Model + texture:** render sheet (4 views, with AO if used) plus the `bbmodel_study` score.
2. **Animations:** pose tiles (`--pose`) plus the list of animations with their lengths. If possible, the user
   opens the saved `.bbmodel` in Blockbench to play them.
3. **In game:** only now write the Java side (mc-geckolib), then build, GameTest and server.

**Keep every test artifact** in `studio-tests/<id>/` next to the project (outside the mod and the repo):
`spec.json`, `<id>.bbmodel` (`bb_render.py --save-bbmodel`, geometry + texture + animations), textures (raw,
AO, density variants), `renders/`, and `geckolib/` (geo + animation json). Never overwrite an earlier variant;
add a suffix instead (`_v2`, `_d4_ao`).

## Method (derived from studying 11 high-quality community rigs, see docs/reference-models.md)
1. **Brief, 5 lines:** role (pet, monster, boss), size vs vanilla mobs, shape language (round = friendly, square =
   sturdy, triangle = dangerous), a 60/30/10 palette (main / secondary / accent like eyes or claws), and one
   memorable feature. Less is more: 1-2 signature details.
2. **Spec, not hand clicks:** write `<id>.json` (bones, cubes, materials, details, animations) and generate:
   `entity_gen.py <spec> --out <mod>/src/main/resources/assets/<modid> [--density N]`.
   - **Bones:** `root → body → head / limbs / tail`. Pivots go at joints (hip, shoulder, neck base), never at cube
     centres. Name segments like the references: `leg_left_0`, `leg_left_0_lower`.
   - **Budget:** small 8-24 cubes, medium 20-60, large 50-150. Hierarchy depth ≤ 6. One root.
   - **Box UV**, constant texel density (`density`).
     - Density 1 (1 px per unit) = vanilla look.
     - Density 2-4 = room for real shading and AO. Use it when quality matters; it's not mandatory.
3. **Silhouette test first:** `bb_render.py` on the untextured or flat model. The mob must read from front,
   side and 3/4 views. Fix proportions before any texture work. The cave crawler needed a second pass here: its
   first legs read as blobs, so they became raised-knee, planted-foot spider legs.
4. **Texture (generated, then improved):** the painting rules live in `entity_gen.py`:
   - 4-shade hue-shifted ramps per material (shadows drift to blue/purple, highlights to warm; same idea as the
     *Colour Gradient Generator* plugin).
   - Light from above: `up` is brightest, `down` darkest. Rim light on top edges, form shadow low on the sides,
     contact shadow on the bottom rows.
   - Material patterns (plates, scales), sparse 2-px clusters (no single-pixel noise, no pillow shading).
   - Details last (eyes as `emit` → glowmask).
5. **Ambient occlusion, with the user's plugin (Mr Salmon's Baked AO):** `bb_render.py ... --ao`.
   - The plugin bakes **one mesh** and GeckoLib projects can't hold meshes. So the script opens a temporary
     Generic project, imports the geo, converts the cubes to meshes, **merges them into one mesh** (parts occlude
     each other) and bakes once (~10-15 s).
   - Settings come from `AO_SETTINGS`: shadow 0.85, radius 6, ground plane on.
   - The result is `<texture>_ao.png`. Never bake mesh by mesh: it's far slower and loses the occlusion between parts.
   - AO is subtle at density 1. Use density ≥ 2 to really see it.
   - `--snap` pulls the AO back onto the palette (stricter pixel art, weaker AO).
6. **Animations:** idle + walk first, then attack / hurt / death (mc-animation). They're generated with the
   spec's `animations`, using bone `role`s.
7. **Render:** `bb_render.py <geo> --texture <png> --out studio/render.png --poses <dir> [--ao]` produces one
   contact sheet: 4 views plus one tile per pose (`entity_gen --pose walk@0.25 --pose attack@0.42 --pose-dir ...`).
   - It uses an off-screen view, so the user's camera never moves.
   - Look at the image once per iteration. Never make videos.
8. **Measure:** `bbmodel_study.py <geo.json> --against ${CLAUDE_PLUGIN_ROOT}/docs/reference-models-profile.json`.
   - Score ≥ the reference median (77).
   - Density spread ≤ 15%.
   - Animation coverage: idle, walk, attack, hurt, death.
   - The ≤ 5 shades-per-ramp rule applies to density-1 pixel art (AO adds gradients by design).
9. **Ship:** mc-geckolib (Java + `gradle_run.py build/gametest/server`).

## Plugins (use them, the user relies on them)
| Plugin | Use |
|---|---|
| Baked Ambient Occlusion | step 5 (action `bake_ambient_occlusion`, one merged mesh) |
| Colour Gradient Generator | hue-shifted ramps; `entity_gen.ramp()` implements the same idea headlessly |
| CEM Template Loader (+ EMF addon) | load vanilla entity models to compare proportions and texture layout |
| GeckoLib | project format `geckolib_model`, `geckolib_validate_model`, exports |
| Bone View | rig check (pivots and hierarchy) before animating |
| Voxel Shape Generator / glTF importer | hitboxes for block entities / importing Blender meshes (Generic projects) |

## Pick a style first (sets the cube budget and texture size)
| Style | Look | Cubes | Texture (density 1) |
|---|---|---|---|
| Vanilla-like mob | simple cubes, readable proportions, few details | 8-30 | 32-64 |
| Cute / chibi | big head, small body, big eyes, bouncy motion | 10-35 | 32 |
| Humanoid / NPC | head, torso, arms, legs; clothes as separate cubes | 15-50 | 64 |
| Semi-detailed creature | separate ears/horns/tail, fur or scale detail | 25-70 | 64 |
| Mech / robot | orthogonal panels, visible joints, linear motion | 30-120 | 64 |
| Organic monster | sculpted forms, controlled asymmetry, teeth, tentacles | 40-150 | 64-128 |
| Boss / elite | strong silhouette, signature parts, layered detail | 60-150 | 128 |
| Animated item / prop | small object with moving parts (chest, book, totem) | 5-40 | 16-32 |
Silhouette and readability beat cube count. To match vanilla proportions, study the vanilla mobs: CEM Template
Loader in Blockbench, or the `.geo.json` files in Mojang/bedrock-samples, read with `bbmodel_study.py`.

## No overlap, no interpenetration (user review of the first test)
- **Chained parts must not share face planes.** Upper and lower limb, body and plate, head and jaw would z-fight
  at the joint. `entity_gen.py` makes each hierarchy level 0.01 thinner and each extra cube of a bone 0.005
  larger, using inflate. It's invisible and the UVs stay the same. When modelling by hand in Blockbench, do the
  same: sizes very slightly different (inflate ±0.01), never exactly equal touching faces.
- **Leave room for motion when placing limbs.** Neighbouring legs that swing in opposite phase converge. The gap
  between them must be ≥ 2 × length × sin(swing angle). For example, a 7-long leg swinging 22° needs about
  5 units between neighbours. Increase the spacing or reduce the swing in the spec rather than accepting overlap.
- `entity_gen.py` checks every animation frame for parts passing through each other (oriented boxes, forward
  kinematics). It ignores parts attached at rest and parent/child joints.
  - Colliding bones are damped automatically, down to 50% at most.
  - What remains prints as `[LOOK] walk @ 0.3s: leg_left_0 passes through leg_left_1`. Fix those in the spec
    (spacing, phase, rest pose), then regenerate.
  - Show the user a pose tile of the worst frame.

## Fix-ups seen in practice
- Z-fighting between coplanar cubes → `inflate` 0.001 on the front cube.
- Outlines are a style choice (black vs darker local colour). On 3D entities, prefer darker local colour.
- Seamless repeating materials: paint on a 2×2 group of duplicated cubes so the pattern crosses the edges.
- Blockbench tabs pile up: `bb_render.py` closes the projects it opened.

Further reading: `${CLAUDE_PLUGIN_ROOT}/docs/learning-resources.md`.

## From a photo reference (next step)
Extract the palette (quantise to 4-shade ramps) and the proportions (bounding boxes of head, body, limbs) first.
Write the spec from those numbers, then follow the same pipeline. Copy proportions and colour language, not pixels.
