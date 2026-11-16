#!/usr/bin/env bash
set -euo pipefail
exec python3 - <<'PY'
import datetime, fnmatch, glob, os, re, subprocess, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

RED, GREEN, YELLOW, NC = "\033[0;31m", "\033[0;32m", "\033[1;33m", "\033[0m"
BT = chr(96)
failed = False


def git_out(args):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


is_git = git_out(["rev-parse", "--is-inside-work-tree"])[0] == 0
has_head = is_git and git_out(["rev-parse", "--verify", "HEAD"])[0] == 0
verify_staged = os.environ.get("VERIFY_STAGED") == "1"


def git_diff(path=None, unified0=False):
    tail = (["--unified=0"] if unified0 else []) + (["--", path] if path else [])
    if verify_staged:
        return git_out(["diff", "--no-renames", "--cached"] + tail)[1]
    if has_head:
        return git_out(["diff", "--no-renames", "HEAD"] + tail)[1]
    return git_out(["diff", "--no-renames"] + tail)[1] + "\n" + git_out(["diff", "--no-renames", "--cached"] + tail)[1]


def read_ctx(path):
    if verify_staged and is_git and git_out(["ls-files", "--error-unmatch", "--", path])[0] == 0:
        rc, out = git_out(["show", f":{path}"])
        return out if rc == 0 else None
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


scoped_files = []
if is_git:
    if verify_staged:
        raw = git_out(["diff", "--cached", "--name-only"])[1].splitlines()
    else:
        raw = git_out(["diff", "HEAD", "--name-only"] if has_head else ["diff", "--name-only"])[1].splitlines()
        if not has_head:
            raw += git_out(["diff", "--cached", "--name-only"])[1].splitlines()
        raw += git_out(["ls-files", "--others", "--exclude-standard"])[1].splitlines()
    changed = sorted({ln.strip() for ln in raw if ln.strip()})
    vf = os.environ.get("VERIFY_FILES", "").strip()
    if vf:
        allow = {re.sub(r"^\./+", "", x.strip()) for x in re.split(r"[\s,]+", vf) if x.strip()}
        scoped_files = [f for f in changed if f in allow]
    else:
        scoped_files = changed

print("🔍 [1/3] Checking Tests & Active Plan Integrity...")
if is_git and scoped_files:
    NON_CODE = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".lock", ".csv", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf"}
    CHEAT_RE = re.compile(r"(\.(skip|only)\s*\(|@(Disabled|Ignore)\b|pytest\.mark\.(skip|xfail)|catch\s*\([^)]*\)\s*\{\s*\})")
    ASSERT_RE = re.compile(r"(expect\(|assert|should|verify\()")
    fatal_hits, deleted_asserts = [], []

    for rel in scoped_files:
        if os.path.splitext(rel)[1].lower() in NON_CODE or ("test" not in rel.lower() and "spec" not in rel.lower()):
            continue
        if git_out(["ls-files", "--error-unmatch", "--", rel])[0] == 0:
            for ln in git_diff(rel, unified0=True).splitlines():
                if ln.startswith("+") and not ln.startswith("+++") and CHEAT_RE.search(ln[1:]):
                    fatal_hits.append((rel, "tracked diff", ln[1:].strip()))
                elif ln.startswith("-") and not ln.startswith("---") and ASSERT_RE.search(ln[1:]):
                    deleted_asserts.append((rel, ln[1:].strip()))
        elif os.path.isfile(rel):
            with open(rel, "r", encoding="utf-8", errors="replace") as f:
                for idx, ln in enumerate(f, 1):
                    if CHEAT_RE.search(ln):
                        fatal_hits.append((rel, f"untracked line {idx}", ln.strip()))

    if deleted_asserts:
        print(f"{YELLOW}⚠️  [HIGH RISK] Existing test assertions were modified or deleted:{NC}")
        for p, s in deleted_asserts[:10]:
            print(f"   - {p}: {s}")
        print(f"{YELLOW}👉 Verify this is explicitly authorized under MODIFIED/REMOVED in the active Spec.{NC}")
    if fatal_hits:
        print(f"{RED}❌ [FATAL] Banned test-cheating pattern detected (.skip, .only, @Disabled, or empty catch{{}}):{NC}")
        for p, loc, s in fatal_hits[:10]:
            print(f"   ❌ {p} ({loc}): {s}")
        failed = True

verify_spec = os.environ.get("VERIFY_SPEC", "").strip()
target_specs = []
if verify_spec:
    if verify_spec != "None":
        for folder in ("plans", "changes"):
            if os.path.isfile(f".context/{folder}/{verify_spec}.md"):
                target_specs.append(f".context/{folder}/{verify_spec}.md")
                break
elif scoped_files:
    basenames = {os.path.basename(f) for f in scoped_files}
    status_re = re.compile(r"^(?:[-*]\s+)?[*`]*Status[*`]*:\**\s*(APPROVED|IN_PROGRESS)\b", re.MULTILINE)
    for spec in sorted(glob.glob(".context/plans/*.md") + glob.glob(".context/changes/*.md")):
        if os.path.basename(spec) in ("_TEMPLATE.md", "rules-log.md", "decisions.md"):
            continue
        with open(spec, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
        if status_re.search(txt) and any(bn in txt for bn in basenames):
            target_specs.append(spec)

tc_fail_re = re.compile(rf"^\| *{BT}?TC-[0-9]+{BT}? *\|.*(\buntested\b|\bfail\b|\bTBD\b)")
unchecked_re = re.compile(r"^\s*[-*]\s*\[\s\]\s+")
for spec in target_specs:
    with open(spec, "r", encoding="utf-8", errors="replace") as f:
        bad_rows = [ln.rstrip() for ln in f if tc_fail_re.match(ln) or unchecked_re.match(ln)]
    if bad_rows:
        print(f"{RED}❌ [FATAL] Active Plan ({spec}) still has incomplete items or TBD test cases:{NC}")
        for r in bad_rows:
            print(f"   {r}")
        failed = True
    else:
        print(f"{GREEN}✅ Active Plan ({spec}) has zero incomplete items.{NC}")

print("🔍 [2/3] Checking Governance & Decisions Log (.context/decisions.md) Sync...")
RULES_LOG = ".context/decisions.md"
EXACT_GOV = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".context/project.md"}
PREFIX_GOV = (".agents/", ".claude/", ".cursor/rules/")
HARNESS_INSTALL = {"AGENTS.md", "CLAUDE.md", ".context/project.md", ".agents/rules/coding-base.md", ".claude/rules/coding-base.md", ".cursor/rules/coding-base.mdc"}
in_head = lambda p: has_head and git_out(["cat-file", "-e", f"HEAD:{p}"])[0] == 0
is_junk = lambda p: "__pycache__/" in p or p.endswith((".pyc", ".pyo", ".DS_Store"))
vf_raw = os.environ.get("VERIFY_FILES", "").strip()
vf_allow = {re.sub(r"^\./+", "", x.strip()) for x in re.split(r"[\s,]+", vf_raw) if x.strip()} if vf_raw else None

proj_txt = read_ctx(".context/project.md") or ""
gov_patterns = []
gov_re = re.compile(r"^\s*(?:[-*]\s+)?[*`]*GOVERNANCE_DOCS[*`]*(?:\s*\([^)\n\r]*\))?[*`]*\s*:\**\s*(.*)$")
for ln in proj_txt.splitlines():
    if m := gov_re.match(ln):
        rest = re.sub(r"\s+\([^)]*\)\s*$", "", m.group(1).strip())
        items = [x for span in re.findall(r"`([^`]+)`", rest) for x in span.split(",")] if "`" in rest else rest.split(",")
        gov_patterns = [c for raw in items if (c := re.sub(r"^\./+", "", raw.strip().strip("'\""))) and c.upper() not in ("TBD", "NONE") and c not in ("*", "**")]
        break

entry_re = re.compile(r"^-\s*\[\d{4}-\d{2}-\d{2}")
ts_re = re.compile(r"^-\s*\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]")
msg = "Expected top entry: - [YYYY-MM-DD HH:MM] [base: <short-sha|unborn>] <scope/file(s)> — <decision/change> | Why: <reason> | Rejected/Replaces: <old|None>"
log_txt = read_ctx(RULES_LOG)
entries = [ln.strip() for ln in log_txt.splitlines() if entry_re.match(ln.strip())] if log_txt is not None else []
has_real_entries = any("Upgraded coding-base harness engine via inject.sh" not in e for e in entries)

if is_git and scoped_files:
    init_install = (".context/project.md" in scoped_files) and not in_head(".context/project.md")
    proj_diff = git_diff(".context/project.md") if ".context/project.md" in scoped_files else ""
    mode0 = bool(re.search(r"^-\s*STATUS:\s*UNINITIALIZED\b", proj_diff, re.M) and re.search(r"^\+\s*STATUS:\s*READY\b", proj_diff, re.M))

    def is_gov(p):
        if p in (RULES_LOG, ".context/changes/rules-log.md") or p.startswith(".agents/teamwork/") or is_junk(p) or (init_install and p in HARNESS_INSTALL and not in_head(p)):
            return False
        if p in EXACT_GOV or p.startswith(PREFIX_GOV):
            return not (p == ".context/project.md" and mode0)
        return any(p == pat or (pat.endswith("/") and p.startswith(pat)) or fnmatch.fnmatch(p, pat) for pat in gov_patterns)

    norm_files = [re.sub(r"^\./+", "", f) for f in scoped_files]
    modified_gov = [f for f in norm_files if is_gov(f)]
    if modified_gov:
        if log_txt is None:
            print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) but {RULES_LOG} does not exist!{NC}")
            failed = True
        else:
            top = entries[0] if entries else ""
            mentions = lambda ln, gp: bool(re.search(rf"(?<![\w./-]){re.escape(gp)}(?![\w./-])|(?<![\w./-]){re.escape(os.path.basename(gp))}(?![\w./-])", ln))

            if git_out(["ls-files", "--error-unmatch", "--", RULES_LOG])[0] == 0:
                added = [ln[1:].strip() for ln in git_diff(RULES_LOG, unified0=True).splitlines() if ln.startswith("+") and not ln.startswith("+++") and entry_re.match(ln[1:].strip())]
                if not added or not top or top not in added or not all(any(mentions(ae, gf) for ae in added) for gf in modified_gov):
                    print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(modified_gov)}) without prepending a matching top entry in {RULES_LOG}!{NC}\n{msg}")
                    failed = True
            else:
                def epoch(ln):
                    m = ts_re.match(ln)
                    try:
                        return int(datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").timestamp()) if m else 0
                    except ValueError:
                        return 0

                log_mtime = int(os.path.getmtime(RULES_LOG))
                last_cts = {gf: (int(o.strip()) if in_head(gf) and (r := git_out(["log", "-1", "--format=%ct", "--", gf]))[0] == 0 and (o := r[1]).strip().isdigit() else 0) for gf in modified_gov}
                stale = [gf for gf, ct in last_cts.items() if ct and log_mtime < ct]
                if stale:
                    print(f"{RED}❌ [FATAL] {RULES_LOG} is older than the last commit to {stale[0]}; prepend a new entry for this edit!{NC}")
                    failed = True
                else:
                    non_up = [e for e in entries if "Upgraded coding-base harness engine via inject.sh" not in e]
                    covered = lambda gf: (bool(entries) and mentions(entries[0], gf)) or (bool(non_up) and mentions(non_up[0], gf)) or any(mentions(e, gf) and (last_cts[gf] == 0 or epoch(e) + 60 > last_cts[gf]) for e in entries[1:])
                    uncovered = [gf for gf in modified_gov if not covered(gf)]
                    if uncovered:
                        print(f"{RED}❌ [FATAL] Governance file(s) modified ({', '.join(uncovered)}) without prepending matching top entry/entries in {RULES_LOG}!{NC}\n{msg}")
                        failed = True

        if not failed and not verify_staged and os.path.isfile(RULES_LOG):
            log_mtime_f = os.path.getmtime(RULES_LOG)
            newer_gov = [gf for gf in modified_gov if os.path.isfile(gf) and not os.path.islink(gf) and os.path.getmtime(gf) > log_mtime_f + 5.0]
            if newer_gov:
                print(f"{RED}❌ [FATAL] Governance file(s) ({', '.join(newer_gov)}) were modified after {RULES_LOG}; prepend or update the top entry in {RULES_LOG} after finishing governance edits!{NC}\n{msg}")
                failed = True

if not failed and not verify_staged and (not is_git or not has_head):
    cands = {p for p in EXACT_GOV if os.path.isfile(p) and not os.path.islink(p)}
    for base_d in (".agents", ".claude", ".cursor/rules"):
        if os.path.isdir(base_d) and not os.path.islink(base_d):
            for root, dirs, files in os.walk(base_d):
                dirs[:] = [d for d in dirs if d != "__pycache__" and not (root == ".agents" and d == "teamwork")]
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel = re.sub(r"^\./+", "", fp.replace(os.sep, "/"))
                    if os.path.isfile(fp) and not os.path.islink(fp) and not is_junk(rel):
                        cands.add(rel)
    for pat in gov_patterns:
        gpat = pat.rstrip("/") + "/**" if pat.endswith("/") else pat
        for fp in glob.glob(gpat, recursive=True):
            rel = re.sub(r"^\./+", "", fp.replace(os.sep, "/"))
            if os.path.isfile(fp) and not os.path.islink(fp) and not is_junk(rel):
                cands.add(rel)
    cands -= {RULES_LOG, ".context/changes/rules-log.md"}
    if not has_real_entries:
        cands -= HARNESS_INSTALL
    if is_git:
        cands &= {re.sub(r"^\./+", "", f) for f in scoped_files}
    if vf_allow is not None:
        cands &= vf_allow
    if cands:
        if log_txt is None:
            print(f"{RED}❌ [FATAL] Governance file(s) exist ({', '.join(sorted(cands))}) but {RULES_LOG} does not exist!{NC}")
            failed = True
        elif len([l for l in log_txt.splitlines() if l.strip()]) > 1 and not entries:
            print(f"{RED}❌ [FATAL] {RULES_LOG} contains text but no valid ADR entries!{NC}\n{msg}")
            failed = True
        elif os.path.isfile(RULES_LOG):
            log_mtime_f = os.path.getmtime(RULES_LOG)
            newer_ng = sorted(gf for gf in cands if os.path.getmtime(gf) > log_mtime_f + 5.0)
            if newer_ng:
                print(f"{RED}❌ [FATAL] Governance file(s) ({', '.join(newer_ng)}) were modified after {RULES_LOG}; prepend or update the top entry in {RULES_LOG} after finishing governance edits!{NC}\n{msg}")
                failed = True

print("🔍 [3/3] Running Project VERIFY_CMD from .context/project.md...")
if (proj_cmd_txt := read_ctx(".context/project.md")) is not None:
    cmd_re = re.compile(rf"^\s*(?:[-*]\s+)?[*{BT}]*VERIFY_CMD[*{BT}]*(?:\s*\([^)\n\r]*\))?[*{BT}]*\s*:\**\s*(.*)$")
    verify_cmd = ""
    for ln in proj_cmd_txt.splitlines():
        if m := cmd_re.match(ln):
            rest = m.group(1).strip()
            if rest.startswith(BT * 2):
                m2 = re.match(rf"^{BT}{{2}}\s*(.*?)\s*{BT}{{2}}", rest)
                verify_cmd = m2.group(1).strip() if m2 else ""
            elif rest.startswith(BT):
                m2 = re.match(rf"^{BT}([^{BT}]*){BT}", rest)
                verify_cmd = m2.group(1).strip() if m2 else ""
            else:
                verify_cmd = rest
            break
    if not verify_cmd or verify_cmd == "TBD":
        print(f"{RED}❌ [FATAL] VERIFY_CMD is still 'TBD' in .context/project.md. Run Mode 0 (Onboard/Bootstrap) first.{NC}")
        failed = True
    else:
        print(f"▶ Executing: {verify_cmd}")
        if subprocess.run(["/bin/bash", "-c", verify_cmd]).returncode != 0:
            print(f"{RED}❌ [FATAL] Project VERIFY_CMD failed!{NC}")
            failed = True

if failed:
    print(f"\n{RED}⛔ GATEKEEPER BLOCKED COMPLETION. Fix all [FATAL] issues above before reporting done.{NC}")
    sys.exit(1)

print(f"\n{GREEN}✅ GATEKEEPER PASSED.{NC}")
PY
