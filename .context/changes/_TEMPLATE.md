# Change: <slug>

- **Status:** DRAFT (`DRAFT` | `APPROVED` | `IN_PROGRESS` | `DONE`)
- **Goal:** 1-2 sentences explaining the problem and desired outcome.
- **Base Git Ref:** `<git rev-parse --short HEAD (pre-change rollback anchor)>`

## 1. Delta Requirements (OpenSpec Format)

### ADDED
- **R-01:** <Requirement summary>

### MODIFIED
- None

### REMOVED
- None

## 2. Spec-to-Test Contract (Traceability Matrix)
> User approves this table before coding. Every row (`TC-xx`) must map to a real assertion in test code. Expected values must come from the requirement, never from copying code output.
> Mandatory coverage: New/modified features must include counterpart parity (`create` vs `update`) and legacy `null`/missing-field compatibility tests.

| ID | Req | Level (`unit`\|`int`\|`e2e`) | Input / Precondition | Action / Steps | Expected Outcome (Exact) | Status (`untested`\|`pass`\|`fail`) | Test Ref (`file:name`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TC-01` | `R-01` | `int` | <Valid input for create operation> | POST /api/... | 200/201 + DB record created + correct response payload/DTO | `untested` | `TBD` |
| `TC-02` | `R-01` | `int` | <Valid input for update counterpart> | PUT /api/.../{id} | 200 + DB record updated symmetrically + returned in GET | `untested` | `TBD` |
| `TC-03` | `R-01` | `unit` | Legacy record with new field = `null` or missing | Call Service / Mapper / Export | Graceful fallback default, zero unhandled null/missing-field error | `untested` | `TBD` |
| `TC-04` | `R-01` | `unit` | <Invalid input / edge case> | <Call API / Function / UI> | <Exact error code / 400 rejection payload> | `untested` | `TBD` |

## 3. Technical Decisions & Blast Radius

### 3.1 Horizontal Domain Coupling Checklist
> Mandatory pre-flight check before coding. Confirm each dimension or explain why N/A.

- [ ] **Counterpart Parity (`create` ↔ `update` ↔ `delete`):** Are all new/modified fields synchronized across create and update paths?
  - Detail: <Explain synchronization or N/A with rationale>
- [ ] **Serialization Pipeline (`Request` → `Domain/Entity` → `Response`):** Are input schemas, domain models, and response payloads/mappers verified against silent field drops?
  - Detail: <Explain full pipeline mapping or N/A>
- [ ] **Batch / Import-Export & Template Flows:** Are import parsers, schemas, and export/report templates updated in sync?
  - Detail: <Explain parser and template updates or N/A>
- [ ] **Legacy Data Safety (`null` / missing fields):** Are existing persisted records with `null` or missing values for new fields handled safely without unhandled errors?
  - Detail: <Explain fallback defaults or N/A>
- [ ] **Symmetrical / Sibling Modules:** Have parallel sibling module variants been checked? If excluded, is it explicitly noted in "Out of scope (YAGNI)"?
  - Detail: <Mark sibling modules as IN SCOPE or explicitly state in "Out of scope (YAGNI)" with rationale>

### 3.2 Cross-Repo & Contract Impact Matrix
> Mandatory check when touching API endpoints, Request/Response DTOs/schemas, Enums, or validation rules consumed across repos.
> If no cross-repo impact (internal logic only), state: "N/A — Internal logic only with zero external API/DTO/Enum contract changes."

| # | Modified Contract Symbol (API / Schema / DTO / Enum) | Impacted Consumer Repo | Consumer Files & Symbols | Contract Doc Updated? | Breaking / Compatible |
|---|------------------------------------------------------|------------------------|--------------------------|-----------------------|-----------------------|
| 1 | `<POST /api/v1/resource>` | `<consumer-app>` | `<resource.service.ts>` | `[x] Yes` | `<BREAKING / COMPATIBLE>` |

### 3.3 Files to touch
- `path/to/file` — <reason>

### 3.4 Legacy Behavior to Lock (Brownfield only)
- <If touching untested legacy code, list existing behavior that must be locked with a characterization test first>

### 3.5 Out of scope (YAGNI)
- <What we are explicitly NOT doing, including any excluded sibling modules>

## 4. Execution Waves (Tasks in the same wave must touch disjoint files or run in isolated worktrees)

### Wave 1 (Core & Unit/Characterization Tests)
- [ ] **T1.1:** <Implement core logic + `TC-01`, `TC-02`>
  - *Files:* `path/to/fileA`, `path/to/fileA.test`
  - *Verify:* `<VERIFY_CMD or targeted test command>`

### Wave 2 (Integration / UI / E2E Tests)
- [ ] **T2.1:** <Atomic task description>
  - *Files:* `path/to/fileB`, `path/to/fileB.test`
  - *Verify:* `<VERIFY_CMD>`
