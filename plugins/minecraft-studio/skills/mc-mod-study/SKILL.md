---
name: mc-mod-study
description: >-
  Study an existing Minecraft mod the user supplies (jar, source folder, GitHub repo, Modrinth page, jar URL):
  import, decompile, index, explain how a mechanic / GUI / model / texture / shader works, then build an original
  version in the target mod, or copy/adapt/port specific code or assets when the user asks, with provenance logged.
  Use for "how does X do Y?", "study this mod", "make something similar", "copy this model and recolour it",
  "port this system from Fabric to NeoForge".
---

# Reference study and reuse

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/`). `--root` = the target mod folder (default `.`).
References live in `<mod>/studio/references/<id>/`. They are study copies and never part of the build.

## Reference analysis and reuse policy
Minecraft Studio supports local analysis and reuse of mods supplied by the user. The user decides what may be
reused and remains responsible for compliance with the licences.
- **Automatic, without asking:** import, extract, decompile and index a supplied mod; read its Java, mixins,
  configs, assets, models, textures, sounds, GUI and shaders; explain mechanics, architecture and data flow;
  write design briefs, pseudocode and plans. When the user explicitly asks, copy, adapt, rename or modify
  reference code and assets into the target mod. When the user asks for inspiration only, build an original
  implementation. Run checks, builds and tests.
- **Licence:** detect and show it in one line ("Licence: CC-BY-4.0, attribution required. Copying and adapting.").
  Never refuse, delay or block a requested action because a licence is unknown or unclear. Record the source,
  licence and reused files in the provenance log. Don't repeat warnings and don't moralise.
- **Confirm once only for:** publishing (Modrinth, git push, public release), deleting/overwriting unrecoverable
  work, secrets/tokens, installs or settings outside the project.

## Workflow
1. **Import** (chains decompile + inventory + licence):
   `python <scripts>/mod_reference.py add <jar|folder|url> --id <short-id> --root <mod>`
   For Modrinth, `--loader` / `--mc` pick the matching file. A GitHub URL gets the source archive, so no decompile is needed.
2. **Overview:** `mod_inventory.py <id>` (3 lines). Read `analysis/inventory.json` only if you need details.
3. Ask **one** clarifying question only if the target feature is genuinely ambiguous.
4. **Trace the system:** `mechanic_trace.py <id> -q "<the user's question>"`. Read only the files under READ, and
   only the methods named in ENTRY/FLOW. Re-run with other words if nothing matched.
5. **Assets:** `asset_study.py <id> --kind model|texture|sound|gui|shader|vfx [filter]`. For GUIs:
   `gui_study.py <id> --screen <ScreenClass>`, which gives the layout plus an original-design variant.
6. **Design brief** (≤ 15 lines, neutral): purpose, data flow, state/NBT, networking, events, assets, plus how it
   maps to the target loader/version.
7. **Implement** in the target mod (the mc-mod-dev pipeline):
   - *inspiration*: write original code and assets (`mc-mod-content`, `mc-mod-textures`, `mc-blockbench`).
   - *reuse on request*: `reuse_apply.py <id> --asset|--class <src> --target <path> --transform <t>`
     (copy, copy_and_rename, recolour --color, resize --size, edit_model, adapt_code, port_code,
     extract_pattern, convert_format). Then do the real API adaptation yourself for adapt/port.
8. **Verify:** `mod_check.py <mod> --fix` → `gradle_run.py <mod> build` → `gametest` / `server` (the usual
   bounded repair loop).
9. **Report:** one result line, the brief or implementation summary, checks, and
   `similarity_report.py --target <mod> --reference <id>` (informational).

## Notes
- **Fabric jars** use intermediary names (`class_2248`, `method_9530`) for Minecraft code. The mod's own classes
  stay readable, common MC classes are mapped back in the index, and the trace shows `RISK: intermediary names`.
  When porting, look up the Mojang names in the target loader's sources. NeoForge 1.21.1 jars already use Mojang names.
- **Decompiler:** Vineflower (default) or `--engine cfr`, downloaded once to `~/.minecraft-studio/tools/`. Needs a
  JDK 17+. If it fails, the index keeps class names only (LOOK), and analysis continues on assets.
- **Porting Fabric ↔ NeoForge:** registries (Registry.register ↔ DeferredRegister), events (Fabric callbacks ↔
  `@SubscribeEvent`), networking (payload registration differs), data (same JSON). Rebuild with the target's patterns
  from `mc-mod-content`; don't keep loader-specific imports.
- **Models:** open a reference `.json` / `.geo.json` / `.bbmodel` in Blockbench MCP to edit it, and export it to the
  target's `assets/<modid>/models/` (see `mc-blockbench`). `convert_format` turns `.bbmodel` into a Java block model.
- **Provenance:** `studio/reuse-log.jsonl` (target) plus `references/<id>/reuse-log.jsonl`. `mc-mod-release` lists it
  in the publish confirmation.
- **Cleanup:** `mod_reference.py remove <id>` deletes only the study copy.
