---
name: mc-blockbench
description: >-
  Make Minecraft models with Blockbench driven by Claude through the Blockbench MCP server: Java block/item models,
  custom block shapes and hitboxes, display transforms, textures, entity models, then export into the mod or
  resource pack and verify. Use for "model", "3D", "Blockbench", "custom block shape", "item in hand looks wrong".
---

# Blockbench pipeline

Needs the Blockbench MCP plugin (desktop, `jasonjgardner/blockbench-mcp-plugin`) with Blockbench open, MCP server
`blockbench` at `http://localhost:3000/bb-mcp` (`/mc-setup` installs it). Without it: write the model JSON by hand
(cuboids in pixels, 0-16 per block) — the rest of the pipeline is the same. Never block on Blockbench.

Tools appear per context: with no project open only `create_project`, `get_capabilities`, screenshots... After
`create_project` you get `place_cube`, `modify_cube`, `create_texture`, `set_cube_uv`, `set_display_transform`,
`inspect_block_bounds`, `export_model`, `capture_screenshot`, etc.

## Block / item model (format `java_block`)
1. `create_project {name: "<id>", format: "java_block"}`
2. `create_texture {name: "<id>", width: 16, height: 16, fill_color: "#hex"}` — or import the PNG made with `texture.py`.
3. `place_cube {elements: [{name, from:[x,y,z], to:[x,y,z]}...], texture: "<id>"}` — pixel units, keep within 0..16
   (hard limit -16..32), rotations only -45/-22.5/0/22.5/45 on one axis.
4. `inspect_block_bounds {}` → must be `valid: true`.
5. Item display: `set_display_transform` for `gui`, `thirdperson_righthand`, `firstperson_righthand`, `ground` if the
   default looks off.
6. `capture_screenshot {max_size: 256}` — look once; fix obvious issues; don't loop on aesthetics.
7. `export_model {codec_id: "java_block", path: "<mod>/src/main/resources/assets/<modid>/models/block/<id>.json", overwrite: true}`
   (ask before overwriting a model the user made by hand; back it up otherwise).
8. Save the texture PNG to `assets/<modid>/textures/block/<id>.png` (Blockbench texture save, or `texture.py`).
9. `python <scripts>/mod_check.py <mod> --fix` — namespaces Blockbench texture refs (`"crystal"` → `"<modid>:block/crystal"`),
   then `bbmodel_check.py <model.json> --modid <modid>` must PASS.
10. Hitbox: copy the element boxes into `Shapes.or(Block.box(...))` (see `CrystalBlock` in the examples), or use the
    **Voxel Shape Generator** plugin to emit the code.

## Installed Blockbench plugins worth knowing (user machine)
| Plugin | Use it for |
|---|---|
| GeckoLib Animated Model | animated entities/items/armor → skill `mc-geckolib` (optional dependency) |
| Voxel Shape Generator | Java `VoxelShape` code from the model (block hitboxes) |
| Baked Ambient Occlusion | bake soft shading into textures for a richer look |
| Colour Gradient Generator | consistent palette ramps (same idea as `texture.py ramp`) |
| Bone View | inspect bone hierarchy of entity models |
| glTF Importer | bring in external meshes (check licence; convert to cuboids for Java) |
| CEM Template Loader / EMF Animation Addon | OptiFine/EMF entity model packs (resource-pack side, not mods) |

## Entities (non-animated)
Format `modded_entity` → export Java code (`list_export_formats` to find the codec) → `ModelPart` layer definition for an
`EntityRenderer`. For animations use GeckoLib (`mc-geckolib`) instead of hand-written keyframes.

## Headless option
`npx -y github:jasonjgardner/blockbench-mcp-plugin --root <models dir>` edits/validates `.bbmodel` files without the
desktop app (CI, or several agents in parallel).

## Starting from a reference model (mc-mod-study)
`asset_study.py <id> --kind model <filter>` gives the structure (elements, bones, UV, bounds). To edit a copy:
`reuse_apply.py <id> --asset <model> --target src/main/resources/assets/<modid>/models/block/<name>.json --transform edit_model`
(namespaces get rewritten), then open the target file in Blockbench, modify it through MCP, export it back to the
same path, and run `bbmodel_check` and `mod_check --fix`. `.bbmodel` → Java block model: `--transform convert_format`.
For "similar but different", read the structure and model a new one from scratch.
