---
description: Run every static gate on a modpack workspace and report PASS / LOOK / FAIL plus the health score
argument-hint: "[workspace folder]"
---

Workspace: $ARGUMENTS (default: current directory). Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/`.

Run, in order, and keep only the relevant lines of each output:
1. `python <scripts>/modrinth.py audit <ws>/pack/pack.lock.json`
2. `python <scripts>/validate.py <ws>/pack --mc <version from the lock> --quiet`
3. `python <scripts>/quests.py check <ws>/quests/design.json` (if it exists)
4. `python <scripts>/health.py <ws>`

Then update `<ws>/studio/gates.md`, and give the user: one table (gate · result · what to do), the score with its
measured weight, and the single most important next action. Don't fix anything without asking.
