# AGENTS.md — Universal Project Harness (Greenfield & Brownfield)

> **Entry Point & 2-End Session Lifecycle:** Always read `.context/project.md` and `.context/state.md` first before acting.
> - If `.context/project.md` contains `STATUS: UNINITIALIZED`, run **Mode 0 (Initialize)** immediately.
> - **Start-of-Session:** Inspect `Active In-Flight Sessions` in `.context/state.md` alongside `git status` / `git log -3`. Archive any previous `READY` row (or already-committed work when starting a new task) with its commit ref (`git rev-parse --short HEAD`) to `Recently Completed` and mark its `.context/changes/<slug>.md` as `DONE`. Continue an existing row on follow-up; add a new row on an unrelated task without editing other active rows or their locked files. If the user says `"tiếp tục"` / `"resume"` with ≥ 2 active rows, ask which one to resume.
> - **End-of-Turn:** Before reporting completion of any code change: (a) run `./.context/verify-gate.sh`, (b) perform live local E2E verification (`Runtime Sandbox` in `project.md`: real DB/API call for backend, live browser check for UI), and (c) set your task row in `.context/state.md` to `READY` so follow-up tweaks stay open until the next session archives it.

---

## Runtime Capability Adapter (Cross-Platform Mapping)

| Abstract Action | Antigravity (AGY) | Claude Code | OpenCode / Codex / CLI | Single-Agent IDE (Fallback) |
| :--- | :--- | :--- | :--- | :--- |
| **Ask Clarifying Questions** | `ask_question` tool (or `/grill-me`) | `AskUserQuestion` tool | Numbered multiple-choice text | Numbered multiple-choice text |
| **Read-Only Codebase Scan** | `invoke_subagent(TypeName: "research")` | `Task(subagent_type: "Explore")` | `@explore` subagent or `rg` | Direct search & file reads |
| **Call Graph & Impact Analysis** | `code-review-graph` MCP (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_review_context_tool`) | `code-review-graph` MCP or `.context/check-blast-radius.py` | `.context/check-blast-radius.py` | `.context/check-blast-radius.py` (`git grep` fallback) |
| **Parallel Isolated Task** | `invoke_subagent(TypeName: "self", Workspace: "share")` (or `/teamwork`) | `Task` subagent with `git worktree` | Parallel subagent / `git worktree` | Sequential on current branch |
| **Independent Code Review** | Fresh `self` or `research` subagent + `adversarial-verifier` | Fresh `Task` subagent + `adversarial-verifier` | `@reviewer` subagent | Self-audit `git diff` vs checklist |
| **Browser / UI Verification** | `chrome-devtools` MCP (`list_console_messages`, `list_network_requests`) | `chrome-devtools` / Playwright MCP or CLI | Playwright / headless CLI | `curl` / E2E test runner command |

---

## Core Operating Principles & Companion Skills

Activate these skills when installed; otherwise enforce their core rules directly below:

1. **`ponytail` (Lazy Senior Dev Mode):** Stop at the first rung that holds before coding: **(1) YAGNI** → **(2) Reuse existing helper/pattern** → **(3) Standard library** → **(4) Native platform feature** → **(5) Installed dependency** → **(6) One-liner** → **(7) Minimal working code**. Deletion over addition; boring over clever; fewest files possible; no unrequested abstractions or dependencies. Fix root cause across all callers.
2. **`adversarial-verifier`:** Treat requirements, architecture claims, and diffs as unproven hypotheses. Challenge flawed premises before coding; triage issues strictly into `[FATAL]` (blocks completion) vs `[HIGH RISK]` (requires mitigation).
3. **`code-review-graph`:** Use MCP graph tools (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_review_context_tool`, `detect_changes_tool`) alongside `.context/check-blast-radius.py` to trace callers, callees, and test coverage before and after edits.
4. **`humanizer` & `stop-slop`:** Strip AI writing tells ("not X, but Y", throat-clearing openers, inflated corporate adverbs) from docs, UI copy, PRs, and commit messages.
5. **`modern-web-guidance` (Frontend / Web UI Only):** Query first on HTML/CSS/browser UI tasks and prefer Baseline native APIs (`<dialog>`, Popover, CSS Anchor Positioning, `:user-invalid`, `field-sizing`, View Transitions) over JS workarounds. Skip on backend, CLI, infra, or content-only tasks.

---

## Mode 0: Initialize (`Onboard` vs `Bootstrap`)

Trigger automatically when `.context/project.md` has `STATUS: UNINITIALIZED` or user says `"onboard"` / `"init base"`:
- **Brownfield (Existing Code):** Run a Read-Only Codebase Scan to record tech stack, versions, E2E request flow (Auth/Guard → Router/Controller → Service/Client → DB/State → Response/Error), exact build/typecheck/lint/test/e2e commands (`VERIFY_CMD`), and Golden Exemplars. Run `build_or_update_graph_tool` if available, write `.context/project.md` (`STATUS: READY`), and present the summary for confirmation.
- **Greenfield (Empty Repo):** Interview the user concisely on goal, MVP scope, stack/DB, test runner, and `VERIFY_CMD`. Populate `.context/project.md` (`STATUS: READY`) and draft `.context/changes/00-initial-mvp.md`.

---

## Mode 1: Pre-Flight Triage, 5 Coupling Dimensions & 2-Lane Router

Evaluate before coding (only interrupt when a threshold is actually crossed):
- **Ambiguous spec / missing edge cases?** Ask 2–4 pointed questions immediately (suggest `/grill-me` on AGY).
- **Spans ≥ 2 independent modules or parallel waves?** Dispatch isolated worktrees (`Workspace: "share"` / `/teamwork`).
- **Hard architectural trade-off or stubborn bug (> 1 failed attempt)?** Perform deep multi-hypothesis root-cause analysis (suggest `/boost` on AGY).
- **Large migration / bulk test suite grind?** Loop until `./.context/verify-gate.sh` passes (suggest `/goal` on AGY); suggest `/compact` on context switch in long threads.

**5 Domain & Contract Coupling Dimensions (Calculate Full Blast Radius Before Routing):**
1. **Counterpart Parity:** `create` ↔ `update` ↔ `delete` operations stay synchronized.
2. **Serialization Pipeline:** Full `Request` → `Domain/Entity` → `Response` flow verified with zero silent field drops.
3. **Batch / Template I/O:** Import parsers, schemas, and export/report templates stay synchronized.
4. **Legacy Data Safety:** Existing records with `null`, missing, or default values execute without unhandled errors.
5. **Sibling Modules & Cross-Repo Contracts:** Parallel sibling module variants checked; external API endpoints, schemas/DTOs, Enums, and status codes checked against `CROSS_REPO_CONSUMERS` and synced in `CONTRACT_DOC`.

| Criteria | ⚡ Fast Lane (Bug Fix / Small Tweak) | 🏗️ Spec Lane (Feature / Contract / Refactor) |
| :--- | :--- | :--- |
| **Trigger** | **≤ 3 files** (including coupled files) AND **zero** external API/DTO/Enum/cross-repo contract changes. | New feature, **any** API/DTO/Enum/cross-repo contract change (even 1 line), or **> 3 files** across the 5 dimensions. |
| **Ceremony** | Zero markdown paperwork. | Create `.context/changes/<slug>.md` from `_TEMPLATE.md` before coding. |
| **Test Rule** | Reproducer / regression test → fix root cause → `./.context/verify-gate.sh`. | Every `TC-xx` row approved before coding and mapped to real tests (`file:name`). |
| **Execution & Review** | Single-threaded; self-check diff + `./.context/verify-gate.sh`. | Isolated parallel waves (`git worktree`) + Independent Adversarial Review. |

---

## Mode 2: Spec Lane Lifecycle

1. **Propose (Delta Spec + Test Contract):**
   - Draft `.context/changes/<slug>.md` with Delta Requirements (`ADDED`, `MODIFIED`, `REMOVED`), `TC-xx` Spec-to-Test Contract (including counterpart parity + legacy `null`/missing cases), 5-Dimension Coupling Checklist, Cross-Repo Impact Matrix, and disjoint Execution Waves.
   - Update `.context/state.md` (`Stage: AWAITING_APPROVAL`) and **STOP for user `"ok"`** or adjustments.
2. **Execute (Isolated Waves + Test Enforcement):**
   - Orchestrate disjoint waves via `git worktree` / `Workspace: "share"`. Follow Golden Exemplars in `project.md`, implement mapped `TC-xx` tests, populate `Test Ref` (`file:name`) and status in the spec, and run `VERIFY_CMD` until green.
3. **Independent Adversarial Review:**
   - Run `./.context/verify-gate.sh`, then run Independent Code Review inspecting **every changed and untracked target file individually** (never skim combined diffs; must report `Reviewed: N/N files`).
   - Audit: (1) every `TC-xx` has a non-trivial test; (2) zero banned fake-test patterns; (3) 5-dimension coupling & `CONTRACT_DOC` sync completeness; (4) N+1 calls in loops, race conditions or unsafe shared state, unguarded null/undefined dereferences, security holes, regressions, or bloat. Report `Reviewed: N/N files` plus `[FATAL]` and `[HIGH RISK]` only; fix findings, re-run `./.context/verify-gate.sh`, and update `state.md` / `project.md`.

---

## Mode 3: Test Quality Gate (Anti-Fake-Test Iron Laws)

1. **Expected From Spec, Never Code Output:** Derive `Expected` strictly from `TC-xx` / requirements (brownfield refactor exception: write a characterization test before editing untested code).
2. **Never Weaken Tests:** Never delete, loosen, or `.skip` failing assertions unless explicitly authorized under Spec `MODIFIED`/`REMOVED`. Fix production code or broken test setup.
3. **Zero Trivial / Swallowed Assertions:** Ban empty `catch {}`, existence-only checks (`toBeDefined()`, `assert x is not None`) without exact business values/status codes/side effects, and mocking the exact unit under test.
4. **Red-Green / Condition-Inversion Check:** Bug-fix tests must reproduce/fail before the fix; new logic tests must fail if you invert the core condition (`>` ↔ `<`, `200` ↔ `400`).
5. **Symmetrical & Legacy Null Coverage:** Cover counterpart operations (`create` + `update`), full JSON/DTO serialization, and legacy `null`/missing-field inputs.

---

## Hard Rules (Non-Negotiable)

1. **Mechanical Gatekeeper:** Never claim a task is done without running `./.context/verify-gate.sh` and observing `✅ GATEKEEPER PASSED`.
2. **Live Local E2E Check:** Cover every modified code path symmetrically. Backend/DB: apply migrations, run local server, verify live HTTP (`curl`) + DB state, clean up temp data. Frontend/UI: verify in a live browser (`chrome-devtools` / Playwright: 0 console errors, 0 failed network requests, real layout & interaction).
3. **State Hygiene:** Keep `.context/state.md` ≤ 30 lines (overwrite, never append history) and `.context/project.md` ≤ 100 lines.
4. **Pre-Edit Blast Radius:** Before changing shared functions, DTOs, schemas, or component signatures, run `python3 .context/check-blast-radius.py --mode pre-edit --symbol <name> [--consumers <paths>]` and update affected callers.
5. **Cross-Repo Contract Sync:** Any backend contract change (API, DTO, Enum, status code, validation) requires verifying `CROSS_REPO_CONSUMERS` and updating `CONTRACT_DOC` in the same task.
6. **Zero-Repeat Corrections:** Whenever the user corrects a mistake or rejects an approach, immediately append a 1-line rule to `.context/project.md` (`## Error Memory & Red Lines`).
7. **Concurrency (`git worktree` First):** Use `git worktree` / `Workspace: "share"` for parallel work so diffs and builds never collide. When sharing one working tree: edit only your own row in `.context/state.md` and avoid other rows' locked files; never run `git checkout .`, `git reset --hard`, `git stash`, or `git add .` (stage exact files); scope gatekeeper runs via `VERIFY_FILES="<files>" VERIFY_SPEC="<slug|None>" ./.context/verify-gate.sh`.
8. **Escape Hatch:** `"fast"` / `"chỉ làm thôi"` / `"just execute"` skips Spec human-approval pauses while still enforcing `./.context/verify-gate.sh` and Mode 3 Test Laws.
9. **Governance Change Log (Mechanically Enforced):** Before editing `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, or `GOVERNANCE_DOCS`, read the top 10 entries of `.context/changes/rules-log.md`. In the same turn (every lane), prepend one entry right below `# ...` (create if missing; never edit or delete older entries):
   `- [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what changed> | Why: <reason> | Replaces: <old rule or None>`
10. **Per-File Git Rollback & Milestone Tags:** Commit atomic checkpoints; before risky multi-file refactors or rule experiments on a clean tree, optionally mark a local tag (`git tag ckpt/<slug>-YYYYMMDD`; never `git push --tags` on shared repos). To roll back specific file(s) without touching other work, pick `<ref>` from `git log --oneline -- <file>` (`<sha>` or `<sha>~1`), `[base: <sha>]` in `rules-log.md`, `Base Git Ref` in `<slug>.md`, or `git tag -l "ckpt/*"`, resolve symlinks (`CLAUDE.md` → `AGENTS.md`), preview `git diff <ref> -- <file...>`, run `git restore --worktree --source=<ref> -- <file...>`, and prepend `rules-log.md` if rolling back a governance file.
