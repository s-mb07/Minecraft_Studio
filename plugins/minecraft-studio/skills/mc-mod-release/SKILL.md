---
name: mc-mod-release
description: >-
  Package and release a Minecraft mod: version bump, changelog, licence, jar inspection, Modrinth publishing
  (dry run by default, explicit confirmation), GitHub Actions build. Use for "release", "publish", "upload to
  Modrinth", "make a jar", versioning a mod.
---

# Release a mod

1. Checks green: `mod_check`, `build`, `gametest` PASS (server/client may be LOOK — say so in the changelog if relevant).
2. Version: `gradle.properties` (`version` on Fabric, `mod_version` on NeoForge). Semantic: MAJOR breaking worlds/API,
   MINOR content, PATCH fixes. Prefix with MC version in the jar name if you support several (`1.0.0+1.21.1`).
3. Inspect the jar:
   ```
   python <scripts>/jar_inspect.py <mod>/build/libs/<mod>-<v>.jar --ids
   ```
   Must show the right modid, version, loader, your items/blocks, and no unexpected files (no test structures in a
   release you didn't mean to ship, no secrets).
4. `CHANGELOG.md`: Added / Changed / Fixed, player-facing language.
5. Licence: the scaffold sets `--license` (default MIT). Assets you didn't make need their licence noted in the README.
   **Provenance:** if `studio/reuse-log.jsonl` exists, include one line per reference in the publish confirmation
   (`<ref>: N files, licence X`), and add credits for the reused sources to the README. This is factual, not a blocker.
   Optionally offer `mod_reference.py remove <id>` to delete the study copies (they are never in the jar).
6. **Publish (ask first — public and permanent):**
   ```
   python <scripts>/modrinth_publish.py <jar> --project <slug> --version <v> --mc 1.21.1 --loader neoforge \
          --changelog CHANGELOG.md --dep fabric-api:required     # dry run
   ```
   After the user says yes: `MODRINTH_TOKEN` must be set in their environment (never write it in files); add `--yes`.
   The Modrinth project page itself is created once by the user on modrinth.com.
7. CI (optional): a GitHub Actions workflow running `./gradlew build` on Java 21 and uploading `build/libs/*.jar` as an
   artifact — copy `.github/workflows/mods.yml` from the Minecraft Studio repo.

Using the mod in a modpack: put the jar in the pack's `overrides/mods/` (your own work), or publish and add its slug
to `mods.txt`.
