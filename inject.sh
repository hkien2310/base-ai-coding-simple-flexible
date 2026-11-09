#!/usr/bin/env bash
set -euo pipefail

# Inject Universal Agentic Base into any project (Greenfield or Brownfield)
# Safely coexists with existing AGENTS.md / CLAUDE.md and hides from git status via .git/info/exclude by default.
#
# Usage:
#   ./inject.sh /path/to/target-repo             # Stealth mode (hidden via .git/info/exclude, coexists with existing AGENTS.md)
#   ./inject.sh /path/to/target-repo --track     # Tracked mode (for your own repos where you want to commit the harness to git)
#   ./inject.sh /path/to/target-repo --force     # Overwrite existingcoding-base files

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-}"
MODE="${2:-stealth}"

if [[ -z "$TARGET_DIR" ]]; then
  echo "Usage: $0 <target-project-path> [--stealth (default) | --track | --force]"
  exit 1
fi

mkdir -p "$TARGET_DIR/.context/changes"

copy_safe() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" && "$MODE" != "--force" ]]; then
    echo "⏭️  Skipped (already exists): $dst (use --force to overwrite)"
  else
    cp "$src" "$dst"
    echo "✅ Installed: $dst"
  fi
}

# 1. Handle AGENTS.md / CLAUDE.md without clobbering existing project rules
if [[ -f "$TARGET_DIR/AGENTS.md" || -f "$TARGET_DIR/CLAUDE.md" || -f "$TARGET_DIR/GEMINI.md" ]] && [[ "$MODE" != "--force" ]]; then
  echo "ℹ️  Existing AGENTS.md/CLAUDE.md/GEMINI.md detected in $TARGET_DIR."
  echo "   Installing in additive coexistence mode (.agents/, .claude/, .cursor/) so existing project rules stay 100% intact."
  mkdir -p "$TARGET_DIR/.agents/rules" "$TARGET_DIR/.claude/rules" "$TARGET_DIR/.cursor/rules"
  {
    echo "---"
    echo "trigger: always_on"
    echo "description: Universal Project Harness (2-Lane Router, Spec-to-Test Contract, Mechanical Gatekeeper)"
    echo "alwaysApply: true"
    echo "---"
    echo ""
    cat "$BASE_DIR/AGENTS.md"
  } > "$TARGET_DIR/.agents/rules/coding-base.md"
  ln -sf "../../.agents/rules/coding-base.md" "$TARGET_DIR/.claude/rules/coding-base.md"
  ln -sf "../../.agents/rules/coding-base.md" "$TARGET_DIR/.cursor/rules/coding-base.mdc"
  echo "✅ Installed additive rule (AGY/Claude/Cursor): $TARGET_DIR/.agents/rules/coding-base.md"
else
  copy_safe "$BASE_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.md"
  if [[ ! -e "$TARGET_DIR/CLAUDE.md" ]]; then
    ln -s AGENTS.md "$TARGET_DIR/CLAUDE.md"
    echo "🔗 Linked: $TARGET_DIR/CLAUDE.md -> AGENTS.md"
  fi
fi

# 2. Install .context/ state & mechanical gatekeeper
copy_safe "$BASE_DIR/.context/project.md" "$TARGET_DIR/.context/project.md"
copy_safe "$BASE_DIR/.context/state.md" "$TARGET_DIR/.context/state.md"
copy_safe "$BASE_DIR/.context/changes/_TEMPLATE.md" "$TARGET_DIR/.context/changes/_TEMPLATE.md"
copy_safe "$BASE_DIR/.context/check-blast-radius.py" "$TARGET_DIR/.context/check-blast-radius.py"
chmod +x "$TARGET_DIR/.context/check-blast-radius.py"
copy_safe "$BASE_DIR/.context/verify-gate.sh" "$TARGET_DIR/.context/verify-gate.sh"
chmod +x "$TARGET_DIR/.context/verify-gate.sh"

# 3. Git Stealth Mode (default): hide harness files in .git/info/exclude (supports both standard repos and git worktrees)
if git -C "$TARGET_DIR" rev-parse --git-common-dir >/dev/null 2>&1 && [[ "$MODE" != "--track" ]]; then
  GIT_COMMON_DIR="$(cd "$TARGET_DIR" && cd "$(git rev-parse --git-common-dir)" && pwd)"
  EXCLUDE_FILE="$GIT_COMMON_DIR/info/exclude"
  mkdir -p "$(dirname "$EXCLUDE_FILE")"
  touch "$EXCLUDE_FILE"
  for pattern in ".context/" ".code-review-graph/" ".agents/rules/coding-base.md" ".claude/rules/coding-base.md" ".cursor/rules/coding-base.mdc" "CLAUDE.local.md"; do
    if ! grep -qxF "$pattern" "$EXCLUDE_FILE" 2>/dev/null; then
      echo "$pattern" >> "$EXCLUDE_FILE"
    fi
  done
  # Only exclude root AGENTS.md / CLAUDE.md if they are not already tracked by git
  for root_file in "AGENTS.md" "CLAUDE.md"; do
    if ! git -C "$TARGET_DIR" ls-files --error-unmatch "$root_file" >/dev/null 2>&1; then
      if ! grep -qxF "$root_file" "$EXCLUDE_FILE" 2>/dev/null; then
        echo "$root_file" >> "$EXCLUDE_FILE"
      fi
    fi
  done
  echo "👻 Stealth Mode active: Added harness paths to $EXCLUDE_FILE (invisible to 'git status' and team PRs)."
fi

# 4. Install non-destructive git pre-commit hook if .git exists
if [[ -d "$TARGET_DIR/.git/hooks" && ! -f "$TARGET_DIR/.git/hooks/pre-commit" ]]; then
  cat > "$TARGET_DIR/.git/hooks/pre-commit" <<'EOF'
#!/usr/bin/env bash
if [[ -x ".context/verify-gate.sh" ]]; then
  ./.context/verify-gate.sh
fi
EOF
  chmod +x "$TARGET_DIR/.git/hooks/pre-commit"
  echo "🔒 Installed local Git pre-commit gatekeeper hook: $TARGET_DIR/.git/hooks/pre-commit"
fi

echo ""
echo "🎯 Universal Base injected into: $TARGET_DIR"
