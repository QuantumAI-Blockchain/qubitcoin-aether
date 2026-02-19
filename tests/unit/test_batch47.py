"""
Batch 47 Tests: Quantum Solidity Compiler (.qsol → QVM bytecode)
  - QSolLexer (qvm/qsol_compiler.py)
  - QSolParser (qvm/qsol_compiler.py)
  - QSolCodeGenerator (qvm/qsol_compiler.py)
  - QSolCompiler (qvm/qsol_compiler.py)
"""

import pytest

from qubitcoin.qvm.opcodes import Opcode


# ═══════════════════════════════════════════════════════════════════════
#  Sample .qsol source code
# ═══════════════════════════════════════════════════════════════════════

SIMPLE_CONTRACT = """
pragma solidity ^0.8.24;

contract SimpleToken {
    uint256 public totalSupply;
    address public owner;

    event Transfer(address indexed from, address indexed to, uint256 amount);

    function mint(uint256 amount) public {
        totalSupply = totalSupply + amount;
        return;
    }

    function getSupply() public view returns (uint256) {
        return totalSupply;
    }
}
"""

QUANTUM_CONTRACT = """
pragma solidity ^0.8.24;

contract QuantumWallet {
    qstate myState;
    qregister myRegister;

    function createEntanglement() public {
        entangle(myState, myRegister);
    }

    function measureState() public returns (uint256) {
        measure(myState);
        return;
    }

    function applyHadamard() public {
        apply_gate(myState);
    }

    function verify() public returns (bool) {
        q_verify(myState);
        return;
    }
}
"""

EMPTY_CONTRACT = """
pragma solidity ^0.8.24;

contract Empty {
}
"""

MINIMAL = """
contract Minimal {
    function hello() public {
        return;
    }
}
"""


# ═══════════════════════════════════════════════════════════════════════
#  Lexer Tests
# ═══════════════════════════════════════════════════════════════════════

class TestQSolLexer:
    """Tests for Quantum Solidity lexer."""

    def _make_lexer(self, source: str):
        from qubitcoin.qvm.qsol_compiler import QSolLexer
        return QSolLexer(source)

    def test_tokenise_simple(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("contract Foo { }")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens]
        assert TokenType.CONTRACT in types
        assert TokenType.IDENTIFIER in types
        assert TokenType.LBRACE in types
        assert TokenType.RBRACE in types
        assert tokens[-1].type == TokenType.EOF

    def test_tokenise_keywords(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("function public view returns uint256")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.FUNCTION in types
        assert TokenType.PUBLIC in types
        assert TokenType.VIEW in types
        assert TokenType.RETURNS in types
        assert TokenType.UINT256 in types

    def test_tokenise_quantum_keywords(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("qstate qregister entangled measure entangle apply_gate superpose q_verify")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.QSTATE in types
        assert TokenType.QREGISTER in types
        assert TokenType.MEASURE in types
        assert TokenType.ENTANGLE in types
        assert TokenType.APPLY_GATE in types
        assert TokenType.SUPERPOSE in types
        assert TokenType.Q_VERIFY in types

    def test_tokenise_numbers(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("42 100 0")
        tokens = lexer.tokenise()
        nums = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(nums) == 3
        assert nums[0].value == "42"

    def test_tokenise_string_literal(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer('"hello world"')
        tokens = lexer.tokenise()
        strings = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strings) == 1
        assert strings[0].value == "hello world"

    def test_tokenise_operators(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("+ - * / == != <= >= && ||")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.PLUS in types
        assert TokenType.MINUS in types
        assert TokenType.EQ in types
        assert TokenType.NEQ in types
        assert TokenType.AND in types
        assert TokenType.OR in types

    def test_skip_line_comments(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("// this is a comment\nuint256")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.UINT256 in types
        assert len(types) == 1

    def test_skip_block_comments(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer("/* block comment */ uint256")
        tokens = lexer.tokenise()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.UINT256 in types
        assert len(types) == 1

    def test_tokenise_full_contract(self):
        from qubitcoin.qvm.qsol_compiler import TokenType
        lexer = self._make_lexer(SIMPLE_CONTRACT)
        tokens = lexer.tokenise()
        assert len(tokens) > 20  # Should produce many tokens
        assert tokens[-1].type == TokenType.EOF

    def test_line_tracking(self):
        lexer = self._make_lexer("line1\nline2\nline3")
        tokens = lexer.tokenise()
        # Should track line numbers
        lines = set(t.line for t in tokens if t.value.startswith("line"))
        assert len(lines) == 3


# ═══════════════════════════════════════════════════════════════════════
#  Parser Tests
# ═══════════════════════════════════════════════════════════════════════

class TestQSolParser:
    """Tests for Quantum Solidity parser."""

    def _parse(self, source: str):
        from qubitcoin.qvm.qsol_compiler import QSolLexer, QSolParser, ASTNodeType
        lexer = QSolLexer(source)
        tokens = lexer.tokenise()
        parser = QSolParser(tokens)
        return parser.parse()

    def test_parse_empty_contract(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(EMPTY_CONTRACT)
        assert ast.node_type == ASTNodeType.PROGRAM
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        assert len(contracts) == 1
        assert contracts[0].value == "Empty"

    def test_parse_pragma(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse("pragma solidity ^0.8.24;")
        pragmas = [c for c in ast.children if c.node_type == ASTNodeType.PRAGMA]
        assert len(pragmas) == 1

    def test_parse_function(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(MINIMAL)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        funcs = [c for c in contracts[0].children if c.node_type == ASTNodeType.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].value == "hello"

    def test_parse_multiple_functions(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(SIMPLE_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        funcs = [c for c in contracts[0].children if c.node_type == ASTNodeType.FUNCTION]
        assert len(funcs) == 2  # mint and getSupply

    def test_parse_state_variables(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(SIMPLE_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        state_vars = [c for c in contracts[0].children if c.node_type == ASTNodeType.STATE_VAR]
        assert len(state_vars) >= 1

    def test_parse_events(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(SIMPLE_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        events = [c for c in contracts[0].children if c.node_type == ASTNodeType.EVENT_DEF]
        assert len(events) == 1
        assert events[0].value == "Transfer"

    def test_parse_quantum_declarations(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(QUANTUM_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        qdecls = [c for c in contracts[0].children
                  if c.node_type in (ASTNodeType.QSTATE_DECL, ASTNodeType.QREGISTER_DECL)]
        assert len(qdecls) == 2

    def test_parse_quantum_operations(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(QUANTUM_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        funcs = [c for c in contracts[0].children if c.node_type == ASTNodeType.FUNCTION]
        # Should have 4 functions with quantum operations
        assert len(funcs) == 4

    def test_parse_contract_name(self):
        from qubitcoin.qvm.qsol_compiler import ASTNodeType
        ast = self._parse(SIMPLE_CONTRACT)
        contracts = [c for c in ast.children if c.node_type == ASTNodeType.CONTRACT]
        assert contracts[0].value == "SimpleToken"


# ═══════════════════════════════════════════════════════════════════════
#  Code Generator Tests
# ═══════════════════════════════════════════════════════════════════════

class TestQSolCodeGenerator:
    """Tests for QVM bytecode generation."""

    def _compile(self, source: str):
        from qubitcoin.qvm.qsol_compiler import QSolCompiler
        compiler = QSolCompiler()
        return compiler.compile(source)

    def test_compile_simple_contract(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert result.success is True
        assert len(result.bytecode) > 0
        assert result.contract_name == "SimpleToken"

    def test_compile_produces_hex(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert result.bytecode_hex.startswith("0x")
        assert len(result.bytecode_hex) > 2

    def test_compile_generates_abi(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert len(result.abi) >= 2  # mint + getSupply
        names = [entry["name"] for entry in result.abi]
        assert "mint" in names
        assert "getSupply" in names

    def test_compile_abi_has_inputs(self):
        result = self._compile(SIMPLE_CONTRACT)
        mint_entry = next(e for e in result.abi if e["name"] == "mint")
        assert "inputs" in mint_entry
        assert len(mint_entry["inputs"]) >= 1

    def test_compile_stats(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert "functions" in result.stats
        assert result.stats["functions"] == 2
        assert "bytecode_size" in result.stats

    def test_compile_source_hash(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert len(result.source_hash) == 64  # SHA-256 hex

    def test_compile_quantum_contract(self):
        result = self._compile(QUANTUM_CONTRACT)
        assert result.success is True
        assert result.stats.get("quantum_ops", 0) > 0

    def test_quantum_opcodes_in_bytecode(self):
        result = self._compile(QUANTUM_CONTRACT)
        bytecode = result.bytecode
        # Should contain quantum opcodes
        quantum_opcodes = {Opcode.QGATE, Opcode.QMEASURE, Opcode.QENTANGLE,
                           Opcode.QCREATE, Opcode.QVERIFY}
        found_quantum = any(b in quantum_opcodes for b in bytecode)
        assert found_quantum

    def test_compile_empty_contract(self):
        result = self._compile(EMPTY_CONTRACT)
        assert result.success is True
        assert result.contract_name == "Empty"

    def test_compile_minimal(self):
        result = self._compile(MINIMAL)
        assert result.success is True
        assert result.stats["functions"] == 1

    def test_compile_to_dict(self):
        result = self._compile(SIMPLE_CONTRACT)
        d = result.to_dict()
        assert "success" in d
        assert "bytecode_hex" in d
        assert "abi" in d
        assert "errors" in d
        assert "stats" in d

    def test_bytecode_contains_stop(self):
        result = self._compile(MINIMAL)
        assert Opcode.STOP in result.bytecode

    def test_bytecode_contains_push4(self):
        result = self._compile(MINIMAL)
        # Function selector is PUSH4
        assert Opcode.PUSH4 in result.bytecode


# ═══════════════════════════════════════════════════════════════════════
#  Compiler Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCompilerErrors:
    """Tests for compiler error handling."""

    def _compile(self, source: str):
        from qubitcoin.qvm.qsol_compiler import QSolCompiler
        compiler = QSolCompiler()
        return compiler.compile(source)

    def test_no_contract(self):
        result = self._compile("pragma solidity ^0.8.24;")
        assert result.success is False
        assert len(result.errors) > 0

    def test_empty_source(self):
        result = self._compile("")
        assert result.success is False

    def test_compile_file_nonexistent(self):
        from qubitcoin.qvm.qsol_compiler import QSolCompiler
        compiler = QSolCompiler()
        with pytest.raises(FileNotFoundError):
            compiler.compile_file("/nonexistent/file.qsol")

    def test_source_hash_on_error(self):
        result = self._compile("not valid code")
        # Should still produce a source hash even on failure
        assert len(result.source_hash) == 64


# ═══════════════════════════════════════════════════════════════════════
#  Integration: Full Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end compiler pipeline tests."""

    def _compile(self, source: str):
        from qubitcoin.qvm.qsol_compiler import QSolCompiler
        return QSolCompiler().compile(source)

    def test_standard_solidity_compiles(self):
        result = self._compile(SIMPLE_CONTRACT)
        assert result.success is True
        assert result.stats["quantum_ops"] == 0

    def test_quantum_solidity_compiles(self):
        result = self._compile(QUANTUM_CONTRACT)
        assert result.success is True
        assert result.stats["quantum_ops"] > 0

    def test_deterministic_compilation(self):
        r1 = self._compile(SIMPLE_CONTRACT)
        r2 = self._compile(SIMPLE_CONTRACT)
        assert r1.bytecode == r2.bytecode
        assert r1.source_hash == r2.source_hash

    def test_different_sources_different_bytecode(self):
        r1 = self._compile(SIMPLE_CONTRACT)
        r2 = self._compile(QUANTUM_CONTRACT)
        assert r1.bytecode != r2.bytecode

    def test_quantum_state_declarations_create_opcodes(self):
        result = self._compile(QUANTUM_CONTRACT)
        # qstate + qregister declarations should each produce QCREATE
        qcreate_count = sum(1 for b in result.bytecode if b == Opcode.QCREATE)
        assert qcreate_count >= 2  # myState + myRegister
