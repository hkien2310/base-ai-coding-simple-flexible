#!/usr/bin/env python3
"""
Mechanical Blast-Radius & Caller Integrity Checker for AI Coding Agents.
Universal Project Harness (coding-base).

Priority 1: Query .code-review-graph/graph.db (SQLite) for modified nodes, callers, and test references.
Fallback: Parse git diff line ranges, locate enclosing function/method definitions, and query callers via git grep / ripgrep.
Cross-Repo: Scan consumer repositories (CROSS_REPO_CONSUMERS) for impacted call sites.

Guarantees (Zero-Crash Contract):
- Zero crashes on non-git directory, empty diff, non-code files, or missing/corrupt graph.db.
- Distinguishes fatal signature breaks from internal body modifications.
- Enforces caller & test updates across git diff.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Supported source file extensions for code symbol extraction
CODE_EXTENSIONS = {
    ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".cs", ".cpp", ".c", ".h"
}

# Ignore list for common language keywords and standard methods
IGNORED_SYMBOLS = {
    "if", "for", "while", "switch", "catch", "return", "throw", "assert",
    "constructor", "render", "setup", "build", "run", "execute", "handle",
    "get", "set", "id", "name", "toString", "equals", "hashCode", "clone",
    "componentDidMount", "componentWillUnmount", "ngOnInit", "ngOnDestroy",
    "main", "init", "close", "open", "read", "write", "export", "default"
}

# Statements that cannot be method definitions
STATEMENT_KEYWORDS = {
    "return", "throw", "new", "super", "this", "yield", "await", "import", "package", "from"
}

# Regex heuristics for detecting method/function definitions across languages
FUNCTION_PATTERNS = [
    # Java / Kotlin / C# / C++ methods with explicit modifiers
    re.compile(
        r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|static|final|synchronized|abstract|default|async|override)\s+)+"
        r"(?:[\w<>\[\],\s\?]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*\{?"
    ),
    # Package-private or constructor methods (no explicit modifier, but has valid type or constructor)
    re.compile(
        r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:[A-Z][\w<>\[\],\s\?]*|void|boolean|int|long|double|float|byte|short|char)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*\{?"
    ),
    # TypeScript / JavaScript functions and arrow functions
    re.compile(
        r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\s+([a-zA-Z_][a-zA-Z0-9_]*)|"
        r"(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s*)?(?:<[^>]+>\s*)?\([^)]*\)(?:\s*:\s*[\w<>\[\],\s\?|&]+)?\s*=>|"
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{)"
    ),
    # Python functions
    re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
    # Go functions
    re.compile(r"^func\s+(?:\([^)]+\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\("),
    # Rust functions
    re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*\("),
]

# Regex heuristics for detecting enclosing class, enum, interface, or type definitions (fallback)
TYPE_PATTERNS = [
    # Java / Kotlin / C# / TS class, enum, interface, record
    re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract|sealed)\s+)*(?:class|enum|interface|record)\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    # TypeScript / JavaScript class, interface, enum, type
    re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:class|interface|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    re.compile(r"^\s*(?:export\s+)?type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*="),
    # Python class
    re.compile(r"^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?:"),
    # Rust struct, enum, trait
    re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?(?:struct|enum|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    # Go type struct / interface
    re.compile(r"^type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:struct|interface)"),
]

# Pattern for API endpoint URLs
ENDPOINT_PATTERN = re.compile(r"/(?:api|v[0-9]+)/[a-zA-Z0-9_\-\/]+")


def is_git_repo(repo_root: Path) -> bool:
    """Check if directory is inside a valid git work tree."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_git_diff_ranges(repo_root: Path, base: Optional[str] = None) -> Dict[str, List[Tuple[int, int]]]:
    """
    Parse git diff into mapping: relative_file_path -> list of (start_line, end_line) ranges.
    Diffs working tree against HEAD or specified base.
    """
    cmd = ["git", "diff", "--unified=0"]
    if base:
        cmd.append(base)
    cmd.append("--")

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        diff_text = res.stdout
    except Exception:
        return {}

    # If unstaged diff is empty and no base specified, also check staged changes
    if not diff_text.strip() and not base:
        try:
            res_cached = subprocess.run(
                ["git", "diff", "--cached", "--unified=0", "--"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            diff_text = res_cached.stdout
        except Exception:
            pass

    ranges: Dict[str, List[Tuple[int, int]]] = {}
    current_file: Optional[str] = None
    last_a_file: Optional[str] = None
    is_deleted = False

    file_pattern_b = re.compile(r"^\+\+\+ b/(.+)$")
    file_pattern_null = re.compile(r"^\+\+\+ /dev/null$")
    file_pattern_a = re.compile(r"^--- a/(.+)$")
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    for line in diff_text.splitlines():
        ma = file_pattern_a.match(line)
        if ma:
            last_a_file = ma.group(1).strip()
            continue
        mb = file_pattern_b.match(line)
        if mb:
            current_file = mb.group(1).strip()
            is_deleted = False
            continue
        mnull = file_pattern_null.match(line)
        if mnull:
            current_file = last_a_file
            is_deleted = True
            continue
        hm = hunk_pattern.match(line)
        if hm and current_file:
            if is_deleted:
                old_start = int(hm.group(1))
                old_count = int(hm.group(2)) if hm.group(2) is not None else 1
                old_end = old_start if old_count == 0 else old_start + old_count - 1
                ranges.setdefault(current_file, []).append((old_start, old_end))
            else:
                start = int(hm.group(3))
                count = int(hm.group(4)) if hm.group(4) is not None else 1
                end = start if count == 0 else start + count - 1
                ranges.setdefault(current_file, []).append((start, end))

    return ranges


def get_changed_files(repo_root: Path, base: Optional[str] = None) -> Set[str]:
    """Get list of changed files relative to repo root."""
    files: Set[str] = set()
    cmd = ["git", "diff", "--name-only"]
    if base:
        cmd.append(base)
    cmd.append("--")
    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        for line in res.stdout.splitlines():
            f = line.strip()
            if f:
                files.add(f)
    except Exception:
        pass

    # Also include staged if base not specified
    if not base:
        try:
            res_cached = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            for line in res_cached.stdout.splitlines():
                f = line.strip()
                if f:
                    files.add(f)
        except Exception:
            pass

    return files


def parse_cross_repo_consumers(repo_root: Path, consumers_arg: Optional[str] = None) -> List[Path]:
    """Parse list of sibling consumer repositories from CLI or .context/project.md."""
    raw_paths: List[str] = []

    if consumers_arg:
        raw_paths = [p.strip() for p in consumers_arg.split(",") if p.strip()]
    else:
        project_md = repo_root / ".context" / "project.md"
        if project_md.is_file():
            try:
                with open(project_md, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if "CROSS_REPO_CONSUMERS" in line:
                            m = re.search(r"CROSS_REPO_CONSUMERS.*?[:=]\s*[`'\"]?([^`'\"\n\r]+)[`'\"]?", line)
                            if m:
                                raw_paths = [p.strip() for p in m.group(1).split(",") if p.strip()]
                                break
            except Exception:
                pass

    resolved: List[Path] = []
    for raw in raw_paths:
        p = (repo_root / raw).resolve()
        if p.is_dir():
            resolved.append(p)
    return resolved


# ---------------------------------------------------------------------------
# Priority 1: SQLite Call Graph Engine (.code-review-graph/graph.db)
# ---------------------------------------------------------------------------


def analyze_with_graph_db(
    db_path: Path,
    repo_root: Path,
    diff_ranges: Dict[str, List[Tuple[int, int]]],
    changed_files: Set[str],
) -> Dict[str, Any]:
    """Query .code-review-graph/graph.db for changed nodes and un-updated callers."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()

    changed_nodes: List[Dict[str, Any]] = []
    un_updated_callers: List[Dict[str, Any]] = []
    missing_test_updates: List[Dict[str, Any]] = []
    tests_updated: List[Dict[str, Any]] = []
    impacted_files: Set[str] = set()

    for rel_path, ranges in diff_ranges.items():
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in CODE_EXTENSIONS:
            continue

        # Nodes matching this file
        nodes = c.execute(
            """
            SELECT id, kind, name, qualified_name, file_path, line_start, line_end, is_test
            FROM nodes
            WHERE (file_path = ? OR file_path LIKE ? OR file_path LIKE ?)
              AND line_start IS NOT NULL AND line_end IS NOT NULL
              AND kind IN ('Function', 'Method', 'Class', 'Endpoint')
              AND is_test = 0
            """,
            (rel_path, f"%/{rel_path}", f"%\\{rel_path}"),
        ).fetchall()

        for node_row in nodes:
            nid, kind, name, qn, fp, ls, le, is_test = node_row
            # Check overlap with any changed range in this file
            overlaps = any(ls <= end and le >= start for start, end in ranges)
            if not overlaps:
                continue

            # Detect whether signature line itself changed
            sig_changed = any(ls >= start and ls <= end for start, end in ranges)

            node_dict = {
                "id": nid,
                "kind": kind,
                "name": name,
                "symbol": name,
                "qualified_name": qn,
                "file_path": rel_path,
                "defined_in": rel_path,
                "line_start": ls,
                "line_end": le,
                "signature_changed": sig_changed,
            }
            changed_nodes.append(node_dict)

            # Query callers and test edges pointing to this node
            edges = c.execute(
                """
                SELECT e.source_qualified, e.kind, e.file_path, e.line, n.name, n.kind, n.is_test
                FROM edges e
                LEFT JOIN nodes n ON e.source_qualified = n.qualified_name
                WHERE e.target_qualified = ?
                  AND e.kind IN ('CALLS', 'REFERENCES', 'INJECTS', 'TESTED_BY')
                """,
                (qn,),
            ).fetchall()

            node_callers = []
            node_tests = []
            for edge in edges:
                src_qn, ekind, edge_file, line_no, src_name, src_kind, src_is_test = edge
                # Normalize edge_file to repo-relative path if absolute
                rel_edge_file = edge_file
                if edge_file.startswith(str(repo_root)):
                    rel_edge_file = os.path.relpath(edge_file, str(repo_root))

                impacted_files.add(rel_edge_file)

                # Check if caller is test
                is_test_caller = (
                    src_is_test == 1
                    or ekind == "TESTED_BY"
                    or any(t in rel_edge_file.lower() for t in ["test", "spec", "__tests__"])
                )

                if is_test_caller:
                    node_tests.append({"file": rel_edge_file, "line": line_no, "source": src_name or src_qn})
                else:
                    # External production caller (different file)
                    if rel_edge_file != rel_path:
                        node_callers.append(
                            {"file": rel_edge_file, "line": line_no, "source": src_name or src_qn}
                        )

            # Check if production callers are present in git diff
            for caller in node_callers:
                if caller["file"] not in changed_files:
                    un_updated_callers.append(
                        {
                            "symbol": f"{name} ({kind})",
                            "defined_in": rel_path,
                            "caller_file": caller["file"],
                            "caller_line": caller["line"],
                            "caller_symbol": caller["source"],
                            "signature_changed": sig_changed,
                        }
                    )

            # Check test coverage update
            if node_tests:
                updated = [t for t in node_tests if t["file"] in changed_files]
                if updated:
                    for u in updated:
                        tests_updated.append({"symbol": name, "file": u["file"]})
                else:
                    missing_test_updates.append(
                        {
                            "symbol": f"{name} ({kind})",
                            "defined_in": rel_path,
                            "existing_tests": [t["file"] for t in node_tests[:3]],
                        }
                    )

    conn.close()

    return {
        "engine": "graph_db",
        "changed_nodes": changed_nodes,
        "symbols_modified": changed_nodes,
        "impacted_files": list(impacted_files),
        "un_updated_callers": un_updated_callers,
        "unupdated_callers": un_updated_callers,
        "tests_updated": tests_updated,
        "missing_test_updates": missing_test_updates,
    }


# ---------------------------------------------------------------------------
# Fallback Engine: Git Grep / Ripgrep Heuristics
# ---------------------------------------------------------------------------


def check_function_signature_at(file_lines: List[str], i: int) -> Optional[Tuple[str, int, bool, int]]:
    """
    Check if a function/method signature begins at line index i (single-line or multi-line).
    Returns (symbol_name, line_number, is_private, sig_end_line) or None.
    """
    line = file_lines[i]
    stripped = line.strip()
    if not stripped or stripped.startswith(("//", "/*", "*", "#")):
        return None
    first_word = stripped.split()[0]
    if first_word in STATEMENT_KEYWORDS:
        return None

    # 1. Direct single-line pattern test
    for pattern in FUNCTION_PATTERNS:
        m = pattern.match(line)
        if m:
            for g in m.groups():
                if g and g not in IGNORED_SYMBOLS and g not in STATEMENT_KEYWORDS:
                    is_private = "private " in line or g.startswith("_")
                    sig_end = i + 1
                    if line.count("(") > line.count(")"):
                        for k in range(i + 1, min(len(file_lines), i + 20)):
                            sig_end = k + 1
                            if ")" in file_lines[k]:
                                break
                    return (g, i + 1, is_private, sig_end)

    # 2. Multi-line signature test: assemble lines until ')' or '{' or ';' (up to 20 lines)
    if any(k in line for k in ["public", "private", "protected", "static", "final", "def ", "function", "func ", "fn "]) or "(" in line:
        joined_parts = [stripped]
        for k in range(i + 1, min(len(file_lines), i + 20)):
            sub_line = file_lines[k].strip()
            if not sub_line or sub_line.startswith(("//", "/*", "*", "#")):
                continue
            joined_parts.append(sub_line)
            joined_text = " ".join(joined_parts)
            for pattern in FUNCTION_PATTERNS:
                m = pattern.match(joined_text)
                if m:
                    for g in m.groups():
                        if g and g not in IGNORED_SYMBOLS and g not in STATEMENT_KEYWORDS:
                            is_private = "private " in joined_text or g.startswith("_")
                            sig_end = k + 1
                            return (g, i + 1, is_private, sig_end)
            if ")" in sub_line or "{" in sub_line or ";" in sub_line:
                break

    return None


def extract_enclosing_function_fallback(file_lines: List[str], target_line: int) -> Optional[Tuple[str, int, bool, int]]:
    """Scan upwards from target_line to locate enclosing function definition.
    Returns (symbol_name, line_number, is_private, sig_end_line).
    """
    start_idx = min(target_line - 1, len(file_lines) - 1)
    if start_idx < 0:
        return None

    # If changed line starts with decorator/annotation '@', scan downwards first to locate decorated function
    if file_lines[start_idx].strip().startswith("@"):
        for down_i in range(start_idx + 1, min(len(file_lines), start_idx + 10)):
            d_line = file_lines[down_i].strip()
            if not d_line or d_line.startswith(("//", "/*", "*", "#")):
                continue
            if d_line.startswith("@"):
                continue
            res = check_function_signature_at(file_lines, down_i)
            if res:
                return res
            break

    min_idx = max(0, start_idx - 120)
    for i in range(start_idx, min_idx - 1, -1):
        res = check_function_signature_at(file_lines, i)
        if res:
            return res
    return None


def extract_enclosing_type_fallback(file_lines: List[str], target_line: int) -> Optional[Tuple[str, int, bool, int]]:
    """Scan upwards from target_line to locate enclosing class/interface/enum/type definition.
    Returns (type_name, line_number, is_private, sig_end_line).
    """
    start_idx = min(target_line - 1, len(file_lines) - 1)
    min_idx = max(0, start_idx - 150)

    for i in range(start_idx, min_idx - 1, -1):
        line = file_lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "#")):
            continue
        first_word = stripped.split()[0]
        if first_word in STATEMENT_KEYWORDS:
            continue

        for pattern in TYPE_PATTERNS:
            m = pattern.match(line)
            if m:
                for g in m.groups():
                    if g and g not in IGNORED_SYMBOLS and g not in STATEMENT_KEYWORDS:
                        is_private = "private " in line or g.startswith("_")
                        return (g, i + 1, is_private, i + 1)
    return None


def query_callers_fallback(
    repo_root: Path, symbol: str, defined_file: str, defined_line: int, is_private: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Query callers and tests using git grep or ripgrep."""
    callers = []
    tests = []

    has_rg = shutil.which("rg") is not None
    cmd = (
        ["rg", "-n", "-w", symbol, "--glob", "!**/{target,node_modules,dist,build,.git,.agents,.code-review-graph}/*"]
        if has_rg
        else ["git", "grep", "-n", "-w", symbol, "--"]
    )

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        output = res.stdout
    except Exception:
        return ([], [])

    for line in output.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        rel_file, line_str, content = parts[0].strip(), parts[1].strip(), parts[2].strip()
        try:
            line_no = int(line_str)
        except ValueError:
            continue

        # Skip definition line itself
        if rel_file == defined_file and abs(line_no - defined_line) <= 1:
            continue
        # Skip comments or imports
        if content.startswith(("//", "/*", "*", "#", "import ", "from ")):
            continue
        # Skip definition lines when defined_file is empty (e.g. pre-edit mode symbol lookup)
        if not defined_file:
            stripped_c = content.strip()
            is_defining_symbol = False
            for p in FUNCTION_PATTERNS:
                pm = p.match(stripped_c)
                if pm and any(g == symbol for g in pm.groups()):
                    is_defining_symbol = True
                    break
            if is_defining_symbol:
                continue

        is_test = any(t in rel_file.lower() for t in ["test", "spec", "__tests__"])
        record = {"file": rel_file, "line": line_no, "content": content[:80]}
        if is_test:
            tests.append(record)
        else:
            # If method is private, only calls within the same file are valid callers
            if is_private and rel_file != defined_file:
                continue
            if rel_file != defined_file:
                callers.append(record)

    return (callers, tests)


def analyze_with_fallback(
    repo_root: Path,
    diff_ranges: Dict[str, List[Tuple[int, int]]],
    changed_files: Set[str],
    strict: bool = False,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Run fallback heuristic blast-radius analysis."""
    changed_symbols: List[Dict[str, Any]] = []
    un_updated_callers: List[Dict[str, Any]] = []
    missing_test_updates: List[Dict[str, Any]] = []
    tests_updated: List[Dict[str, Any]] = []
    impacted_files: Set[str] = set()

    MAX_BODY_QUERIES = 999999 if strict else 25
    body_queries_count = 0

    for rel_path, ranges in diff_ranges.items():
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in CODE_EXTENSIONS:
            continue

        abs_file = repo_root / rel_path
        if not abs_file.is_file():
            # File was deleted in working tree / git diff!
            # Query git show HEAD:<rel_path> to extract symbols that existed in the file
            cmd_show = ["git", "show", f"{base or 'HEAD'}:{rel_path}"]
            try:
                res_show = subprocess.run(
                    cmd_show,
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                )
                if res_show.returncode != 0:
                    continue
                old_lines = res_show.stdout.splitlines(keepends=True)
            except Exception:
                continue

            deleted_file_symbols: Set[str] = set()
            for idx in range(len(old_lines)):
                target_info = extract_enclosing_function_fallback(old_lines, idx + 1)
                if not target_info:
                    target_info = extract_enclosing_type_fallback(old_lines, idx + 1)
                if target_info and target_info[0] not in deleted_file_symbols:
                    sym_name, sym_line, is_private = target_info[0], target_info[1], target_info[2]
                    deleted_file_symbols.add(sym_name)

                    sym_dict = {
                        "symbol": sym_name,
                        "name": sym_name,
                        "defined_in": rel_path,
                        "file_path": rel_path,
                        "line": sym_line,
                        "is_private": is_private,
                        "signature_changed": True,  # Deletion is always a breaking signature change
                        "deleted": True,
                    }
                    changed_symbols.append(sym_dict)

                    callers, tests = query_callers_fallback(
                        repo_root, sym_name, rel_path, sym_line, is_private=is_private
                    )

                    for c in callers:
                        impacted_files.add(c["file"])
                        if c["file"] not in changed_files:
                            un_updated_callers.append({
                                "symbol": sym_name,
                                "defined_in": rel_path,
                                "caller_file": c["file"],
                                "caller_line": c["line"],
                                "caller_symbol": c.get("content", ""),
                                "signature_changed": True,
                            })

                    for t in tests:
                        impacted_files.add(t["file"])

                    if tests:
                        updated = [t for t in tests if t["file"] in changed_files]
                        if updated:
                            for u in updated:
                                tests_updated.append({"symbol": sym_name, "file": u["file"]})
                        else:
                            missing_test_updates.append({
                                "symbol": sym_name,
                                "defined_in": rel_path,
                                "existing_tests": list({t["file"] for t in tests})[:3],
                            })

            for line_idx, line_content in enumerate(old_lines):
                for ep_match in ENDPOINT_PATTERN.findall(line_content):
                    ep = ep_match.rstrip("',\"`")
                    if ep and ep not in deleted_file_symbols and len(ep) > 6:
                        deleted_file_symbols.add(ep)
                        changed_symbols.append({
                            "symbol": ep,
                            "name": ep,
                            "defined_in": rel_path,
                            "file_path": rel_path,
                            "line": line_idx + 1,
                            "is_private": False,
                            "signature_changed": True,
                            "deleted": True,
                        })
            continue

        try:
            with open(abs_file, "r", encoding="utf-8", errors="replace") as f:
                file_lines = f.readlines()
        except Exception:
            continue

        found_symbols_in_file: Set[str] = set()
        for start, end in ranges:
            target_info = extract_enclosing_function_fallback(file_lines, start)
            if not target_info:
                # If outside a function/method (e.g. enum constants, DTO fields, class decl), find enclosing type
                target_info = extract_enclosing_type_fallback(file_lines, start)

            if target_info and target_info[0] not in found_symbols_in_file:
                sym_name, sym_line, is_private = target_info[0], target_info[1], target_info[2]
                sig_end_line = target_info[3] if len(target_info) > 3 else sym_line
                found_symbols_in_file.add(sym_name)

                # Signature changed if changed ranges overlap the signature lines [sym_line, sig_end_line]
                sig_changed = any(s <= sig_end_line and e >= sym_line for s, e in ranges)

                sym_dict = {
                    "symbol": sym_name,
                    "name": sym_name,
                    "defined_in": rel_path,
                    "file_path": rel_path,
                    "line": sym_line,
                    "is_private": is_private,
                    "signature_changed": sig_changed,
                }
                changed_symbols.append(sym_dict)

                if not sig_changed and body_queries_count >= MAX_BODY_QUERIES:
                    # Skip caller query for excess body-only changes on large diffs
                    continue

                if not sig_changed:
                    body_queries_count += 1

                callers, tests = query_callers_fallback(repo_root, sym_name, rel_path, sym_line, is_private=is_private)

                for c in callers:
                    impacted_files.add(c["file"])
                    if c["file"] not in changed_files:
                        un_updated_callers.append({
                            "symbol": sym_name,
                            "defined_in": rel_path,
                            "caller_file": c["file"],
                            "caller_line": c["line"],
                            "caller_symbol": c.get("content", ""),
                            "signature_changed": sig_changed,
                        })

                for t in tests:
                    impacted_files.add(t["file"])

                if tests:
                    updated = [t for t in tests if t["file"] in changed_files]
                    if updated:
                        for u in updated:
                            tests_updated.append({"symbol": sym_name, "file": u["file"]})
                    else:
                        missing_test_updates.append({
                            "symbol": sym_name,
                            "defined_in": rel_path,
                            "existing_tests": list({t["file"] for t in tests})[:3],
                        })

            # Also detect API endpoint URLs on modified lines for cross-repo impact detection
            for line_idx in range(start - 1, min(end, len(file_lines))):
                line_content = file_lines[line_idx]
                for ep_match in ENDPOINT_PATTERN.findall(line_content):
                    ep = ep_match.rstrip("',\"`")
                    if ep and ep not in found_symbols_in_file and len(ep) > 6:
                        found_symbols_in_file.add(ep)
                        changed_symbols.append({
                            "symbol": ep,
                            "name": ep,
                            "defined_in": rel_path,
                            "file_path": rel_path,
                            "line": line_idx + 1,
                            "is_private": False,
                            "signature_changed": True,
                        })

    return {
        "engine": "git_grep_fallback",
        "changed_nodes": changed_symbols,
        "symbols_modified": changed_symbols,
        "impacted_files": list(impacted_files),
        "un_updated_callers": un_updated_callers,
        "unupdated_callers": un_updated_callers,
        "tests_updated": tests_updated,
        "missing_test_updates": missing_test_updates,
    }


# ---------------------------------------------------------------------------
# Cross-Repo Impact Scanner
# ---------------------------------------------------------------------------


def extract_deleted_symbols_from_diff(repo_root: Path, base: Optional[str] = None) -> List[str]:
    """
    Extract deleted or replaced symbols (API endpoints, DTO fields, Enum literals, function names)
    from '-' lines in git diff to verify external consumer repositories.
    """
    cmd = ["git", "diff", "--unified=0"]
    if base:
        cmd.append(base)
    cmd.append("--")

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        diff_text = res.stdout
    except Exception:
        return []

    if not diff_text.strip() and not base:
        try:
            res_cached = subprocess.run(
                ["git", "diff", "--cached", "--unified=0", "--"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            diff_text = res_cached.stdout
        except Exception:
            pass

    deleted_symbols: Set[str] = set()
    enum_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,})\s*[,;]?$")
    field_pattern_java = re.compile(r"^\s*(?:private|protected|public)?\s+(?:[\w<>\[\],\s\?]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;")
    field_pattern_ts = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\??\s*:\s*[\w<>\[\],\s\?|&]+;?")

    for line in diff_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if not content:
                continue

            # 1. API endpoint URLs
            for ep_match in ENDPOINT_PATTERN.findall(content):
                ep = ep_match.rstrip("',\"`")
                if len(ep) > 6:
                    deleted_symbols.add(ep)

            # 2. Enum constants
            em = enum_pattern.match(content)
            if em:
                c = em.group(1)
                if c not in IGNORED_SYMBOLS and len(c) > 2:
                    deleted_symbols.add(c)

            # 3. DTO field definitions
            fm_j = field_pattern_java.match(content)
            if fm_j:
                f = fm_j.group(1)
                if f not in IGNORED_SYMBOLS and f not in STATEMENT_KEYWORDS and len(f) > 2:
                    deleted_symbols.add(f)
            fm_ts = field_pattern_ts.match(content)
            if fm_ts:
                f = fm_ts.group(1)
                if f not in IGNORED_SYMBOLS and f not in STATEMENT_KEYWORDS and len(f) > 2:
                    deleted_symbols.add(f)

            # 4. Method / function names
            for pattern in FUNCTION_PATTERNS:
                m = pattern.match(content)
                if m:
                    for g in m.groups():
                        if g and g not in IGNORED_SYMBOLS and g not in STATEMENT_KEYWORDS and len(g) > 2:
                            deleted_symbols.add(g)

    return list(deleted_symbols)


def scan_cross_repo_consumers(
    consumer_repos: List[Path],
    symbols: List[str],
    deleted_symbols: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Scan external consumer repositories for occurrences of changed symbols."""
    impacts: List[Dict[str, Any]] = []
    has_rg = shutil.which("rg") is not None
    deleted_set = deleted_symbols or set()

    for consumer in consumer_repos:
        consumer_name = consumer.name
        for sym in symbols:
            if not sym or sym in IGNORED_SYMBOLS:
                continue

            is_endpoint = sym.startswith("/")
            flag = "-F" if is_endpoint else "-w"

            cmd = (
                ["rg", "-n", flag, sym, "--glob", "!**/{node_modules,dist,build,.git,target}/*"]
                if has_rg
                else ["git", "grep", "-n", flag, sym, "--"]
            )

            try:
                res = subprocess.run(
                    cmd,
                    cwd=str(consumer),
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in res.stdout.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        rel_file = parts[0].strip()
                        try:
                            lno = int(parts[1].strip())
                        except ValueError:
                            continue
                        content = parts[2].strip()
                        impacts.append({
                            "consumer": consumer_name,
                            "file": rel_file,
                            "line": lno,
                            "symbol": sym,
                            "content": content[:100],
                            "is_deleted_contract": sym in deleted_set,
                        })
            except Exception:
                pass

    return impacts


# ---------------------------------------------------------------------------
# Main Orchestration & Output Formatters
# ---------------------------------------------------------------------------


def run_blast_radius_check(
    repo_root: Path,
    base: Optional[str] = None,
    mode: str = "gate",
    output_format: str = "text",
    strict: bool = False,
    target_symbol: Optional[str] = None,
    consumers_arg: Optional[str] = None,
    files_arg: Optional[str] = None,
) -> int:
    """Execute blast-radius verification with dual engine and zero-crash contract."""
    is_json = (mode == "json" or output_format == "json")

    # 1. Graceful check for non-git repository
    if not is_git_repo(repo_root):
        if is_json:
            result_payload = {
                "status": "PASS",
                "engine": "none",
                "message": "Not inside a git repository. Blast radius check bypassed cleanly.",
                "symbols_modified": [],
                "unupdated_callers": [],
                "tests_updated": [],
                "missing_test_updates": [],
                "cross_repo_impacts": [],
            }
            print(json.dumps(result_payload, indent=2))
        else:
            print("ℹ️  [BLAST RADIUS] Not inside a git repository. Skipping check cleanly.")
        return 0

    # 2. If explicit target_symbol is provided (e.g. pre-edit inspection)
    if target_symbol:
        graph_db_path = repo_root / ".code-review-graph" / "graph.db"
        use_graph_db = graph_db_path.is_file() and os.access(graph_db_path, os.R_OK)
        callers = []
        tests = []
        engine_name = "git_grep_fallback"

        if use_graph_db:
            try:
                conn = sqlite3.connect(f"file:{graph_db_path}?mode=ro", uri=True)
                c = conn.cursor()
                nodes = c.execute(
                    """
                    SELECT id, kind, name, qualified_name, file_path, line_start, line_end
                    FROM nodes
                    WHERE name = ? AND kind IN ('Function', 'Method', 'Class', 'Endpoint')
                    """,
                    (target_symbol,),
                ).fetchall()
                if nodes:
                    engine_name = "graph_db"
                    for nid, nkind, nname, qn, fp, ls, le in nodes:
                        rel_fp = fp if not fp.startswith(str(repo_root)) else os.path.relpath(fp, str(repo_root))
                        edges = c.execute(
                            """
                            SELECT e.source_qualified, e.kind, e.file_path, e.line, n.name, n.kind, n.is_test
                            FROM edges e
                            LEFT JOIN nodes n ON e.source_qualified = n.qualified_name
                            WHERE e.target_qualified = ?
                              AND e.kind IN ('CALLS', 'REFERENCES', 'INJECTS', 'TESTED_BY')
                            """,
                            (qn,),
                        ).fetchall()
                        for edge in edges:
                            src_qn, ekind, edge_file, line_no, src_name, src_kind, src_is_test = edge
                            rel_edge_file = edge_file if not edge_file.startswith(str(repo_root)) else os.path.relpath(edge_file, str(repo_root))
                            is_test_caller = (src_is_test == 1 or ekind == "TESTED_BY" or any(t in rel_edge_file.lower() for t in ["test", "spec", "__tests__"]))
                            rec = {"file": rel_edge_file, "line": line_no, "source": src_name or src_qn, "content": f"{src_name or src_qn} ({ekind})"}
                            if is_test_caller:
                                tests.append(rec)
                            elif rel_edge_file != rel_fp:
                                callers.append(rec)
                conn.close()
            except Exception:
                pass

        if not callers and not tests:
            callers, tests = query_callers_fallback(repo_root, target_symbol, "", 0)
            engine_name = "git_grep_fallback"

        consumer_repos = parse_cross_repo_consumers(repo_root, consumers_arg)
        cross_impacts = scan_cross_repo_consumers(consumer_repos, [target_symbol])

        if is_json:
            print(json.dumps({
                "status": "PASS",
                "engine": engine_name,
                "target_symbol": target_symbol,
                "symbols_modified": [{"symbol": target_symbol}],
                "unupdated_callers": callers,
                "tests_updated": tests,
                "missing_test_updates": [],
                "cross_repo_impacts": cross_impacts,
            }, indent=2))
        else:
            title = "CROSS-REPO CONSUMER AUDIT" if mode == "cross-repo" else "PRE-EDIT SYMBOL AUDIT"
            print(f"\n🔍 [{title}] Symbol: {target_symbol} (Engine: {engine_name})")
            print(f"   Internal Callers: {len(callers)}")
            for c in callers[:10]:
                print(f"   - {c['file']}:{c['line']} -> {c.get('content', '')}")
            print(f"   Test References: {len(tests)}")
            for t in tests[:5]:
                print(f"   - {t['file']}:{t['line']}")
            if cross_impacts:
                print(f"\n🌐 [CROSS-REPO CONSUMERS] ({len(cross_impacts)} occurrences):")
                for ci in cross_impacts[:10]:
                    print(f"   - [{ci['consumer']}] {ci['file']}:{ci['line']} -> {ci['content']}")
                print("   👉 Verify contract documentation (fe-guide-combined.md) and consumer compatibility.")
            elif consumer_repos:
                print(f"\n🌐 [CROSS-REPO CONSUMERS] 0 occurrences found across {len(consumer_repos)} consumer repos.")
        return 0

    # 3. Extract changed files and diff ranges
    diff_ranges = get_git_diff_ranges(repo_root, base)
    changed_files = get_changed_files(repo_root, base)

    # Optional multi-session file scoping (via --files or VERIFY_FILES env var)
    scoped_files_raw = files_arg or os.environ.get("VERIFY_FILES", "")
    if scoped_files_raw.strip():
        scoped_set = {f.strip().lstrip("./") for f in re.split(r"[\s,]+", scoped_files_raw.strip()) if f.strip()}
        diff_ranges = {k: v for k, v in diff_ranges.items() if k in scoped_set}
        changed_files = {f for f in changed_files if f in scoped_set}

    # Clean diff check or non-code only files
    has_code_changes = any(os.path.splitext(f)[1].lower() in CODE_EXTENSIONS for f in diff_ranges)
    if not diff_ranges or not has_code_changes:
        msg = (
            "No code changes detected in git diff. Use --symbol <name> to scan a specific symbol across consumer repos."
            if mode == "cross-repo"
            else "No code changes detected in git diff. Blast radius clean."
        )
        if is_json:
            print(json.dumps({
                "status": "PASS",
                "engine": "none",
                "message": msg,
                "symbols_modified": [],
                "unupdated_callers": [],
                "tests_updated": [],
                "missing_test_updates": [],
                "cross_repo_impacts": [],
            }, indent=2))
        else:
            if mode == "cross-repo":
                print(f"ℹ️  [CROSS-REPO] {msg}")
            else:
                print(f"✅ [BLAST RADIUS] {msg}")
        return 0

    # 4. Choose engine: Priority 1 is graph.db, Fallback is git-grep
    graph_db_path = repo_root / ".code-review-graph" / "graph.db"
    use_graph_db = graph_db_path.is_file() and os.access(graph_db_path, os.R_OK)

    if use_graph_db:
        try:
            result = analyze_with_graph_db(graph_db_path, repo_root, diff_ranges, changed_files)
        except Exception as e:
            print(f"⚠️  [BLAST RADIUS] Failed querying graph.db ({e}). Falling back to git grep...")
            result = analyze_with_fallback(repo_root, diff_ranges, changed_files, strict=strict, base=base)
    else:
        result = analyze_with_fallback(repo_root, diff_ranges, changed_files, strict=strict, base=base)

    # 5. Check Cross-Repo Consumers if configured
    consumer_repos = parse_cross_repo_consumers(repo_root, consumers_arg)
    changed_sym_names = [n.get("name") or n.get("symbol") for n in result["changed_nodes"] if (n.get("name") or n.get("symbol"))]
    deleted_diff_symbols = extract_deleted_symbols_from_diff(repo_root, base)
    all_scan_symbols = list(dict.fromkeys(changed_sym_names + deleted_diff_symbols))

    cross_impacts: List[Dict[str, Any]] = []
    if consumer_repos and all_scan_symbols:
        cross_impacts = scan_cross_repo_consumers(consumer_repos, all_scan_symbols, deleted_symbols=set(deleted_diff_symbols))
    result["cross_repo_impacts"] = cross_impacts

    # 6. Evaluate Blocking vs Warning Conditions
    fatal_callers = [c for c in result["un_updated_callers"] if c.get("signature_changed", True)]
    body_callers = [c for c in result["un_updated_callers"] if not c.get("signature_changed", False)]

    has_fatal = False
    if strict and (result["un_updated_callers"] or result["missing_test_updates"]):
        has_fatal = True
    elif mode == "gate" and fatal_callers:
        has_fatal = True

    status_str = "FAIL" if has_fatal else ("WARN" if (result["un_updated_callers"] or result["missing_test_updates"] or cross_impacts) else "PASS")
    result["status"] = status_str

    # 7. JSON output mode
    if is_json:
        payload = {
            "status": status_str,
            "engine": result["engine"],
            "symbols_modified": result["symbols_modified"],
            "unupdated_callers": result["un_updated_callers"],
            "tests_updated": result["tests_updated"],
            "missing_test_updates": result["missing_test_updates"],
            "cross_repo_impacts": result["cross_repo_impacts"],
            "impacted_files": result["impacted_files"],
        }
        print(json.dumps(payload, indent=2))
        return 1 if has_fatal else 0

    # 8. Formatted Terminal Report
    print(f"\n🔍 [BLAST RADIUS REPORT] Engine: {result['engine']}")
    print(f"   Changed Code Entities: {len(result['changed_nodes'])}")
    print(f"   Total Impacted Files: {len(result['impacted_files'])}")

    for node in result["changed_nodes"][:5]:
        sym = node.get("name") or node.get("symbol")
        fp = node.get("file_path") or node.get("defined_in")
        sig_info = " (SIGNATURE CHANGED)" if node.get("signature_changed") else " (internal body)"
        print(f"   - Modified: {sym} in {fp}{sig_info}")

    # Un-updated callers section
    if fatal_callers:
        print(f"\n❌ [FATAL BLAST RADIUS] Un-updated external callers with broken signatures ({len(fatal_callers)} call sites):")
        for c in fatal_callers[:8]:
            print(f"   ❌ {c['caller_file']}:{c['caller_line']} calls '{c['symbol']}' (defined in {c['defined_in']})")
        if len(fatal_callers) > 8:
            print(f"   ... and {len(fatal_callers) - 8} more.")

    if body_callers:
        print(f"\n⚠️  [HIGH RISK] Un-updated external callers on internal body change ({len(body_callers)} call sites):")
        for c in body_callers[:5]:
            print(f"   ⚠️  {c['caller_file']}:{c['caller_line']} calls '{c['symbol']}'")

    # Missing test updates
    if result["missing_test_updates"]:
        print(f"\n⚠️  [TEST GAP] Changed symbols with missing test updates ({len(result['missing_test_updates'])}):")
        for t in result["missing_test_updates"][:5]:
            tests_str = ", ".join(t["existing_tests"]) if "existing_tests" in t else "none"
            print(f"   ⚠️  Symbol '{t['symbol']}' in {t['defined_in']} was modified without updating existing tests ({tests_str}).")

    # Cross-repo impacts
    if cross_impacts:
        print(f"\n🌐 [CROSS-REPO CONSUMER IMPACT] Detected {len(cross_impacts)} consumer references:")
        for ci in cross_impacts[:8]:
            tag = " (DELETED/REPLACED CONTRACT)" if ci.get("is_deleted_contract") else ""
            print(f"   🌐 [{ci['consumer']}] {ci['file']}:{ci['line']} references '{ci['symbol']}'{tag}")
        print("   👉 Verify contract documentation (fe-guide-combined.md) and consumer compatibility.")

    if has_fatal:
        print("\n⛔ [GATE BLOCKED] External callers exist that were NOT updated after signature changes.")
        print("👉 Update all affected callers and rerun verify-gate.sh.")
        return 1

    print("\n✅ [BLAST RADIUS PASSED] No un-updated external callers blocking gate.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Mechanical Blast-Radius & Caller Integrity Checker")
    parser.add_argument("--repo-root", default=".", help="Path to repository root")
    parser.add_argument("--base", default=None, help="Base git ref for diff (e.g. HEAD, origin/main)")
    parser.add_argument("--mode", choices=["gate", "pre-edit", "cross-repo", "json"], default="gate", help="Execution mode")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format (text or json)")
    parser.add_argument("--strict", action="store_true", help="Fail with exit 1 if any caller or test is un-updated")
    parser.add_argument("--symbol", default=None, help="Specific symbol to query in pre-edit mode")
    parser.add_argument("--consumers", default=None, help="Comma-separated paths to consumer repos")
    parser.add_argument("--files", default=None, help="Space or comma-separated list of files to scope the diff check (multi-session isolation)")

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    sys.exit(
        run_blast_radius_check(
            repo_root=repo_root,
            base=args.base,
            mode=args.mode,
            output_format=args.format,
            strict=args.strict,
            target_symbol=args.symbol,
            consumers_arg=args.consumers,
            files_arg=args.files,
        )
    )


if __name__ == "__main__":
    main()
