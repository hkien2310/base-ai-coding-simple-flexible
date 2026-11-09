# Project Profile & Guardrails

STATUS: UNINITIALIZED

## 1. Stack & Environment
- **Language / Runtime:** TBD
- **Framework:** TBD
- **Database / State:** TBD
- **Test Framework(s):** TBD

## 2. Domain & Cross-Repo Architecture
- **Business Domain:** TBD
- **Cross-Repo Consumers:**
  - **CROSS_REPO_CONSUMERS**: ``
  - **CONTRACT_DOC**: ``
- **Call Graph Index:** `.code-review-graph/graph.db` (Priority 1 SQLite query; automated fallback to git diff + git grep when absent)

## 3. Verification Commands & Lane Router (Single Source of Truth)
- **Lane Router:** Touching **≤ 3 files** = **Fast Lane** (Zero spec paperwork — edit directly + write/update test + run `./.context/verify-gate.sh`). Touching **> 3 files** = **Spec Lane** (Create `.context/changes/<slug>.md` first). Contract changes (API/DTO/Enum) ALWAYS enter Spec Lane.
- **`VERIFY_CMD` (Full gate before completion):** `bash -n .context/verify-gate.sh && python3 -m py_compile .context/check-blast-radius.py`
- **Typecheck / Compile:** `TBD`
- **Linter / Syntax:** `TBD`
- **Targeted Test (Blast Radius):** `python3 .context/check-blast-radius.py --mode gate`
- **E2E / Browser Verification:** `TBD`

## 4. Architecture & Golden Exemplars
- **Service / Business Logic Exemplar:** `TBD`
- **Controller / Route / UI Exemplar:** `TBD`
- **Test Exemplar:** `TBD`

## 5. Runtime Sandbox & Conventions
- **Local Verification:** Run `./.context/verify-gate.sh` from repo root before reporting done.
- **Live E2E Sandbox:** `TBD` (e.g. local dev server URL, DB connection, or `chrome-devtools` check)

## 6. Error Memory & Red Lines (Append 1 line per real pitfall discovered)
- [ ] Never mark a task complete without running `./.context/verify-gate.sh` and seeing `✅ GATEKEEPER PASSED`.
- [ ] Never weaken or delete an existing test assertion unless the spec explicitly modifies/removes that behavior.
- [ ] Before modifying shared functions, run `python3 .context/check-blast-radius.py --mode pre-edit --symbol <name>` to check all call sites.
