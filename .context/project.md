# Project Context — Universal Project Harness (`coding-base`)
STATUS: READY

## Stack, Structure & Rules
- **Domain & Stack:** Bash + Python 3 stdlib universal AI project harness & 3-step gatekeeper (zero external dependencies)
- **Key Paths & Flow:** `AGENTS.md` (`CLAUDE.md` symlink), `inject.sh` (installer/upgrader with embedded blank templates), `.context/verify-gate.sh` (3-step gatekeeper), `tests/test_harness.py` (`T1`–`T10` E2E suite)
- **CROSS_REPO_CONSUMERS:** `NQI`, `NQI-Admin`, `nqi-be` (`--stealth`); `coslient-free`, `kilen`, `lyra-vance`, `cute-life`, `surreal-for-mind` (`--track`)
- **GOVERNANCE_DOCS:** `README.md, inject.sh, .context/verify-gate.sh`

## Verification
- **VERIFY_CMD:** `bash -n inject.sh .context/verify-gate.sh && python3 tests/test_harness.py`
- **Live / Manual Check:** Run `./inject.sh <repo> --upgrade` on downstream repos only when `AGENTS.md` or `.context/verify-gate.sh` changes

## Error Memory & Red Lines
- Blank `project.md` and `state.md` templates live inside `inject.sh` (`write_state`) — never copy `coding-base/.context/{project,state}.md` into target repos.
- Always update `.context/decisions.md` **last** after editing `AGENTS.md`, `.context/project.md`, or `GOVERNANCE_DOCS` so its `mtime` is newest.
- Never stage untracked `.agents/` scratch directory; `git add` explicit file paths only and preserve `CLAUDE.md -> AGENTS.md` symlink.
