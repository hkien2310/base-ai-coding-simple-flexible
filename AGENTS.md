# AGENTS.md — Universal Project Harness

> **Session Start:** Read `.context/project.md` and `.context/state.md` first. If `STATUS: UNINITIALIZED`, populate `.context/project.md`, set `STATUS: READY`, and confirm before working. Clear finished `READY` rows from `state.md` and delete finished `.context/changes/<slug>.md` plans (Git history keeps completed work).
> **Session End:** Run `./.context/verify-gate.sh`, run required live checks, and update only your active row in `.context/state.md`.

## 1. Core Principles
- **Minimalism First (`/ponytail`):** Reuse existing helpers, templates, and stdlib/platform features; prefer deletion over addition; zero unrequested abstractions or dependencies.
- **Adversarial Verification:** Treat claims, specs, and outputs as unproven until checked; surface `[FATAL]` and `[HIGH RISK]` gaps immediately.
- **Clean Prose:** Strip filler, throat-clearing, and AI clichés from docs, copy, prompts, and commits.

## 2. Pre-Flight & 2-Lane Routing
- Ask 2–4 pointed questions if requirements or edge cases are ambiguous; use `git worktree` / parallel subagents for ≥ 2 independent modules.
- **Fast Lane** (`≤ 3` files, no public contract/schema/pipeline change): No plan file. Edit directly → `./.context/verify-gate.sh`.
- **Plan Lane** (`> 3` files, new feature/workflow, or contract/schema change): Create temporary `.context/changes/<slug>.md` (`Status: DRAFT` → `APPROVED`) with scope, coupled paths, and `- [ ]` / `TC-xx` checks; set `state.md` to `PLAN`, wait for `"ok"` (unless `"fast"`/`"just execute"`), and delete once done.

## 3. Source-Tree Guardrails (3 Universal Layers)
- **Governance & Specs (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, `GOVERNANCE_DOCS`):** Inspect top entries of `.context/changes/rules-log.md` before editing; in the same turn, prepend right below `# ...` (never edit/delete older entries):
  `- [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what changed> | Why: <reason> | Replaces: <old rule or None>`
- **Contracts & Coupling (Producer → Consumer):** Before changing shared interfaces (signatures, API/DB schemas, configs, or upstream pipeline artifacts), trace consumers via `git grep` or `code-review-graph` MCP; keep symmetric paths (`create`/`update`/`delete`, serialization, batch I/O, legacy `null`/data) and `CROSS_REPO_CONSUMERS` in sync.
- **Verification & Runtime (`Tests`, `VERIFY_CMD`, Live Check):** Derive checks from specs/contracts, never buggy output; forbid fake-pass patterns (`.skip`/`.only`/`@Disabled`, empty `catch`, mocking the unit under test, weakening assertions). Every active `- [ ]` / `TC-xx` must pass, plus live API/DB/UI/output checks when behavior changes.

## 4. State, Concurrency & Native Git Rollback
- **Gatekeeper & Hygiene:** Require `✅ GATEKEEPER PASSED.` from `./.context/verify-gate.sh`. Keep `.context/state.md` ≤ 25 lines and `.context/project.md` ≤ 80 lines; append user corrections under `## Error Memory & Red Lines`.
- **Concurrency & Rollback:** Never run `git checkout .`, `git reset --hard`, `git stash`, or `git add .` on shared trees; scope via `VERIFY_FILES="<files>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`. Roll back via `git log --oneline -- <file>` / `[base: <sha>]` in `rules-log.md` + `git restore --worktree --source=<ref> -- <file...>`, logging in `rules-log.md` if governance files changed.
