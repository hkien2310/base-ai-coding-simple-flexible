# Universal Project Harness (`coding-base`)

A minimal, domain-agnostic harness for AI agents working across backend APIs, frontends, CLI/bots, and AI content pipelines. Every project gets a **4-file `.context/` directory** and a **3-step mechanical gatekeeper** without replacing your existing tools or `git log`.

## Repository Structure

```text
coding-base/
├── AGENTS.md                 # Universal 4-section agent rules (Fast vs Plan lanes, domain guardrails, Git rollback)
├── CLAUDE.md -> AGENTS.md    # Symlink for Claude Code compatibility
├── inject.sh                 # Installer / upgrader (--stealth default, --track, --upgrade, --force)
└── .context/
    ├── project.md            # Project profile: stack, VERIFY_CMD, GOVERNANCE_DOCS, Error Memory
    ├── state.md              # Active work & open blockers table only (<= 25 lines; Git log tracks finished work)
    ├── verify-gate.sh        # 3-step pre-commit / end-of-turn gatekeeper
    └── changes/
        └── rules-log.md      # Reverse-chronological audit trail for rule/prompt/governance edits
```

## Quick Start

Run from `coding-base`:

```bash
# Default Stealth Mode: hidden via .git/info/exclude, coexists with custom AGENTS.md/CLAUDE.md
./inject.sh /path/to/project

# Tracked Mode: visible to Git so .context/ and rules travel with team commits
./inject.sh /path/to/project --track

# Upgrade harness rules, verify-gate.sh, hooks & scrub legacy files (preserves project.md/state.md)
./inject.sh /path/to/project --upgrade
```

| Flag | Behavior |
| :--- | :--- |
| `(default)` / `--stealth` | Writes `.context/` and excludes harness files via `.git/info/exclude` (zero noise in `git status` / PRs). |
| `--track` | Excludes only `.code-review-graph/` and keeps `.context/` + rules tracked in Git. |
| `--upgrade` | Updates `AGENTS.md` (or `.agents/rules/coding-base.md`), `.context/verify-gate.sh`, and hooks; removes legacy files; scrubs stale `check-blast-radius.py` references from preserved `project.md`. |
| `--force` | Resets `.context/project.md` and `.context/state.md` to blank templates (preserves custom rules & `rules-log.md`). |

On first run in a project, `.context/project.md` starts as `STATUS: UNINITIALIZED`. Your agent fills in `VERIFY_CMD`, `GOVERNANCE_DOCS`, key paths, and flips it to `STATUS: READY`.

## How the 3-Step Gatekeeper Works (`./.context/verify-gate.sh`)

1. **`[1/3]` Tests & Active Plans:** Blocks `.skip`, `.only`, `@Disabled`, `pytest.mark.skip`, or empty `catch {}` in changed code tests; flags deleted assertions (`HIGH RISK`); blocks unchecked `- [ ]` items or unresolved `TC-xx` rows (`untested`/`fail`/`TBD`) in `APPROVED` / `IN_PROGRESS` plans under `.context/changes/` (delete temporary plan files once merged/done).
2. **`[2/3]` Governance Log Sync:** When `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, or `GOVERNANCE_DOCS` change, enforces a matching top entry in `.context/changes/rules-log.md` (skips Mode 0 onboarding & initial harness install).
3. **`[3/3]` Project `VERIFY_CMD`:** Runs the exact `VERIFY_CMD` from `.context/project.md` (`typecheck && test && build`, `mvn test`, asset checks, etc.).

Supports scoped parallel execution via `VERIFY_FILES="<paths>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`.

## Native Git Rollback

`rules-log.md` pairs `[base: <short-sha>]` anchors with standard Git commands — no shadow repo or sidecar database needed:

```bash
git log --oneline -n 10 -- AGENTS.md .context/project.md   # Find exact commit
git diff <ref> -- <file...>                                # Preview before restoring
git restore --worktree --source=<ref> -- <file...>         # Restore specific file(s)
```
