# Minecraft Studio

**Free, open methods and skills that let Claude build Minecraft modpacks with you, from idea to release.**

[Français](README.fr.md)

Give this plugin to Claude Code and say *"make me a dark-fantasy modpack for 1.21.1"*. Claude works like a
lead developer: it asks the missing questions, picks **existing** mods that really exist for your version, checks
dependencies, writes quests and balancing scripts, tests that the pack boots, and exports a `.mrpack`. Every
step waits for your approval, and nothing counts as "done" without proof from a tool.

> v0.1 covers **modpacks built from existing mods**. Writing your own Java mods comes later
> (meanwhile `/mc-setup` can install third-party modding skills).

## Install

In Claude Code:
```
/plugin marketplace add s-mb07/Minecraft_Studio
/plugin install minecraft-studio@minecraft-studio
```
Requirements: Python 3.9+ (scripts use the standard library only). Java is only needed for the server boot test.
[Prism Launcher](https://prismlauncher.org/) is recommended for client tests.

No plugin system? Copy `plugins/minecraft-studio/` somewhere and point Claude at
`plugins/minecraft-studio/skills/mc-studio/SKILL.md`. The skills work as plain instructions.

## Use
| Command | What it does |
|---|---|
| `/mc-new [folder] [idea]` | asks the brief questions, creates a workspace |
| `/mc-setup` | installs vetted third-party skills / MCP servers (asks first) |
| `/mc-audit` | runs every static check and gives a health score |
| `/mc-release 1.0.0` | builds the `.mrpack` (+ server pack), credits, changelog |

Or just talk: *"add 20 quests for the Create chapter"*, *"my pack crashes on launch, here's the log"*.

## How it works: 8 stages, each with a gate
```mermaid
flowchart LR
  A[1 Brief] --> B[2 Mod selection] --> C[3 Dependency audit] --> D[4 Quests]
  D --> E[5 Balancing] --> F[6 Resource pack & shaders] --> G[7 Test loop] --> H[8 Export]
```
| Stage | Skill | Gate (evidence) |
|---|---|---|
| Brief & design brief | `mc-brief` | brief has no empty core field |
| Mod selection | `mc-mod-selection` | `pack.lock.json`, 0 unresolved |
| Dependency audit | `mc-dependency-audit` | `modrinth.py audit` has no FAIL |
| Quests | `mc-quests-ftb` + `mc-writing-voice` | `quests.py check` PASS |
| Balancing | `mc-balancing-kubejs` | review table approved, scripts valid |
| Resource pack & shaders | `mc-resource-pack`, `mc-shaders` | `validate.py --mc` no FAIL, licences listed |
| Test loop | `mc-test-loop` | server + client boot recorded |
| Export | `mc-export` | `.mrpack` built, health score with nothing unmeasured |

The principles:
- **Plan, approve, then do.** Claude writes the stage plan and waits for you.
- **PASS / LOOK / FAIL.** Anything that wasn't measured is LOOK ("unverified"), never PASS.
- **Bounded fixing.** At most 5 fix attempts per problem, and the loop stops if the same crash comes back.
- **Memory on disk.** `studio/` holds verified facts, decisions, gates and test logs, so any session can resume cheaply.
- **Respect other people's work.** No editing of third-party mods. Behaviour changes go through configs, KubeJS
  or datapacks. Mods are referenced by URL and never redistributed without a licence.

## Scripts (`plugins/minecraft-studio/scripts/`)
| Script | Use |
|---|---|
| `modrinth.py` | search, info, resolve (pins versions + hashes + dependencies), audit, download, loader-version |
| `validate.py` | JSON, `pack.mcmeta` format per version, resource paths, textures, SNBT, KubeJS brackets, secrets |
| `quests.py` | readable JSON quest design → FTB Quests SNBT (stable IDs), graph checks, Mermaid tree |
| `log_scan.py` | crash/log triage: rule, suspect mod, suggested fix, repeat detection |
| `server_test.py` | headless server boot test (Fabric / NeoForge / Forge) |
| `build_mrpack.py` | `.mrpack` + optional server pack |
| `release_docs.py` | CREDITS.md from the lock, changelog between two locks |
| `health.py` | 0-100 score from evidence, lists what's unmeasured |
| `new_project.py` | workspace scaffold from `templates/` |
| `registry_check.py` | re-checks the third-party registry on GitHub |

Each script has `-h`.

## Workspace layout (created by `/mc-new`)
```
my-pack/
  studio/   brief, dossier (verified facts), plan, decisions, gates, test-log, style-guide
  pack/     mods.txt, pack.lock.json, overrides/ (config, kubejs, quests), client-overrides/, server-overrides/
  quests/   design.json
  assets/   resourcepack/ sources, licences.md
  dist/     build output
```

## Third-party tools
`/mc-setup` can install these. Each one was checked (it exists, its licence, recent activity) and is listed in
[`third-party/registry.json`](plugins/minecraft-studio/third-party/registry.json). We link to them and don't
copy them. Thanks to their authors:
- [ParticleG/ftb-quests](https://github.com/ParticleG/ftb-quests): FTB Quests reference
- [Jahrome907/minecraft-agent-skills](https://github.com/Jahrome907/minecraft-agent-skills): resource pack, datapack, imagegen, modding
- [dorondo0000/minecraft-core-shaders-skill](https://github.com/dorondo0000/minecraft-core-shaders-skill): vanilla core shaders
- [choice21hax/MinecraftSkills](https://github.com/choice21hax/MinecraftSkills): modpack / migration / debug
- [KeiNodens/prismlauncher-mcp](https://github.com/KeiNodens/prismlauncher-mcp): Prism Launcher control
- [RenasDemirbas/BlockBenchMCP](https://github.com/RenasDemirbas/BlockBenchMCP): Blockbench models
- [Y-RyuZU/MinecraftModsLocalizer](https://github.com/Y-RyuZU/MinecraftModsLocalizer): translation

## Platforms
v0.1 automates **Modrinth** (`.mrpack`). Some mods, notably the FTB mods, are CurseForge-only. See
[docs/platforms.md](plugins/minecraft-studio/docs/platforms.md) for what that means and the manual CurseForge route.

## Roadmap
- v0.2: CurseForge API (`curseforge.py`, CurseForge manifest export), Prism instance automation via MCP
- v0.3: mod creation (Fabric / NeoForge / multiloader), Blockbench pipeline, datapack quest generator
- later: maybe a desktop app on top of the same methods

## Contributing
Contributions are welcome: new crash signatures, pack formats for new versions, better methods, translations.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
[MIT](LICENSE). Minecraft is a trademark of Mojang/Microsoft. This project is not affiliated with them.
