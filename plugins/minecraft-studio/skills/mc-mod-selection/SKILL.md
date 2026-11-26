---
name: mc-mod-selection
description: >-
  Stage 2 of a Minecraft modpack: choose existing mods, resource packs, shaderpacks and datapacks that fit the
  brief and actually exist for the target version and loader, using the Modrinth API. Produces pack/mods.txt and
  a pinned pack/pack.lock.json. Use when the user asks which mods to add, wants a mod list, or adds/removes a mod.
---

# Mod selection (Modrinth)

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (or `../../scripts/` from this file).

## Method
1. **Read the brief** (`studio/brief.md`): version, loader, theme, size, must-haves, bans.
2. **Build a skeleton by role** before searching. For each role pick 1 mod (not 3 that overlap):
   - Core: loader API (fabric-api / none for NeoForge), recipe viewer (EMI or JEI), map (one), performance set
   - Theme pillars: 2-5 big content mods that carry the fantasy
   - Support: storage, QoL, world-gen / structures, mobs, bosses
   - Progression: quest mod (ftb-quests + ftb-library + ftb-teams) if quests are wanted, KubeJS if balancing
   - Client: shader loader (iris on Fabric/NeoForge), resource packs, UI tweaks
3. **Search and check** each candidate:
   ```
   python <scripts>/modrinth.py search "<words>" --mc 1.21.1 --loader neoforge --limit 8
   python <scripts>/modrinth.py info <slug> --mc 1.21.1 --loader neoforge
   ```
   Keep a mod only if: it has a version for the exact MC + loader, it was updated in the last ~12 months (or is
   "finished" and widely used), its licence is known, and it doesn't duplicate another pick.
   Use `--type resourcepack|shader|datapack` for non-mod content.
4. **Write `pack/mods.txt`**, grouped with comments by role, one slug per line (`slug@version` to pin,
   `rp:` / `shader:` / `dp:` prefixes for packs).
5. **Resolve**:
   ```
   python <scripts>/modrinth.py resolve --file pack/mods.txt --mc 1.21.1 --loader neoforge --out pack/pack.lock.json --name "<Pack>"
   ```
   It pins exact versions + hashes, pulls required dependencies, and prints unresolved entries. Fix every
   unresolved one (replace the mod or change the plan with the user). Gate = 0 unresolved.
6. **Present the list** to the user as a table: role · mod · why · side (client/server/both) · licence.
   Mark anything with a beta/alpha version. Log the choice in `studio/decisions.md` and continue (the user can change the list any time).

## Rules
- Prefer Modrinth. CurseForge-only mods need a CurseForge API key and can't go in a .mrpack by URL: list them
  separately and tell the user (they'll be a manual download or a CurseForge export). FTB mods (FTB Quests ...)
  are CurseForge-only: read `${CLAUDE_PLUGIN_ROOT}/docs/platforms.md` and settle Modrinth vs CurseForge with the user.
- Never invent a slug. If search finds nothing, say so.
- A must-have mod that doesn't exist for the chosen version is a **blocker**: stop and offer options
  (other version, other loader, replacement mod).
- Size budget: respect the brief (light <80, medium 80-200, heavy 200+). Count dependencies too.
- Optional: one `templates/mod-sheet.md` per pillar mod (in the vault or `studio/mods/`) with key items for quests
  and recipes to rebalance. That's the input of stages 4-5.

## Overlap cheat sheet (pick one per row)
| Role | Usual choices |
|---|---|
| Renderer | Sodium (Fabric) / Embeddium or Sodium (NeoForge, check the version) |
| Recipe viewer | EMI / JEI / REI |
| Minimap | Xaero's / JourneyMap / FTB Chunks |
| Shader loader | Iris (Fabric, NeoForge) / Oculus (Forge, older) |
| Storage network | AE2 / Refined Storage / Tom's Simple Storage |
