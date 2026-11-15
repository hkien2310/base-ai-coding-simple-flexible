# Base AI Coding — Simple & Flexible Agentic Harness

A minimal, zero-dependency project harness for AI coding agents (**Antigravity, Claude Code, Cursor, OpenCode, Codex**). Works out of the box for both **Greenfield** and **Brownfield** repositories.

## Key Features

1. **Additive Coexistence (Never Overwrites Existing Rules):**
   - If the target project already has `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`, `inject.sh` leaves them untouched and installs the harness into `.agents/rules/coding-base.md`, `.claude/rules/coding-base.md`, and `.cursor/rules/coding-base.mdc`.
2. **Git Stealth Mode or Solo `--track` Mode:**
   - **Stealth (default):** Hides harness files via `.git/info/exclude` (including `git worktree` setups). `git status` stays clean with zero noise in team PRs.
   - **Tracked (`--track`):** Removes stealth exclusions so solo or private repos can commit and push `.context/` and harness rules to Git (while keeping `.context/changes/commit-log.md` and `.code-review-graph/` ignored). `--upgrade` and `--force` preserve the repo's active mode.
3. **Multi-Session Concurrency (`git worktree` First):**
   - Uses isolated `git worktree` / `Workspace: "share"` checkouts as the primary mechanism for parallel work so diffs and builds never collide; when sharing a working tree, coordinates via the `Active In-Flight Sessions` table in `.context/state.md` and full-pipeline scoped verification (`VERIFY_FILES`, `VERIFY_SPEC`).
4. **2-End Session Lifecycle:**
   - **Start-of-Session:** Automatically archives previous `READY` tasks (with commit ref) into `Recently Completed` when you move on to a new task, or resumes an active row without stepping on concurrent sessions.
   - **End-of-Turn:** Runs the mechanical gatekeeper + live E2E verification (DB/API/Browser), then parks the task row as `READY` so you can still request follow-up tweaks before it closes.
5. **Governance Change Log (Mechanically Enforced):**
   - Any edit to `AGENTS.md`, `CLAUDE.md`, `.agents/**`, `.context/project.md`, or docs listed in `GOVERNANCE_DOCS` gets a one-line entry with `[base: <short-sha>]` at the top of `.context/changes/rules-log.md` (what changed, why, what it replaced), verified mechanically by `verify-gate.sh` (except initial Mode 0 `UNINITIALIZED` → `READY` onboarding). Agents read the top entries before touching rules, so deliberate decisions don't get silently reverted.
6. **Native Git Per-File Rollback & Auto Context Commit Log:**
   - Zero custom `.vault` repos or extra bloat: every `git commit` triggers a lightweight `post-commit` hook that records `commit:<sha>`, `prev:<sha>`, optional tags, changed files, and the active AI task/spec context into gitignored `.context/changes/commit-log.md`.
   - Spec files (`_TEMPLATE.md`) and `rules-log.md` anchor pre-change refs (`Base Git Ref` / `[base: <sha>]`), and optional milestone tags (`git tag ckpt/<slug>`) bookmark risky experiments so any single file can be restored cleanly via `git restore --worktree --source=<ref> -- <file...>`.
7. **Mechanical Anti-Cheat Gatekeeper (`verify-gate.sh` & `check-blast-radius.py`):**
   - Blocks `.skip`, `.only`, `@Disabled`, empty `catch {}` blocks, and unauthorized test assertion deletions across both tracked diffs and untracked test files, scoped cleanly by `VERIFY_FILES` across all 5 steps.
   - Traces caller blast radius via `.code-review-graph/graph.db` (SQLite AST — `FATAL` on breaking signature changes, `WARN` on backward-compatible optional parameter additions) with automatic `WARN`-level fallback to `git diff` + `git grep` (`--strict` to enforce), plus dynamic `CONTRACT_DOC` cross-repo consumer scanning.

---

## Repository Structure

```text
base-ai-coding-simple-flexible/
├── AGENTS.md                      # 2-Lane Router (Fast vs Spec Lane) + 2-End Lifecycle + 5 Test Laws
├── CLAUDE.md -> AGENTS.md         # Symlink for Claude Code compatibility
├── inject.sh                      # 1-command installer (Stealth / Upgrade / Track / Force modes)
└── .context/
    ├── .gitignore                 # Ignores local changes/commit-log.md in tracked repos
    ├── project.md                 # Project map: Stack, VERIFY_CMD, Runtime Sandbox, Error Memory
    ├── state.md                   # Shared-tree session state table (< 30 lines)
    ├── verify-gate.sh             # 5-step mechanical gatekeeper (Anti-cheat, Blast-radius, TC-xx, rules-log, VERIFY_CMD)
    ├── check-blast-radius.py      # Dual-engine caller impact analyzer (SQLite Call Graph + Git Grep)
    └── changes/
        ├── _TEMPLATE.md           # Delta Spec + Base Git Ref + Spec-to-Test Contract + Cross-Repo Matrix
        ├── rules-log.md           # Reverse-chronological log (newest at top) of every rule / key-doc change
        └── commit-log.md          # Auto-generated local log (gitignored) linking commits, prev refs, tags & AI context
```

---

## Recommended Companion Skills & MCP Servers

The harness works out of the box with **zero external dependencies** (its core rules and `git grep` fallbacks are baked directly into `AGENTS.md` and `check-blast-radius.py`), but automatically upgrades its capabilities when these companion skills/MCPs are installed:

| Skill / MCP | Role in Harness | Built-in Fallback (If Not Installed) |
| :--- | :--- | :--- |
| **`ponytail`** *(Skill)* | Enforces the 7-rung simplicity ladder (YAGNI → reuse existing → stdlib → native → installed dep → 1-liner → minimal code) and `ponytail-review`. | Core 7-rung ladder is embedded directly in `AGENTS.md`. |
| **`adversarial-verifier`** *(Skill)* | Eliminates sycophancy, stress-tests architecture proposals, and triages review issues into `[FATAL]` vs `[HIGH RISK]`. | Adversarial review prompt & risk triage rules are baked into `AGENTS.md` Mode 2. |
| **`code-review-graph`** *(MCP / CLI)* | Builds `.code-review-graph/graph.db` (Tree-sitter + SQLite) for instant AST caller/callee impact radius (`get_impact_radius_tool`, `get_review_context_tool`). | `.context/check-blast-radius.py` automatically falls back to `git diff` + `git grep`. |
| **`chrome-devtools` / Playwright** *(MCP)* | Live browser verification (`list_console_messages`, `list_network_requests`, DOM snapshot) at the End-of-Turn check. | E2E test runner command / `curl` checks defined in `.context/project.md`. |
| **`humanizer` / `stop-slop`** *(Skill)* | Strips AI writing patterns from documentation, UI copy, and commit messages. | Anti-slop rules embedded in `AGENTS.md`. |
| **`modern-web-guidance`** *(Skill / CLI)* | Queries Baseline modern Web Platform APIs (`<dialog>`, Popover, Anchor Positioning, View Transitions) on HTML/CSS/UI tasks before writing JS workarounds (skipped on backend/CLI tasks). | Native-platform-first rule (Ponytail Rung 4) embedded in `AGENTS.md`. |

---

## Injecting into Any Project

### Option A — Terminal (1 Command)

```bash
# 1. Clone once anywhere on your machine
git clone https://github.com/hkien2310/base-ai-coding-simple-flexible.git ~/coding-base

# 2. Inject into any existing or empty project (Default: Stealth + Coexistence)
~/coding-base/inject.sh /path/to/your-project
```

| Flag | Behavior |
| :--- | :--- |
| *(no flag)* / `--stealth` | **Stealth + Coexistence (Default):** Keeps existing `AGENTS.md`/`CLAUDE.md` untouched (installs `.agents/rules/coding-base.md` alongside them) and hides all harness files in `.git/info/exclude`. |
| `--upgrade` | **Safe Engine Update:** Updates engine files (`AGENTS.md` / `coding-base.md`, `verify-gate.sh`, `check-blast-radius.py`, `_TEMPLATE.md`) + `pre-commit`/`post-commit` hooks, and preserves `project.md`, `state.md`, `commit-log.md`, custom project rules, and active tracking mode (`stealth` vs `track`). |
| `--track` | **Git-Tracked Mode (Solo / Private Repos):** Removes harness exclusions from `.git/info/exclude` so you can commit and push `.context/` and rules to Git while keeping `.context/changes/commit-log.md` and `.code-review-graph/` ignored. Re-run with `--stealth` anytime to hide again. |
| `--force` | **Factory Reset:** Resets `.context/project.md` and `.context/state.md` back to blank templates (never overwrites custom project `AGENTS.md`/`CLAUDE.md`; preserves tracking mode). |

> **Note for non-Git folders:** You can inject into an empty folder before running `git init`. Once you run `git init` later, re-run `~/coding-base/inject.sh /path/to/your-project` so `.git/info/exclude`, `pre-commit`/`post-commit` hooks, and `commit-log.md` are wired up automatically.

### Option B — Ask Your AI Agent Directly

Paste this single prompt into Antigravity, Claude Code, Cursor, or Codex inside any target project:

```text
Clone https://github.com/hkien2310/base-ai-coding-simple-flexible.git to ~/coding-base (or git pull if already cloned), run ~/coding-base/inject.sh on this workspace, and onboard .context/project.md.
```

---

## Per-File Rollback & Milestone Tags (Native Git)

Every `git commit` triggers a lightweight `post-commit` hook that logs `commit:<sha>`, `prev:<sha>`, optional tags, changed files, and active AI task/spec context at the top of `.context/changes/commit-log.md` (gitignored). Combined with `[base: <sha>]` in `rules-log.md` and `Base Git Ref` in specs, you always have exact refs to restore individual files without touching the rest of your workspace.

```bash
# 1. Pick the commit / prev / base ref from .context/changes/commit-log.md or rules-log.md (or git log --oneline -- path/to/file)

# 2. Preview differences before rolling back
git diff <ref> -- path/to/file

# 3. Roll back ONLY that file (safe for stealth/excluded files too — never stages into .git/index)
git restore --worktree --source=<ref> -- path/to/file

# 4. Optional milestone tag before big experiments (local bookmarks — never `git push --tags` on shared repos)
git tag ckpt/ten-moc                   # Mark current commit
git tag -l "ckpt/*"                    # List milestone tags
git tag -d ckpt/ten-moc                # Delete local milestone tag when done
```

---

## Workflow

1. **One-Time Initialization (`Mode 0`):**
   - **Brownfield (Existing Code):** Open the project and type `"onboard"`. The agent scans your stack, indexes the call graph (if available), and populates `.context/project.md` with your exact build/lint/test commands (`VERIFY_CMD`).
   - **Greenfield (New Project):** Open the project and type `"bootstrap"`. The agent asks 2–4 pointed questions to lock down the stack and creates the initial MVP spec.
2. **Daily Execution (`Mode 1` — 2-Lane Router):**
   - **⚡ Fast Lane (≤ 3 files, zero external API/DTO contract changes):** Zero markdown paperwork. Edit code → write/update regression test → run `./.context/verify-gate.sh` → done.
   - **🏗️ Spec Lane (> 3 files, horizontal domain coupling, or API/DTO/Cross-repo changes):** Draft `.context/changes/<slug>.md` with a `TC-xx` test contract → wait for `"ok"` → execute parallel waves → run Independent Adversarial Review → pass `./.context/verify-gate.sh`.
