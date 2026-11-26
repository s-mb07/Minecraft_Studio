---
name: mc-animation
description: >-
  Animate Minecraft entities (GeckoLib / Bedrock animation JSON): idle, walk, run, attack, hurt, death; gait
  patterns, timing, overlap, procedural generation with entity_gen.py, polish in Blockbench. Use for "animate my
  mob", "the walk looks stiff", "add an attack animation".
---

# Entity animation

## Numbers measured on the reference rigs (docs/reference-models.md)
| Animation | Length | Loop | Notes |
|---|---|---|---|
| idle | 2.5-4 s | loop | breathing, small head and antenna motion, nothing sync'd |
| walk | 0.7-1.4 s | loop | one full gait cycle |
| run | 0.6-0.75 s | loop | more airtime, bigger amplitude |
| attack | 1-2 s | once | anticipation → strike → recover |
| hurt | 0.5-0.7 s | once | quick flinch, decays |
| death | 1.5-2.8 s | hold_on_last_frame | ends in a still pose |

The best rigs (spider, troll) use **densely baked linear keys** (~20 fps, 40-50 keys per bone), not a few eased
keys. `entity_gen.py` produces exactly that. GeckoLib 4 easings (read from the jar): linear, step, catmullrom,
easeIn/Out/InOut + sine, quad, cubic, quart, quint, expo, circ, back, elastic, bounce.

## Workflow (pose-to-pose, from the creature-animation tutorial)
1. References (slow-motion video of the real animal).
2. Root and body motion first: position only, the up/down bob.
3. Main poses of the big bones (contact / passing, windup / strike). In-betweens come next.
4. Legs. Walk: first contact → ground → last contact → passing. Run: first contact → last contact → airtime →
   passing. Fix feet sliding through the ground where it shows.
5. Offset and overlap: mirrored limbs use a phase offset. Ears, tails and antennae **drag** behind their parent
   (chained bones lag a little more each), and lighter tips move more.
6. Easing: organic = smooth (ease-in-out); mechanical = linear. Anticipation before big actions.
7. Loops start and end on the same pose.

## Gaits (phase = fraction of the cycle)
- **Biped:** legs 0 / 0.5, arms opposite to legs. Body bob at 2× the step frequency.
- **Quadruped walk:** diagonal pairs (front-left with back-right = 0, the others = 0.5).
- **Insect / 6 legs:** tripod (L0, R1, L2 = 0; R0, L1, R2 = 0.5). Spider / 8 legs: alternating groups of 4.
- **Serpent:** sine wave travelling down the spine, phase increasing from head to tail.
- **Flyer:** the downstroke lifts the body, the body lags the wings slightly.

## Collisions
- Limbs must never pass through other parts (legs through legs, the jaw through the head, the tail through the
  body, legs curling into the body on death).
- `entity_gen.py` checks every frame, damps the offenders (floor 50%) and reports the rest as LOOK.
- Fix the rest by changing the phase (neighbours not in exact antiphase), the rest pose (splay legs outwards), or
  the spacing (see mc-entity-art). Damping further would make the animation stiff.
- When polishing by hand in Blockbench, scrub the timeline at contact and passing poses from the top view and
  the side view.

## Generate, then polish
- In the spec, each bone gets a `role` (root, body, head, jaw, antenna, tail, leg, leg_lower) plus `side`
  (-1/1), `phase` and `drag`. `animations: {name: {length, loop: loop|once|hold}}`.
- `entity_gen.py` writes `animations/entity/<id>.animation.json` named `animation.<id>.<name>`. The Java
  `RawAnimation` strings must match these exactly.
- Polish by hand in Blockbench MCP (`animation_timeline`, `manage_keyframes`, `geckolib_set_keyframe_easing`) when
  an action needs character, then export with `geckolib_export_animations`.
- Check: `bbmodel_study.py` (coverage, keyframes inside the length, no NaN) and pose tiles from
  `entity_gen --pose walk@0.25` in `bb_render.py`.
- GeckoLib controllers (Java): base loop (death > walk > idle, 5-tick blend) plus a separate `action` controller
  with `triggerableAnim` for attack/hurt, called from `doHurtTarget` / `hurt` on the server (see mc-geckolib).
  Set `getDeathMaxRotation` to 0 when the death animation handles the fall.
