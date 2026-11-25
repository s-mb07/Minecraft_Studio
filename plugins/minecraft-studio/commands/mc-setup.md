---
description: Install vetted third-party Minecraft skills and MCP servers that Minecraft Studio can use
argument-hint: "[all | recommended | <id> ...]"
---

Read `${CLAUDE_PLUGIN_ROOT}/third-party/registry.json` (if the variable is not expanded: `third-party/registry.json`
at the root of the minecraft-studio plugin).

Requested: $ARGUMENTS (empty = ask).

1. Show the user a table: id · repo · licence · stage · purpose · recommended. Mention the `rejected` list briefly.
2. Ask which to install (default: the `recommended: true` entries). Never install without an explicit yes:
   these are other people's projects and they run on the user's machine.
3. Optional freshness check first: `python ${CLAUDE_PLUGIN_ROOT}/scripts/registry_check.py` — skip any entry that
   now FAILs (archived, gone, licence changed) and tell the user.
4. For each approved entry with `manual` absent/false, run its `install` command and report success/failure.
   For `manual: true` entries (MCP servers, apps), print the steps and offer to run them one by one; replace
   `<ABSOLUTE_PATH>` with the real path where you cloned it.
5. Remind the user to restart Claude Code (or run /reload-plugins) so new skills/MCP servers load.
