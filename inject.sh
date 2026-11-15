#!/usr/bin/env bash
set -euo pipefail

# Inject Universal Agentic Base into any project (Greenfield or Brownfield)
# Safely coexists with existing AGENTS.md / CLAUDE.md and hides from git status via .git/info/exclude by default.
#
# Usage:
#   ./inject.sh /path/to/target-repo                       # Stealth mode (hidden via .git/info/exclude, coexists with existing AGENTS.md)
#   ./inject.sh /path/to/target-repo --upgrade             # Upgrade engine files & hooks only (preserves project.md, state.md, commit-log.md, tracking mode, custom AGENTS.md)
#   ./inject.sh /path/to/target-repo --track               # Tracked mode (commit & push .context/ and harness rules to Git; keeps .context/changes/commit-log.md ignored)
#   ./inject.sh /path/to/target-repo --upgrade --track     # Upgrade engine files & hooks AND switch to tracked mode (or --upgrade --stealth)
#   ./inject.sh /path/to/target-repo --force               # Reset harness state files including project.md & state.md (still preserves custom AGENTS.md & commit-log.md)

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-}"

usage() {
  echo "Usage: $0 <target-project-path> [--stealth | --track] [--upgrade | --force]" >&2
  exit 1
}

if [[ -z "$TARGET_DIR" || "$TARGET_DIR" == -* ]]; then
  usage
fi
shift

DO_UPGRADE=0
DO_FORCE=0
EXPLICIT_MODE=""
for arg in "$@"; do
  case "$arg" in
    stealth|--stealth)
      EXPLICIT_MODE="stealth"
      ;;
    --track)
      EXPLICIT_MODE="track"
      ;;
    --upgrade)
      DO_UPGRADE=1
      ;;
    --force)
      DO_FORCE=1
      ;;
    *)
      echo "❌ Unknown flag: $arg" >&2
      usage
      ;;
  esac
done

HAD_CONTEXT=0
if [[ -d "$TARGET_DIR/.context" ]]; then
  HAD_CONTEXT=1
fi

PRIOR_MODE=""
GIT_COMMON_DIR=""
EXCLUDE_FILE=""
if git -C "$TARGET_DIR" rev-parse --git-common-dir >/dev/null 2>&1; then
  GIT_COMMON_DIR="$(cd "$TARGET_DIR" && cd "$(git rev-parse --git-common-dir)" && pwd)"
  EXCLUDE_FILE="$GIT_COMMON_DIR/info/exclude"
  if git -C "$TARGET_DIR" ls-files --error-unmatch ".context/project.md" >/dev/null 2>&1; then
    PRIOR_MODE="track"
  elif [[ "$HAD_CONTEXT" -eq 1 && -f "$EXCLUDE_FILE" ]] && grep -qxF ".code-review-graph/" "$EXCLUDE_FILE" 2>/dev/null && ! grep -qxF ".context/" "$EXCLUDE_FILE" 2>/dev/null; then
    PRIOR_MODE="track"
  fi
fi

mkdir -p "$TARGET_DIR/.context/changes"

copy_state() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" && "$DO_FORCE" -eq 0 ]]; then
    echo "⏭️  Preserved: $dst"
  else
    cp "$src" "$dst"
    echo "✅ Installed: $dst"
  fi
}

copy_engine() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" && "$DO_UPGRADE" -eq 0 && "$DO_FORCE" -eq 0 ]]; then
    echo "⏭️  Skipped (already exists): $dst (use --upgrade to update)"
  else
    cp "$src" "$dst"
    echo "✅ Installed: $dst"
  fi
}

ensure_line_in_file() {
  local file="$1" line="$2"
  touch "$file"
  if ! grep -qxF "$line" "$file" 2>/dev/null; then
    if [[ -s "$file" ]] && [[ "$(tail -c 1 "$file" | wc -l | tr -d '[:space:]')" -eq 0 ]]; then
      printf '\n' >> "$file"
    fi
    printf '%s\n' "$line" >> "$file"
  fi
}

# Detect whether the target project has its own custom AGENTS.md / CLAUDE.md / GEMINI.md
HAS_CUSTOM_RULES=0
if [[ -f "$TARGET_DIR/GEMINI.md" ]]; then
  HAS_CUSTOM_RULES=1
elif [[ -f "$TARGET_DIR/CLAUDE.md" && ! -L "$TARGET_DIR/CLAUDE.md" ]]; then
  HAS_CUSTOM_RULES=1
elif [[ -f "$TARGET_DIR/AGENTS.md" ]] && ! head -n 1 "$TARGET_DIR/AGENTS.md" 2>/dev/null | grep -q "^# AGENTS.md — Universal Project Harness"; then
  HAS_CUSTOM_RULES=1
fi

if [[ "$HAS_CUSTOM_RULES" -eq 1 ]]; then
  RULE_REL=".agents/rules/coding-base.md"
else
  RULE_REL="AGENTS.md"
fi
RULE_BEFORE_HASH=""
if [[ -f "$TARGET_DIR/$RULE_REL" ]]; then
  RULE_BEFORE_HASH="$(cksum "$TARGET_DIR/$RULE_REL" | awk '{print $1 ":" $2}')"
fi

# 1. Install entry rules without ever clobbering custom project rules
if [[ "$HAS_CUSTOM_RULES" -eq 1 ]]; then
  echo "ℹ️  Custom AGENTS.md/CLAUDE.md/GEMINI.md detected in $TARGET_DIR."
  echo "   Installing in additive coexistence mode (.agents/, .claude/, .cursor/) so project rules stay 100% intact."
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
  copy_engine "$BASE_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.md"
  if [[ ! -e "$TARGET_DIR/CLAUDE.md" ]]; then
    ln -s AGENTS.md "$TARGET_DIR/CLAUDE.md"
    echo "🔗 Linked: $TARGET_DIR/CLAUDE.md -> AGENTS.md"
  fi
fi

RULE_AFTER_HASH="$(cksum "$TARGET_DIR/$RULE_REL" | awk '{print $1 ":" $2}')"
RULE_CHANGED=0
if [[ -n "$RULE_BEFORE_HASH" && "$RULE_BEFORE_HASH" != "$RULE_AFTER_HASH" ]]; then
  RULE_CHANGED=1
fi

# 2. Install .context/ state (preserved on --upgrade) & mechanical gatekeeper (updated on --upgrade)
CTX_GITIGNORE="$TARGET_DIR/.context/.gitignore"
ensure_line_in_file "$CTX_GITIGNORE" "changes/commit-log.md"

copy_state "$BASE_DIR/.context/project.md" "$TARGET_DIR/.context/project.md"
copy_state "$BASE_DIR/.context/state.md" "$TARGET_DIR/.context/state.md"
copy_engine "$BASE_DIR/.context/changes/_TEMPLATE.md" "$TARGET_DIR/.context/changes/_TEMPLATE.md"
copy_engine "$BASE_DIR/.context/check-blast-radius.py" "$TARGET_DIR/.context/check-blast-radius.py"
chmod +x "$TARGET_DIR/.context/check-blast-radius.py"
copy_engine "$BASE_DIR/.context/verify-gate.sh" "$TARGET_DIR/.context/verify-gate.sh"
chmod +x "$TARGET_DIR/.context/verify-gate.sh"

if [[ -n "$EXPLICIT_MODE" ]]; then
  EFFECTIVE_MODE="$EXPLICIT_MODE"
elif [[ "$DO_UPGRADE" -eq 1 || "$DO_FORCE" -eq 1 ]]; then
  EFFECTIVE_MODE="${PRIOR_MODE:-stealth}"
else
  EFFECTIVE_MODE="stealth"
fi

if [[ "$HAD_CONTEXT" -eq 1 && "$EFFECTIVE_MODE" == "track" && "$RULE_CHANGED" -eq 1 ]]; then
  TARGET_DIR="$TARGET_DIR" RULE_REL="$RULE_REL" python3 - <<'PY'
import datetime, os, subprocess
from pathlib import Path

repo = Path(os.environ["TARGET_DIR"])
rule_rel = os.environ["RULE_REL"]
log_path = repo / ".context" / "changes" / "rules-log.md"
base_res = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
base_sha = base_res.stdout.strip() if base_res.returncode == 0 and base_res.stdout.strip() else "unborn"
now_s = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
entry = f"- [{now_s}] [base: {base_sha}] {rule_rel} — Upgraded coding-base harness engine via inject.sh | Why: sync latest coding-base rules and gatekeeper | Replaces: previous coding-base version"

if log_path.is_file():
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
else:
    lines = ["# Governance Change Log (newest at top — never edit or delete older entries)"]

header = lines[0] if lines and lines[0].lstrip().startswith("#") else "# Governance Change Log (newest at top — never edit or delete older entries)"
rest = lines[1:] if (lines and lines[0].lstrip().startswith("#")) else lines
while rest and not rest[0].strip():
    rest = rest[1:]

out = [header, "", entry] + rest
log_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  echo "📝 Prepended rule upgrade entry to: $TARGET_DIR/.context/changes/rules-log.md"
fi

# 3. Git Stealth vs Tracked Mode via .git/info/exclude & native hooks via git-common-dir (supports worktrees)
if [[ -n "$GIT_COMMON_DIR" ]]; then
  mkdir -p "$(dirname "$EXCLUDE_FILE")"

  for internal_pattern in ".code-review-graph/" ".context/changes/commit-log.md"; do
    ensure_line_in_file "$EXCLUDE_FILE" "$internal_pattern"
  done

  if [[ "$EFFECTIVE_MODE" == "track" ]]; then
    EXCLUDE_FILE="$EXCLUDE_FILE" HAS_CUSTOM_RULES="$HAS_CUSTOM_RULES" python3 - <<'PY'
import os
from pathlib import Path

p = Path(os.environ["EXCLUDE_FILE"])
remove_set = {
    ".context/",
    ".context/.vault/",
    ".agents/rules/coding-base.md",
    ".claude/rules/coding-base.md",
    ".cursor/rules/coding-base.mdc",
}
if os.environ.get("HAS_CUSTOM_RULES") == "0":
    remove_set |= {"AGENTS.md", "CLAUDE.md"}
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
filtered = [ln for ln in lines if ln.strip() not in remove_set]
p.write_text(("\n".join(filtered) + "\n") if filtered else "", encoding="utf-8")
PY
    echo "📦 Tracked Mode active: .context/ & harness rules are visible to Git (commit-log.md stays ignored)."
  else
    for pattern in ".context/" ".agents/rules/coding-base.md" ".claude/rules/coding-base.md" ".cursor/rules/coding-base.mdc" "CLAUDE.local.md"; do
      ensure_line_in_file "$EXCLUDE_FILE" "$pattern"
    done
    # Only exclude untracked root AGENTS.md / CLAUDE.md if managed by harness (not custom project rules)
    if [[ "$HAS_CUSTOM_RULES" -eq 0 ]]; then
      for root_file in "AGENTS.md" "CLAUDE.md"; do
        if ! git -C "$TARGET_DIR" ls-files --error-unmatch "$root_file" >/dev/null 2>&1; then
          ensure_line_in_file "$EXCLUDE_FILE" "$root_file"
        fi
      done
    fi
    echo "👻 Stealth Mode active: Added harness paths to $EXCLUDE_FILE (invisible to 'git status' and team PRs)."
  fi

  # 4. Install/refresh coding-base Git hooks (preserving any user-owned hooks without '# coding-base-hook')
  mkdir -p "$GIT_COMMON_DIR/hooks"
  PRE_COMMIT_HOOK="$GIT_COMMON_DIR/hooks/pre-commit"
  PRE_COMMIT_OWNED=0
  if [[ ! -f "$PRE_COMMIT_HOOK" ]] || grep -q "# coding-base-hook" "$PRE_COMMIT_HOOK" 2>/dev/null; then
    PRE_COMMIT_OWNED=1
  elif [[ "$(wc -l < "$PRE_COMMIT_HOOK" | tr -d '[:space:]')" -le 5 ]] && grep -q '^[[:space:]]*\./\.context/verify-gate\.sh[[:space:]]*$' "$PRE_COMMIT_HOOK" 2>/dev/null; then
    PRE_COMMIT_OWNED=1
  fi
  if [[ "$PRE_COMMIT_OWNED" -eq 1 ]]; then
    cat > "$PRE_COMMIT_HOOK" <<'EOF'
#!/usr/bin/env bash
# coding-base-hook
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT" || exit 1
if [[ -x ".context/verify-gate.sh" ]]; then
  ./.context/verify-gate.sh
fi
EOF
    chmod +x "$PRE_COMMIT_HOOK"
    echo "🔒 Installed local Git pre-commit gatekeeper hook: $PRE_COMMIT_HOOK"
  else
    echo "⏭️  Preserved custom pre-commit hook: $PRE_COMMIT_HOOK"
  fi

  POST_COMMIT_HOOK="$GIT_COMMON_DIR/hooks/post-commit"
  if [[ ! -f "$POST_COMMIT_HOOK" ]] || grep -q "# coding-base-hook" "$POST_COMMIT_HOOK" 2>/dev/null; then
    cat > "$POST_COMMIT_HOOK" <<'EOF'
#!/usr/bin/env bash
# coding-base-hook
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT" || exit 0
[[ -d ".context/changes" ]] || exit 0

SEED_MODE="${1:-}" exec python3 - "$REPO_ROOT" <<'PY'
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(sys.argv[1])
changes_dir = repo / ".context" / "changes"
log_path = changes_dir / "commit-log.md"
seed_mode = os.environ.get("SEED_MODE", "") == "--seed"
env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k == "GIT_EXEC_PATH"}
env["GIT_TERMINAL_PROMPT"] = "0"
bt = chr(96)

HEADER = [
    "# Context Commit Log (local only, gitignored — newest at top, max 200)",
    f"> Preview diff: {bt}git diff <prev> -- <file>{bt} | Per-file rollback: {bt}git restore --worktree --source=<prev> -- <file>{bt}",
    f"> Optional milestone tag: {bt}git tag ckpt/<slug>-YYYYMMDD{bt} | Never {bt}git push --tags{bt} on shared repos",
]


def g(args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def active_context():
    st = repo / ".context" / "state.md"
    if not st.is_file():
        return ""
    rows = []
    for raw in st.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cols = [re.sub(r"^`+|`+$", "", c.strip()) for c in s.strip("|").split("|")]
        if len(cols) < 3:
            continue
        slug, lane, stage = cols[0], cols[1], cols[2]
        if (
            not slug
            or slug.lower() in ("session / task slug", "none", "-", "—")
            or slug.startswith("---")
            or slug.startswith(":---")
            or stage.upper() == "IDLE"
            or "stage" in stage.lower()
        ):
            continue
        goal = ""
        spec = changes_dir / f"{slug}.md"
        if spec.is_file() and spec.resolve().parent == changes_dir.resolve():
            for ln in spec.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^\s*[-*]\s*\*\*Goal:\*\*\s*(.+)$", ln)
                if m:
                    cand = re.sub(r"\s+", " ", m.group(1)).strip()
                    if (
                        cand
                        and not (cand.startswith("<") and cand.endswith(">"))
                        and "1-2 sentences explaining" not in cand
                    ):
                        goal = cand[:90] + ("..." if len(cand) > 90 else "")
                    break
        lbl = f"{slug} ({lane}/{stage})" if lane and stage else slug
        rows.append(f"{lbl}: {goal}" if goal else lbl)
    return "; ".join(rows).replace("|", "/")


def format_commit(rev, ctx=""):
    r = g(["log", "-1", "--format=%H%x09%h%x09%p%x09%cd%x09%s", "--date=format:%Y-%m-%d %H:%M", rev])
    if r.returncode != 0 or not r.stdout.strip():
        return None, ""
    parts = r.stdout.rstrip("\r\n").split("\t", 4)
    if len(parts) < 5:
        return None, ""
    full_sha, sha, parents, dt, subj = parts
    prev = parents.split()[0] if parents.strip() else "root"
    t_res = g(["tag", "--points-at", full_sha])
    tags = ",".join(ln.strip() for ln in t_res.stdout.splitlines() if ln.strip()) if t_res.returncode == 0 else ""
    f_res = g(["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", full_sha])
    cfiles = [ln.strip() for ln in f_res.stdout.splitlines() if ln.strip()] if f_res.returncode == 0 else []
    if len(cfiles) > 6:
        f_str = ", ".join(cfiles[:6]) + f" (+{len(cfiles) - 6} more)"
    else:
        f_str = ", ".join(cfiles)
    subj_clean = re.sub(r"\s+", " ", subj).strip().replace("|", "/")
    tag_part = f" tag:{bt}{tags}{bt}" if tags else ""
    ctx_part = f" | ctx: {ctx}" if ctx else ""
    files_part = f" | files: {f_str}" if f_str else ""
    line = f"- [{dt}] commit:{bt}{sha}{bt} prev:{bt}{prev}{bt}{tag_part} — {subj_clean}{ctx_part}{files_part}"
    return line, sha


try:
    existing_entries = []
    if log_path.is_file():
        for ln in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("- ["):
                existing_entries.append(ln)

    if seed_mode:
        revs_res = g(["rev-list", "-n", "10", "HEAD"])
        revs = [ln.strip() for ln in revs_res.stdout.splitlines() if ln.strip()] if revs_res.returncode == 0 else []
        new_entries = []
        for rv in revs:
            ln, _ = format_commit(rv, ctx="")
            if ln:
                new_entries.append(ln)
    else:
        ln, sha = format_commit("HEAD", ctx=active_context())
        if not ln:
            sys.exit(0)
        if existing_entries and f"commit:{bt}{sha}{bt}" in existing_entries[0]:
            sys.exit(0)
        new_entries = [ln] + existing_entries

    entries = new_entries[:200]
    content = "\n".join(HEADER + [""] + entries) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".commit-log-", dir=str(changes_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, str(log_path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
except Exception:
    pass
sys.exit(0)
PY
EOF
    chmod +x "$POST_COMMIT_HOOK"
    echo "📝 Installed local Git post-commit context hook: $POST_COMMIT_HOOK"
    if [[ ! -f "$TARGET_DIR/.context/changes/commit-log.md" ]] && git -C "$TARGET_DIR" rev-parse --verify -q HEAD >/dev/null 2>&1; then
      (cd "$TARGET_DIR" && "$POST_COMMIT_HOOK" --seed) || true
    fi
  else
    echo "⏭️  Preserved custom post-commit hook: $POST_COMMIT_HOOK"
  fi
fi

echo ""
echo "🎯 Universal Base injected into: $TARGET_DIR (mode: $EFFECTIVE_MODE)"
