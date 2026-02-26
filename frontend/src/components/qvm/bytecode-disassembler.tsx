"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";

/** EVM opcode lookup table — standard + quantum opcodes. */
const OPCODES: Record<number, { name: string; inputs: number; outputs: number }> = {
  0x00: { name: "STOP", inputs: 0, outputs: 0 },
  0x01: { name: "ADD", inputs: 2, outputs: 1 },
  0x02: { name: "MUL", inputs: 2, outputs: 1 },
  0x03: { name: "SUB", inputs: 2, outputs: 1 },
  0x04: { name: "DIV", inputs: 2, outputs: 1 },
  0x05: { name: "SDIV", inputs: 2, outputs: 1 },
  0x06: { name: "MOD", inputs: 2, outputs: 1 },
  0x07: { name: "SMOD", inputs: 2, outputs: 1 },
  0x08: { name: "ADDMOD", inputs: 3, outputs: 1 },
  0x09: { name: "MULMOD", inputs: 3, outputs: 1 },
  0x0a: { name: "EXP", inputs: 2, outputs: 1 },
  0x0b: { name: "SIGNEXTEND", inputs: 2, outputs: 1 },
  0x10: { name: "LT", inputs: 2, outputs: 1 },
  0x11: { name: "GT", inputs: 2, outputs: 1 },
  0x12: { name: "SLT", inputs: 2, outputs: 1 },
  0x13: { name: "SGT", inputs: 2, outputs: 1 },
  0x14: { name: "EQ", inputs: 2, outputs: 1 },
  0x15: { name: "ISZERO", inputs: 1, outputs: 1 },
  0x16: { name: "AND", inputs: 2, outputs: 1 },
  0x17: { name: "OR", inputs: 2, outputs: 1 },
  0x18: { name: "XOR", inputs: 2, outputs: 1 },
  0x19: { name: "NOT", inputs: 1, outputs: 1 },
  0x1a: { name: "BYTE", inputs: 2, outputs: 1 },
  0x1b: { name: "SHL", inputs: 2, outputs: 1 },
  0x1c: { name: "SHR", inputs: 2, outputs: 1 },
  0x1d: { name: "SAR", inputs: 2, outputs: 1 },
  0x20: { name: "SHA3", inputs: 2, outputs: 1 },
  0x30: { name: "ADDRESS", inputs: 0, outputs: 1 },
  0x31: { name: "BALANCE", inputs: 1, outputs: 1 },
  0x32: { name: "ORIGIN", inputs: 0, outputs: 1 },
  0x33: { name: "CALLER", inputs: 0, outputs: 1 },
  0x34: { name: "CALLVALUE", inputs: 0, outputs: 1 },
  0x35: { name: "CALLDATALOAD", inputs: 1, outputs: 1 },
  0x36: { name: "CALLDATASIZE", inputs: 0, outputs: 1 },
  0x37: { name: "CALLDATACOPY", inputs: 3, outputs: 0 },
  0x38: { name: "CODESIZE", inputs: 0, outputs: 1 },
  0x39: { name: "CODECOPY", inputs: 3, outputs: 0 },
  0x3a: { name: "GASPRICE", inputs: 0, outputs: 1 },
  0x3b: { name: "EXTCODESIZE", inputs: 1, outputs: 1 },
  0x3c: { name: "EXTCODECOPY", inputs: 4, outputs: 0 },
  0x3d: { name: "RETURNDATASIZE", inputs: 0, outputs: 1 },
  0x3e: { name: "RETURNDATACOPY", inputs: 3, outputs: 0 },
  0x3f: { name: "EXTCODEHASH", inputs: 1, outputs: 1 },
  0x40: { name: "BLOCKHASH", inputs: 1, outputs: 1 },
  0x41: { name: "COINBASE", inputs: 0, outputs: 1 },
  0x42: { name: "TIMESTAMP", inputs: 0, outputs: 1 },
  0x43: { name: "NUMBER", inputs: 0, outputs: 1 },
  0x44: { name: "DIFFICULTY", inputs: 0, outputs: 1 },
  0x45: { name: "GASLIMIT", inputs: 0, outputs: 1 },
  0x46: { name: "CHAINID", inputs: 0, outputs: 1 },
  0x47: { name: "SELFBALANCE", inputs: 0, outputs: 1 },
  0x50: { name: "POP", inputs: 1, outputs: 0 },
  0x51: { name: "MLOAD", inputs: 1, outputs: 1 },
  0x52: { name: "MSTORE", inputs: 2, outputs: 0 },
  0x53: { name: "MSTORE8", inputs: 2, outputs: 0 },
  0x54: { name: "SLOAD", inputs: 1, outputs: 1 },
  0x55: { name: "SSTORE", inputs: 2, outputs: 0 },
  0x56: { name: "JUMP", inputs: 1, outputs: 0 },
  0x57: { name: "JUMPI", inputs: 2, outputs: 0 },
  0x58: { name: "PC", inputs: 0, outputs: 1 },
  0x59: { name: "MSIZE", inputs: 0, outputs: 1 },
  0x5a: { name: "GAS", inputs: 0, outputs: 1 },
  0x5b: { name: "JUMPDEST", inputs: 0, outputs: 0 },
  0xf0: { name: "QCREATE", inputs: 1, outputs: 1 },
  0xf1: { name: "QMEASURE", inputs: 1, outputs: 1 },
  0xf2: { name: "QENTANGLE", inputs: 2, outputs: 1 },
  0xf3: { name: "QGATE", inputs: 2, outputs: 0 },
  0xf4: { name: "QVERIFY", inputs: 2, outputs: 1 },
  0xf5: { name: "QCOMPLIANCE", inputs: 1, outputs: 1 },
  0xf6: { name: "QRISK", inputs: 1, outputs: 1 },
  0xf7: { name: "QRISK_SYS", inputs: 0, outputs: 1 },
  0xf8: { name: "QBRIDGE_ENT", inputs: 2, outputs: 1 },
  0xf9: { name: "QBRIDGE_VER", inputs: 2, outputs: 1 },
  0xfa: { name: "STATICCALL", inputs: 6, outputs: 1 },
  0xfd: { name: "REVERT", inputs: 2, outputs: 0 },
  0xfe: { name: "INVALID", inputs: 0, outputs: 0 },
  0xff: { name: "SELFDESTRUCT", inputs: 1, outputs: 0 },
};

// PUSH1-PUSH32
for (let i = 0; i < 32; i++) {
  OPCODES[0x60 + i] = { name: `PUSH${i + 1}`, inputs: 0, outputs: 1 };
}
// DUP1-DUP16
for (let i = 0; i < 16; i++) {
  OPCODES[0x80 + i] = { name: `DUP${i + 1}`, inputs: i + 1, outputs: i + 2 };
}
// SWAP1-SWAP16
for (let i = 0; i < 16; i++) {
  OPCODES[0x90 + i] = { name: `SWAP${i + 1}`, inputs: i + 2, outputs: i + 2 };
}
// LOG0-LOG4
for (let i = 0; i < 5; i++) {
  OPCODES[0xa0 + i] = { name: `LOG${i}`, inputs: i + 2, outputs: 0 };
}

interface DisassembledOp {
  offset: number;
  opcode: number;
  name: string;
  operand?: string;
  isQuantum: boolean;
}

function disassemble(hex: string): DisassembledOp[] {
  const clean = hex.replace(/^0x/i, "").replace(/\s/g, "");
  if (!/^[0-9a-fA-F]*$/.test(clean)) return [];
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }

  const ops: DisassembledOp[] = [];
  let pc = 0;
  while (pc < bytes.length) {
    const opcode = bytes[pc];
    const info = OPCODES[opcode];
    const name = info?.name ?? `UNKNOWN(0x${opcode.toString(16).padStart(2, "0")})`;
    const isQuantum = opcode >= 0xf0 && opcode <= 0xf9;

    let operand: string | undefined;
    // PUSH instructions have inline data
    if (opcode >= 0x60 && opcode <= 0x7f) {
      const pushSize = opcode - 0x5f;
      const dataBytes = bytes.slice(pc + 1, pc + 1 + pushSize);
      operand = "0x" + Array.from(dataBytes).map((b) => b.toString(16).padStart(2, "0")).join("");
      ops.push({ offset: pc, opcode, name, operand, isQuantum });
      pc += 1 + pushSize;
    } else {
      ops.push({ offset: pc, opcode, name, isQuantum, operand: undefined });
      pc += 1;
    }

    if (ops.length >= 500) break; // Safety cap
  }
  return ops;
}

export function BytecodeDisassembler() {
  const [input, setInput] = useState("");
  const [ops, setOps] = useState<DisassembledOp[]>([]);

  function handleDisassemble() {
    setOps(disassemble(input));
  }

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Bytecode Disassembler
      </h3>

      <div className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste bytecode (0x6080604052...)"
          className="flex-1 rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
        />
        <button
          onClick={handleDisassemble}
          disabled={!input.trim()}
          className="rounded-lg bg-quantum-green/20 px-5 py-2.5 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30 disabled:opacity-40"
        >
          Disassemble
        </button>
      </div>

      {ops.length > 0 && (
        <div className="mt-4 max-h-80 overflow-y-auto rounded-lg border border-border-subtle bg-bg-deep">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-deep">
              <tr className="border-b border-border-subtle text-left text-text-secondary">
                <th className="px-3 py-2">Offset</th>
                <th className="px-3 py-2">Hex</th>
                <th className="px-3 py-2">Opcode</th>
                <th className="px-3 py-2">Operand</th>
              </tr>
            </thead>
            <tbody className="font-[family-name:var(--font-code)]">
              {ops.map((op, i) => (
                <tr
                  key={i}
                  className={`border-b border-border-subtle/30 ${
                    op.isQuantum ? "bg-quantum-violet/5" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 text-text-secondary">
                    {op.offset.toString(16).padStart(4, "0")}
                  </td>
                  <td className="px-3 py-1.5 text-text-secondary">
                    {op.opcode.toString(16).padStart(2, "0")}
                  </td>
                  <td
                    className={`px-3 py-1.5 font-medium ${
                      op.isQuantum ? "text-quantum-violet" : "text-quantum-green"
                    }`}
                  >
                    {op.name}
                  </td>
                  <td className="max-w-[200px] truncate px-3 py-1.5 text-text-secondary">
                    {op.operand ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-border-subtle px-3 py-2 text-xs text-text-secondary">
            {ops.length} instruction{ops.length !== 1 ? "s" : ""} decoded
          </p>
        </div>
      )}
    </Card>
  );
}
