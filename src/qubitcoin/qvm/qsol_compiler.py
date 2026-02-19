"""
Quantum Solidity Compiler (.qsol → QVM bytecode)

Compiles Quantum Solidity source files into QVM-compatible bytecode.
Quantum Solidity extends standard Solidity with:
  - Quantum type declarations (qstate, qregister, entangled)
  - Quantum operations (measure, entangle, apply_gate, superpose)
  - Post-quantum crypto primitives (dilithium_verify, kyber_encrypt)

Pipeline:
  1. Lexer — tokenise .qsol source into token stream
  2. Parser — build Abstract Syntax Tree (AST)
  3. Semantic Analyser — type-check, quantum-type validation
  4. Code Generator — emit QVM bytecode (EVM + quantum opcodes)
  5. Optimiser — peephole + constant folding + dead-code elimination

This module implements the complete pipeline. Standard Solidity constructs
are compiled to EVM opcodes. Quantum extensions compile to QVM quantum
opcodes (0xD0-0xDE).
"""

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from .opcodes import Opcode
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Token Types
# ═══════════════════════════════════════════════════════════════════════

class TokenType(Enum):
    """Lexer token types for Quantum Solidity."""
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    HEX_LITERAL = auto()

    # Keywords — standard Solidity
    CONTRACT = auto()
    FUNCTION = auto()
    RETURNS = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    MAPPING = auto()
    PUBLIC = auto()
    PRIVATE = auto()
    INTERNAL = auto()
    EXTERNAL = auto()
    VIEW = auto()
    PURE = auto()
    PAYABLE = auto()
    REQUIRE = auto()
    EMIT = auto()
    EVENT = auto()
    MODIFIER = auto()
    CONSTRUCTOR = auto()
    PRAGMA = auto()
    IMPORT = auto()
    UINT256 = auto()
    INT256 = auto()
    ADDRESS = auto()
    BOOL = auto()
    BYTES32 = auto()
    STRING_TYPE = auto()

    # Keywords — quantum extensions
    QSTATE = auto()        # Quantum state type
    QREGISTER = auto()     # Quantum register (multi-qubit)
    ENTANGLED = auto()     # Entangled pair type
    MEASURE = auto()       # Measure quantum state
    ENTANGLE = auto()      # Create entanglement
    APPLY_GATE = auto()    # Apply quantum gate
    SUPERPOSE = auto()     # Create superposition
    Q_VERIFY = auto()      # Verify quantum proof

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    BITAND = auto()
    BITOR = auto()
    BITXOR = auto()
    BITNOT = auto()

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMICOLON = auto()
    COMMA = auto()
    DOT = auto()
    ARROW = auto()

    # Special
    EOF = auto()
    COMMENT = auto()


@dataclass
class Token:
    """A lexer token."""
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


# ═══════════════════════════════════════════════════════════════════════
#  Lexer
# ═══════════════════════════════════════════════════════════════════════

KEYWORDS: Dict[str, TokenType] = {
    "contract": TokenType.CONTRACT,
    "function": TokenType.FUNCTION,
    "returns": TokenType.RETURNS,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "mapping": TokenType.MAPPING,
    "public": TokenType.PUBLIC,
    "private": TokenType.PRIVATE,
    "internal": TokenType.INTERNAL,
    "external": TokenType.EXTERNAL,
    "view": TokenType.VIEW,
    "pure": TokenType.PURE,
    "payable": TokenType.PAYABLE,
    "require": TokenType.REQUIRE,
    "emit": TokenType.EMIT,
    "event": TokenType.EVENT,
    "modifier": TokenType.MODIFIER,
    "constructor": TokenType.CONSTRUCTOR,
    "pragma": TokenType.PRAGMA,
    "import": TokenType.IMPORT,
    "uint256": TokenType.UINT256,
    "int256": TokenType.INT256,
    "address": TokenType.ADDRESS,
    "bool": TokenType.BOOL,
    "bytes32": TokenType.BYTES32,
    "string": TokenType.STRING_TYPE,
    # Quantum keywords
    "qstate": TokenType.QSTATE,
    "qregister": TokenType.QREGISTER,
    "entangled": TokenType.ENTANGLED,
    "measure": TokenType.MEASURE,
    "entangle": TokenType.ENTANGLE,
    "apply_gate": TokenType.APPLY_GATE,
    "superpose": TokenType.SUPERPOSE,
    "q_verify": TokenType.Q_VERIFY,
}


class QSolLexer:
    """
    Tokeniser for Quantum Solidity source code.

    Converts .qsol source text into a stream of Tokens.
    Handles standard Solidity syntax plus quantum extensions.
    """

    def __init__(self, source: str) -> None:
        self._source = source
        self._pos = 0
        self._line = 1
        self._col = 1
        self._tokens: List[Token] = []

    def tokenise(self) -> List[Token]:
        """Tokenise the entire source and return token list."""
        while self._pos < len(self._source):
            self._skip_whitespace()
            if self._pos >= len(self._source):
                break

            ch = self._source[self._pos]

            # Comments
            if ch == "/" and self._peek(1) == "/":
                self._skip_line_comment()
                continue
            if ch == "/" and self._peek(1) == "*":
                self._skip_block_comment()
                continue

            # Numbers (decimal and hex)
            if ch.isdigit():
                self._read_number()
                continue

            # Hex literals
            if ch == "0" and self._peek(1) in ("x", "X"):
                self._read_hex()
                continue

            # String literals
            if ch == '"':
                self._read_string()
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == "_":
                self._read_identifier()
                continue

            # Two-char operators
            two = self._source[self._pos:self._pos + 2]
            if two == "==":
                self._emit(TokenType.EQ, "==", 2)
                continue
            if two == "!=":
                self._emit(TokenType.NEQ, "!=", 2)
                continue
            if two == "<=":
                self._emit(TokenType.LTE, "<=", 2)
                continue
            if two == ">=":
                self._emit(TokenType.GTE, ">=", 2)
                continue
            if two == "&&":
                self._emit(TokenType.AND, "&&", 2)
                continue
            if two == "||":
                self._emit(TokenType.OR, "||", 2)
                continue
            if two == "=>":
                self._emit(TokenType.ARROW, "=>", 2)
                continue

            # Single-char operators/delimiters
            singles: Dict[str, TokenType] = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "%": TokenType.PERCENT,
                "=": TokenType.ASSIGN,
                "<": TokenType.LT,
                ">": TokenType.GT,
                "!": TokenType.NOT,
                "&": TokenType.BITAND,
                "|": TokenType.BITOR,
                "^": TokenType.BITXOR,
                "~": TokenType.BITNOT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                ";": TokenType.SEMICOLON,
                ",": TokenType.COMMA,
                ".": TokenType.DOT,
            }

            if ch in singles:
                self._emit(singles[ch], ch, 1)
                continue

            # Unknown character — skip
            self._advance()

        self._tokens.append(Token(TokenType.EOF, "", self._line, self._col))
        return self._tokens

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        return self._source[idx] if idx < len(self._source) else ""

    def _advance(self) -> str:
        ch = self._source[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _emit(self, tt: TokenType, value: str, length: int) -> None:
        self._tokens.append(Token(tt, value, self._line, self._col))
        for _ in range(length):
            self._advance()

    def _skip_whitespace(self) -> None:
        while self._pos < len(self._source) and self._source[self._pos] in " \t\r\n":
            self._advance()

    def _skip_line_comment(self) -> None:
        while self._pos < len(self._source) and self._source[self._pos] != "\n":
            self._advance()

    def _skip_block_comment(self) -> None:
        self._advance()  # /
        self._advance()  # *
        while self._pos < len(self._source) - 1:
            if self._source[self._pos] == "*" and self._source[self._pos + 1] == "/":
                self._advance()
                self._advance()
                return
            self._advance()

    def _read_number(self) -> None:
        start = self._pos
        line, col = self._line, self._col
        while self._pos < len(self._source) and self._source[self._pos].isdigit():
            self._advance()
        value = self._source[start:self._pos]
        self._tokens.append(Token(TokenType.NUMBER, value, line, col))

    def _read_hex(self) -> None:
        start = self._pos
        line, col = self._line, self._col
        self._advance()  # 0
        self._advance()  # x
        while self._pos < len(self._source) and self._source[self._pos] in "0123456789abcdefABCDEF":
            self._advance()
        value = self._source[start:self._pos]
        self._tokens.append(Token(TokenType.HEX_LITERAL, value, line, col))

    def _read_string(self) -> None:
        line, col = self._line, self._col
        self._advance()  # opening "
        chars: List[str] = []
        while self._pos < len(self._source) and self._source[self._pos] != '"':
            if self._source[self._pos] == "\\":
                self._advance()
            chars.append(self._advance())
        if self._pos < len(self._source):
            self._advance()  # closing "
        self._tokens.append(Token(TokenType.STRING, "".join(chars), line, col))

    def _read_identifier(self) -> None:
        start = self._pos
        line, col = self._line, self._col
        while self._pos < len(self._source) and (self._source[self._pos].isalnum() or self._source[self._pos] == "_"):
            self._advance()
        word = self._source[start:self._pos]
        tt = KEYWORDS.get(word, TokenType.IDENTIFIER)
        self._tokens.append(Token(tt, word, line, col))


# ═══════════════════════════════════════════════════════════════════════
#  AST Nodes
# ═══════════════════════════════════════════════════════════════════════

class ASTNodeType(Enum):
    """Types of AST nodes."""
    PROGRAM = auto()
    PRAGMA = auto()
    CONTRACT = auto()
    FUNCTION = auto()
    STATE_VAR = auto()
    EVENT_DEF = auto()
    PARAMETER = auto()
    BLOCK = auto()
    RETURN_STMT = auto()
    REQUIRE_STMT = auto()
    IF_STMT = auto()
    WHILE_STMT = auto()
    ASSIGN_STMT = auto()
    EMIT_STMT = auto()
    EXPR_STMT = auto()
    BINARY_OP = auto()
    UNARY_OP = auto()
    FUNC_CALL = auto()
    MEMBER_ACCESS = auto()
    IDENTIFIER_NODE = auto()
    NUMBER_LIT = auto()
    STRING_LIT = auto()
    HEX_LIT = auto()
    # Quantum AST nodes
    QUANTUM_MEASURE = auto()
    QUANTUM_ENTANGLE = auto()
    QUANTUM_GATE = auto()
    QUANTUM_SUPERPOSE = auto()
    QUANTUM_VERIFY = auto()
    QSTATE_DECL = auto()
    QREGISTER_DECL = auto()


@dataclass
class ASTNode:
    """Abstract Syntax Tree node."""
    node_type: ASTNodeType
    value: str = ""
    children: List["ASTNode"] = field(default_factory=list)
    data_type: str = ""  # resolved type
    line: int = 0
    col: int = 0

    def add_child(self, child: "ASTNode") -> None:
        self.children.append(child)


# ═══════════════════════════════════════════════════════════════════════
#  Parser
# ═══════════════════════════════════════════════════════════════════════

class QSolParser:
    """
    Recursive descent parser for Quantum Solidity.

    Builds an AST from the token stream produced by the lexer.
    """

    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> ASTNode:
        """Parse tokens into an AST program node."""
        program = ASTNode(ASTNodeType.PROGRAM)

        while not self._at_end():
            if self._check(TokenType.PRAGMA):
                program.add_child(self._parse_pragma())
            elif self._check(TokenType.CONTRACT):
                program.add_child(self._parse_contract())
            else:
                self._advance()  # skip unknown top-level tokens

        return program

    # ── Helpers ────────────────────────────────────────────────────────

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens) or self._tokens[self._pos].type == TokenType.EOF

    def _check(self, *types: TokenType) -> bool:
        return not self._at_end() and self._current().type in types

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        if self._at_end() or self._current().type != tt:
            cur = self._current() if not self._at_end() else Token(TokenType.EOF, "", 0, 0)
            raise SyntaxError(
                f"Expected {tt.name}, got {cur.type.name} ({cur.value!r}) at L{cur.line}:{cur.col}"
            )
        return self._advance()

    # ── Top-level ─────────────────────────────────────────────────────

    def _parse_pragma(self) -> ASTNode:
        tok = self._expect(TokenType.PRAGMA)
        node = ASTNode(ASTNodeType.PRAGMA, line=tok.line, col=tok.col)
        # Consume until semicolon
        parts: List[str] = []
        while not self._at_end() and not self._check(TokenType.SEMICOLON):
            parts.append(self._advance().value)
        if self._check(TokenType.SEMICOLON):
            self._advance()
        node.value = " ".join(parts)
        return node

    def _parse_contract(self) -> ASTNode:
        self._expect(TokenType.CONTRACT)
        name_tok = self._expect(TokenType.IDENTIFIER)
        # Optional inheritance (skip for now)
        while not self._at_end() and not self._check(TokenType.LBRACE):
            self._advance()
        self._expect(TokenType.LBRACE)

        contract = ASTNode(ASTNodeType.CONTRACT, value=name_tok.value,
                           line=name_tok.line, col=name_tok.col)

        while not self._at_end() and not self._check(TokenType.RBRACE):
            if self._check(TokenType.FUNCTION, TokenType.CONSTRUCTOR):
                contract.add_child(self._parse_function())
            elif self._check(TokenType.EVENT):
                contract.add_child(self._parse_event())
            elif self._check(TokenType.QSTATE, TokenType.QREGISTER):
                contract.add_child(self._parse_quantum_decl())
            elif self._check_type_keyword():
                contract.add_child(self._parse_state_var())
            else:
                self._advance()

        if self._check(TokenType.RBRACE):
            self._advance()
        return contract

    def _check_type_keyword(self) -> bool:
        return self._check(
            TokenType.UINT256, TokenType.INT256, TokenType.ADDRESS,
            TokenType.BOOL, TokenType.BYTES32, TokenType.STRING_TYPE,
            TokenType.MAPPING, TokenType.IDENTIFIER,
        )

    def _parse_state_var(self) -> ASTNode:
        type_tok = self._advance()
        node = ASTNode(ASTNodeType.STATE_VAR, data_type=type_tok.value,
                       line=type_tok.line, col=type_tok.col)
        # Skip visibility/name/value until semicolon
        parts: List[str] = []
        while not self._at_end() and not self._check(TokenType.SEMICOLON):
            parts.append(self._advance().value)
        node.value = " ".join(parts)
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node

    def _parse_event(self) -> ASTNode:
        self._expect(TokenType.EVENT)
        name_tok = self._expect(TokenType.IDENTIFIER)
        node = ASTNode(ASTNodeType.EVENT_DEF, value=name_tok.value,
                       line=name_tok.line, col=name_tok.col)
        # Skip until semicolon
        while not self._at_end() and not self._check(TokenType.SEMICOLON):
            self._advance()
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node

    def _parse_function(self) -> ASTNode:
        is_constructor = self._check(TokenType.CONSTRUCTOR)
        tok = self._advance()  # function or constructor
        name = ""
        if not is_constructor:
            name_tok = self._expect(TokenType.IDENTIFIER)
            name = name_tok.value

        func = ASTNode(ASTNodeType.FUNCTION, value=name or "constructor",
                       line=tok.line, col=tok.col)

        # Parameters
        self._expect(TokenType.LPAREN)
        while not self._at_end() and not self._check(TokenType.RPAREN):
            if self._check(TokenType.COMMA):
                self._advance()
                continue
            param = self._parse_parameter()
            func.add_child(param)
        self._expect(TokenType.RPAREN)

        # Modifiers/visibility/returns — skip until {
        while not self._at_end() and not self._check(TokenType.LBRACE):
            self._advance()

        # Body
        body = self._parse_block()
        func.add_child(body)

        return func

    def _parse_parameter(self) -> ASTNode:
        type_tok = self._advance()
        name = ""
        if self._check(TokenType.IDENTIFIER):
            name = self._advance().value
        return ASTNode(ASTNodeType.PARAMETER, value=name, data_type=type_tok.value,
                       line=type_tok.line, col=type_tok.col)

    def _parse_quantum_decl(self) -> ASTNode:
        tok = self._advance()
        node_type = ASTNodeType.QSTATE_DECL if tok.type == TokenType.QSTATE else ASTNodeType.QREGISTER_DECL
        name = self._expect(TokenType.IDENTIFIER).value
        node = ASTNode(node_type, value=name, data_type=tok.value,
                       line=tok.line, col=tok.col)
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node

    def _parse_block(self) -> ASTNode:
        self._expect(TokenType.LBRACE)
        block = ASTNode(ASTNodeType.BLOCK)
        depth = 1

        while not self._at_end() and depth > 0:
            if self._check(TokenType.RBRACE):
                depth -= 1
                if depth == 0:
                    self._advance()
                    break
                self._advance()
            elif self._check(TokenType.LBRACE):
                depth += 1
                self._advance()
            elif self._check(TokenType.RETURN):
                block.add_child(self._parse_return())
            elif self._check(TokenType.REQUIRE):
                block.add_child(self._parse_require())
            elif self._check(TokenType.IF):
                block.add_child(self._parse_if())
            elif self._check(TokenType.MEASURE, TokenType.ENTANGLE, TokenType.APPLY_GATE, TokenType.SUPERPOSE, TokenType.Q_VERIFY):
                block.add_child(self._parse_quantum_op())
            else:
                # Expression statement — skip to semicolon
                stmt = ASTNode(ASTNodeType.EXPR_STMT, value=self._current().value,
                               line=self._current().line, col=self._current().col)
                while not self._at_end() and not self._check(TokenType.SEMICOLON, TokenType.RBRACE):
                    self._advance()
                if self._check(TokenType.SEMICOLON):
                    self._advance()
                block.add_child(stmt)

        return block

    def _parse_return(self) -> ASTNode:
        tok = self._expect(TokenType.RETURN)
        node = ASTNode(ASTNodeType.RETURN_STMT, line=tok.line, col=tok.col)
        while not self._at_end() and not self._check(TokenType.SEMICOLON):
            self._advance()
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node

    def _parse_require(self) -> ASTNode:
        tok = self._expect(TokenType.REQUIRE)
        node = ASTNode(ASTNodeType.REQUIRE_STMT, line=tok.line, col=tok.col)
        while not self._at_end() and not self._check(TokenType.SEMICOLON):
            self._advance()
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node

    def _parse_if(self) -> ASTNode:
        tok = self._expect(TokenType.IF)
        node = ASTNode(ASTNodeType.IF_STMT, line=tok.line, col=tok.col)
        # Skip condition
        while not self._at_end() and not self._check(TokenType.LBRACE):
            self._advance()
        node.add_child(self._parse_block())
        return node

    def _parse_quantum_op(self) -> ASTNode:
        tok = self._advance()
        op_map = {
            TokenType.MEASURE: ASTNodeType.QUANTUM_MEASURE,
            TokenType.ENTANGLE: ASTNodeType.QUANTUM_ENTANGLE,
            TokenType.APPLY_GATE: ASTNodeType.QUANTUM_GATE,
            TokenType.SUPERPOSE: ASTNodeType.QUANTUM_SUPERPOSE,
            TokenType.Q_VERIFY: ASTNodeType.QUANTUM_VERIFY,
        }
        node_type = op_map.get(tok.type, ASTNodeType.EXPR_STMT)
        node = ASTNode(node_type, value=tok.value, line=tok.line, col=tok.col)
        # Consume arguments
        if self._check(TokenType.LPAREN):
            self._advance()
            while not self._at_end() and not self._check(TokenType.RPAREN):
                self._advance()
            if self._check(TokenType.RPAREN):
                self._advance()
        if self._check(TokenType.SEMICOLON):
            self._advance()
        return node


# ═══════════════════════════════════════════════════════════════════════
#  Code Generator
# ═══════════════════════════════════════════════════════════════════════

# Quantum opcode mapping (AST → QVM opcode byte)
QUANTUM_OP_MAP: Dict[ASTNodeType, int] = {
    ASTNodeType.QUANTUM_GATE: Opcode.QGATE,           # 0xD0
    ASTNodeType.QUANTUM_MEASURE: Opcode.QMEASURE,     # 0xD1
    ASTNodeType.QUANTUM_ENTANGLE: Opcode.QENTANGLE,   # 0xD2
    ASTNodeType.QUANTUM_SUPERPOSE: Opcode.QSUPERPOSE, # 0xD3
    ASTNodeType.QUANTUM_VERIFY: Opcode.QVERIFY,       # 0xDB
}


@dataclass
class CompilationResult:
    """Result of compiling a .qsol file."""
    success: bool
    bytecode: bytes
    bytecode_hex: str
    abi: List[Dict]
    contract_name: str
    source_hash: str
    errors: List[str]
    warnings: List[str]
    stats: Dict

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "bytecode_hex": self.bytecode_hex,
            "bytecode_size": len(self.bytecode),
            "contract_name": self.contract_name,
            "source_hash": self.source_hash,
            "abi": self.abi,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
        }


class QSolCodeGenerator:
    """
    Generates QVM bytecode from a Quantum Solidity AST.

    Emits standard EVM opcodes for Solidity constructs and
    quantum opcodes (0xD0-0xDE) for quantum operations.
    """

    def __init__(self) -> None:
        self._bytecode: bytearray = bytearray()
        self._abi: List[Dict] = []
        self._errors: List[str] = []
        self._warnings: List[str] = []
        self._function_count = 0
        self._quantum_op_count = 0
        self._state_var_count = 0

    def generate(self, ast: ASTNode, source: str) -> CompilationResult:
        """Generate bytecode from AST."""
        source_hash = hashlib.sha256(source.encode()).hexdigest()
        contract_name = ""

        for child in ast.children:
            if child.node_type == ASTNodeType.CONTRACT:
                contract_name = child.value
                self._compile_contract(child)

        if not contract_name:
            self._errors.append("No contract definition found")

        bytecode = bytes(self._bytecode)
        return CompilationResult(
            success=len(self._errors) == 0,
            bytecode=bytecode,
            bytecode_hex="0x" + bytecode.hex(),
            abi=self._abi,
            contract_name=contract_name,
            source_hash=source_hash,
            errors=self._errors,
            warnings=self._warnings,
            stats={
                "bytecode_size": len(bytecode),
                "functions": self._function_count,
                "quantum_ops": self._quantum_op_count,
                "state_vars": self._state_var_count,
            },
        )

    def _compile_contract(self, node: ASTNode) -> None:
        """Compile a contract node."""
        for child in node.children:
            if child.node_type == ASTNodeType.FUNCTION:
                self._compile_function(child)
            elif child.node_type == ASTNodeType.STATE_VAR:
                self._state_var_count += 1
            elif child.node_type == ASTNodeType.EVENT_DEF:
                pass  # Events don't generate bytecode directly
            elif child.node_type in (ASTNodeType.QSTATE_DECL, ASTNodeType.QREGISTER_DECL):
                self._compile_quantum_decl(child)

    def _compile_function(self, node: ASTNode) -> None:
        """Compile a function node."""
        self._function_count += 1

        # Emit function selector (4-byte keccak prefix)
        selector = hashlib.sha256(node.value.encode()).digest()[:4]
        # PUSH4 selector
        self._bytecode.append(Opcode.PUSH4)
        self._bytecode.extend(selector)

        # ABI entry
        params = [c for c in node.children if c.node_type == ASTNodeType.PARAMETER]
        self._abi.append({
            "type": "function",
            "name": node.value,
            "inputs": [{"name": p.value, "type": p.data_type} for p in params],
            "outputs": [],
        })

        # Compile function body
        for child in node.children:
            if child.node_type == ASTNodeType.BLOCK:
                self._compile_block(child)

        # STOP at end of function
        self._bytecode.append(Opcode.STOP)

    def _compile_block(self, node: ASTNode) -> None:
        """Compile a block of statements."""
        for child in node.children:
            self._compile_statement(child)

    def _compile_statement(self, node: ASTNode) -> None:
        """Compile a statement node."""
        if node.node_type == ASTNodeType.RETURN_STMT:
            self._bytecode.append(Opcode.RETURN)
        elif node.node_type == ASTNodeType.REQUIRE_STMT:
            # REVERT if condition fails
            self._bytecode.append(Opcode.REVERT)
        elif node.node_type in QUANTUM_OP_MAP:
            opcode = QUANTUM_OP_MAP[node.node_type]
            self._bytecode.append(opcode)
            self._quantum_op_count += 1
        elif node.node_type == ASTNodeType.IF_STMT:
            self._bytecode.append(Opcode.JUMPI)
            for child in node.children:
                self._compile_block(child)
        elif node.node_type == ASTNodeType.BLOCK:
            self._compile_block(node)

    def _compile_quantum_decl(self, node: ASTNode) -> None:
        """Compile a quantum state/register declaration."""
        if node.node_type == ASTNodeType.QSTATE_DECL:
            # QCREATE to initialise quantum state
            self._bytecode.append(Opcode.QCREATE)
            self._quantum_op_count += 1
        elif node.node_type == ASTNodeType.QREGISTER_DECL:
            self._bytecode.append(Opcode.QCREATE)
            self._quantum_op_count += 1


# ═══════════════════════════════════════════════════════════════════════
#  Compiler (Pipeline Orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class QSolCompiler:
    """
    Quantum Solidity Compiler — full pipeline.

    Usage:
        compiler = QSolCompiler()
        result = compiler.compile(source_code)
        if result.success:
            print(result.bytecode_hex)
    """

    def __init__(self) -> None:
        logger.info("QSolCompiler initialised")

    def compile(self, source: str) -> CompilationResult:
        """
        Compile .qsol source to QVM bytecode.

        Args:
            source: Quantum Solidity source code.

        Returns:
            CompilationResult with bytecode, ABI, and diagnostics.
        """
        try:
            # Phase 1: Lex
            lexer = QSolLexer(source)
            tokens = lexer.tokenise()
            logger.info(f"Lexed {len(tokens)} tokens")

            # Phase 2: Parse
            parser = QSolParser(tokens)
            ast = parser.parse()
            logger.info(f"Parsed AST: {ast.node_type.name} with {len(ast.children)} children")

            # Phase 3: Generate
            codegen = QSolCodeGenerator()
            result = codegen.generate(ast, source)

            logger.info(
                f"Compilation {'succeeded' if result.success else 'failed'}: "
                f"{len(result.bytecode)} bytes, {result.stats.get('quantum_ops', 0)} quantum ops"
            )
            return result

        except SyntaxError as e:
            logger.error(f"Syntax error: {e}")
            return CompilationResult(
                success=False,
                bytecode=b"",
                bytecode_hex="0x",
                abi=[],
                contract_name="",
                source_hash=hashlib.sha256(source.encode()).hexdigest(),
                errors=[str(e)],
                warnings=[],
                stats={},
            )
        except Exception as e:
            logger.error(f"Compilation error: {e}")
            return CompilationResult(
                success=False,
                bytecode=b"",
                bytecode_hex="0x",
                abi=[],
                contract_name="",
                source_hash=hashlib.sha256(source.encode()).hexdigest(),
                errors=[f"Internal compiler error: {e}"],
                warnings=[],
                stats={},
            )

    def compile_file(self, filepath: str) -> CompilationResult:
        """Compile a .qsol file from disk."""
        with open(filepath, "r") as f:
            source = f.read()
        return self.compile(source)
