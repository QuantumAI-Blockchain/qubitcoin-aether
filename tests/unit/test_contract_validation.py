"""
Unit tests for the Solidity contract validation script.

Tests the validation logic in scripts/deploy/validate_contracts.py
without requiring solc or any Solidity toolchain.
"""

import re
import textwrap
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest


# ─── Import the validation module ──────────────────────────────────────────

# The validation script lives outside the package, so we import it by path
import importlib.util
import sys

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "validate_contracts.py"

spec = importlib.util.spec_from_file_location("validate_contracts", _SCRIPT_PATH)
vc = importlib.util.module_from_spec(spec)
sys.modules["validate_contracts"] = vc
spec.loader.exec_module(vc)

# Now we can use: vc.validate_file, vc.validate_all, etc.


# ─── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_sol_dir(tmp_path: Path) -> Path:
    """Create a temporary directory structure for Solidity contracts."""
    return tmp_path


def _write_sol(directory: Path, filename: str, content: str) -> Path:
    """Helper to write a .sol file in the given directory."""
    filepath = directory / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(textwrap.dedent(content))
    return filepath


# ─── Test: SPDX License Detection ─────────────────────────────────────────

class TestSPDXLicenseDetection:
    """Test SPDX license identifier validation."""

    def test_valid_spdx_mit(self, tmp_sol_dir: Path) -> None:
        """Valid MIT SPDX license is detected."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert result.spdx_license == "MIT"
        assert not any("SPDX" in e for e in result.errors)

    def test_valid_spdx_apache(self, tmp_sol_dir: Path) -> None:
        """Apache-2.0 SPDX license is detected."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: Apache-2.0
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert result.spdx_license == "Apache-2.0"

    def test_missing_spdx(self, tmp_sol_dir: Path) -> None:
        """Missing SPDX license triggers an error."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert any("SPDX" in e for e in result.errors)
        assert not result.passed


# ─── Test: Pragma Solidity Detection ───────────────────────────────────────

class TestPragmaDetection:
    """Test pragma solidity version detection."""

    def test_valid_pragma(self, tmp_sol_dir: Path) -> None:
        """Standard pragma is correctly parsed."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert result.pragma_version == "^0.8.24"

    def test_missing_pragma(self, tmp_sol_dir: Path) -> None:
        """Missing pragma triggers an error."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert any("pragma" in e.lower() for e in result.errors)
        assert not result.passed

    def test_range_pragma(self, tmp_sol_dir: Path) -> None:
        """Range pragma (>=0.8.0 <0.9.0) is correctly parsed."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity >=0.8.0 <0.9.0;
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert result.pragma_version is not None
        assert "0.8.0" in result.pragma_version


# ─── Test: Contract Name vs Filename Match ─────────────────────────────────

class TestContractNameMatch:
    """Test that contract name matches the filename."""

    def test_matching_name(self, tmp_sol_dir: Path) -> None:
        """Contract name matches filename — no warning."""
        filepath = _write_sol(tmp_sol_dir, "MyToken.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract MyToken {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        name_warnings = [w for w in result.warnings if "Filename" in w]
        assert len(name_warnings) == 0

    def test_mismatched_name(self, tmp_sol_dir: Path) -> None:
        """Contract name does not match filename — triggers warning."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract SomethingElse {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        name_warnings = [w for w in result.warnings if "Filename" in w]
        assert len(name_warnings) == 1

    def test_interface_in_file(self, tmp_sol_dir: Path) -> None:
        """Interface detected as a valid contract type."""
        filepath = _write_sol(tmp_sol_dir, "IQBC20.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            interface IQBC20 {
                function totalSupply() external view returns (uint256);
            }
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert "IQBC20" in result.contract_names
        assert result.passed


# ─── Test: Import Path Resolution ──────────────────────────────────────────

class TestImportResolution:
    """Test import path validation."""

    def test_valid_import(self, tmp_sol_dir: Path) -> None:
        """Valid relative import resolves correctly."""
        _write_sol(tmp_sol_dir, "interfaces/IQBC20.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            interface IQBC20 {}
        """)
        filepath = _write_sol(tmp_sol_dir, "tokens/QBC20.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "../interfaces/IQBC20.sol";
            contract QBC20 is IQBC20 {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert len(result.resolved_imports) == 1
        assert len(result.unresolved_imports) == 0
        assert result.passed

    def test_invalid_import(self, tmp_sol_dir: Path) -> None:
        """Invalid import path triggers an error."""
        filepath = _write_sol(tmp_sol_dir, "Token.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "./NonExistent.sol";
            contract Token {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert len(result.unresolved_imports) == 1
        assert any("Unresolved import" in e for e in result.errors)
        assert not result.passed

    def test_multiple_imports(self, tmp_sol_dir: Path) -> None:
        """Multiple imports are all checked."""
        _write_sol(tmp_sol_dir, "A.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract A {}
        """)
        filepath = _write_sol(tmp_sol_dir, "B.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "./A.sol";
            import "./Missing.sol";
            contract B {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert len(result.resolved_imports) == 1
        assert len(result.unresolved_imports) == 1


# ─── Test: Duplicate Contract Detection ────────────────────────────────────

class TestDuplicateContracts:
    """Test duplicate contract name detection across files."""

    def test_duplicate_names_detected(self, tmp_sol_dir: Path) -> None:
        """Duplicate contract names across files trigger a warning."""
        _write_sol(tmp_sol_dir, "Token1.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        _write_sol(tmp_sol_dir, "Token2.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Token {}
        """)
        results, summary = vc.validate_all(tmp_sol_dir)
        # At least one file should have a duplicate warning
        all_warnings = []
        for r in results:
            all_warnings.extend(r.warnings)
        dup_warnings = [w for w in all_warnings if "Duplicate" in w]
        assert len(dup_warnings) >= 1


# ─── Test: Deployment Order Computation ────────────────────────────────────

class TestDeployOrder:
    """Test deployment order computation from dependencies."""

    def test_simple_dependency_order(self, tmp_sol_dir: Path) -> None:
        """Contracts are ordered so dependencies deploy first."""
        _write_sol(tmp_sol_dir, "Base.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Base {}
        """)
        _write_sol(tmp_sol_dir, "Child.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "./Base.sol";
            contract Child is Base {}
        """)
        results, _ = vc.validate_all(tmp_sol_dir)
        order = vc.compute_deploy_order(results)
        # Base should come before Child
        assert "Base" in order
        assert "Child" in order
        assert order.index("Base") < order.index("Child")

    def test_no_dependencies(self, tmp_sol_dir: Path) -> None:
        """Contracts with no dependencies are ordered alphabetically."""
        _write_sol(tmp_sol_dir, "Bravo.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Bravo {}
        """)
        _write_sol(tmp_sol_dir, "Alpha.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Alpha {}
        """)
        results, _ = vc.validate_all(tmp_sol_dir)
        order = vc.compute_deploy_order(results)
        assert order.index("Alpha") < order.index("Bravo")

    def test_deep_dependency_chain(self, tmp_sol_dir: Path) -> None:
        """Deep dependency chain A -> B -> C is correctly ordered."""
        _write_sol(tmp_sol_dir, "A.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract A {}
        """)
        _write_sol(tmp_sol_dir, "B.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "./A.sol";
            contract B is A {}
        """)
        _write_sol(tmp_sol_dir, "C.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            import "./B.sol";
            contract C is B {}
        """)
        results, _ = vc.validate_all(tmp_sol_dir)
        order = vc.compute_deploy_order(results)
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")


# ─── Test: Validate Real Contract Suite ────────────────────────────────────

class TestRealContractSuite:
    """Validate the actual Qubitcoin Solidity contracts."""

    def _get_contracts_root(self) -> Path:
        return Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "contracts" / "solidity"

    def test_all_contracts_have_spdx(self) -> None:
        """All real .sol files have SPDX license identifiers."""
        root = self._get_contracts_root()
        if not root.exists():
            pytest.skip("Contracts directory not found")
        results, summary = vc.validate_all(root)
        spdx_errors = []
        for r in results:
            for e in r.errors:
                if "SPDX" in e:
                    spdx_errors.append(str(r.filepath.relative_to(root)))
        assert len(spdx_errors) == 0, f"Files missing SPDX: {spdx_errors}"

    def test_all_contracts_have_pragma(self) -> None:
        """All real .sol files have pragma solidity declarations."""
        root = self._get_contracts_root()
        if not root.exists():
            pytest.skip("Contracts directory not found")
        results, summary = vc.validate_all(root)
        pragma_errors = []
        for r in results:
            for e in r.errors:
                if "pragma" in e.lower():
                    pragma_errors.append(str(r.filepath.relative_to(root)))
        assert len(pragma_errors) == 0, f"Files missing pragma: {pragma_errors}"

    def test_all_imports_resolve(self) -> None:
        """All import paths in real contracts resolve to existing files."""
        root = self._get_contracts_root()
        if not root.exists():
            pytest.skip("Contracts directory not found")
        results, summary = vc.validate_all(root)
        unresolved = []
        for r in results:
            for imp in r.unresolved_imports:
                unresolved.append(f"{r.filepath.relative_to(root)}: {imp}")
        assert len(unresolved) == 0, f"Unresolved imports: {unresolved}"

    def test_contract_count(self) -> None:
        """At least 40 unique contracts exist (expected ~49)."""
        root = self._get_contracts_root()
        if not root.exists():
            pytest.skip("Contracts directory not found")
        results, summary = vc.validate_all(root)
        assert summary["unique_contracts"] >= 40, (
            f"Expected at least 40 contracts, got {summary['unique_contracts']}"
        )

    def test_deployment_order_computable(self) -> None:
        """Deployment order can be computed for the real contract suite."""
        root = self._get_contracts_root()
        if not root.exists():
            pytest.skip("Contracts directory not found")
        results, _ = vc.validate_all(root)
        order = vc.compute_deploy_order(results)
        assert len(order) >= 40, f"Expected at least 40 contracts in deploy order, got {len(order)}"


# ─── Test: Regex Pattern Correctness ───────────────────────────────────────

class TestRegexPatterns:
    """Test that the regex patterns correctly match Solidity syntax."""

    def test_spdx_pattern_variants(self) -> None:
        """SPDX pattern matches various comment styles."""
        assert vc.SPDX_PATTERN.search("// SPDX-License-Identifier: MIT")
        assert vc.SPDX_PATTERN.search("//SPDX-License-Identifier: Apache-2.0")
        assert vc.SPDX_PATTERN.search("// spdx-license-identifier: GPL-3.0")
        assert not vc.SPDX_PATTERN.search("SPDX-License-Identifier MIT")

    def test_pragma_pattern_variants(self) -> None:
        """Pragma pattern matches various version specifiers."""
        assert vc.PRAGMA_PATTERN.search("pragma solidity ^0.8.24;")
        assert vc.PRAGMA_PATTERN.search("pragma solidity >=0.8.0 <0.9.0;")
        assert vc.PRAGMA_PATTERN.search("pragma solidity 0.8.24;")
        assert not vc.PRAGMA_PATTERN.search("pragma experimental ABIEncoderV2;")

    def test_contract_pattern_variants(self) -> None:
        """Contract pattern matches contract, interface, abstract contract, library."""
        content = textwrap.dedent("""\
            contract MyToken { }
            interface IToken { }
            abstract contract Base { }
            library SafeMath { }
        """)
        matches = vc.CONTRACT_PATTERN.findall(content)
        names = [m[1] for m in matches]
        assert "MyToken" in names
        assert "IToken" in names
        assert "Base" in names
        assert "SafeMath" in names

    def test_import_pattern_variants(self) -> None:
        """Import pattern extracts paths from various import styles."""
        content = textwrap.dedent("""\
            import "./Token.sol";
            import "../interfaces/IQBC20.sol";
            import "../../proxy/Initializable.sol";
        """)
        imports = vc.IMPORT_PATTERN.findall(content)
        assert "./Token.sol" in imports
        assert "../interfaces/IQBC20.sol" in imports
        assert "../../proxy/Initializable.sol" in imports


# ─── Test: Edge Cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases in contract validation."""

    def test_empty_file(self, tmp_sol_dir: Path) -> None:
        """Empty .sol file has appropriate errors."""
        filepath = _write_sol(tmp_sol_dir, "Empty.sol", "")
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert any("SPDX" in e for e in result.errors)
        assert any("pragma" in e.lower() for e in result.errors)

    def test_comment_only_file(self, tmp_sol_dir: Path) -> None:
        """File with only comments triggers pragma error."""
        filepath = _write_sol(tmp_sol_dir, "Comments.sol", """\
            // SPDX-License-Identifier: MIT
            // This file has no pragma and no contract
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert result.spdx_license == "MIT"
        assert any("pragma" in e.lower() for e in result.errors)

    def test_multiple_contracts_in_file(self, tmp_sol_dir: Path) -> None:
        """Multiple contracts in a single file are all detected."""
        filepath = _write_sol(tmp_sol_dir, "Multi.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            contract Alpha {}
            contract Beta {}
            library Gamma {}
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert len(result.contract_names) == 3
        assert "Alpha" in result.contract_names
        assert "Beta" in result.contract_names
        assert "Gamma" in result.contract_names

    def test_validate_all_empty_dir(self, tmp_sol_dir: Path) -> None:
        """validate_all on an empty directory returns empty results."""
        results, summary = vc.validate_all(tmp_sol_dir)
        assert len(results) == 0
        assert summary["total_files"] == 0

    def test_abstract_contract_detection(self, tmp_sol_dir: Path) -> None:
        """Abstract contracts are properly detected."""
        filepath = _write_sol(tmp_sol_dir, "Base.sol", """\
            // SPDX-License-Identifier: MIT
            pragma solidity ^0.8.24;
            abstract contract Base {
                function foo() external virtual;
            }
        """)
        result = vc.validate_file(filepath, tmp_sol_dir)
        assert "Base" in result.contract_names
        assert result.passed
