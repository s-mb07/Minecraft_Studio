---
description: Build the release of a modpack (.mrpack, optional server pack, credits, changelog) after the gates pass
argument-hint: "[version, e.g. 1.0.0]"
---

Use the **mc-export** skill. Version requested: $ARGUMENTS.

1. Run the pre-flight checks of mc-export. If one fails, stop and report it — don't build.
2. Build: `python ${CLAUDE_PLUGIN_ROOT}/scripts/build_mrpack.py pack/pack.lock.json --out dist --version <v>`
   (add `--server-pack` only after checking licences with the user).
3. `python ${CLAUDE_PLUGIN_ROOT}/scripts/release_docs.py credits pack/pack.lock.json --out CREDITS.md`
   and, if a previous lock exists, `release_docs.py changelog <old> pack/pack.lock.json --version <v>`.
4. Report files in `dist/`, the health score, and anything unverified.
