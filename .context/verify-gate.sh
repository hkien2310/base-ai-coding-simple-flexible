#!/usr/bin/env bash
set -euo pipefail

# Mechanical Quality & Anti-Cheat Gatekeeper for AI Coding Agents
# Blocks fake tests, skipped tests, un-updated callers, and broken builds.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

echo "🔍 [1/4] Checking Git Diff for AI Test-Cheating Patterns..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  TEST_DIFF=$(git diff HEAD --unified=0 -- '*test*' '*spec*' '*Test*' 2>/dev/null | grep -E '^\+[^+]' || true)
  if [[ -n "$TEST_DIFF" ]]; then
    if echo "$TEST_DIFF" | grep -E '(\.(skip|only)\s*\(|@(Disabled|Ignore)|pytest\.mark\.(skip|xfail)|catch\s*\([^)]*\)\s*\{\s*\})' >/dev/null; then
      echo -e "${RED}❌ [FATAL] Banned test-cheating pattern detected in test diff (.skip, .only, @Disabled, or empty catch{}):${NC}"
      echo "$TEST_DIFF" | grep -E '(\.(skip|only)\s*\(|@(Disabled|Ignore)|pytest\.mark\.(skip|xfail)|catch\s*\([^)]*\)\s*\{\s*\})'
      FAILED=1
    fi
  fi

  DELETED_ASSERTS=$(git diff HEAD --unified=0 -- '*test*' '*spec*' '*Test*' 2>/dev/null | grep -E '^\-[^-].*(expect\(|assert|should|verify\()' || true)
  if [[ -n "$DELETED_ASSERTS" ]]; then
    echo -e "${YELLOW}⚠️  [HIGH RISK] Existing test assertions were modified or deleted:${NC}"
    echo "$DELETED_ASSERTS"
    echo -e "${YELLOW}👉 Verify this is explicitly authorized under MODIFIED/REMOVED in the active Spec.${NC}"
  fi
fi

echo "🔍 [2/4] Checking Mechanical Blast-Radius & Caller Integrity..."
if [[ -f ".context/check-blast-radius.py" ]]; then
  if ! python3 .context/check-blast-radius.py --mode gate; then
    echo -e "${RED}❌ [FATAL] Mechanical blast-radius check failed! Un-updated callers or missing test updates detected.${NC}"
    FAILED=1
  fi
fi

echo "🔍 [3/4] Checking Spec-to-Test Contract Traceability..."
TARGET_SPECS=()
if [[ -n "${VERIFY_SPEC:-}" ]]; then
  if [[ "$VERIFY_SPEC" != "None" && -f ".context/changes/${VERIFY_SPEC}.md" ]]; then
    TARGET_SPECS+=(".context/changes/${VERIFY_SPEC}.md")
  fi
elif [[ -d ".context/changes" ]]; then
  MODIFIED_FILES=""
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    MODIFIED_FILES=$(git diff HEAD --name-only 2>/dev/null || true)
  fi
  for spec in .context/changes/*.md; do
    [[ ! -f "$spec" || "$(basename "$spec")" == "_TEMPLATE.md" ]] && continue
    if grep -E '^\- \*\*Status:\*\* *(APPROVED|IN_PROGRESS)' "$spec" >/dev/null 2>&1; then
      if [[ -n "$MODIFIED_FILES" ]]; then
        for mf in $MODIFIED_FILES; do
          if grep -F "$(basename "$mf")" "$spec" >/dev/null 2>&1; then
            TARGET_SPECS+=("$spec")
            break
          fi
        done
      fi
    fi
  done
fi

for SPEC_FILE in "${TARGET_SPECS[@]:-}"; do
  [[ -z "$SPEC_FILE" ]] && continue
  if grep -E '^\| *`?TC-[0-9]+`? *\|.*(\buntested\b|\bfail\b|\bTBD\b)' "$SPEC_FILE" >/dev/null; then
    echo -e "${RED}❌ [FATAL] Active Spec ($SPEC_FILE) still has unverified or TBD test cases:${NC}"
    grep -E '^\| *`?TC-[0-9]+`? *\|.*(\buntested\b|\bfail\b|\bTBD\b)' "$SPEC_FILE"
    FAILED=1
  else
    echo -e "${GREEN}✅ All TC-xx rows in $SPEC_FILE are mapped and marked pass.${NC}"
  fi
done

echo "🔍 [4/4] Running Project VERIFY_CMD from .context/project.md..."
if [[ -f ".context/project.md" ]]; then
  VERIFY_CMD=$(grep 'VERIFY_CMD' .context/project.md | head -n 1 | awk -F'`' '{print $(NF-1)}' || true)
  if [[ -z "$VERIFY_CMD" || "$VERIFY_CMD" == "TBD" ]]; then
    echo -e "${RED}❌ [FATAL] VERIFY_CMD is still 'TBD' in .context/project.md. Run Mode 0 (Onboard/Bootstrap) first.${NC}"
    FAILED=1
  else
    echo "▶ Executing: $VERIFY_CMD"
    if ! eval "$VERIFY_CMD"; then
      echo -e "${RED}❌ [FATAL] Project VERIFY_CMD failed!${NC}"
      FAILED=1
    fi
  fi
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo -e "\n${RED}⛔ GATEKEEPER BLOCKED COMPLETION. Fix all [FATAL] issues above before reporting done.${NC}"
  exit 1
fi

echo -e "\n${GREEN}✅ GATEKEEPER PASSED.${NC}"
