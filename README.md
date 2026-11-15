# Universal Project Harness (`coding-base`)

A minimal, domain-agnostic harness for AI agents working across backend APIs, frontends, CLI/bots, and content pipelines: a **4-file `.context/` directory** and a **3-step mechanical gatekeeper**.

## Structure

```text
coding-base/
├── AGENTS.md                 # 3-layer source-tree rules (Governance, Contracts, Verification) + 2-lane router
├── CLAUDE.md -> AGENTS.md    # Symlink for Claude Code compatibility
├── inject.sh                 # Installer / upgrader (--stealth default, --track, --upgrade, --force)
└── .context/
    ├── project.md            # Project profile: stack, VERIFY_CMD, GOVERNANCE_DOCS, Error Memory
    ├── state.md              # Active work & open blockers table only (<= 25 lines)
    ├── verify-gate.sh        # 3-step end-of-turn & pre-commit gatekeeper
    └── changes/
        └── rules-log.md      # Reverse-chronological log for governance/spec edits
```

## Quick Start

```bash
./inject.sh /path/to/project                 # Stealth mode (excluded via .git/info/exclude; default)
./inject.sh /path/to/project --track         # Tracked mode (.context/ & rules committed; .code-review-graph/ excluded)
./inject.sh /path/to/project --upgrade       # Update rules/gatekeeper/hook, scrub legacy refs, keep project.md & state.md
./inject.sh /path/to/project --force         # Reset project.md & state.md to blank templates (keeps rules-log.md)
```

On first run, `.context/project.md` starts with `STATUS: UNINITIALIZED`. Populate `VERIFY_CMD`, `GOVERNANCE_DOCS`, and key paths, then set `STATUS: READY`.

## 3-Step Gatekeeper (`./.context/verify-gate.sh`)

1. **`[1/3]` Tests & Active Plans:** Blocks `.skip`, `.only`, `@Disabled`, `pytest.mark.skip`, or empty `catch {}` in changed code tests; warns on deleted assertions; blocks incomplete `- [ ]` items or unresolved `TC-xx` rows (`untested`/`fail`/`TBD`) in `APPROVED`/`IN_PROGRESS` plans under `.context/changes/`.
2. **`[2/3]` Governance Log Sync:** Requires a matching top entry in `.context/changes/rules-log.md` when `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, or `GOVERNANCE_DOCS` change (skips Mode 0 onboarding and initial install).
3. **`[3/3]` Project `VERIFY_CMD`:** Runs `VERIFY_CMD` from `.context/project.md`.

The installed `pre-commit` hook runs `VERIFY_STAGED=1 ./.context/verify-gate.sh` to validate staged files without failing on unrelated unstaged WIP. Scope manual runs with `VERIFY_FILES="<paths>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`.

## Native Git Rollback

Use `git log` plus `[base: <short-sha>]` in `rules-log.md` — no shadow repo or custom tags:

```bash
git log --oneline -n 10 -- AGENTS.md .context/project.md
git diff <ref> -- <file...>
git restore --worktree --source=<ref> -- <file...>
```
