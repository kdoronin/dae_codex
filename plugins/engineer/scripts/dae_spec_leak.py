#!/usr/bin/env python3
"""dae_spec_leak.py - deterministic implementation-leakage scan for specs.

Scans Gherkin/acceptance spec files for common implementation details that
should not appear in behavior contracts. It is intentionally conservative:
findings are review gates, not automatic rewrites.

Usage:
  dae_spec_leak.py [SPEC_OR_DIR ...] [--format text|json]

Exit codes:
  0  no findings
  1  implementation-leakage findings present
  2  no readable spec files found
  3  usage error
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

SPEC_NAMES = {"spec.md"}
SPEC_SUFFIXES = {".feature", ".spec.md", ".txt"}

RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "http_method_or_endpoint",
        re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b|(?:^|\s)/(?:api|v\d+|graphql)\b", re.I),
        "Specs should describe user/system actions, not HTTP methods or endpoints.",
    ),
    (
        "source_path",
        re.compile(r"\b[\w./-]+\.(py|js|ts|tsx|jsx|go|rb|java|kt|rs|cs|php)\b"),
        "Specs should not name source files or modules.",
    ),
    (
        "private_or_function_name",
        re.compile(r"\b_+[a-zA-Z]\w*\b|\b[a-z][a-z0-9]+_[a-zA-Z0-9_]+\b"),
        "Specs should not name private helpers, functions, variables, or internal identifiers.",
    ),
    (
        "framework_or_layer_term",
        re.compile(
            r"\b(controller|service|repository|handler|middleware|serializer|"
            r"database|table|column|query|ORM|DTO|schema|cache key|branch structure)\b",
            re.I,
        ),
        "Specs should not require framework, persistence, or algorithm structure.",
    ),
    (
        "class_or_component_name",
        re.compile(r"\b[A-Z][A-Za-z0-9]*(Service|Repository|Controller|Handler|Manager|Client|Factory)\b"),
        "Specs should not name implementation classes or components.",
    ),
]


def is_spec_file(path: Path) -> bool:
    name = path.name
    return name in SPEC_NAMES or any(name.endswith(suffix) for suffix in SPEC_SUFFIXES)


def iter_spec_files(paths: Iterable[str]) -> list[Path]:
    roots = [Path(p) for p in paths] or [Path("features"), Path("specs")]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and is_spec_file(root):
            files.append(root)
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and is_spec_file(path):
                    files.append(path)
    return sorted(dict.fromkeys(files))


def scan_file(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        for rule_id, pattern, message in RULES:
            for match in pattern.finditer(line):
                findings.append({
                    "file": str(path),
                    "line": number,
                    "rule": rule_id,
                    "term": match.group(0),
                    "message": message,
                })
    return findings


def render_text(findings: list[dict[str, object]]) -> str:
    if not findings:
        return "ok - no deterministic spec leakage findings"
    rows = ["implementation leakage findings:"]
    for finding in findings:
        rows.append(
            "{file}:{line}: {rule}: {term} - {message}".format(**finding)
        )
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    fmt = "text"
    args: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--format":
            if i + 1 >= len(argv):
                sys.stderr.write("missing value for --format\n")
                return 3
            fmt = argv[i + 1]
            i += 2
        elif argv[i] in {"-h", "--help"}:
            print(__doc__)
            return 0
        else:
            args.append(argv[i])
            i += 1
    if fmt not in {"text", "json"}:
        sys.stderr.write("--format must be text or json\n")
        return 3

    files = iter_spec_files(args)
    if not files:
        payload = {"status": "no-specs", "findings": []}
        if fmt == "json":
            print(json.dumps(payload, indent=2))
        else:
            print("no readable spec files found")
        return 2

    findings: list[dict[str, object]] = []
    for path in files:
        findings.extend(scan_file(path))

    payload = {"status": "fail" if findings else "ok", "findings": findings}
    if fmt == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
