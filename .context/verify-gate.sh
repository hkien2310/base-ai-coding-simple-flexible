#!/usr/bin/env bash
set -euo pipefail

# 3-Step Mechanical Quality & Anti-Cheat Gatekeeper
# Checks diff/untracked tests & active plans, governance log sync, and project VERIFY_CMD.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

IS_GIT=0
HAS_HEAD=0
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  IS_GIT=1
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    HAS_HEAD=1
  fi
fi

SCOPED_FILES=""
if [[ "$IS_GIT" -eq 1 ]]; then
  RAW_CHANGED=$(
    {
      if [[ "$HAS_HEAD" -eq 1 ]]; then
        git diff HEAD --name-only 2>/dev/null || true
      else
        git diff --name-only 2>/dev/null || true
        git diff --cached --name-only 2>/dev/null || true
      fi
      git ls-files --others --exclude-standard 2>/dev/null || true
    } | awk 'NF' | sort -u
  )
  if [[ -n "${VERIFY_FILES:-}" ]]; then
    SCOPED_FILES=$(RAW_CHANGED="$RAW_CHANGED" python3 - <<'PY'
import os, re
raw = [ln.strip() for ln in os.environ.get("RAW_CHANGED", "").splitlines() if ln.strip()]
scoped = {re.sub(r"^\./+", "", f.strip()) for f in re.split(r"[\s,]+", os.environ.get("VERIFY_FILES", "").strip()) if f.strip()}
print("\n".join(f for f in raw if f in scoped))
PY
)
  else
    SCOPED_FILES="$RAW_CHANGED"
  fi
fi

echo "🔍 [1/3] Checking Tests & Active Plan Integrity..."
if [[ "$IS_GIT" -eq 1 && -n "$SCOPED_FILES" ]]; then
  if ! SCOPED_FILES="$SCOPED_FILES" HAS_HEAD="$HAS_HEAD" RED="$RED" YELLOW="$YELLOW" NC="$NC" python3 - <<'PY'
import os, re, subprocess, sys

RED = os.environ["RED"]
YELLOW = os.environ["YELLOW"]
NC = os.environ["NC"]
has_head = os.environ.get("HAS_HEAD") == "1"
files = [ln.strip() for ln in os.environ.get("SCOPED_FILES", "").splitlines() if ln.strip()]

NON_CODE_EXTS = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
    ".lock", ".csv", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf",
}
CHEAT_RE = re.compile(r"(\.(skip|only)\s*\(|@(Disabled|Ignore)\b|pytest\.mark\.(skip|xfail)|catch\s*\([^)]*\)\s*\{\s*\})")
ASSERT_RE = re.compile(r"(expect\(|assert|should|verify\()")

def git_out(args):
    res = subprocess.run(["git"] + args, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout

fatal_hits = []
deleted_asserts = []

for rel_path in files:
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in NON_CODE_EXTS:
        continue
    low = rel_path.lower()
    if "test" not in low and "spec" not in low:
        continue

    rc, _ = git_out(["ls-files", "--error-unmatch", "--", rel_path])
    is_tracked = (rc == 0)

    if is_tracked:
        if has_head:
            _, diff_text = git_out(["diff", "HEAD", "--unified=0", "--", rel_path])
        else:
            _, d1 = git_out(["diff", "--unified=0", "--", rel_path])
            _, d2 = git_out(["diff", "--cached", "--unified=0", "--", rel_path])
            diff_text = d1 + "\n" + d2
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if CHEAT_RE.search(content):
                    fatal_hits.append((rel_path, "tracked diff", content.strip()))
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:]
                if ASSERT_RE.search(content):
                    deleted_asserts.append((rel_path, content.strip()))
    elif os.path.isfile(rel_path):
        try:
            with open(rel_path, "r", encoding="utf-8", errors="replace") as f:
                for idx, ln in enumerate(f, 1):
                    if CHEAT_RE.search(ln):
                        fatal_hits.append((rel_path, f"untracked line {idx}", ln.strip()))
        except OSError:
            pass

if deleted_asserts:
    print(f"{YELLOW}⚠️  [HIGH RISK] Existing test assertions were modified or deleted:{NC}")
    for path, snippet in deleted_asserts[:10]:
        print(f"   - {path}: {snippet}")
    print(f"{YELLOW}👉 Verify this is explicitly authorized under MODIFIED/REMOVED in the active Spec.{NC}")

if fatal_hits:
    print(f"{RED}❌ [FATAL] Banned test-cheating pattern detected (.skip, .only, @Disabled, or empty catch{{}}):{NC}")
    for path, loc, snippet in fatal_hits[:10]:
        print(f"   ❌ {path} ({loc}): {snippet}")
    sys.exit(1)
PY
  then
    FAILED=1
  fi
fi

if ! SCOPED_FILES="$SCOPED_FILES" VERIFY_SPEC="${VERIFY_SPEC:-}" RED="$RED" GREEN="$GREEN" NC="$NC" python3 - <<'PY'
import glob, os, re, sys

RED = os.environ["RED"]
GREEN = os.environ["GREEN"]
NC = os.environ["NC"]
verify_spec = os.environ.get("VERIFY_SPEC", "").strip()
scoped_files = [ln.strip() for ln in os.environ.get("SCOPED_FILES", "").splitlines() if ln.strip()]

target_specs = []
if verify_spec:
    if verify_spec != "None":
        candidate = f".context/changes/{verify_spec}.md"
        if os.path.isfile(candidate):
            target_specs.append(candidate)
elif os.path.isdir(".context/changes") and scoped_files:
    basenames = {os.path.basename(f) for f in scoped_files}
    status_re = re.compile(r"^(?:[-*]\s+)?[*`]*Status[*`]*:\**\s*(APPROVED|IN_PROGRESS)\b", re.MULTILINE)
    for spec in sorted(glob.glob(".context/changes/*.md")):
        base = os.path.basename(spec)
        if base in ("_TEMPLATE.md", "rules-log.md"):
            continue
        try:
            with open(spec, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        if status_re.search(content) and any(bn in content for bn in basenames):
            target_specs.append(spec)

bt = chr(96)
tc_fail_re = re.compile(rf"^\| *{bt}?TC-[0-9]+{bt}? *\|.*(\buntested\b|\bfail\b|\bTBD\b)")
unchecked_re = re.compile(r"^\s*[-*]\s*\[\s\]\s+")
spec_failed = False
for spec in target_specs:
    try:
        with open(spec, "r", encoding="utf-8", errors="replace") as f:
            bad_rows = [ln.rstrip() for ln in f if tc_fail_re.match(ln) or unchecked_re.match(ln)]
    except OSError:
        continue
    if bad_rows:
        print(f"{RED}❌ [FATAL] Active Plan ({spec}) still has incomplete items or TBD test cases:{NC}")
        for row in bad_rows:
            print(f"   {row}")
        spec_failed = True
    else:
        print(f"{GREEN}✅ Active Plan ({spec}) has zero incomplete items.{NC}")

if spec_failed:
    sys.exit(1)
PY
then
  FAILED=1
fi

echo "🔍 [2/3] Checking Governance Change Log (rules-log.md) Sync..."
if [[ "$IS_GIT" -eq 1 && -n "$SCOPED_FILES" ]]; then
  if ! SCOPED_FILES="$SCOPED_FILES" HAS_HEAD="$HAS_HEAD" RED="$RED" NC="$NC" python3 - <<'PY'
import datetime, fnmatch, os, re, subprocess, sys

RED = os.environ["RED"]
NC = os.environ["NC"]
has_head = os.environ.get("HAS_HEAD") == "1"
files = [re.sub(r"^\./+", "", ln.strip()) for ln in os.environ.get("SCOPED_FILES", "").splitlines() if ln.strip()]

RULES_LOG = ".context/changes/rules-log.md"
EXACT_GOV = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".context/project.md"}
PREFIX_GOV = (".agents/", ".claude/", ".cursor/rules/")
HARNESS_INSTALL_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    ".context/project.md",
    ".agents/rules/coding-base.md",
    ".claude/rules/coding-base.md",
    ".cursor/rules/coding-base.mdc",
}

def git_out(args):
    res = subprocess.run(["git"] + args, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout

def is_in_head(path):
    if not has_head:
        return False
    rc, _ = git_out(["cat-file", "-e", f"HEAD:{path}"])
    return rc == 0

is_initial_harness_install = (".context/project.md" in files) and (not is_in_head(".context/project.md"))

def parse_governance_docs():
    patterns = []
    if not os.path.isfile(".context/project.md"):
        return patterns
    header_re = re.compile(
        r"^\s*(?:[-*]\s+)?[*`]*GOVERNANCE_DOCS[*`]*(?:\s*\([^)\n\r]*\))?[*`]*\s*:\**\s*(.*)$"
    )
    try:
        with open(".context/project.md", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = header_re.match(line)
                if not m:
                    continue
                rest = re.sub(r"\s+\([^)]*\)\s*$", "", m.group(1).strip())
                if "`" in rest:
                    raw_items = [
                        item
                        for span in re.findall(r"`([^`]+)`", rest)
                        for item in span.split(",")
                    ]
                else:
                    raw_items = rest.split(",")
                for raw_item in raw_items:
                    cleaned = re.sub(r"^\./+", "", raw_item.strip().strip("'\""))
                    if cleaned and cleaned.upper() not in ("TBD", "NONE") and cleaned not in ("*", "**"):
                        patterns.append(cleaned)
                break
    except OSError:
        pass
    return patterns

def is_mode0_onboarding():
    if has_head:
        _, diff_txt = git_out(["diff", "HEAD", "--", ".context/project.md"])
    else:
        _, d1 = git_out(["diff", "--", ".context/project.md"])
        _, d2 = git_out(["diff", "--cached", "--", ".context/project.md"])
        diff_txt = d1 + "\n" + d2
    return bool(
        re.search(r"^-\s*STATUS:\s*UNINITIALIZED\b", diff_txt, re.MULTILINE)
        and re.search(r"^\+\s*STATUS:\s*READY\b", diff_txt, re.MULTILINE)
    )

gov_patterns = parse_governance_docs()

def matches_gov(path):
    if path == RULES_LOG or path.startswith(".agents/teamwork/"):
        return False
    if is_initial_harness_install and path in HARNESS_INSTALL_FILES and not is_in_head(path):
        return False
    if path in EXACT_GOV or path.startswith(PREFIX_GOV):
        if path == ".context/project.md" and is_mode0_onboarding():
            return False
        return True
    for pat in gov_patterns:
        if path == pat or (pat.endswith("/") and path.startswith(pat)) or fnmatch.fnmatch(path, pat):
            return True
    return False

modified_gov = [f for f in files if matches_gov(f)]
if not modified_gov:
    sys.exit(0)

if not os.path.isfile(RULES_LOG):
    print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) but {RULES_LOG} does not exist!{NC}")
    sys.exit(1)

rc, _ = git_out(["ls-files", "--error-unmatch", "--", RULES_LOG])
is_log_tracked = (rc == 0)

entry_re = re.compile(r"^-\s*\[\d{4}-\d{2}-\d{2}")

def mentions_file(entry_line, gov_path):
    base = os.path.basename(gov_path)
    pat = rf"(?<![\w./-]){re.escape(gov_path)}(?![\w./-])|(?<![\w./-]){re.escape(base)}(?![\w./-])"
    return bool(re.search(pat, entry_line))

entries = []
try:
    with open(RULES_LOG, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if entry_re.match(ln.strip()):
                entries.append(ln.strip())
except OSError:
    pass
top_entry = entries[0] if entries else ""

if is_log_tracked:
    if has_head:
        _, log_diff = git_out(["diff", "HEAD", "--unified=0", "--", RULES_LOG])
    else:
        _, d1 = git_out(["diff", "--unified=0", "--", RULES_LOG])
        _, d2 = git_out(["diff", "--cached", "--unified=0", "--", RULES_LOG])
        log_diff = d1 + "\n" + d2
    added_entries = [
        line[1:].strip()
        for line in log_diff.splitlines()
        if line.startswith("+") and not line.startswith("+++") and entry_re.match(line[1:].strip())
    ]
    if (
        not added_entries
        or not top_entry
        or top_entry not in added_entries
        or not all(any(mentions_file(ae, gf) for ae in added_entries) for gf in modified_gov)
    ):
        print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) without prepending a matching top entry in {RULES_LOG}!{NC}")
        print("Expected top entry: - [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what> | Why: <reason> | Replaces: <old|None>")
        sys.exit(1)
else:
    if not top_entry or not any(mentions_file(top_entry, gf) for gf in modified_gov):
        print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) without prepending matching top entry/entries in {RULES_LOG}!{NC}")
        print("Expected top entry: - [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what> | Why: <reason> | Replaces: <old|None>")
        sys.exit(1)
    log_mtime = int(os.path.getmtime(RULES_LOG))
    last_cts = {}
    for gf in modified_gov:
        last_ct = 0
        if is_in_head(gf):
            rc_ct, out_ct = git_out(["log", "-1", "--format=%ct", "--", gf])
            if rc_ct == 0 and out_ct.strip().isdigit():
                last_ct = int(out_ct.strip())
                if log_mtime < last_ct:
                    print(f"{RED}❌ [FATAL] {RULES_LOG} is older than the last commit to {gf}; prepend a new entry for this edit!{NC}")
                    sys.exit(1)
        last_cts[gf] = last_ct

    ts_re = re.compile(r"^-\s*\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]")
    def entry_epoch(line):
        m = ts_re.match(line)
        if not m:
            return 0
        try:
            return int(datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").timestamp())
        except ValueError:
            return 0

    def file_covered(gf):
        if mentions_file(top_entry, gf):
            return True
        ct = last_cts[gf]
        for e in entries[1:]:
            if not any(mentions_file(e, x) for x in modified_gov):
                break
            if mentions_file(e, gf) and (ct == 0 or entry_epoch(e) + 60 > ct):
                return True
        return False

    if not all(file_covered(gf) for gf in modified_gov):
        print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) without prepending matching top entry/entries in {RULES_LOG}!{NC}")
        print("Expected top entry: - [YYYY-MM-DD HH:MM] [base: <short-sha>] <file(s)> — <what> | Why: <reason> | Replaces: <old|None>")
        sys.exit(1)
PY
  then
    FAILED=1
  fi
fi

echo "🔍 [3/3] Running Project VERIFY_CMD from .context/project.md..."
if [[ -f ".context/project.md" ]]; then
  VERIFY_CMD=$(python3 - <<'PY'
import re
bt = chr(96)
pat = re.compile(
    rf"^\s*(?:[-*]\s+)?[*{bt}]*VERIFY_CMD[*{bt}]*(?:\s*\([^)\n\r]*\))?[*{bt}]*\s*:\**\s*(.*)$"
)
with open(".context/project.md", "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        m = pat.match(line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith(bt * 2):
            m2 = re.match(rf"^{bt}{{2}}\s*(.*?)\s*{bt}{{2}}", rest)
            val = m2.group(1).strip() if m2 else ""
        elif rest.startswith(bt):
            m2 = re.match(rf"^{bt}([^{bt}]*){bt}", rest)
            val = m2.group(1).strip() if m2 else ""
        else:
            val = rest
        print(val)
        break
PY
)
  if [[ -z "$VERIFY_CMD" || "$VERIFY_CMD" == "TBD" ]]; then
    echo -e "${RED}❌ [FATAL] VERIFY_CMD is still 'TBD' in .context/project.md. Run Mode 0 (Onboard/Bootstrap) first.${NC}"
    FAILED=1
  else
    echo "▶ Executing: $VERIFY_CMD"
    if ! bash -c "$VERIFY_CMD"; then
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
