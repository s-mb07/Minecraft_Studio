---
name: mc-project-memory
description: >-
  Keep a modpack project's memory on disk so any Claude session (or contributor) can resume without re-exploring:
  dossier of verified facts, append-only decision log, dated pitfalls, mod sheets, optional Obsidian vault.
  Use at the start/end of a session, when the user says "remember", "where were we", or works on several packs.
---

# Project memory

The workspace's `studio/` folder IS the memory. Files and what goes in them:

| File | Content | Write rule |
|---|---|---|
| `dossier.md` | facts verified by a tool or the user, with source + date | update in place; never store guesses |
| `decisions.md` | one line per approved decision (date · stage · decision · why · rejected) | append only |
| `plan.md` | the current stage plan, with "approved" box | rewrite per stage |
| `gates.md` | PASS/LOOK/FAIL per gate with date | update after each tool run |
| `test-log.md` | one row per launch | append only (server_test.py appends automatically) |
| `test-status.json` | machine-readable boot/walkthrough results | written by scripts / you |
| `fix-history.json` | failure signatures for the bounded loop | written by log_scan.py |
| `balancing.md` | review tables | per stage 5 |
| `style-guide.md` | voice for player-facing text | per stage 1/4 |
| `pitfalls.md` (create when needed) | dated lessons: "2026-11-25 — X breaks Y on NeoForge 21.1 → use Z" | append only |

## Session start (cheap)
Read `dossier.md`, the last 10 lines of `decisions.md`, `gates.md`. That's enough to know the stage. Don't read
logs/locks/quests unless the current task needs them.

## Session end
Update gates, add decisions, add pitfalls learnt, and tell the user the next step in one line.

## Learned methods → draft first
If you discover a technique that should become part of these skills (a new crash signature, a better recipe
pattern), write it to `studio/pitfalls.md` marked `DRAFT`, and suggest the user opens a PR / issue on the
Minecraft Studio repo. Don't silently change your own rules.

## Several packs: Obsidian vault (optional)
See `templates/vault/README.md` for the layout (index, briefs, per-pack notes, reusable mod sheets, research,
pitfalls). With an Obsidian MCP server, search the vault before re-researching a mod; without one, it's plain
Markdown. Keep mod sheets reusable across packs (`03-MODS/<slug>.md`).

## Git
Version the workspace with git (template `.gitignore` excludes dist/, logs, .run/). Commit after each validated
stage with a message naming the stage. Never commit API keys (validate.py flags them).
