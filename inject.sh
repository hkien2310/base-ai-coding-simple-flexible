#!/usr/bin/env bash
set -euo pipefail

# Inject Universal Project Harness into any repo or folder (Code, Bots/CLI, Content).
# Usage: ./inject.sh <target-path> [--stealth | --track] [--upgrade | --force]

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-}"
usage() { echo "Usage: $0 <target-path> [--stealth | --track] [--upgrade | --force]" >&2; exit 1; }
[[ -z "$TARGET_DIR" || "$TARGET_DIR" == -* ]] && usage
shift

DO_UPGRADE=0; DO_FORCE=0; EXPLICIT_MODE=""
for arg in "$@"; do
  case "$arg" in
    stealth|--stealth) EXPLICIT_MODE="stealth" ;;
    --track) EXPLICIT_MODE="track" ;;
    --upgrade) DO_UPGRADE=1 ;;
    --force) DO_FORCE=1 ;;
    *) echo "❌ Unknown flag: $arg" >&2; usage ;;
  esac
done

HAD_CONTEXT=0; [[ -d "$TARGET_DIR/.context" ]] && HAD_CONTEXT=1
PRIOR_MODE=""; GIT_COMMON_DIR=""; EXCLUDE_FILE=""
if git -C "$TARGET_DIR" rev-parse --git-common-dir >/dev/null 2>&1; then
  GIT_COMMON_DIR="$(cd "$TARGET_DIR" && cd "$(git rev-parse --git-common-dir)" && pwd)"
  EXCLUDE_FILE="$GIT_COMMON_DIR/info/exclude"
  if git -C "$TARGET_DIR" ls-files --error-unmatch ".context/project.md" >/dev/null 2>&1; then
    PRIOR_MODE="track"
  elif [[ "$HAD_CONTEXT" -eq 1 && -f "$EXCLUDE_FILE" ]] && grep -qxF ".code-review-graph/" "$EXCLUDE_FILE" 2>/dev/null && ! grep -qxF ".context/" "$EXCLUDE_FILE" 2>/dev/null; then
    PRIOR_MODE="track"
  fi
fi

mkdir -p "$TARGET_DIR/.context"
copy_state() {
  if [[ -f "$2" && "$DO_FORCE" -eq 0 ]]; then echo "⏭️  Preserved: $2"
  else cp "$1" "$2"; echo "✅ Installed: $2"; fi
}
copy_engine() {
  if [[ -f "$2" && "$DO_UPGRADE" -eq 0 && "$DO_FORCE" -eq 0 ]]; then
    echo "⏭️  Skipped (already exists): $2 (use --upgrade to update)"
  else cp "$1" "$2"; echo "✅ Installed: $2"; fi
}

HAS_CUSTOM_RULES=0
if [[ -f "$TARGET_DIR/GEMINI.md" || ( -f "$TARGET_DIR/CLAUDE.md" && ! -L "$TARGET_DIR/CLAUDE.md" ) ]]; then
  HAS_CUSTOM_RULES=1
elif [[ -f "$TARGET_DIR/AGENTS.md" ]] && ! head -n 1 "$TARGET_DIR/AGENTS.md" 2>/dev/null | grep -q "^# AGENTS.md — Universal Project Harness"; then
  HAS_CUSTOM_RULES=1
fi

RULE_REL="AGENTS.md"; [[ "$HAS_CUSTOM_RULES" -eq 1 ]] && RULE_REL=".agents/rules/coding-base.md"
RULE_SNAP=""; trap '[[ -n "$RULE_SNAP" ]] && rm -f "$RULE_SNAP"' EXIT
if [[ -f "$TARGET_DIR/$RULE_REL" ]]; then RULE_SNAP="$(mktemp)"; cp "$TARGET_DIR/$RULE_REL" "$RULE_SNAP"; fi

if [[ "$HAS_CUSTOM_RULES" -eq 1 ]]; then
  echo "ℹ️  Custom rules detected in $TARGET_DIR — installing additively (.agents/, .claude/, .cursor/)."
  mkdir -p "$TARGET_DIR/.agents/rules" "$TARGET_DIR/.claude/rules" "$TARGET_DIR/.cursor/rules"
  { printf -- "---\ntrigger: always_on\ndescription: Universal Project Harness\nalwaysApply: true\n---\n\n"; cat "$BASE_DIR/AGENTS.md"; } > "$TARGET_DIR/.agents/rules/coding-base.md"
  ln -sf "../../.agents/rules/coding-base.md" "$TARGET_DIR/.claude/rules/coding-base.md"
  ln -sf "../../.agents/rules/coding-base.md" "$TARGET_DIR/.cursor/rules/coding-base.mdc"
  echo "✅ Installed additive rule (AGY/Claude/Cursor): $TARGET_DIR/.agents/rules/coding-base.md"
else
  copy_engine "$BASE_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.md"
  [[ ! -e "$TARGET_DIR/CLAUDE.md" ]] && { ln -s AGENTS.md "$TARGET_DIR/CLAUDE.md"; echo "🔗 Linked: $TARGET_DIR/CLAUDE.md -> AGENTS.md"; }
fi

RULE_CHANGED=0
[[ -n "$RULE_SNAP" ]] && ! cmp -s "$RULE_SNAP" "$TARGET_DIR/$RULE_REL" && RULE_CHANGED=1

rm -f "$TARGET_DIR/.context/changes/commit-log.md" "$TARGET_DIR/.context/changes/_TEMPLATE.md" "$TARGET_DIR/.context/check-blast-radius.py" "$TARGET_DIR/.context/checkpoint.sh"
rm -rf "$TARGET_DIR/.context/__pycache__"

copy_state "$BASE_DIR/.context/project.md" "$TARGET_DIR/.context/project.md"
copy_state "$BASE_DIR/.context/state.md" "$TARGET_DIR/.context/state.md"
copy_engine "$BASE_DIR/.context/verify-gate.sh" "$TARGET_DIR/.context/verify-gate.sh"
chmod +x "$TARGET_DIR/.context/verify-gate.sh"

if [[ -n "$EXPLICIT_MODE" ]]; then EFFECTIVE_MODE="$EXPLICIT_MODE"
elif [[ "$DO_UPGRADE" -eq 1 || "$DO_FORCE" -eq 1 ]]; then EFFECTIVE_MODE="${PRIOR_MODE:-stealth}"
else EFFECTIVE_MODE="stealth"; fi

TARGET_DIR="$TARGET_DIR" EXCLUDE_FILE="$EXCLUDE_FILE" EFFECTIVE_MODE="$EFFECTIVE_MODE" \
HAS_CUSTOM_RULES="$HAS_CUSTOM_RULES" HAD_CONTEXT="$HAD_CONTEXT" RULE_REL="$RULE_REL" \
RULE_CHANGED="$RULE_CHANGED" DO_FORCE="$DO_FORCE" python3 - <<'PY'
import datetime, os, re, subprocess
from pathlib import Path

repo = Path(os.environ["TARGET_DIR"])
mode = os.environ["EFFECTIVE_MODE"]
has_custom = os.environ["HAS_CUSTOM_RULES"] == "1"
bt = chr(96)

# 1. Clean obsolete .context/.gitignore
cg = repo / ".context" / ".gitignore"
if cg.is_file():
    kept = [ln for ln in cg.read_text("utf-8", "replace").splitlines() if ln.strip() not in {"changes/commit-log.md", ".vault/", ".vault", "__pycache__/"}]
    if any(ln.strip() for ln in kept):
        cg.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        cg.unlink()

# 2. Migrate legacy .context/changes/ & scrub preserved project.md / state.md
dec_path = repo / ".context" / "decisions.md"
old_dir = repo / ".context" / "changes"
old_log = old_dir / "rules-log.md"
if old_log.is_file():
    if not dec_path.is_file():
        old_log.rename(dec_path)
        print(f"📦 Migrated: {old_log} -> {dec_path}")
    else:
        old_log.unlink()
if old_dir.is_dir():
    for item in list(old_dir.iterdir()):
        if item.is_file() and item.suffix == ".md":
            plans_dir = repo / ".context" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            dst = plans_dir / item.name
            if not dst.exists():
                item.rename(dst)
                print(f"📦 Moved active plan: {item} -> {dst}")
    if not any(old_dir.iterdir()):
        old_dir.rmdir()

def scrub_paths(txt):
    t = txt.replace(".context/changes/rules-log.md", ".context/decisions.md")
    t = t.replace("rules-log.md", "decisions.md")
    return t.replace(".context/changes/", ".context/plans/")

proj = repo / ".context" / "project.md"
proj_changed = False
if os.environ["DO_FORCE"] == "0" and proj.is_file():
    old_txt = proj.read_text("utf-8", "replace")
    if any(k in old_txt for k in ("check-blast-radius.py", "_TEMPLATE.md", "rules-log.md", ".context/changes")):
        out = []
        for ln in old_txt.splitlines():
            s = ln
            if "check-blast-radius.py" in ln or "_TEMPLATE.md" in ln:
                if re.match(r"^\s*[-*]\s+\*\*Targeted Test.*check-blast-radius\.py", ln) or re.match(rf"^\s*[-*]\s+[*`]*[^:]+[*`]*:\s*{bt}python3\s+(?:\./)?\.context/check-blast-radius\.py[^`]*{bt}\s*$", ln):
                    continue
                s = re.sub(r"\s*&&\s*python3\s+-m\s+py_compile\s+(?:\./)?\.context/check-blast-radius\.py\b", "", s)
                s = re.sub(r"\bpython3\s+-m\s+py_compile\s+(?:\./)?\.context/check-blast-radius\.py\s*&&\s*", "", s)
                s = re.sub(r"\bpython3\s+-m\s+py_compile\s+(?:\./)?\.context/check-blast-radius\.py\b", "bash -n .context/verify-gate.sh", s)
                s = re.sub(r"\s*&&\s*python3\s+(?:\./)?\.context/check-blast-radius\.py(?:\s+--[\w-]+(?:\s+(?:<[^>]+>|[^\s`&]+))?)*", "", s)
                s = re.sub(r"\bpython3\s+(?:\./)?\.context/check-blast-radius\.py(?:\s+--[\w-]+(?:\s+(?:<[^>]+>|[^\s`&]+))?)*\s*&&\s*", "", s)
                s = re.sub(r"\bpython3\s+(?:\./)?\.context/check-blast-radius\.py(?:\s+--[\w-]+(?:\s+(?:<[^>]+>|[^\s`&;]+))?)*", "git grep", s)
                s = re.sub(r"(?:\./)?\.context/check-blast-radius\.py|check-blast-radius\.py", "git grep", s)
                s = re.sub(r"(?:\./)?\.context/changes/_TEMPLATE\.md|_TEMPLATE\.md", "plan checklist", s)
            s = scrub_paths(s)
            if s.strip():
                out.append(s)
        new_txt = "\n".join(out) + "\n"
        if new_txt != old_txt:
            proj.write_text(new_txt, encoding="utf-8")
            proj_changed = True
            print(f"🧹 Scrubbed legacy harness references from: {proj}")

st = repo / ".context" / "state.md"
if os.environ["DO_FORCE"] == "0" and st.is_file():
    old_st = st.read_text("utf-8", "replace")
    new_st = scrub_paths(old_st)
    if new_st != old_st:
        st.write_text(new_st, encoding="utf-8")

# 3. Initialize / update .context/decisions.md
header_default = "# Decisions & Governance Log (Single-File ADR — newest at top, never edit/delete older entries)"
if not dec_path.is_file():
    dec_path.write_text(header_default + "\n", encoding="utf-8")
    print(f"✅ Initialized: {dec_path}")

if os.environ["HAD_CONTEXT"] == "1" and mode == "track" and (os.environ["RULE_CHANGED"] == "1" or proj_changed):
    base_res = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
    base_sha = base_res.stdout.strip() or "unborn" if base_res.returncode == 0 else "unborn"
    targets = ([os.environ["RULE_REL"]] if os.environ["RULE_CHANGED"] == "1" else []) + ([".context/project.md"] if proj_changed else [])
    head_lines = set()
    if base_sha != "unborn":
        hr = subprocess.run(["git", "-C", str(repo), "show", "HEAD:.context/decisions.md"], capture_output=True, text=True, check=False)
        if hr.returncode != 0:
            hr = subprocess.run(["git", "-C", str(repo), "show", "HEAD:.context/changes/rules-log.md"], capture_output=True, text=True, check=False)
        if hr.returncode == 0:
            head_lines = set(hr.stdout.splitlines())
    lines = dec_path.read_text("utf-8", "replace").splitlines()
    header = lines[0] if lines and lines[0].lstrip().startswith("#") else header_default
    rest = lines[1:] if (lines and lines[0].lstrip().startswith("#")) else lines
    while rest and not rest[0].strip():
        rest = rest[1:]
    suffix = " — Upgraded coding-base harness engine via inject.sh"
    if rest and rest[0] not in head_lines and f"[base: {base_sha}] " in rest[0] and suffix in rest[0]:
        if m := re.search(rf"\[base:\s*{re.escape(base_sha)}\]\s+(.+?)\s+—\s+Upgraded coding-base harness engine via inject\.sh", rest[0]):
            targets = list(dict.fromkeys([x.strip() for x in m.group(1).split(",") if x.strip()] + targets))
        rest = rest[1:]
    now_s = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{now_s}] [base: {base_sha}] {', '.join(targets)}{suffix} | Why: sync latest coding-base harness | Rejected/Replaces: previous coding-base version"
    dec_path.write_text("\n".join([header, "", entry] + rest) + "\n", encoding="utf-8")
    print(f"📝 Prepended governance upgrade entry to: {dec_path}")

# 4. Sync .git/info/exclude
excl_raw = os.environ.get("EXCLUDE_FILE", "").strip()
if excl_raw:
    excl = Path(excl_raw)
    excl.parent.mkdir(parents=True, exist_ok=True)
    remove = {".context/.vault/", ".context/changes/commit-log.md"}
    if mode == "track":
        remove |= {".context/", ".agents/rules/coding-base.md", ".claude/rules/coding-base.md", ".cursor/rules/coding-base.mdc"}
        if not has_custom:
            remove |= {"AGENTS.md", "CLAUDE.md"}
    cur = [ln for ln in (excl.read_text("utf-8", "replace").splitlines() if excl.is_file() else []) if ln.strip() not in remove]
    add = [".code-review-graph/"]
    if mode == "stealth":
        add += [".context/", ".agents/rules/coding-base.md", ".claude/rules/coding-base.md", ".cursor/rules/coding-base.mdc", "CLAUDE.local.md"]
        if not has_custom:
            for rf in ("AGENTS.md", "CLAUDE.md"):
                if subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rf], capture_output=True).returncode != 0:
                    add.append(rf)
    existing = {ln.strip() for ln in cur}
    for pat in add:
        if pat not in existing:
            cur.append(pat)
            existing.add(pat)
    excl.write_text(("\n".join(cur) + "\n") if cur else "", encoding="utf-8")
    print("📦 Tracked Mode active (.code-review-graph/ stays ignored)." if mode == "track" else f"👻 Stealth Mode active: Added harness paths to {excl}.")
PY

if [[ -n "$GIT_COMMON_DIR" ]]; then
  mkdir -p "$GIT_COMMON_DIR/hooks"
  PRE="$GIT_COMMON_DIR/hooks/pre-commit"; OWNED=0
  if [[ ! -f "$PRE" ]] || grep -q "# coding-base-hook" "$PRE" 2>/dev/null; then OWNED=1
  elif [[ "$(wc -l < "$PRE" | tr -d '[:space:]')" -le 5 ]] && grep -q '^[[:space:]]*\./\.context/verify-gate\.sh[[:space:]]*$' "$PRE" 2>/dev/null; then OWNED=1; fi
  if [[ "$OWNED" -eq 1 ]]; then
    cat > "$PRE" <<'EOF'
#!/usr/bin/env bash
# coding-base-hook
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT" || exit 1
if [[ -x ".context/verify-gate.sh" ]]; then
  VERIFY_STAGED=1 ./.context/verify-gate.sh
fi
EOF
    chmod +x "$PRE"
    echo "🔒 Installed local Git pre-commit hook (VERIFY_STAGED=1): $PRE"
  else
    echo "⏭️  Preserved custom pre-commit hook: $PRE"
  fi
  POST="$GIT_COMMON_DIR/hooks/post-commit"
  [[ -f "$POST" ]] && grep -q "# coding-base-hook" "$POST" 2>/dev/null && { rm -f "$POST"; echo "🧹 Removed legacy post-commit hook: $POST"; }
fi

echo ""
echo "🎯 Universal Base injected into: $TARGET_DIR (mode: $EFFECTIVE_MODE)"
