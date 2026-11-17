#!/usr/bin/env python3
"""E2E verification suite (10 tests) for the flat 4-file coding-base harness."""

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
INJECT_SH = BASE_DIR / "inject.sh"


_SCRUB_ENV = {
    "VERIFY_STAGED",
    "VERIFY_FILES",
    "VERIFY_SPEC",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


def run(cmd, cwd, env=None):
    merged_env = {k: v for k, v in os.environ.items() if k not in _SCRUB_ENV}
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )


def git_init(repo: Path, make_commit: bool = True):
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    if make_commit:
        (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        run(["git", "add", "README.md"], repo)
        res = run(["git", "commit", "-m", "init"], repo)
        assert res.returncode == 0, res.stderr


def configure_project_md(repo: Path, verify_cmd: str = "true", gov_docs: str = None):
    p = repo / ".context" / "project.md"
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace("STATUS: UNINITIALIZED", "STATUS: READY")
    txt = re.sub(
        r"(\*\*`?VERIFY_CMD`?[^:]*:\*\*\s*`)[^`]*(`)",
        lambda m: f"{m.group(1)}{verify_cmd}{m.group(2)}",
        txt,
    )
    if gov_docs is not None:
        txt = re.sub(
            r"(\*\*`?GOVERNANCE_DOCS`?[^:]*:\*\*\s*`)[^`]*(`)",
            lambda m: f"{m.group(1)}{gov_docs}{m.group(2)}",
            txt,
        )
    p.write_text(txt, encoding="utf-8")


def test_t1_anticheat_doc_immunity_and_unborn():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        git_init(repo, make_commit=True)
        res = run([str(INJECT_SH), str(repo)], BASE_DIR)
        assert res.returncode == 0, res.stderr + res.stdout
        assert not (repo / ".context" / "changes").exists()
        assert (repo / ".context" / "decisions.md").is_file()
        proj_init = (repo / ".context" / "project.md").read_text(encoding="utf-8")
        state_init = (repo / ".context" / "state.md").read_text(encoding="utf-8")
        assert "STATUS: UNINITIALIZED" in proj_init, proj_init
        assert "- **VERIFY_CMD:** `bash -n .context/verify-gate.sh`" in proj_init, proj_init
        assert "- Initialized harness; no completed session yet." in state_init, state_init
        assert "test_harness.py" not in proj_init, proj_init
        configure_project_md(repo, verify_cmd="true")

        # 1a. Untracked test with skipped case must FAIL
        (repo / "foo.spec.ts").write_text("it." + "skip('x', () => {});\n", encoding="utf-8")
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r1.returncode != 0 and "FATAL" in r1.stdout, r1.stdout

        # 1b. Tracked test diff with deleted assert + empty catch block must FAIL + warn HIGH RISK
        (repo / "foo.spec.ts").write_text("it('x', () => { expect(1).toBe(1); });\n", encoding="utf-8")
        run(["git", "add", "foo.spec.ts"], repo)
        assert run(["git", "commit", "-m", "add spec"], repo).returncode == 0
        (repo / "foo.spec.ts").write_text("it('x', () => { try { work(); } catch (e) {" + "} });\n", encoding="utf-8")
        r2 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r2.returncode != 0 and "FATAL" in r2.stdout and "HIGH RISK" in r2.stdout, r2.stdout

        # 1c. Restore clean test + add .md file containing skip pattern -> PASS (doc immunity)
        run(["git", "restore", "foo.spec.ts"], repo)
        (repo / ".context" / "plans").mkdir(parents=True, exist_ok=True)
        (repo / ".context" / "plans" / "guide.md").write_text(
            "# Guide\n- **Status:** DRAFT\nDo not use .skip" + "( in tests.\n",
            encoding="utf-8",
        )
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r3.returncode == 0 and "GATEKEEPER PASSED" in r3.stdout, r3.stdout + r3.stderr

    # 1d. Unborn HEAD + untracked cheat -> FAIL
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "unborn"
        repo.mkdir()
        git_init(repo, make_commit=False)
        assert run([str(INJECT_SH), str(repo)], BASE_DIR).returncode == 0
        assert not (repo / ".context" / "changes").exists()
        configure_project_md(repo, verify_cmd="true")
        (repo / "bar.test.py").write_text("@pytest.mark." + "skip\ndef test_a(): pass\n", encoding="utf-8")
        r4 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r4.returncode != 0 and "FATAL" in r4.stdout, r4.stdout

    print("PASS T1: Anti-cheat, deleted-assert warning, doc .md immunity, and unborn HEAD")


def test_t2_scoped_verify_and_active_plans():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        git_init(repo, make_commit=True)
        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        assert not (repo / ".context" / "changes").exists()
        configure_project_md(repo, verify_cmd="true")
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "init harness"], repo).returncode == 0

        # Active plan under .context/plans/ mixing markdown checkbox (- [ ]) and legacy TC-01 row
        (repo / ".context" / "plans").mkdir(parents=True, exist_ok=True)
        plan = repo / ".context" / "plans" / "feat-auth.md"
        plan.write_text(
            "# Plan: feat-auth\n- **Status:** APPROVED\n"
            "- [ ] Wire token refresh endpoint\n\n"
            "| `TC-01` | Refresh token | valid | TBD |\n"
            "Target file: auth.py\n",
            encoding="utf-8",
        )
        (repo / "auth.py").write_text("def refresh(): return True\n", encoding="utf-8")
        (repo / "other.py").write_text("x = 1\n", encoding="utf-8")

        # 2a. Unscoped run fails because auth.py touches feat-auth
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r1.returncode != 0 and "Active Plan" in r1.stdout, r1.stdout

        # 2b. Scoped VERIFY_FILES=other.py VERIFY_SPEC=None skips feat-auth -> PASS
        r2 = run(
            ["/bin/bash", "./.context/verify-gate.sh"],
            repo,
            env={"VERIFY_FILES": "other.py", "VERIFY_SPEC": "None"},
        )
        assert r2.returncode == 0 and "GATEKEEPER PASSED" in r2.stdout, r2.stdout + r2.stderr

        # 2c. Fix checklist but keep TC-01 TBD -> still FAIL
        plan.write_text(
            "# Plan: feat-auth\nStatus: IN_PROGRESS\n"
            "- [x] Wire token refresh endpoint\n\n"
            "| `TC-01` | Refresh token | valid | untested |\n"
            "Target file: auth.py\n",
            encoding="utf-8",
        )
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], repo, env={"VERIFY_SPEC": "feat-auth"})
        assert r3.returncode != 0 and "TC-01" in r3.stdout, r3.stdout

        # 2d. Complete both -> PASS
        plan.write_text(
            "# Plan: feat-auth\nStatus: APPROVED\n"
            "- [x] Wire token refresh endpoint\n\n"
            "| `TC-01` | Refresh token | valid | pass |\n"
            "Target file: auth.py\n",
            encoding="utf-8",
        )
        r4 = run(["/bin/bash", "./.context/verify-gate.sh"], repo, env={"VERIFY_SPEC": "feat-auth"})
        assert r4.returncode == 0 and "zero incomplete items" in r4.stdout, r4.stdout + r4.stderr

    print("PASS T2: Scoped VERIFY_FILES/VERIFY_SPEC and active plan (- [ ] + TC-xx) gating")


def test_t3_decisions_tracked_mode0_stealth_gov_docs():
    # 3a. Tracked mode: initial commit, Mode 0, AGENTS.md edit, GOVERNANCE_DOCS edit
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "tracked"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "docs").mkdir()
        (repo / "docs" / "rules.md").write_text("# Domain Rules\nv1\n", encoding="utf-8")
        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        run(["git", "add", "."], repo)
        r_init = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_init.returncode == 0, r_init.stdout + r_init.stderr
        assert run(["git", "commit", "-m", "initial harness"], repo).returncode == 0

        # Mode 0 onboarding (UNINITIALIZED -> READY + setting GOVERNANCE_DOCS) without logging -> PASS
        configure_project_md(repo, verify_cmd="true", gov_docs="docs/rules.md")
        r_m0 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_m0.returncode == 0, r_m0.stdout + r_m0.stderr
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "mode 0 ready"], repo).returncode == 0

        # Modify AGENTS.md without decisions.md -> FAIL
        (repo / "AGENTS.md").write_text((repo / "AGENTS.md").read_text(encoding="utf-8") + "\n# extra\n", encoding="utf-8")
        r_fail = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_fail.returncode != 0 and "decisions.md" in r_fail.stdout, r_fail.stdout

        # Prepend matching entry -> PASS
        sha = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        log_f = repo / ".context" / "decisions.md"
        old_log = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([old_log[0], "", f"- [2026-11-15 15:40] [base: {sha}] AGENTS.md — extra note | Why: test | Rejected/Replaces: None"] + old_log[1:]) + "\n",
            encoding="utf-8",
        )
        r_ok = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_ok.returncode == 0, r_ok.stdout + r_ok.stderr
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "update agents"], repo).returncode == 0

        # Modify GOVERNANCE_DOCS target docs/rules.md without decisions.md -> FAIL, then log -> PASS
        (repo / "docs" / "rules.md").write_text("# Domain Rules\nv2\n", encoding="utf-8")
        assert run(["/bin/bash", "./.context/verify-gate.sh"], repo).returncode != 0
        sha2 = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        cur = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur[0], "", f"- [2026-11-15 15:41] [base: {sha2}] docs/rules.md — v2 | Why: sync | Rejected/Replaces: v1"] + cur[1:]) + "\n",
            encoding="utf-8",
        )
        assert run(["/bin/bash", "./.context/verify-gate.sh"], repo).returncode == 0

    # 3b. Stealth mode: tracked GOVERNANCE_DOCS edited while decisions.md is stealth-excluded
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "stealth"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "docs").mkdir()
        (repo / "docs" / "rules.md").write_text("# Tracked Governance Doc\nv1\n", encoding="utf-8")
        run(["git", "add", "docs/rules.md"], repo)
        assert run(["git", "commit", "-m", "add tracked rule doc"], repo).returncode == 0

        assert run([str(INJECT_SH), str(repo), "--stealth"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true", gov_docs="docs/rules.md")
        (repo / "docs" / "rules.md").write_text("# Tracked Governance Doc\nv2\n", encoding="utf-8")
        r_s1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_s1.returncode != 0 and "decisions.md" in r_s1.stdout, r_s1.stdout
        log_f = repo / ".context" / "decisions.md"
        log_f.write_text(
            "# Decisions & Governance Log\n\n- [2026-11-15 15:42] [base: abc1234] docs/rules.md — v2 | Why: test | Rejected/Replaces: v1\n",
            encoding="utf-8",
        )
        r_s2 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_s2.returncode == 0, r_s2.stdout + r_s2.stderr

    print("PASS T3: decisions.md (tracked, Mode 0 bypass, GOVERNANCE_DOCS, and stealth)")


def test_t4_verify_cmd_parser_and_tbd_guard():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "parser"
        repo.mkdir()
        git_init(repo, make_commit=True)
        assert run([str(INJECT_SH), str(repo)], BASE_DIR).returncode == 0

        p = repo / ".context" / "project.md"
        p.write_text(
            "# Project\nSTATUS: READY\n- **GOVERNANCE_DOCS:** `None`\n- **VERIFY_CMD:** TBD\n",
            encoding="utf-8",
        )
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r1.returncode != 0 and "TBD" in r1.stdout, r1.stdout

        p.write_text(
            "# Project\nSTATUS: READY\n- **GOVERNANCE_DOCS:** `None`\n"
            "- **VERIFY_CMD:** ``echo \"hi | pipe\" | grep -q \"hi | pipe\" && test -f README.md``\n",
            encoding="utf-8",
        )
        r2 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r2.returncode == 0 and "GATEKEEPER PASSED" in r2.stdout, r2.stdout + r2.stderr

        p.write_text(
            "# Project\nSTATUS: READY\n- **GOVERNANCE_DOCS:** `None`\n- **VERIFY_CMD:** `false`\n",
            encoding="utf-8",
        )
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r3.returncode != 0 and "Project VERIFY_CMD failed" in r3.stdout, r3.stdout

    print("PASS T4: VERIFY_CMD parser (TBD guard, pipes/double-backticks, None GOVERNANCE_DOCS)")


def test_t5_upgrade_coexistence_migration_and_scrubber():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "legacy"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "AGENTS.md").write_text("# Custom Repo Rules\nKeep intact.\n", encoding="utf-8")
        (repo / "CLAUDE.md").write_text("# Custom Claude Rules\nKeep intact.\n", encoding="utf-8")
        run(["git", "add", "AGENTS.md", "CLAUDE.md"], repo)
        assert run(["git", "commit", "-m", "custom rules"], repo).returncode == 0

        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0

        # Simulate pre-refactor legacy installation committed to HEAD with changes/rules-log.md & active plan
        (repo / ".agents" / "rules" / "coding-base.md").write_text("# OLD ENGINE\n", encoding="utf-8")
        (repo / ".context" / "check-blast-radius.py").write_text("print('legacy')\n", encoding="utf-8")
        (repo / ".context" / "changes").mkdir(parents=True, exist_ok=True)
        (repo / ".context" / "changes" / "_TEMPLATE.md").write_text("# Template\n", encoding="utf-8")
        (repo / ".context" / "changes" / "commit-log.md").write_text("# Commit Log\n", encoding="utf-8")
        (repo / ".context" / "changes" / "feat-wip.md").write_text("# Plan: feat-wip\n- **Status:** DRAFT\n- [ ] wip\n", encoding="utf-8")
        (repo / ".context" / "changes" / "rules-log.md").write_text(
            "# Governance Log\n\n- [2026-11-15 08:00] [base: init] AGENTS.md — initial custom rule | Why: setup | Replaces: None\n",
            encoding="utf-8",
        )
        (repo / ".context" / "decisions.md").unlink()
        (repo / ".context" / "checkpoint.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (repo / ".context" / "__pycache__").mkdir()
        (repo / ".context" / "__pycache__" / "x.pyc").write_bytes(b"pyc")
        (repo / ".context" / ".gitignore").write_text("changes/commit-log.md\n.vault/\n", encoding="utf-8")
        (repo / ".context" / "project.md").write_text(
            "# Project\nSTATUS: READY\n"
            "- **GOVERNANCE_DOCS** (edits logged in `.context/changes/rules-log.md`): `README.md`\n"
            "- **Call Graph:** Run `python3 .context/check-blast-radius.py --mode pre-edit --symbol foo` or `code-review-graph` MCP.\n"
            "- **VERIFY_CMD:** `bash -n .context/verify-gate.sh && python3 -m py_compile .context/check-blast-radius.py && test -f README.md`\n"
            "- **Targeted Test (Blast Radius):** `python3 .context/check-blast-radius.py --mode gate`\n",
            encoding="utf-8",
        )
        (repo / ".context" / "state.md").write_text(
            "| `feat-wip` | `Plan` | `PLAN` | `.context/changes/feat-wip.md` | Draft |\n",
            encoding="utf-8",
        )
        run(["git", "add", "-A"], repo)
        assert run(["git", "commit", "--no-verify", "-m", "legacy committed state"], repo).returncode == 0

        # Upgrade without --track -> migrates rules-log -> decisions.md, feat-wip -> plans/feat-wip.md, removes changes/
        r_up = run([str(INJECT_SH), str(repo), "--upgrade"], BASE_DIR)
        assert r_up.returncode == 0, r_up.stderr + r_up.stdout

        assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "# Custom Repo Rules\nKeep intact.\n"
        assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == "# Custom Claude Rules\nKeep intact.\n"
        assert (repo / ".claude" / "rules" / "coding-base.md").is_symlink()
        assert (repo / ".cursor" / "rules" / "coding-base.mdc").is_symlink()

        for gone in [
            ".context/check-blast-radius.py",
            ".context/changes",
            ".context/checkpoint.sh",
            ".context/__pycache__",
            ".context/.gitignore",
        ]:
            assert not (repo / gone).exists(), f"Legacy artifact still exists: {gone}"

        assert (repo / ".context" / "plans" / "feat-wip.md").is_file()
        assert ".context/plans/feat-wip.md" in (repo / ".context" / "state.md").read_text(encoding="utf-8")

        proj_txt = (repo / ".context" / "project.md").read_text(encoding="utf-8")
        assert "check-blast-radius.py" not in proj_txt, proj_txt
        assert "rules-log.md" not in proj_txt and ".context/decisions.md" in proj_txt, proj_txt
        assert "bash -n .context/verify-gate.sh && test -f README.md" in proj_txt, proj_txt
        assert "Targeted Test (Blast Radius)" not in proj_txt, proj_txt

        dec_txt = (repo / ".context" / "decisions.md").read_text(encoding="utf-8")
        entries = [ln for ln in dec_txt.splitlines() if ln.startswith("- [")]
        assert len(entries) == 2 and "initial custom rule" in entries[1], dec_txt
        assert ".agents/rules/coding-base.md" in entries[0] and ".context/project.md" in entries[0], entries[0]

        r_gate = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_gate.returncode == 0 and "GATEKEEPER PASSED" in r_gate.stdout, r_gate.stdout + r_gate.stderr

        # Staging everything (including rename rules-log.md -> decisions.md) passes pre-commit hook!
        run(["git", "add", "-A"], repo)
        c_mig = run(["git", "commit", "-m", "migrated"], repo)
        assert c_mig.returncode == 0, c_mig.stdout + c_mig.stderr

    print("PASS T5: Coexistence, changes/ migration, project.md scrubber, and staged pre-commit commit")


def test_t6_mode_preservation_coalescing_and_nongit():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "coalesce"
        repo.mkdir()
        git_init(repo, make_commit=True)
        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true")
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "v1"], repo).returncode == 0

        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\nold1\n", encoding="utf-8")
        run(["git", "add", "AGENTS.md"], repo)
        assert run(["git", "commit", "--no-verify", "-m", "old agents"], repo).returncode == 0

        assert run([str(INJECT_SH), str(repo), "--upgrade"], BASE_DIR).returncode == 0
        excl = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        assert ".code-review-graph/" in excl and ".context/" not in excl.splitlines(), excl

        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\nold2\n", encoding="utf-8")
        (repo / ".context" / "project.md").write_text(
            (repo / ".context" / "project.md").read_text(encoding="utf-8") + "\n- `check-blast-radius.py`\n",
            encoding="utf-8",
        )
        assert run([str(INJECT_SH), str(repo), "--upgrade"], BASE_DIR).returncode == 0
        entries = [ln for ln in (repo / ".context" / "decisions.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- [")]
        assert len(entries) == 1 and "AGENTS.md" in entries[0] and ".context/project.md" in entries[0], entries
        assert run(["/bin/bash", "./.context/verify-gate.sh"], repo).returncode == 0

        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "v2"], repo).returncode == 0
        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\nold3\n", encoding="utf-8")
        run(["git", "add", "AGENTS.md"], repo)
        assert run(["git", "commit", "--no-verify", "-m", "old3"], repo).returncode == 0
        assert run([str(INJECT_SH), str(repo), "--upgrade"], BASE_DIR).returncode == 0
        entries2 = [ln for ln in (repo / ".context" / "decisions.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- [")]
        assert len(entries2) == 2, entries2

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "plain"
        folder.mkdir()
        assert run([str(INJECT_SH), str(folder), "--track"], BASE_DIR).returncode == 0
        assert not (folder / ".context" / "changes").exists()
        configure_project_md(folder, verify_cmd="test -f AGENTS.md")
        r_ng = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r_ng.returncode == 0 and "GATEKEEPER PASSED" in r_ng.stdout, r_ng.stdout + r_ng.stderr
        assert not (folder / ".context" / "__pycache__").exists()

        (folder / ".context" / "state.md").write_text("# Custom State\n## Last Handoff\n- custom\n", encoding="utf-8")
        (folder / ".context" / "decisions.md").write_text(
            "# Decisions & Governance Log\n\n- [2026-11-16 12:00] [base: unborn] README.md — keep | Why: test | Rejected/Replaces: None\n",
            encoding="utf-8",
        )
        assert run([str(INJECT_SH), str(folder), "--force"], BASE_DIR).returncode == 0
        assert "STATUS: UNINITIALIZED" in (folder / ".context" / "project.md").read_text(encoding="utf-8")
        assert "- Initialized harness; no completed session yet." in (folder / ".context" / "state.md").read_text(encoding="utf-8")
        assert "keep | Why: test" in (folder / ".context" / "decisions.md").read_text(encoding="utf-8")

    print("PASS T6: Track preservation, decisions.md coalescing, and non-Git __pycache__-free run")


def test_t7_native_git_rollback_and_stealth_gov():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "rollback"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "app.py").write_text("v1 = 1\n", encoding="utf-8")
        (repo / "other.txt").write_text("keep\n", encoding="utf-8")
        run(["git", "add", "app.py", "other.txt"], repo)
        assert run(["git", "commit", "-m", "v1"], repo).returncode == 0
        (repo / "app.py").write_text("v2 = 2\n", encoding="utf-8")
        run(["git", "add", "app.py"], repo)
        assert run(["git", "commit", "-m", "v2"], repo).returncode == 0

        (repo / "other.txt").write_text("dirty-unrelated\n", encoding="utf-8")
        assert run(["git", "restore", "--worktree", "--source=HEAD~1", "--", "app.py"], repo).returncode == 0
        assert (repo / "app.py").read_text(encoding="utf-8") == "v1 = 1\n"
        assert (repo / "other.txt").read_text(encoding="utf-8") == "dirty-unrelated\n"

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "stealth_gov"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\n", encoding="utf-8")
        run(["git", "add", "AGENTS.md"], repo)
        assert run(["git", "commit", "-m", "tracked base agents"], repo).returncode == 0
        assert run([str(INJECT_SH), str(repo), "--stealth"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true")

        time.sleep(0.05)
        log_f = repo / ".context" / "decisions.md"
        sha = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        log_f.write_text(
            f"# Decisions & Governance Log\n\n- [2026-11-15 16:05] [base: {sha}] AGENTS.md — rollback AGENTS.md via git restore | Why: test | Rejected/Replaces: edit\n",
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\n# rollback edit\n", encoding="utf-8")
        r = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r.returncode == 0 and "GATEKEEPER PASSED" in r.stdout, r.stdout + r.stderr

    print("PASS T7: Native Git per-file rollback and stealth governance verification")


def test_t8_worktree_legacy_precommit_and_custom_hooks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "mainrepo"
        repo.mkdir()
        git_init(repo, make_commit=True)

        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        custom_pre = hooks_dir / "pre-commit"
        custom_pre.write_text("#!/bin/sh\necho 1\necho 2\necho 3\necho 4\necho 5\necho 6\n", encoding="utf-8")
        custom_pre.chmod(0o755)
        custom_post = hooks_dir / "post-commit"
        custom_post.write_text("#!/bin/sh\necho user-post-commit\n", encoding="utf-8")
        custom_post.chmod(0o755)

        wt = root / "wt1"
        assert run(["git", "worktree", "add", "-b", "feat/wt", str(wt)], repo).returncode == 0
        assert run([str(INJECT_SH), str(wt), "--stealth"], BASE_DIR).returncode == 0

        assert "echo 6" in custom_pre.read_text(encoding="utf-8")
        assert "user-post-commit" in custom_post.read_text(encoding="utf-8")
        st = run(["git", "status", "--short"], wt).stdout.strip()
        assert st == "", f"Worktree stealth leaked files:\n{st}"

        custom_pre.write_text("#!/usr/bin/env bash\n./.context/verify-gate.sh\n", encoding="utf-8")
        custom_post.write_text("#!/usr/bin/env bash\n# coding-base-hook\necho legacy\n", encoding="utf-8")
        assert run([str(INJECT_SH), str(repo), "--upgrade", "--stealth"], BASE_DIR).returncode == 0
        assert "# coding-base-hook" in custom_pre.read_text(encoding="utf-8")
        assert not custom_post.exists(), "Legacy coding-base post-commit should be removed"

    print("PASS T8: Worktree stealth, legacy hook upgrade, and custom hook preservation")


def test_t9_precommit_staged_isolation():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "staged"
        repo.mkdir()
        git_init(repo, make_commit=True)
        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true")
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "init"], repo).returncode == 0

        (repo / "dirty.spec.ts").write_text("it." + "skip('broken', () => {});\n", encoding="utf-8")
        (repo / "app.py").write_text("ok = True\n", encoding="utf-8")
        run(["git", "add", "app.py"], repo)
        c1 = run(["git", "commit", "-m", "clean staged only"], repo)
        assert c1.returncode == 0, c1.stdout + c1.stderr

        r_full = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_full.returncode != 0 and "FATAL" in r_full.stdout, r_full.stdout
        (repo / "dirty.spec.ts").unlink()

        (repo / "AGENTS.md").write_text((repo / "AGENTS.md").read_text(encoding="utf-8") + "\n# rule2\n", encoding="utf-8")
        sha = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        log_f = repo / ".context" / "decisions.md"
        lines = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([lines[0], "", f"- [2026-11-15 16:06] [base: {sha}] AGENTS.md — staged check | Why: test | Rejected/Replaces: None"] + lines[1:]) + "\n",
            encoding="utf-8",
        )
        run(["git", "add", "AGENTS.md"], repo)
        c_block = run(["git", "commit", "-m", "missing staged decisions"], repo)
        assert c_block.returncode != 0 and "decisions.md" in (c_block.stdout + c_block.stderr), c_block.stdout + c_block.stderr

        run(["git", "add", ".context/decisions.md"], repo)
        c_ok = run(["git", "commit", "-m", "both staged"], repo)
        assert c_ok.returncode == 0, c_ok.stdout + c_ok.stderr

    print("PASS T9: pre-commit VERIFY_STAGED=1 isolation (unstaged WIP safe, unstaged decisions.md blocked)")


def test_t10_uncommitted_repeat_gov_edits_and_nongit_mtime():
    # 10a. Tracked decisions.md: uncommitted repeat governance edit blocked by mtime check
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repeat_tracked"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "craft").mkdir()
        style_f = repo / "craft" / "style.md"
        style_f.write_text("# Style v1\n", encoding="utf-8")
        run(["git", "add", "craft/style.md"], repo)
        assert run(["git", "commit", "-m", "add craft"], repo).returncode == 0
        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true", gov_docs="craft/**")
        run(["git", "add", "."], repo)
        assert run(["git", "commit", "-m", "baseline"], repo).returncode == 0

        sha = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        log_f = repo / ".context" / "decisions.md"

        # Round 1 edit + E1 -> PASS
        style_f.write_text("# Style v2\n", encoding="utf-8")
        cur = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur[0], "", f"- [2026-11-16 13:50] [base: {sha}] craft/style.md — round 1 | Why: e1 | Rejected/Replaces: v1"] + cur[1:]) + "\n",
            encoding="utf-8",
        )
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r1.returncode == 0 and "GATEKEEPER PASSED" in r1.stdout, r1.stdout + r1.stderr

        # Round 2 edit without committing + decisions.md 10s older -> FAIL
        style_f.write_text("# Style v3\n", encoding="utf-8")
        now = time.time()
        os.utime(log_f, (now - 10, now - 10))
        r2 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r2.returncode != 0 and "modified after .context/decisions.md" in r2.stdout, r2.stdout

        # Scoped VERIFY_FILES outside governance ignores craft/style.md even while decisions.md is older
        (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
        r_scoped = run(
            ["/bin/bash", "./.context/verify-gate.sh"],
            repo,
            env={"VERIFY_FILES": "app.py", "VERIFY_SPEC": "None"},
        )
        assert r_scoped.returncode == 0 and "GATEKEEPER PASSED" in r_scoped.stdout, r_scoped.stdout + r_scoped.stderr

        # Prepend E2 -> PASS
        cur2 = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur2[0], "", f"- [2026-11-16 13:55] [base: {sha}] craft/style.md — round 2 | Why: e2 | Rejected/Replaces: v2"] + cur2[1:]) + "\n",
            encoding="utf-8",
        )
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r3.returncode == 0 and "GATEKEEPER PASSED" in r3.stdout, r3.stdout + r3.stderr

        # Unchanged re-upgrade preserves AGENTS.md mtime (or aligns it with decisions.md) -> still PASS
        past = time.time() - 15
        os.utime(log_f, (past, past))
        os.utime(style_f, (past, past))
        os.utime(repo / "AGENTS.md", (past, past))
        assert run([str(INJECT_SH), str(repo), "--upgrade", "--track"], BASE_DIR).returncode == 0
        r_idem = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r_idem.returncode == 0 and "GATEKEEPER PASSED" in r_idem.stdout, r_idem.stdout + r_idem.stderr

    # 10b. Untracked decisions.md: uncommitted repeat governance edit (lyra-vance / coslient-free pattern)
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repeat_untracked"
        repo.mkdir()
        git_init(repo, make_commit=True)
        (repo / "craft").mkdir()
        style_f = repo / "craft" / "style.md"
        style_f.write_text("# Style v1\n", encoding="utf-8")
        run(["git", "add", "craft/style.md"], repo)
        assert run(["git", "commit", "-m", "track style"], repo).returncode == 0

        assert run([str(INJECT_SH), str(repo), "--track"], BASE_DIR).returncode == 0
        configure_project_md(repo, verify_cmd="true", gov_docs="craft/**")
        sha = run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
        log_f = repo / ".context" / "decisions.md"

        # Round 1 edit + E1 -> PASS
        style_f.write_text("# Style v2\n", encoding="utf-8")
        log_f.write_text(
            f"# Decisions & Governance Log\n\n- [2026-11-16 13:50] [base: {sha}] craft/style.md — round 1 | Why: e1 | Rejected/Replaces: v1\n",
            encoding="utf-8",
        )
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r1.returncode == 0 and "GATEKEEPER PASSED" in r1.stdout, r1.stdout + r1.stderr

        # Round 2 edit without committing + decisions.md 10s older -> FAIL
        style_f.write_text("# Style v3\n", encoding="utf-8")
        now = time.time()
        os.utime(log_f, (now - 10, now - 10))
        r2 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r2.returncode != 0 and ".context/decisions.md" in r2.stdout, r2.stdout

        # Update top E2 -> PASS
        cur = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur[0], "", f"- [2026-11-16 13:56] [base: {sha}] craft/style.md — round 2 | Why: e2 | Rejected/Replaces: v2"] + cur[1:]) + "\n",
            encoding="utf-8",
        )
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r3.returncode == 0 and "GATEKEEPER PASSED" in r3.stdout, r3.stdout + r3.stderr

        # Regression: inject.sh --upgrade prepends AGENTS.md upgrade entry above E2 while AGENTS.md is untracked -> still PASS
        (repo / "AGENTS.md").write_text("# AGENTS.md — Universal Project Harness\nold\n", encoding="utf-8")
        assert run([str(INJECT_SH), str(repo), "--upgrade", "--track"], BASE_DIR).returncode == 0
        r4 = run(["/bin/bash", "./.context/verify-gate.sh"], repo)
        assert r4.returncode == 0 and "GATEKEEPER PASSED" in r4.stdout, r4.stdout + r4.stderr

    # 10c. Non-Git folder (cute-life pattern): mtime freshness, __pycache__/.pyc immunity, HARNESS_INSTALL protection
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "nongit_mtime"
        folder.mkdir()
        assert run([str(INJECT_SH), str(folder), "--track"], BASE_DIR).returncode == 0
        configure_project_md(folder, verify_cmd="true", gov_docs="craft/**")
        (folder / "craft").mkdir()
        c01 = folder / "craft" / "01.md"
        c01.write_text("# Craft 01 v1\n", encoding="utf-8")
        log_f = folder / ".context" / "decisions.md"
        cur = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur[0], "", "- [2026-11-16 13:50] [base: unborn] craft/01.md — init craft 01 | Why: e1 | Rejected/Replaces: None"] + cur[1:]) + "\n",
            encoding="utf-8",
        )
        r1 = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r1.returncode == 0 and "GATEKEEPER PASSED" in r1.stdout, r1.stdout + r1.stderr

        # Edit craft/01.md with decisions.md 10s older -> FAIL
        c01.write_text("# Craft 01 v2\n", encoding="utf-8")
        now = time.time()
        os.utime(log_f, (now - 10, now - 10))
        r2 = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r2.returncode != 0 and "modified after .context/decisions.md" in r2.stdout, r2.stdout

        # Log E2 + add newer __pycache__/y.pyc under .agents/ -> PASS (__pycache__/.pyc immunity)
        cur2 = log_f.read_text(encoding="utf-8").splitlines()
        log_f.write_text(
            "\n".join([cur2[0], "", "- [2026-11-16 13:55] [base: unborn] craft/01.md — update craft 01 | Why: e2 | Rejected/Replaces: v1"] + cur2[1:]) + "\n",
            encoding="utf-8",
        )
        pyc_dir = folder / ".agents" / "skills" / "x" / "__pycache__"
        pyc_dir.mkdir(parents=True)
        pyc_f = pyc_dir / "y.pyc"
        pyc_f.write_bytes(b"pyc")
        future = time.time() + 20
        os.utime(pyc_f, (future, future))
        r3 = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r3.returncode == 0 and "GATEKEEPER PASSED" in r3.stdout, r3.stdout + r3.stderr

        # Unchanged re-upgrade preserves AGENTS.md mtime (or aligns it with decisions.md) -> still PASS
        past2 = time.time() - 15
        os.utime(log_f, (past2, past2))
        os.utime(c01, (past2, past2))
        os.utime(folder / ".context" / "project.md", (past2, past2))
        os.utime(folder / "AGENTS.md", (past2, past2))
        assert run([str(INJECT_SH), str(folder), "--upgrade", "--track"], BASE_DIR).returncode == 0
        r_idem_ng = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r_idem_ng.returncode == 0 and "GATEKEEPER PASSED" in r_idem_ng.stdout, r_idem_ng.stdout + r_idem_ng.stderr

        # Edit AGENTS.md with decisions.md 10s older -> FAIL (HARNESS_INSTALL protected once has_real_entries=True)
        agents_f = folder / "AGENTS.md"
        agents_f.write_text(agents_f.read_text(encoding="utf-8") + "\n# local rule edit\n", encoding="utf-8")
        now2 = time.time()
        os.utime(log_f, (now2 - 10, now2 - 10))
        r4 = run(["/bin/bash", "./.context/verify-gate.sh"], folder)
        assert r4.returncode != 0 and "modified after .context/decisions.md" in r4.stdout and "AGENTS.md" in r4.stdout, r4.stdout

    print("PASS T10: Uncommitted repeat governance edits (tracked/untracked) and non-Git mtime + __pycache__ immunity")


def main():
    test_t1_anticheat_doc_immunity_and_unborn()
    test_t2_scoped_verify_and_active_plans()
    test_t3_decisions_tracked_mode0_stealth_gov_docs()
    test_t4_verify_cmd_parser_and_tbd_guard()
    test_t5_upgrade_coexistence_migration_and_scrubber()
    test_t6_mode_preservation_coalescing_and_nongit()
    test_t7_native_git_rollback_and_stealth_gov()
    test_t8_worktree_legacy_precommit_and_custom_hooks()
    test_t9_precommit_staged_isolation()
    test_t10_uncommitted_repeat_gov_edits_and_nongit_mtime()
    print("\nALL 10 E2E HARNESS TESTS PASSED.")


if __name__ == "__main__":
    main()
