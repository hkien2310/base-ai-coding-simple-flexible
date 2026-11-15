# AGENTS.md — Universal Project Harness

> **Session Start:** Read `.context/project.md`, `.context/state.md` (`Active`, `Last Handoff`, `Open Blockers`), and the top ~20 lines of `.context/decisions.md`. If `STATUS: UNINITIALIZED`, populate `.context/project.md`, set `STATUS: READY`, and confirm before working. Clear finished `READY` rows from `state.md` and delete finished `.context/plans/<slug>.md` files.
> **Session End:** Run `./.context/verify-gate.sh`, run required live checks, and update `.context/state.md` (your active row + overwrite `## Last Handoff` in 1–3 bullets summarizing what shipped and next pickup point).

## 1. Core Principles
- **Minimalism First (`/ponytail`):** Reuse existing helpers, templates, and stdlib/platform features; prefer deletion over addition; zero unrequested abstractions or dependencies.
- **Adversarial Verification:** Treat claims, specs, and outputs as unproven until checked; surface `[FATAL]` and `[HIGH RISK]` gaps immediately.
- **Clean Prose:** Strip filler, throat-clearing, and AI clichés from docs, copy, prompts, and commits.

## 2. Pre-Flight & 2-Lane Routing
- Ask 2–4 pointed questions if requirements or edge cases are ambiguous; use `git worktree` / parallel subagents for ≥ 2 independent modules.
- **Fast Lane** (`≤ 3` files, no public contract/schema/pipeline change): No plan file. Edit directly → `./.context/verify-gate.sh`.
- **Plan Lane** (`> 3` files, new feature/workflow, or contract/schema change): Create temporary `.context/plans/<slug>.md` (`Status: DRAFT` → `APPROVED`) with scope, coupled paths, and `- [ ]` / `TC-xx` checks; set `state.md` to `PLAN`, wait for `"ok"` (unless `"fast"`/`"just execute"`). When complete, distill key architectural/business decisions into `.context/decisions.md` and delete `.context/plans/<slug>.md` (rmdir `.context/plans/` if empty).

## 3. Source-Tree Guardrails & Single-File ADR
- **Decisions & Governance (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, `GOVERNANCE_DOCS`, plus major architectural/product choices):** Check `.context/decisions.md` before changing rules or architecture so rejected options are not re-proposed. When editing governance files (enforced by `verify-gate.sh`) or closing a Plan Lane decision, prepend 1 ADR line right below `# ...` (never edit/delete older entries):
  `- [YYYY-MM-DD HH:MM] [base: <short-sha|unborn>] <scope/file(s)> — <decision or change> | Why: <context & rationale> | Rejected/Replaces: <rejected option, old rule, or None>`
- **Contracts & Coupling (Producer → Consumer):** Trace consumers via `git grep` or `code-review-graph` MCP before changing shared interfaces (signatures, API/DB schemas, configs, or upstream pipeline artifacts); keep symmetric paths (`create`/`update`/`delete`, serialization, batch I/O, legacy `null`/data) and `CROSS_REPO_CONSUMERS` in sync.
- **Verification & Runtime (`Tests`, `VERIFY_CMD`, Live Check):** Derive checks from specs/contracts, never buggy output; forbid fake-pass patterns (`.skip`/`.only`/`@Disabled`, empty `catch`, mocking the unit under test, weakening assertions). Every active `- [ ]` / `TC-xx` must pass, plus live API/DB/UI/output checks when behavior changes.

## 4. State, Concurrency & Native Git Rollback
- **Gatekeeper & Hygiene:** Require `✅ GATEKEEPER PASSED.` from `./.context/verify-gate.sh`. Keep `.context/state.md` ≤ 25 lines and `.context/project.md` ≤ 80 lines; append recurring pitfalls/user corrections under `## Error Memory & Red Lines` in `project.md`.
- **Concurrency & Rollback:** Never run `git checkout .`, `git reset --hard`, `git stash`, or `git add .` on shared trees; scope via `VERIFY_FILES="<files>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`. Roll back via `git log --oneline -- <file>` / `[base: <sha>]` in `decisions.md` + `git restore --worktree --source=<ref> -- <file...>`, logging in `decisions.md` if governance files changed.
