---
name: mc-writing-voice
description: >-
  Write player-facing text for a Minecraft modpack (quest titles/descriptions, item lore, guide books, loading
  tips, README pitch) in a consistent voice from the pack's style guide, without generic filler. Use when
  writing or rewriting quest text, lore, tooltips, or when text "sounds like AI" / bland.
---

# Writing voice

Source of truth: `studio/style-guide.md` (template in `templates/style-guide.md`). If it's empty, build it with the
user first: narrator, 3 tone words, person, vocabulary to use/avoid, 3 good/bad examples. Then follow it strictly.

## Rules for quest text
- **Title**: 1-4 words, concrete, in the world's language ("Timber", "Brass Lungs", "The Drowned Bell").
- **Subtitle**: one line, a hook or a hint, not a summary.
- **Description**: ≤ 3 short lines. Line 1 = why it matters in the world. Line 2 = a useful hint the task box
  doesn't give (which mod, where to look, a trick). Optional line 3 = flavour.
- Never restate the task ("Collect 16 logs" — the task box already shows it).
- Vary sentence openings across a chapter. Read the chapter as a whole before finishing.
- Specific beats grand: name the place, the smell, the tool, the consequence.
- Colour codes sparingly: `&e` for key item names, `&c` for warnings. Never whole lines.

## Filler to cut (and why)
"Embark on a journey", "Unleash the power", "Dive into", "Delve", "a testament to", "tapestry",
"Epic adventure awaits", "Now that you have…", "Congratulations!", stacked adjectives, rhetorical questions,
exclamation marks everywhere. They carry no information and make every pack sound the same.

## Process
1. Draft the whole chapter in the design file (`quests/design.json`).
2. Self-review against the style guide: cut filler, check length, check variety, check hints are true for the
   mods in the lock (never invent a mechanic).
3. Show 3 examples to the user before writing 40 more.
4. Translations: keep keys, translate values in `lang/<locale>.snbt`; for whole-pack translation see
   MinecraftModsLocalizer (`/mc-setup`). Have a native speaker review before release.

## Example
Bad: "Embark on an epic journey to gather 16 logs and unleash your crafting potential!"
Good: "The cold comes early here. / Birch burns fast — oak lasts the night."
