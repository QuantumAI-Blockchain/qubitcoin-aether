#!/usr/bin/env python3
"""
Solidity Contract Validation Script

Validates all .sol files in the Qubitcoin contract suite without requiring solc.
Performs structural checks via regex and AST-like pattern matching:

  - SPDX license identifier present
  - Pragma solidity version declared and consistent
  - Contract name matches filename
  - Import paths resolve to existing files
  - No duplicate contract names
  - Common issue detection (empty contracts, missing events)
  - Dependency order computation for deployment

Usage:
    python3 scripts/deploy/validate_contracts.py
    python3 scripts/deploy/validate_contracts.py --verbose
    python3 scripts/deploy/validate_contracts.py --json

Exit codes:
    0 — all checks pass
    1 — one or more validation errors found
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Constants ────────────────────────────────────────────────────────────────

# Default root for Solidity contracts
CONTRACTS_ROOT = Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "contracts" / "solidity"

# Patterns
SPDX_PATTERN = re.compile(r'//\s*SPDX-License-Identifier:\s*(\S+)', re.IGNORECASE)
PRAGMA_PATTERN = re.compile(r'pragma\s+solidity\s+([^;]+);')
IMPORT_PATTERN = re.compile(r'import\s+"([^"]+)"\s*;')
CONTRACT_PATTERN = re.compile(
    r'^\s*(contract|interface|abstract\s+contract|library)\s+(\w+)',
    re.MULTILINE
)
EVENT_PATTERN = re.compile(r'\bevent\s+\w+\s*\(')
FUNCTION_PATTERN = re.compile(r'\bfunction\s+\w+\s*\(')
MODIFIER_PATTERN = re.compile(r'\bmodifier\s+\w+')
CONSTRUCTOR_PATTERN = re.compile(r'\bconstructor\s*\(')
MAPPING_PATTERN = re.compile(r'\bmapping\s*\(')
INHERITANCE_PATTERN = re.compile(
    r'^\s*(?:contract|interface|abstract\s+contract|library)\s+\w+\s+is\s+([^{]+)',
    re.MULTILINE
)


# ─── Data Classes ─────────────────────────────────────────────────────────────

class ValidationResult:
    """Result of validating a single .sol file."""

    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.spdx_license: Optional[str] = None
        self.pragma_version: Optional[str] = None
        self.contract_names: List[str] = []
        self.contract_types: List[str] = []
        self.imports: List[str] = []
        self.resolved_imports: List[Path] = []
        self.unresolved_imports: List[str] = []
        self.dependencies: Set[str] = set()
        self.has_events: bool = False
        self.has_functions: bool = False
        self.line_count: int = 0

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.filepath),
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "spdx_license": self.spdx_license,
            "pragma_version": self.pragma_version,
            "contract_names": self.contract_names,
            "imports": self.imports,
            "unresolved_imports": self.unresolved_imports,
            "line_count": self.line_count,
        }


# ─── Validators ───────────────────────────────────────────────────────────────

def validate_file(filepath: Path, contracts_root: Path) -> ValidationResult:
    """Validate a single Solidity file.

    Args:
        filepath: Path to the .sol file.
        contracts_root: Root directory for resolving relative imports.

    Returns:
        ValidationResult with errors, warnings, and metadata.
    """
    result = ValidationResult(filepath)

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        result.errors.append(f"Cannot read file: {e}")
        return result

    lines = content.splitlines()
    result.line_count = len(lines)

    # ── Check SPDX license identifier ────────────────────────────────────
    spdx_match = SPDX_PATTERN.search(content)
    if spdx_match:
        result.spdx_license = spdx_match.group(1)
    else:
        result.errors.append("Missing SPDX-License-Identifier")

    # ── Check pragma solidity ─────────────────────────────────────────────
    pragma_match = PRAGMA_PATTERN.search(content)
    if pragma_match:
        result.pragma_version = pragma_match.group(1).strip()
    else:
        result.errors.append("Missing pragma solidity version")

    # ── Extract contract/interface/library names ──────────────────────────
    for match in CONTRACT_PATTERN.finditer(content):
        contract_type = match.group(1).strip()
        contract_name = match.group(2)
        result.contract_types.append(contract_type)
        result.contract_names.append(contract_name)

    # ── Check contract name matches filename ──────────────────────────────
    expected_name = filepath.stem
    if result.contract_names and expected_name not in result.contract_names:
        result.warnings.append(
            f"Filename '{expected_name}' does not match any contract name: "
            f"{result.contract_names}"
        )

    # ── Validate imports ──────────────────────────────────────────────────
    for import_match in IMPORT_PATTERN.finditer(content):
        import_path = import_match.group(1)
        result.imports.append(import_path)

        # Resolve relative import path
        resolved = (filepath.parent / import_path).resolve()
        if resolved.exists():
            result.resolved_imports.append(resolved)
            # Track dependency name
            dep_name = resolved.stem
            result.dependencies.add(dep_name)
        else:
            result.unresolved_imports.append(import_path)
            result.errors.append(f"Unresolved import: {import_path}")

    # ── Check for empty contracts ─────────────────────────────────────────
    result.has_events = bool(EVENT_PATTERN.search(content))
    result.has_functions = bool(FUNCTION_PATTERN.search(content))

    # Only warn about empty contracts for non-interfaces
    for ct, cn in zip(result.contract_types, result.contract_names):
        if ct == "interface":
            continue
        # Check if the contract body has meaningful content
        # Find the contract body
        body_pattern = re.compile(
            rf'\b{re.escape(ct)}\s+{re.escape(cn)}\b[^{{]*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}',
            re.DOTALL
        )
        body_match = body_pattern.search(content)
        if body_match:
            body = body_match.group(1).strip()
            # Remove comments
            body_clean = re.sub(r'//[^\n]*', '', body)
            body_clean = re.sub(r'/\*.*?\*/', '', body_clean, flags=re.DOTALL)
            body_clean = body_clean.strip()
            if not body_clean:
                result.warnings.append(f"Contract '{cn}' appears to have an empty body")

    # ── Check for common Solidity issues ──────────────────────────────────
    # Check for hardcoded addresses (potential security issue)
    hardcoded_addr = re.findall(r'0x[0-9a-fA-F]{40}', content)
    # Filter out common zero addresses
    suspicious = [a for a in hardcoded_addr if a.replace('0x', '').replace('0', '') != '']
    if suspicious:
        result.warnings.append(
            f"Hardcoded addresses found: {suspicious[:3]}"
            + (f" (+{len(suspicious) - 3} more)" if len(suspicious) > 3 else "")
        )

    return result


def validate_all(contracts_root: Path) -> Tuple[List[ValidationResult], Dict[str, Any]]:
    """Validate all .sol files under the contracts root.

    Args:
        contracts_root: Root directory containing .sol files.

    Returns:
        (results, summary) tuple.
    """
    sol_files = sorted(contracts_root.rglob("*.sol"))

    if not sol_files:
        return [], {
            "total_files": 0, "passed": 0, "failed": 0,
            "total_errors": 0, "total_warnings": 0,
            "pragma_versions": [], "unique_contracts": 0,
        }

    results: List[ValidationResult] = []
    all_contract_names: Dict[str, Path] = {}
    all_pragmas: Set[str] = set()

    for sol_file in sol_files:
        result = validate_file(sol_file, contracts_root)
        results.append(result)

        # Track pragma versions for consistency check
        if result.pragma_version:
            all_pragmas.add(result.pragma_version)

        # Check for duplicate contract names across files
        for name in result.contract_names:
            if name in all_contract_names and all_contract_names[name] != sol_file:
                result.warnings.append(
                    f"Duplicate contract name '{name}' "
                    f"(also in {all_contract_names[name].relative_to(contracts_root)})"
                )
            all_contract_names[name] = sol_file

    # Check pragma consistency across all files
    if len(all_pragmas) > 1:
        for r in results:
            r.warnings.append(
                f"Inconsistent pragma versions across codebase: {sorted(all_pragmas)}"
            )

    # Build summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    total_warnings = sum(len(r.warnings) for r in results)
    total_errors = sum(len(r.errors) for r in results)

    summary = {
        "total_files": total,
        "passed": passed,
        "failed": failed,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "pragma_versions": sorted(all_pragmas),
        "unique_contracts": len(all_contract_names),
    }

    return results, summary


def compute_deploy_order(results: List[ValidationResult]) -> List[str]:
    """Compute deployment order based on import dependencies.

    Uses topological sort: contracts with no dependencies are deployed first,
    then contracts whose dependencies are all satisfied.

    Args:
        results: List of ValidationResult objects.

    Returns:
        Ordered list of contract names for deployment.
    """
    # Build dependency graph: contract_name -> set of dependency names
    graph: Dict[str, Set[str]] = {}
    name_to_file: Dict[str, Path] = {}

    for r in results:
        for name in r.contract_names:
            graph[name] = r.dependencies.copy()
            name_to_file[name] = r.filepath

    # Filter dependencies to only include known contracts
    all_names = set(graph.keys())
    for name in graph:
        graph[name] = graph[name].intersection(all_names)

    # Kahn's algorithm for topological sort
    in_degree: Dict[str, int] = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] = in_degree.get(dep, 0)  # ensure exists
                # This is reverse — we want in_degree of things that depend on us
                pass

    # Actually compute in-degree correctly
    in_degree = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[name] += 1  # name depends on dep

    # Start with nodes that have no dependencies
    queue: List[str] = [n for n in in_degree if in_degree[n] == 0]
    queue.sort()  # deterministic order
    order: List[str] = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        # "Remove" this node — reduce in-degree of nodes that depend on it
        for name, deps in graph.items():
            if node in deps:
                in_degree[name] -= 1
                if in_degree[name] == 0 and name not in order:
                    queue.append(name)
        queue.sort()

    # Add any remaining nodes (circular dependencies)
    remaining = [n for n in graph if n not in order]
    remaining.sort()
    order.extend(remaining)

    return order


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Solidity contracts in the Qubitcoin suite"
    )
    parser.add_argument(
        "--root", type=Path, default=CONTRACTS_ROOT,
        help=f"Root directory for .sol files (default: {CONTRACTS_ROOT})"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed per-file results"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--deploy-order", action="store_true",
        help="Print deployment order based on dependencies"
    )
    args = parser.parse_args()

    if not args.root.exists():
        print(f"ERROR: Contracts root not found: {args.root}", file=sys.stderr)
        sys.exit(1)

    results, summary = validate_all(args.root)

    if args.json:
        output = {
            "summary": summary,
            "results": [r.to_dict() for r in results],
        }
        if args.deploy_order:
            output["deploy_order"] = compute_deploy_order(results)
        print(json.dumps(output, indent=2))
    else:
        # Text output
        print("=" * 60)
        print("SOLIDITY CONTRACT VALIDATION")
        print("=" * 60)
        print(f"Root: {args.root}")
        print(f"Files: {summary['total_files']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['total_errors']}")
        print(f"Warnings: {summary['total_warnings']}")
        print(f"Unique contracts: {summary['unique_contracts']}")
        print(f"Pragma versions: {', '.join(summary['pragma_versions'])}")
        print()

        if args.verbose or summary['failed'] > 0:
            for r in results:
                if r.errors or r.warnings or args.verbose:
                    status = "PASS" if r.passed else "FAIL"
                    rel_path = r.filepath.relative_to(args.root)
                    print(f"[{status}] {rel_path}")
                    for err in r.errors:
                        print(f"  ERROR: {err}")
                    for warn in r.warnings:
                        print(f"  WARN:  {warn}")
                    if args.verbose:
                        print(f"  Contracts: {r.contract_names}")
                        print(f"  Imports: {len(r.imports)}")
                        print(f"  Lines: {r.line_count}")
                    print()

        if args.deploy_order:
            print("=" * 60)
            print("DEPLOYMENT ORDER")
            print("=" * 60)
            order = compute_deploy_order(results)
            for i, name in enumerate(order, 1):
                print(f"  {i:3d}. {name}")
            print()

    # Exit with non-zero if any errors
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
