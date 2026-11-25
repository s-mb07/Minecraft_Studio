# Minecraft Studio — repo instructions for Claude

This repo is a Claude Code plugin marketplace with one plugin: `plugins/minecraft-studio/` (skills, commands,
scripts, templates, third-party registry). It's public, open to contributors, MIT licensed.

## Rules when working on this repo
- **Commits and PRs: no `Co-Authored-By: Claude` line and no "Generated with Claude Code" footer.** The maintainer asked for this.
- Skills and docs in English; `README.fr.md` mirrors the README in French (keep both in sync on user-facing changes).
- Scripts: Python 3.9+, standard library only, cross-platform, `-h` usage docstring, offline tests in `tests/`.
- Anything the skills reference at runtime must live inside `plugins/minecraft-studio/` (only that folder is
  installed). Repo-root files are for contributors.
- Third-party projects: link them in `third-party/registry.json` after checking them; never copy their content.
- Don't put facts about versions/APIs into skills without verifying them (Modrinth API, wiki, a script run).
- Run `python -m unittest discover -s tests` before committing.
