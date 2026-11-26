# Creation logic rules (Minecraft-style entities)

These are the rules to check before rendering anything. Each one comes from a mistake caught in review or from the
reference rigs. Each line is a yes/no check.

## 1. Reading the reference
- Before modelling, describe each signature part **in each view** (front, side, back): where it starts, which way
  it goes, where its tip ends. Example: "back horns: start behind the ears, go **back and down** behind the head,
  tips spread outwards". Turn every sentence into an `expect` (see `mc-entity-art` "Orientation").
- Sides are the **character's** sides. In a front view the character's right is on the viewer's left
  (= geo -X). Asymmetric gear (gauntlet, pauldron) goes on the side the reference shows.
- Keep the 1-3 signature features big and readable. Drop details that won't survive at block scale.
- Compare the silhouette with the reference in the same 3 views. If a part reads differently in one view, it's
  wrong, even if the other views look right.

## 2. Anatomy and proportions
- Pivots go at the real joints (hip, knee, ankle, shoulder, elbow, wrist, neck base, horn root). Never at the cube centre.
- Horn roots sit on the skull (top-side of the head), not above it. The user lowered the front horns once.
- Proportions are measured on the reference in head heights (legs/body/head ratio, arm length to the knee,
  shoulder width) and written in the spec header.
- Digitigrade legs: the thigh angles forward, the shin back, the hoof flat on the ground. Feet touch y = 0.
- Mass reads at a distance: massive characters have thick limbs (thigh ≈ arm thickness), not thin sticks under a big torso.
- Hunched heavy creatures: tilt the chest forward and let the head hang in front of the chest line.

## 3. Faces and expression
- Expression comes from the brows. **Inner ends low = angry**, inner ends high = sad or worried. Flat = neutral.
- Brows must **overlap the top of the eyes** (about a third). Brows floating above the eyes kill the expression.
- Eyes sit right under the brows, 2 units wide on a big head, with a dark socket line below. Glowing eyes go in
  the glowmask.
- The muzzle or snout sticks out in front of the face. Nostrils and the mouth line are small dark shapes, not noise.

## 4. Symmetry and orientation (definitive)
- Never write a raw rotation sign for a symmetric part. Use `raise_outer`, `swing_forward`, `tip_front_down`,
  `mirror_cube`, and `LEFT` / `RIGHT` as the character's sides.
- Every expressive or symmetric bone declares `expect`. `[FAIL] orientation` must be empty before rendering.
- A cube grows from its origin in the direction of its size. A segment's **tip** can point backwards even with
  the right rotation, so check the tip, not the rotation.
- Chains (horns, tails, tentacles) curl by a consistent amount per segment. Declare the direction of the last segment.

## 5. Geometry hygiene
- Whole-number cube sizes with box UV (fractional sizes show see-through slivers and seams; `entity_gen`
  rounds them).
- No coplanar touching faces: chained parts get a size offset of 0.01 per level (`entity_gen` does it).
  Layered armour over skin: inflate ≥ 0.25 or a clear gap.
- Parts must not pass through each other at rest or in animation (collision check, damping floor 50%, then fix
  the spec).
- Cube budget by style (see the table in mc-entity-art). Hierarchy depth ≤ 6 for animated chains. Static
  decorations can stay deeper, or be merged into one bone.

## 6. Texture logic
- Texture group by group, with user validation: skin and face → horns/bones → metal → leather/cloth → AO.
- Every face is framed by a 1-px darker outline (material definition, not lighting). No lit tops or dark
  bottoms on animated models (see 7).
- Motifs are coherent shapes in model units: bevelled panels (metal, leather), bright trims (gold rims, cloth
  hems), ridges every 3 units (horns), sparse grain (skin). **No random dots.**
- Ramps: 5 shades per material, never purple. Ivory and gold must never turn pink.
- The palette follows 60/30/10: main skin/fur, secondary armour, accent (eyes, gold trim, red tips).
- Density: 1 px/unit for the vanilla look, 2-4 when shading and AO need room.

## 7. Shading and ambient occlusion
- **Animated entities: no shading in the texture.** The game lights the model. Painted light (bright tops,
  dark bottoms) and baked AO turn wrong as soon as a limb or the head rotates. `entity_gen` paints entities
  unlit by default: flat material colour, 1-px outline, material motifs.
- Baked AO (`bb_render.py --ao`, Baked AO plugin on one merged mesh) and lit painting (`"lighting": "lit"`) are
  only for **static** things: blocks, items, non-animated props.
- Shadow colours **never go purple or violet**: cool materials keep their own hue when darker, warm ones drift
  slightly to red-brown.

## 8. Animation logic (when we get there)
- Animate bones, never single cubes. Idle and walk first, then attack, hurt, death.
- Gait patterns: biped 0/0.5, quadruped diagonal pairs, insects tripod. Overlap and drag on tails and ears.
- No interpenetration (collision check). The weight shows in a body bob at 2× the step frequency.

## 9. Process
- Model → validate → texture (by group) → validate → animations → validate → game (AO only for static props).
- **The user's manual fixes in Blockbench are kept:** `bb_sync.py spec.json edited.bbmodel --out spec_vN.json`,
  then regenerate. Learn the rule behind each fix and add it here.
- The user's fix is the truth. If a synced part now fails its `expect`, the expectation was wrong: update it to
  describe the fixed pose, so the check protects the fix from then on.
- Render once per validation step (one contact sheet), after the checks pass. Never render to "see if it worked"
  when a check can tell.
- Keep every iteration (`studio-tests/<name>/`: script, spec, bbmodel, renders).
