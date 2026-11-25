---
name: mc-brief
description: >-
  Stage 1 of a Minecraft modpack: turn a vague idea into a complete project sheet and design brief
  (version, loader, theme, audience, size, quests, visual direction, constraints). Use when the user starts
  a new pack, gives a one-line idea ("a dark fantasy modpack"), or when brief.md has empty fields.
---

# Brief & design brief

Goal: a filled `studio/brief.md` (template in the plugin `templates/brief.md`) that every later stage can rely on.

## 1. Ask only what is missing — in ONE round
Read what the user already said. Then ask the missing questions together, grouped, with a suggested default for
each ("decide for me" is a valid answer). If you have an interactive question tool, use it with 2-4 options per
question. Never more than 8 questions in the first round.

Priority order (stop once the first 6 are known; the rest can default):
1. Minecraft version
2. Loader (Fabric / NeoForge / Forge / Quilt) — see the decision table below
3. Theme in one sentence + pack type (tech, magic, adventure, skyblock, expert, vanilla+ ...)
4. Solo or multiplayer (server pack?) and platform: Modrinth (.mrpack) or CurseForge — FTB mods need CurseForge (`docs/platforms.md`)
5. Size target and player hardware
6. Quests: FTB Quests / vanilla advancements / none, and roughly how many
7. Must-have mods / banned mods
8. Visual direction: textures, shaders, UI style

## 2. Version & loader decision table
| Situation | Suggest |
|---|---|
| User names a must-have mod | Check which versions/loaders it supports first (`modrinth.py info <slug> --mc X --loader Y`) and pick from there |
| Big tech/magic pack (Create, Mekanism, AE2, Ars...) | NeoForge on the latest version those mods share (often 1.21.1) |
| Performance / vanilla+ / light pack | Fabric on a recent version |
| Legacy favourites only on old versions | Forge 1.20.1 |
| No mods at all, just quests | Vanilla + datapack (skip loader) |

Derive Java: 1.20.5+ → Java 21; 1.18-1.20.4 → Java 17. Newer versions: check the Minecraft Wiki and write the
result in the dossier.

## 3. Design brief (before any asset)
Fill the "Visual direction" section: palette (3-5 hex colours), 3 mood words, UI style, texture direction,
shader stance + performance target, ideas for icon/menu/loading screen. Keep the resource pack, shaders, UI and
quest tone consistent with these words. Draft the `studio/style-guide.md` voice section too (mc-writing-voice).

## 4. Output
- Write `studio/brief.md`; verified facts (version, loader, Java) also go into `studio/dossier.md`.
- Add one line to `studio/decisions.md`.
- Show the user a 5-line summary and ask them to validate before stage 2.

## Good brief example
```
Version: 1.21.1 · Loader: NeoForge · Theme: Victorian steampunk, brass and copper UI
Type: tech + exploration · Quests: 40, linear chapters, FTB Quests · Multiplayer: small server
Mods: "suggest a compatible list", Create required · Shaders: optional Iris preset, medium performance
Constraints: no paid mods, licences checked, no NSFW
```
