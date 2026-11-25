# Contributing to Minecraft Studio

Thanks for helping. This repo is **methods + scripts**: every contribution should make Claude more reliable at
building Minecraft content, with proof.

## Easy first contributions
- **Crash signature**: add a rule to `RULES` in `plugins/minecraft-studio/scripts/log_scan.py`, plus a trimmed real
  log in `tests/fixtures/` and a test. Remove usernames and paths from the log first.
- **Pack format for a new Minecraft version**: update the tables in `scripts/_common.py`, citing the source
  (Minecraft Wiki "Pack format") in the PR.
- **Overlap group**: mods that shouldn't be installed together → `OVERLAP_GROUPS` in `modrinth.py`.
- **Third-party skill/MCP**: add it to `third-party/registry.json` only after checking the repo exists, has a licence
  and is maintained (`scripts/registry_check.py`). We only link to other projects, never copy them.
- **Translations**: `README.<lang>.md`.

## Rules for skills (`plugins/minecraft-studio/skills/*/SKILL.md`)
- Frontmatter: `name` (= folder name) and a `description` that says **when** to use it.
- Keep a skill focused on one stage; under ~150 lines. Put long references in a `references/` file next to it.
- Every claim about versions/APIs must be verifiable: link the source or make a script check it.
- Gates: anything not measured is LOOK, never PASS.
- Write for an agent: concrete commands, decision tables, what to do on failure.

## Rules for scripts
- Python 3.9+, **standard library only**, cross-platform (Windows paths!).
- `-h` docstring at the top with usage.
- Human output by default, `--json` when Claude needs to parse.
- Network calls go through `_common.http_json` (User-Agent, retries, rate limits).
- Add offline tests in `tests/` (no network in CI).

## Run the checks
```
python -m unittest discover -s tests -v
claude plugin validate plugins/minecraft-studio     # if you have Claude Code
```

## Commits / PRs
Small PRs, one topic each. Describe what you verified and how. Never commit API keys.
