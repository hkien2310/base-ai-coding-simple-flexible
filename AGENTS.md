# AGENTS.md — Universal Project Harness (Greenfield & Brownfield)

> **Entry Point & 2-End Session Lifecycle**: Always read `.context/project.md` and `.context/state.md` first before acting.
> - If `.context/project.md` contains `STATUS: UNINITIALIZED`, run **Mode 0 (Initialize)** immediately.
> - **1. Start-of-Session Rule (Reconcile & Route):**
>   - Inspect `Active In-Flight Sessions` in `.context/state.md` alongside `git status` / `git log -3`:
>   - **Stale / Finished Row Cleanup:** Any previous row marked `READY` (or whose files are already committed and the user is now asking for a different task) means the user accepted that work and moved on — automatically move that row to `Recently Completed` (and mark its `.context/changes/<slug>.md` as `DONE`).
>   - **Continuation vs Concurrent Task:** If the user's prompt continues an existing row, keep that row active and iterate. If the user gives an unrelated new task while another row is actively `EXEC`/`PLAN` in a concurrent session, leave that other row untouched, avoid its `Locked / Touched Files`, and add a new row for your task. If the user simply says `"tiếp tục"` / `"resume"` with ≥ 2 active rows, ask which one to resume.
> - **2. End-of-Turn Rule (Verify & Park as `READY`):**
>   - Before reporting completion of any code change: (a) run `./.context/verify-gate.sh`, (b) perform live local E2E verification (`Runtime Sandbox` in `project.md`: real DB/API call for backend, live browser check via `chrome-devtools` for UI), and (c) set your task's row in `.context/state.md` to Stage `READY` (do not delete it yet, in case the user wants follow-up tweaks in the next message; the next session's Start Rule will archive it once the user moves on).

---

## Runtime Capability Adapter (Cross-Platform Mapping)

This harness is platform-agnostic (Antigravity, Claude Code, OpenCode, Codex, Cursor, Windsurf, Copilot). Map the abstract actions below to whatever native capability your runtime provides:

| Abstract Action | Antigravity (AGY) | Claude Code | OpenCode / Codex / CLI | Single-Agent IDE (Fallback) |
| :--- | :--- | :--- | :--- | :--- |
| **Ask Clarifying Questions** | `ask_question` tool (or `/grill-me`) | `AskUserQuestion` tool | Numbered multiple-choice text in chat | Numbered multiple-choice text in chat |
| **Read-Only Codebase Scan** | `invoke_subagent(TypeName: "research")` | `Task(subagent_type: "Explore")` | `@explore` subagent or direct `ripgrep` | Direct search & file reads |
| **Call Graph & Impact Analysis** | `code-review-graph` MCP (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_review_context_tool`) | `code-review-graph` MCP or `.context/check-blast-radius.py` | `.context/check-blast-radius.py` | `.context/check-blast-radius.py` (`git grep` fallback) |
| **Parallel Isolated Task** | `invoke_subagent(TypeName: "self", Workspace: "share")` (or `/teamwork`) | `Task` subagent with `git worktree` | Parallel subagent / `git worktree` | Execute tasks sequentially on current branch |
| **Independent Code Review** | Fresh `self` or `research` subagent + `adversarial-verifier` skill | Fresh `Task` subagent + `adversarial-verifier` | `@reviewer` subagent | Self-audit `git diff` against checklist |
| **Browser / UI Verification** | `chrome-devtools` MCP (`list_console_messages`, `list_network_requests`) | `chrome-devtools` / Playwright MCP or CLI | Playwright / headless browser CLI | `curl` / E2E test runner command |

---

## Core Operating Principles & Companion Skills

Always activate these skills if installed in the runtime; if not installed, enforce their core rules directly below:

1. **`ponytail` (Lazy Senior Dev Mode — Mandatory on All Code):**
   - Stop at the first rung that holds before writing code: **(1) YAGNI** (does this need to exist?) → **(2) Reuse existing codebase helper/pattern** → **(3) Standard library** → **(4) Native platform feature** → **(5) Already-installed dependency** → **(6) One-liner** → **(7) Minimum code that works**.
   - Deletion over addition. Boring over clever. Fewest files possible. No speculative abstractions or unrequested dependencies.
   - Bug fix = root cause, never symptom. Grep every caller and fix the shared function once.
2. **`adversarial-verifier` (Zero Sycophancy & Strict Risk Triage):**
   - Treat every requirement, architecture claim, and "passing" diff as an unproven hypothesis.
   - Challenge flawed premises before writing code. Triage findings strictly into `[FATAL]` (blocks completion) vs `[HIGH RISK]` (requires explicit mitigation).
3. **`code-review-graph` (Structural Call-Graph Intelligence):**
   - Prefer `code-review-graph` MCP tools (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_review_context_tool`, `detect_changes_tool`) alongside `.context/check-blast-radius.py` to trace callers, callees, and test coverage before and after edits.
4. **`humanizer` & `stop-slop` (Clean Technical & UI Prose):**
   - Strip AI writing tells ("not X, but Y", throat-clearing openers, inflated corporate adverbs) from documentation, UI copy, PR descriptions, and commit messages.
5. **`modern-web-guidance` (Frontend / Web Platform Tasks Only):**
   - On HTML, CSS, or client-side browser UI tasks, query `modern-web-guidance` first (if installed) and prefer Baseline native Web APIs (`<dialog>`, Popover, CSS Anchor Positioning, `:user-invalid`, `field-sizing`, View Transitions) over custom JS workarounds or extra npm packages (Ponytail Rung 4). Skip completely on backend, CLI, infra, or content-only tasks.

---

## Mode 0: Initialize (`Bootstrap` vs `Onboard`)

Trigger automatically when `.context/project.md` is uninitialized or when the user says `"onboard"` / `"init base"`:

1. **Brownfield (Existing Code Exists in Repo):**
   - Scan the repository (via **Read-Only Codebase Scan**) to detect:
     - Tech stack, framework versions, package manager, and entry points.
     - **Domain & End-to-End Request Flow:** What business domain the repo serves, and how a request/action flows end-to-end (Auth/Guard → Router/Controller → Service/API Client → DB/State → Response/Error wrapper).
     - Exact commands for **build**, **typecheck**, **lint**, **unit/integration test**, and **e2e/browser test**.
     - Directory map & **Golden Exemplars** (the cleanest existing service, controller, UI page, and test file to copy patterns from).
   - **Build Dynamic Call Graph (if `code-review-graph` MCP/CLI is available):** Run `build_or_update_graph_tool(repo_root)` to index `.code-review-graph/graph.db` for instant caller/impact queries.
   - Populate `.context/project.md` with discovered facts and set `STATUS: READY`.
   - Report the discovered profile to the user for quick confirmation.

2. **Greenfield (Empty Repo / New Project):**
   - Interview the user concisely (via **Ask Clarifying Questions**) to lock down:
     - Goal & core MVP scope.
     - Tech stack, database, and **test runner**.
     - Single verification command (`VERIFY_CMD` = typecheck + lint + test).
   - Populate `.context/project.md`, set `STATUS: READY`, and create the initial spec in `.context/changes/00-initial-mvp.md`.

---

## Mode 1: Pre-Flight Triage & 2-Lane Execution Router

Before writing code, evaluate the request against the **Mode Triage Triggers** (do not nag on simple, clear tasks — only trigger when a threshold is actually crossed):
- **Ambiguous requirements / missing edge cases?** → **Do NOT guess.** Ask 2–4 pointed questions immediately (and on AGY, suggest `/grill-me` if deep design alignment is needed).
- **Spans ≥ 2 independent modules (e.g., FE + BE) or parallelizable waves?** → Use **Parallel Isolated Tasks** (and on AGY, suggest `/teamwork` for large multi-agent projects).
- **Hard architectural trade-off or stubborn bug (failed >1 attempt)?** → Perform deep multi-hypothesis root-cause analysis before editing (on AGY, suggest `/boost`).
- **Long autonomous grind until 100% green (migration / bulk test suite)?** → Loop autonomously until `verify-gate.sh` passes (on AGY, suggest `/goal`).
- **Horizontal domain coupling detected?** *(Touches counterpart operations `create` vs `update`, full DTO/mapper pipeline, import/export templates, legacy `null` handling, or sibling module variants)* → **Calculate full blast radius across all 5 dimensions.** If the combined coupled files push blast radius **> 3 files**, route strictly to **Spec Lane**. Never shortcut with Fast Lane when domain coupling is involved.
- **Cross-Repo / Contract coupling detected?** *(Modifies API endpoint URLs, HTTP methods, Request/Response DTO field names/types, Enums, status codes, or validation constraints consumed across repo boundaries)* → **Strict Spec Lane Enforcement.** Changes that cross backend/frontend boundaries **CANNOT use Fast Lane under any circumstances**, even if only touching 1 file or 1 line. Fast Lane is strictly locked to internal service/repository fixes with zero external contract changes.
- **Switching to a new feature in a long chat?** → Suggest `/compact` or starting a fresh chat (since `.context/state.md` preserves state).

Then route to one of two execution lanes based on blast radius:

| Criteria | ⚡ Fast Lane (Bug Fix / Small Tweak) | 🏗️ Spec Lane (Feature / Cross-Module / Refactor) |
| :--- | :--- | :--- |
| **Trigger** | Touching **≤ 3 files** with clear requirements AND **zero external API/DTO/Enum contract changes**. | New feature, DB/API contract change (API endpoint, Request/Response DTO, Enum, status codes), horizontal domain coupling pushing blast radius **> 3 files**, cross-repo impact, or touching **> 3 files**. |
| **Ceremony** | **Zero markdown paperwork.** Do not create `.context/changes/*` files. | Create `.context/changes/<slug>.md` from `_TEMPLATE.md` before coding. |
| **Test Rule** | **Reproducer / Regression Test:** Write or update the test covering the bug/tweak → fix root cause → run `./.context/verify-gate.sh`. | **Spec-to-Test Contract:** Every `TC-xx` row in `.context/changes/<slug>.md` must be approved by user before coding and mapped to a real test. |
| **Parallelism** | Single-threaded in main session. | Independent tasks run via **Parallel Isolated Tasks** (or sequentially if single-agent runtime). |
| **Review** | Self-check diff against Ponytail + Test Quality Gate + `./.context/verify-gate.sh`. | Run **Independent Code Review** acting as Adversarial Code & Test Reviewer. |

---

## Mode 2: Spec Lane Lifecycle (Step-by-Step)

When a task enters **Spec Lane**:

1. **Propose (Delta Spec + Test Contract):**
   - Write `.context/changes/<slug>.md` defining:
     - **Delta Requirements** (`ADDED`, `MODIFIED`, `REMOVED`).
     - **Spec-to-Test Contract Table** (`TC-01`, `TC-02`... mapping each requirement + edge case to concrete Input, Expected Output, and Target Test Level). Must include explicit counterpart parity (`create` vs `update`) and legacy `null` safety test cases.
     - **Horizontal Domain Coupling Checklist** (Mandatory check of 5 pillars: counterpart parity, DTO/mapper pipeline, import/export flows, legacy `null` data compatibility, and sibling family modules before coding).
     - **Cross-Repo & Contract Impact Matrix (Section 3.2)**: Mandatory assessment against sibling consumer repos (`CROSS_REPO_CONSUMERS` in `project.md`). For every modified API endpoint, DTO field, or Enum value: identify impacted consumer repos, consumer files/symbols, breaking vs backward-compatible status, and explicit contract documentation sync plan (`CONTRACT_DOC` in `project.md`).
     - **Task Wave Plan** (tasks in the same wave must touch disjoint files so they can run in parallel).
   - Update `.context/state.md` (`Active Change: <slug>`, `Stage: AWAITING_APPROVAL`).
   - **STOP and ask user to approve** (`"ok"` or adjustments to requirements/test cases).

2. **Execute (Clean-Context Waves + Test Enforcement):**
   - Keep the main conversation lean as the **Orchestrator**.
   - Dispatch tasks in the current wave via **Parallel Isolated Tasks** (passing `.context/project.md` + assigned task and `TC-xx` rows from `.context/changes/<slug>.md`).
   - For each task:
     1. Implement the code following the **Golden Exemplars** in `.context/project.md` and write the mapped tests (`TC-xx`).
     2. Fill in the `Test Ref` column (`file:test_name`) and mark status in `.context/changes/<slug>.md`.
     3. Run `VERIFY_CMD` until 100% green.

3. **Adversarial Code & Test Review (Before Final Report):**
   - Run `./.context/verify-gate.sh` on the integrated branch.
   - Run **Independent Code Review** with prompt:
     *"Audit the full changeset against `.context/changes/<slug>.md` and `.context/project.md`. First run `git diff --name-status` (plus any new untracked target files) to build a complete file checklist and inspect **every changed file individually** — never skim a combined diff or skip files on large changesets (must report `Reviewed: N/N files`). Check: (1) Every `TC-xx` in the Spec Contract has a real, non-trivial test; (2) No banned fake-test patterns exist (see Test Quality Gate in `AGENTS.md`); (3) Horizontal domain coupling completeness: counterpart parity (`create` vs `update`), DTO/mapper pipeline integrity without silent omissions, import/export template/index synchronicity, and legacy null-safety; (4) Cross-repo consumer compatibility across sibling frontend repos (`CROSS_REPO_CONSUMERS`) and verification that contract documentation (`CONTRACT_DOC`) is updated in sync with code changes without breaking consumer contracts; (5) Runtime & logic defect scan: zero DB/API calls inside loops (N+1), zero race conditions or unsafe shared mutable state, zero unguarded null/undefined dereferences, no regressions, security holes, or unnecessary bloat. Report `Reviewed: N/N files` plus `[FATAL]` and `[HIGH RISK]` issues only."*
   - Fix any `[FATAL]` / `[HIGH RISK]` findings and re-run `./.context/verify-gate.sh`.
   - Update `.context/state.md` (and append any new traps to `.context/project.md` under `## Error Memory & Red Lines`).

---

## Mode 3: Test Quality Gate (Anti-Fake-Test Iron Laws)

AI agents frequently cheat at testing by writing tests that merely confirm buggy code. **Strictly enforce these 5 laws:**

1. **Expected Values Come from Spec, NEVER from Code Output:**
   - **BANNED:** Running newly written code first, copying whatever it outputs, and pasting that into `expect(...)` (this locks bugs into tests).
   - **REQUIRED:** Derive `Expected` strictly from the approved `TC-xx` table in the Spec.
   - *Exception (Brownfield Characterization):* When refactoring legacy untested code without changing behavior, write a **Characterization / Golden Test** BEFORE touching the code to lock existing behavior (scrubbing timestamps/random IDs), then refactor.

2. **Never Weaken a Test to Make It Pass:**
   - **BANNED:** Deleting a failing assertion, loosening an expected value, adding `skip`, or changing an existing test just to get green — unless the Spec explicitly lists that behavior under `MODIFIED` or `REMOVED`.
   - If a test fails, fix the **root cause in production code** (or fix a broken test setup), never the business assertion.

3. **Zero Trivial / Swallowed Assertions:**
   - **BANNED:**
     - `try { ... } catch (e) {}` swallowing errors inside tests.
     - Assertions that only check existence/type (`expect(res).toBeDefined()`, `assert result is not None`) without asserting exact business values, status codes, or state side-effects.
     - Mocking the exact function/service being tested so the test only tests the mock.

4. **Red-Green / Mutation Sanity Check:**
   - A test that cannot fail is dead code.
   - For bug fixes: the test MUST fail (or reproduce the symptom) before the fix and pass after the fix.
   - For new logic: mentally or physically invert the core condition (e.g., `>` to `<`, status `200` to `400`) — if the test would still pass, the test is invalid and must be rewritten.

5. **Counterpart Parity & Null Data Coverage:**
   - **BANNED:** Testing only one side of a counterpart operation (e.g., testing `create` but leaving `update` untested, or vice versa); asserting on Entity without asserting JSON ResponseDTO serialization; writing tests that assume fields are always non-null.
   - **REQUIRED:**
     - For every new/modified field in a `create` flow, write a matching `update` test verifying the field is persisted and returned.
     - Mappers/converters must test that all mapped fields are populated (zero silent drops).
     - At least one test case MUST explicitly pass existing/legacy records containing `null` for new fields through Read/Update/Export endpoints to prove absence of `NullPointerException` or unhandled exceptions.

---

## Hard Rules (Non-Negotiable)

1. **Mechanical Gatekeeper Before Completion:** Never claim a task is done without executing `./.context/verify-gate.sh` and seeing `✅ GATEKEEPER PASSED` in terminal output.
2. **End-to-End Local Reality Check (Zero Half-Baked Hand-offs):**
   - **Completeness in Tests & Domain Parity:** Every modified code path MUST be symmetrically covered:
     - Counterpart parity: both `create` and `update` (and `delete`) must be tested.
     - Full pipeline: RequestDTO → Entity → ResponseDTO (real HTTP JSON serialization/deserialization).
     - Document/batch: Excel import (`ExcelSheetUtils`) and Docx/PDF template rendering (`poi-tl` / `TemplateFillService`) if applicable.
     - Legacy `null` compatibility: verify existing records with `null` fields do not throw NPE or crash UI.
     Never test only 1 branch and leave the rest as "chưa test".
   - **Backend / API / DB changes:** Do NOT stop at mocked unit tests. Use the `Runtime Sandbox` commands in `.context/project.md` to: (a) apply any SQL migration to the local DB, (b) start/restart the local server so new code is live, (c) hit the real HTTP endpoint (`curl`) and verify DB rows + JSON response, and (d) clean up temporary test data.
   - **Frontend / UI changes:** Start/connect to the local dev server and verify in a live browser (`chrome-devtools` / Playwright: 0 console errors, 0 failed network requests, visual layout & real interaction verified).
3. **State Hygiene:** Keep `.context/state.md` under **30 lines** (overwrite old state; do not append history). Keep `.context/project.md` under **100 lines**.
4. **Blast-Radius & Cross-Repo Consumer Check Before Editing Shared Code:** Before changing any existing function, DTO, schema, or component signature:
   - Grep all callers (or run `python3 .context/check-blast-radius.py --mode pre-edit --symbol <name> [--consumers <paths>]`) and update/test every affected caller.
   - Assess horizontal domain coupling across all 5 dimensions (counterpart operations, DTO/mapper pipeline, import/export flows, legacy null compatibility, sibling family modules) and cross-repo consumer impact across sibling repos (`CROSS_REPO_CONSUMERS`) to calculate true blast radius before choosing execution lane.
5. **Cross-Repo Contract & Documentation Sync Rule:** Backend contract modifications (API endpoints, Request/Response DTOs, Enums, status codes, validation constraints) must NEVER be completed without: (a) verifying consumer compatibility across frontend repos (`CROSS_REPO_CONSUMERS` in `project.md`) using pre-edit/cross-repo scan, and (b) updating the contract guide (`CONTRACT_DOC` in `project.md`) in the same commit/task. Never silently change backend contracts without updating documentation and validating frontend consumers.
6. **Zero-Repeat Corrections (Compounding Memory):** Whenever the user corrects a mistake or rejects an approach, immediately append a 1-line prevention rule to `.context/project.md` (`## Error Memory & Red Lines`) so the same mistake is never repeated in future sessions.
7. **Multi-Session Concurrency (Zero Collision Rule):** When multiple sessions run concurrently on the same repository:
   - **Row-Level State Updates:** `.context/state.md` uses a concurrent `Active In-Flight Sessions` table. Only add/update/remove **your own task's row** — never wipe rows belonging to other active sessions, and check their `Locked / Touched Files` column to avoid editing the exact same file simultaneously.
   - **No Global Destructive Git Commands:** Never run `git checkout .`, `git reset --hard`, `git stash`, or `git add .` — always stage only your own touched files (`git add <exact-files>`).
   - **Scoped Gatekeeper:** Scope gatekeeper checks to your session's work via `VERIFY_FILES="<your-files>" VERIFY_SPEC="<your-slug-or-None>" ./.context/verify-gate.sh`.
8. **Escape Hatch:** If the user says `"fast"` / `"chỉ làm thôi"` / `"just execute"`, bypass Spec Lane human approval checkpoints and execute directly while still enforcing `./.context/verify-gate.sh` and the Test Quality Gate.
9. **Governance Change Log (Rule & Key Doc Changes — Every Lane, No Exceptions):**
   - **Scope:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/**`, `.claude/**`, `.cursor/rules/**`, `.context/project.md`, plus every path listed in `GOVERNANCE_DOCS` in `.context/project.md` (workflow / craft / review / style / contract docs).
   - **When:** In the same turn you edit any file in scope (even a 1-line Fast Lane tweak), prepend one entry at the **top** of `.context/changes/rules-log.md` right below the `# ...` heading (create it if missing; newest entry at the top; never edit or delete older entries):
     `- [YYYY-MM-DD HH:MM] <file(s)> — <what changed> | Why: <user request / incident> | Replaces: <old rule or None>`
   - **Before editing a governance doc:** read the top 10 entries (`StartLine: 1, EndLine: 15`) of `rules-log.md` so you do not silently revert a rule the user deliberately set.
