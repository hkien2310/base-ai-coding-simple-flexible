# Base AI Coding — Simple & Flexible Agentic Harness

A minimal, zero-dependency project harness for AI coding agents (**Antigravity, Claude Code, Cursor, OpenCode, Codex**). Works out of the box for both **Greenfield** and **Brownfield** repositories.

## Key Features

1. **Additive Coexistence (Never Overwrites Existing Rules):**
   - If the target project already has `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`, `inject.sh` leaves them untouched and installs the harness into `.agents/rules/coding-base.md`, `.claude/rules/coding-base.md`, and `.cursor/rules/coding-base.mdc`.
2. **Git Stealth Mode by Default:**
   - Automatically hides all harness files via `.git/info/exclude` (including `git worktree` setups). `git status` stays 100% clean with zero noise in team PRs.
3. **Multi-Session Concurrency:**
   - Tracks parallel work in an `Active In-Flight Sessions` table inside `.context/state.md` with per-session file locks (`Locked / Touched Files`) and scoped verification (`VERIFY_FILES`, `VERIFY_SPEC`).
4. **2-End Session Lifecycle:**
   - **Start-of-Session:** Automatically archives previous `READY` tasks into `Recently Completed` when you move on to a new task, or resumes an active row without stepping on concurrent sessions.
   - **End-of-Turn:** Runs the mechanical gatekeeper + live E2E verification (DB/API/Browser), then parks the task row as `READY` so you can still request follow-up tweaks before it closes.
5. **Mechanical Anti-Cheat Gatekeeper (`verify-gate.sh` & `check-blast-radius.py`):**
   - Blocks `.skip`, `.only`, `@Disabled`, empty `catch {}` blocks, and unauthorized test assertion deletions in `git diff`.
   - Traces caller blast radius via `.code-review-graph/graph.db` (SQLite) with automatic fallback to `git diff` + `git grep`, plus cross-repo consumer scanning.

---

## Repository Structure

```text
base-ai-coding-simple-flexible/
├── AGENTS.md                      # 2-Lane Router (Fast vs Spec Lane) + 2-End Lifecycle + 5 Test Laws
├── CLAUDE.md -> AGENTS.md         # Symlink for Claude Code compatibility
├── inject.sh                      # 1-command installer (Stealth / Track / Force modes)
└── .context/
    ├── project.md                 # Project map: Stack, VERIFY_CMD, Runtime Sandbox, Error Memory
    ├── state.md                   # Concurrent multi-session state table (< 30 lines)
    ├── verify-gate.sh             # 4-step mechanical gatekeeper (Anti-cheat, Blast-radius, TC-xx, VERIFY_CMD)
    ├── check-blast-radius.py      # Dual-engine caller impact analyzer (SQLite Call Graph + Git Grep)
    └── changes/
        └── _TEMPLATE.md           # Delta Spec + Spec-to-Test Contract + Cross-Repo Impact Matrix
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

---

## Quick Start

```bash
# 1. Clone the harness
git clone https://github.com/hkien2310/base-ai-coding-simple-flexible.git

# 2. Inject into any target repository (Default: Stealth Mode + Coexistence)
./base-ai-coding-simple-flexible/inject.sh /path/to/your-project

# Optional flags:
# ./inject.sh /path/to/your-project --track   # Track harness files in Git
# ./inject.sh /path/to/your-project --force   # Overwrite existing harness files with latest version
```

---

## Workflow

1. **One-Time Initialization (`Mode 0`):**
   - **Brownfield (Existing Code):** Open the project and type `"onboard"`. The agent scans your stack, indexes the call graph (if available), and populates `.context/project.md` with your exact build/lint/test commands (`VERIFY_CMD`).
   - **Greenfield (New Project):** Open the project and type `"bootstrap"`. The agent asks 2–4 pointed questions to lock down the stack and creates the initial MVP spec.
2. **Daily Execution (`Mode 1` — 2-Lane Router):**
   - **⚡ Fast Lane (≤ 3 files, zero external API/DTO contract changes):** Zero markdown paperwork. Edit code → write/update regression test → run `./.context/verify-gate.sh` → done.
   - **🏗️ Spec Lane (> 3 files, horizontal domain coupling, or API/DTO/Cross-repo changes):** Draft `.context/changes/<slug>.md` with a `TC-xx` test contract → wait for `"ok"` → execute parallel waves → run Independent Adversarial Review → pass `./.context/verify-gate.sh`.
