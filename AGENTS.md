# AGENTS.md — Universal Project Harness

> **Session Start:** Read `.context/project.md` and `.context/state.md` first. If `project.md` says `STATUS: UNINITIALIZED`, populate it from the repo (or ask the user if greenfield), set `STATUS: READY`, and confirm before coding/authoring. At session start, clear finished `READY` rows from `state.md` and delete finished `.context/changes/<slug>.md` plans (Git history retains completed work).
> **Session End:** Before finishing, run `./.context/verify-gate.sh`, run any required live/manual check, and update only your active row in `.context/state.md`.

## 1. Core Principles
- **Minimalism First:** Reuse existing helpers, templates, and stdlib/platform features; prefer deletion over addition; keep diffs tight with zero unrequested abstractions or dependencies.
- **Adversarial Verification:** Treat requirements, outputs, and claims as unproven until checked; surface `[FATAL]` and `[HIGH RISK]` gaps immediately.
- **Clean Prose:** Strip filler, throat-clearing, and AI clichés from docs, copy, prompts, and commits.

## 2. Pre-Flight & 2-Lane Routing
- Ask 2–4 pointed clarifying questions if goals, edge cases, or constraints are ambiguous; use `git worktree` / parallel subagents when work spans ≥ 2 independent modules.
- **Fast Lane** (`≤ 3` files and no public API/schema/pipeline contract change): No plan file. Fix/author directly → `./.context/verify-gate.sh`.
- **Plan Lane** (`> 3` files, new feature/workflow, or contract/schema change): Create temporary `.context/changes/<slug>.md` (`Status: DRAFT` → `APPROVED`) listing scope, coupled paths, and verifiable checklist items (`- [ ]` or `TC-xx` rows); set `state.md` to `PLAN` and wait for `"ok"` (unless `"fast"` / `"just execute"`). Delete `.context/changes/<slug>.md` once merged/done.

## 3. Domain Guardrails (Apply When Relevant)
- **Code / API / DB:** Trace callers via `git grep` or `code-review-graph` MCP before signature/schema changes; keep `create`/`update`/`delete`, DTO serialization, batch I/O, legacy `null` handling, and `CROSS_REPO_CONSUMERS` in sync; run live API/DB or browser checks on changed flows.
- **Tests:** Derive expectations from specs/contracts, never buggy code; forbid trivial checks (`toBeDefined()`-only, empty `catch`, mocking the unit under test, weakening assertions). Every active checklist item / `TC-xx` must pass.
- **Content / Bots / Creative Pipelines:** Follow format specs, prompt rules, and `GOVERNANCE_DOCS` in `project.md`; keep artifacts free of unrequested boilerplate.

## 4. State, Governance Log & Native Git Rollback
- **Gatekeeper & Hygiene:** Never declare done without `✅ GATEKEEPER PASSED.` from `./.context/verify-gate.sh`. Keep `.context/state.md` ≤ 25 lines and `.context/project.md` ≤ 80 lines. Record user corrections in `project.md` (`## Error Memory & Red Lines`).
- **Concurrency:** Never run `git checkout .`, `git reset --hard`, `git stash`, or `git add .` on shared trees; scope checks via `VERIFY_FILES="<files>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`.
- **Governance Log:** Before editing `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, or `GOVERNANCE_DOCS`, inspect top entries of `.context/changes/rules-log.md`; in the same turn, prepend one line right below `# ...` (never edit/delete older entries):
  `- [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what changed> | Why: <reason> | Replaces: <old rule or None>`
- **Native Git Rollback:** Inspect `git log --oneline -- <file>`, `[base: <sha>]` in `rules-log.md`, or optional local `git tag ckpt/<slug>-YYYYMMDD`; restore via `git restore --worktree --source=<ref> -- <file...>`, and log in `rules-log.md` if rolling back governance files.
