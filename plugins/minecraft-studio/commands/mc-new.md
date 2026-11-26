---
description: Start a new Minecraft modpack project (brief questions, then workspace scaffold)
argument-hint: "[folder] [one-line idea]"
---

Use the **mc-studio** skill, stage 1 (**mc-brief**).

Idea / arguments from the user: $ARGUMENTS

1. Ask the missing brief questions in one round (version, loader, theme, multiplayer, size, quests, visuals).
2. Once version + loader + name are known, create the workspace:
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/new_project.py <folder> --name "<name>" --mc <version> --loader <loader>`
   (default folder: a kebab-case version of the name in the current directory).
3. Fill `studio/brief.md` and `studio/dossier.md`, log the decision, show a 5-line summary and continue with the
   next stages (Fast mode) unless the user picked Guided mode.
