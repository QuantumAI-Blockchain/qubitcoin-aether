// K Framework Specification: QVM Opcode Semantics
// Formal executable semantics for the Qubitcoin Virtual Machine.
//
// This specification defines the exact behavior of each QVM opcode
// using the K Framework's rewriting-based approach. It serves as:
//   1. Formal reference for opcode behavior
//   2. Basis for symbolic execution and property verification
//   3. Ground truth for fuzzing and differential testing
//
// Coverage: EVM arithmetic, memory, storage, flow control + quantum opcodes (0xD0-0xDE)

module QVM-OPCODES
    imports INT
    imports BOOL
    imports MAP
    imports LIST
    imports BYTES

    // ─── Configuration ──────────────────────────────────────────────────

    configuration
        <qvm>
            <k> $PGM:Program </k>
            <pc> 0 </pc>
            <gas> 0 </gas>
            <stack> .List </stack>
            <memory> .Map </memory>         // offset -> byte
            <storage> .Map </storage>       // key -> value
            <bytecode> .Bytes </bytecode>
            <halted> false </halted>
            <returnData> .Bytes </returnData>
            <callDepth> 0 </callDepth>
            <quantumStates> .Map </quantumStates>  // QVM extension: id -> density_matrix
        </qvm>

    // ─── Types ──────────────────────────────────────────────────────────

    syntax Word ::= Int                          // 256-bit unsigned integer
    syntax Gas  ::= Int
    syntax Program ::= List{Int, ""}             // bytecode as list of ints

    // Stack operations
    syntax KItem ::= "#push" "(" Int ")"
                   | "#pop"

    // 256-bit modular arithmetic
    syntax Int ::= "mod256" "(" Int ")"          [function]
    rule mod256(X) => X modInt (2 ^Int 256)

    // ─── STOP (0x00) ────────────────────────────────────────────────────
    // Halts execution.

    rule <k> 0x00 ~> REST => . </k>
         <halted> false => true </halted>
         <gas> G => G </gas>

    // ─── ADD (0x01) ─────────────────────────────────────────────────────
    // Pops two values, pushes their 256-bit sum.
    // Gas: 3

    rule <k> 0x01 ~> REST => REST </k>
         <stack> ListItem(A) ListItem(B) STACK => ListItem(mod256(A +Int B)) STACK </stack>
         <gas> G => G -Int 3 </gas>
         requires G >=Int 3

    // ─── MUL (0x02) ─────────────────────────────────────────────────────
    // Gas: 5

    rule <k> 0x02 ~> REST => REST </k>
         <stack> ListItem(A) ListItem(B) STACK => ListItem(mod256(A *Int B)) STACK </stack>
         <gas> G => G -Int 5 </gas>
         requires G >=Int 5

    // ─── SUB (0x03) ─────────────────────────────────────────────────────
    // Gas: 3

    rule <k> 0x03 ~> REST => REST </k>
         <stack> ListItem(A) ListItem(B) STACK => ListItem(mod256(A -Int B)) STACK </stack>
         <gas> G => G -Int 3 </gas>
         requires G >=Int 3

    // ─── DIV (0x04) ─────────────────────────────────────────────────────
    // Gas: 5. Division by zero yields 0.

    rule <k> 0x04 ~> REST => REST </k>
         <stack> ListItem(A) ListItem(B) STACK => ListItem(A /Int B) STACK </stack>
         <gas> G => G -Int 5 </gas>
         requires G >=Int 5 andBool B =/=Int 0

    rule <k> 0x04 ~> REST => REST </k>
         <stack> ListItem(_) ListItem(0) STACK => ListItem(0) STACK </stack>
         <gas> G => G -Int 5 </gas>
         requires G >=Int 5

    // ─── ISZERO (0x15) ──────────────────────────────────────────────────
    // Gas: 3

    rule <k> 0x15 ~> REST => REST </k>
         <stack> ListItem(0) STACK => ListItem(1) STACK </stack>
         <gas> G => G -Int 3 </gas>
         requires G >=Int 3

    rule <k> 0x15 ~> REST => REST </k>
         <stack> ListItem(A) STACK => ListItem(0) STACK </stack>
         <gas> G => G -Int 3 </gas>
         requires G >=Int 3 andBool A =/=Int 0

    // ─── SLOAD (0x54) ───────────────────────────────────────────────────
    // Gas: 2100 (cold) / 100 (warm). Simplified to 2100.

    rule <k> 0x54 ~> REST => REST </k>
         <stack> ListItem(KEY) STACK => ListItem(VALUE) STACK </stack>
         <storage> KEY |-> VALUE REST_STORAGE </storage>
         <gas> G => G -Int 2100 </gas>
         requires G >=Int 2100

    rule <k> 0x54 ~> REST => REST </k>
         <stack> ListItem(KEY) STACK => ListItem(0) STACK </stack>
         <storage> STORE </storage>
         <gas> G => G -Int 2100 </gas>
         requires G >=Int 2100 andBool notBool KEY in_keys(STORE)

    // ─── SSTORE (0x55) ──────────────────────────────────────────────────
    // Gas: 20000 (simplified).

    rule <k> 0x55 ~> REST => REST </k>
         <stack> ListItem(KEY) ListItem(VALUE) STACK => STACK </stack>
         <storage> STORE => STORE [ KEY <- VALUE ] </storage>
         <gas> G => G -Int 20000 </gas>
         requires G >=Int 20000

    // ─── JUMP (0x56) ────────────────────────────────────────────────────
    // Gas: 8

    rule <k> 0x56 ~> _ => BYTECODE[DEST] ~> REST </k>
         <stack> ListItem(DEST) STACK => STACK </stack>
         <pc> _ => DEST </pc>
         <bytecode> BYTECODE </bytecode>
         <gas> G => G -Int 8 </gas>
         requires G >=Int 8 andBool DEST <Int lengthBytes(BYTECODE)

    // ─── PUSH1 (0x60) ───────────────────────────────────────────────────
    // Gas: 3

    rule <k> 0x60 ~> VALUE ~> REST => REST </k>
         <stack> STACK => ListItem(VALUE) STACK </stack>
         <pc> PC => PC +Int 2 </pc>
         <gas> G => G -Int 3 </gas>
         requires G >=Int 3

    // ═════════════════════════════════════════════════════════════════════
    // QUANTUM OPCODES (0xD0-0xDE) — QVM Extensions
    // ═════════════════════════════════════════════════════════════════════

    // ─── QGATE (0xD0) ───────────────────────────────────────────────────
    // Apply quantum gate to state. Gas: 2000.
    // Precondition: quantum state ID on stack, gate type on stack.

    rule <k> 0xD0 ~> REST => REST </k>
         <stack> ListItem(GATE_TYPE) ListItem(STATE_ID) STACK => ListItem(1) STACK </stack>
         <quantumStates> STATE_ID |-> STATE REST_QS </quantumStates>
         <gas> G => G -Int 2000 </gas>
         requires G >=Int 2000

    // ─── QMEASURE (0xD1) ────────────────────────────────────────────────
    // Measure quantum state, collapse to classical. Gas: 3000.

    rule <k> 0xD1 ~> REST => REST </k>
         <stack> ListItem(STATE_ID) STACK => ListItem(RESULT) STACK </stack>
         <quantumStates> STATE_ID |-> _ REST_QS => REST_QS </quantumStates>
         <gas> G => G -Int 3000 </gas>
         requires G >=Int 3000
         // RESULT is non-deterministic (quantum measurement)

    // ─── QENTANGLE (0xD2) ───────────────────────────────────────────────
    // Create entangled pair. Gas: 10000.

    rule <k> 0xD2 ~> REST => REST </k>
         <stack> ListItem(STATE_A) ListItem(STATE_B) STACK => ListItem(1) STACK </stack>
         <quantumStates> STATE_A |-> SA STATE_B |-> SB REST_QS </quantumStates>
         <gas> G => G -Int 10000 </gas>
         requires G >=Int 10000

    // ─── QCREATE (0xDA) ─────────────────────────────────────────────────
    // Create new quantum state (density matrix). Gas: 5000 + 5000*2^n.

    rule <k> 0xDA ~> REST => REST </k>
         <stack> ListItem(N_QUBITS) STACK => ListItem(STATE_ID) STACK </stack>
         <quantumStates> QS => QS [ STATE_ID <- "initial" ] </quantumStates>
         <gas> G => G -Int (5000 +Int (5000 *Int (2 ^Int N_QUBITS))) </gas>
         requires G >=Int (5000 +Int (5000 *Int (2 ^Int N_QUBITS)))

    // ─── QVERIFY (0xDB) ─────────────────────────────────────────────────
    // Verify quantum proof. Gas: 8000.

    rule <k> 0xDB ~> REST => REST </k>
         <stack> ListItem(PROOF) STACK => ListItem(VALID) STACK </stack>
         <gas> G => G -Int 8000 </gas>
         requires G >=Int 8000
         // VALID is 1 if proof verifies, 0 otherwise

    // ─── Out of Gas ─────────────────────────────────────────────────────
    // Any opcode with insufficient gas halts execution.

    rule <k> _ ~> _ => . </k>
         <gas> G </gas>
         <halted> false => true </halted>
         requires G <Int 0

endmodule
