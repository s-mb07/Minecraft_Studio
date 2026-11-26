---
description: Create or extend a Minecraft mod (Fabric / NeoForge) end to end — scaffold, content, textures, models, build, tests
argument-hint: "[idea, e.g. 'obsidian sword and a crystal block, NeoForge 1.21.1']"
---

Use the **mc-mod-dev** skill (Fast mode unless the user asks for Balanced/Guided). Request: $ARGUMENTS

Derive modid, name, package, loader and version from the request (defaults: NeoForge or Fabric 1.21.1); ask only if
something essential is ambiguous. Then scaffold with `mod_new.py`, add the content, run `mod_check.py --fix`,
`gradle_run.py build` and `gradle_run.py gametest`, repairing failures automatically. Finish with a ≤10-line summary:
content, jar path, checks, what wasn't verified.
