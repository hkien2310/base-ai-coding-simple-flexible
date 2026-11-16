# Universal Project Harness (`coding-base`)

A minimal, domain-agnostic harness aligned with Anthropic's multi-session handoff model (`state.md`) and Single-File ADR (`decisions.md`): **4 flat files in `.context/`** and a **3-step mechanical gatekeeper**.

## Structure

```text
coding-base/
├── AGENTS.md                 # 3-layer source-tree rules, Single-File ADR, 2-lane router
├── CLAUDE.md -> AGENTS.md    # Symlink for Claude Code compatibility
├── inject.sh                 # Installer / upgrader (--stealth default, --track, --upgrade, --force)
└── .context/
    ├── project.md            # Static truth: stack, VERIFY_CMD, GOVERNANCE_DOCS, Error Memory
    ├── state.md              # Session progress: Active table, Last Handoff (1–3 bullets), Open Blockers
    ├── decisions.md          # Single-File ADR: Governance & major Plan/Architecture decisions
    └── verify-gate.sh        # 3-step end-of-turn & pre-commit gatekeeper
```

*(Temporary `.context/plans/<slug>.md` is created only while executing Plan Lane tasks `> 3` files, then distilled into `decisions.md` + `Last Handoff` and deleted).*

## Quick Start

```bash
./inject.sh /path/to/project                 # Stealth mode (excluded via .git/info/exclude; default)
./inject.sh /path/to/project --track         # Tracked mode (.context/ & rules committed; .code-review-graph/ excluded)
./inject.sh /path/to/project --upgrade       # Update rules/gatekeeper/hook, migrate legacy files, keep project.md & state.md
./inject.sh /path/to/project --force         # Reset project.md & state.md to blank templates (keeps decisions.md)
```

On first run, `.context/project.md` starts with `STATUS: UNINITIALIZED`. Populate `VERIFY_CMD`, `GOVERNANCE_DOCS`, and key paths, then set `STATUS: READY`.

## 3-Step Gatekeeper (`./.context/verify-gate.sh`)

1. **`[1/3]` Tests & Active Plans:** Blocks `.skip`, `.only`, `@Disabled`, `pytest.mark.skip`, or empty `catch {}` in changed code tests; warns on deleted assertions; blocks incomplete `- [ ]` items or unresolved `TC-xx` rows (`untested`/`fail`/`TBD`) in `APPROVED`/`IN_PROGRESS` plans under `.context/plans/`.
2. **`[2/3]` Governance & Decisions Log Sync:** Enforces via Git diff and file `mtime` (covering multi-round uncommitted edits and non-Git folders) that `.context/decisions.md` is updated last with a matching top ADR entry whenever `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, or `GOVERNANCE_DOCS` change (skips Mode 0 onboarding and initial install).
3. **`[3/3]` Project `VERIFY_CMD`:** Runs `VERIFY_CMD` from `.context/project.md`.

The installed `pre-commit` hook runs `VERIFY_STAGED=1 ./.context/verify-gate.sh` to validate staged files without failing on unrelated unstaged WIP. Scope manual runs with `VERIFY_FILES="<paths>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`.

## Native Git Rollback

Use `git log` plus `[base: <short-sha>]` in `decisions.md` — no shadow repo or custom tags:

```bash
git log --oneline -n 10 -- AGENTS.md .context/project.md
git diff <ref> -- <file...>
git restore --worktree --source=<ref> -- <file...>
```
