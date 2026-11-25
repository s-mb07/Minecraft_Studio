# Optional Obsidian vault layout

Use this when you work on several packs and want a long-term memory that Claude can search
(with an Obsidian MCP server, or just as plain Markdown files). One pack's `studio/` folder is enough for a single pack.

```
00-INDEX/      Dashboard.md, Roadmap.md, Decision-Log.md
01-BRIEFS/     YYYY-MM-DD-<pack>.md
02-MODPACKS/<pack>/  00-Overview 01-Mod-List 02-Dependency-Audit 03-Quest-Design 04-Balancing
                     05-Resource-Pack 06-Shaders 07-Test-Log 08-Release
03-MODS/<mod>.md     one sheet per mod (templates/mod-sheet.md), reused across packs
04-ASSETS/     textures/ ui/ icons/ sounds/
05-TEMPLATES/  copies of the plugin templates
06-RESEARCH/   mods-candidates.md, shaders-candidates.md, resource-packs-candidates.md
07-PITFALLS/   dated lessons: "2026-11-25 — Mod X breaks Y on NeoForge 21.1"
```

Rules: wikilinks between mod sheets and packs (`[[sodium]]`), frontmatter `status:` on mod sheets,
never paste whole logs: link the file and quote the 10 relevant lines.
