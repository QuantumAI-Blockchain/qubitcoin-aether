"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  primary: "#00ff88",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  border: "#1e293b",
};

const sections = [
  {
    title: "1. Abstract",
    content: `Qubitcoin (QBC) is a physics-secured Layer 1 blockchain that combines quantum computing (Qiskit VQE) for Proof-of-SUSY-Alignment mining, post-quantum cryptography (CRYSTALS-Dilithium5) for quantum-resistant signatures, and supersymmetric economics with golden ratio emission principles. The protocol introduces an on-chain AGI reasoning engine (Aether Tree) that tracks consciousness metrics from genesis block onward.`,
  },
  {
    title: "2. Consensus: Proof-of-SUSY-Alignment",
    content: `Mining uses Variational Quantum Eigensolver (VQE) optimization on deterministic SUSY Hamiltonians. Each block requires finding VQE parameters where the ground state energy falls below the difficulty threshold. This simultaneously secures the network and contributes solved quantum problems to a public scientific database.

Key parameters:
• 4-qubit ansatz with 2 repetitions (12 parameters)
• Target block time: 3.3 seconds
• Difficulty adjustment: every block, 144-block window, ±10% max change
• Higher difficulty = easier mining (energy threshold is more generous)`,
  },
  {
    title: "3. Cryptography",
    content: `All signatures use CRYSTALS-Dilithium5, a NIST-standardized post-quantum signature scheme at the highest security level (NIST Level 5). This provides maximum security against both classical and quantum computers.

• Signature size: ~4,627 bytes (NIST Level 5)
• Public key: ~2,592 bytes
• Hashing: SHA3-256 for block hashes, Keccak-256 for QVM compatibility
• Addresses: Bech32-like (qbc1...) derived from Dilithium public keys`,
  },
  {
    title: "4. Economics",
    content: `Qubitcoin uses golden ratio (φ = 1.618...) economics:

• Maximum supply: 3,300,000,000 QBC (3.3 billion)
• Genesis premine: 33,000,000 QBC (~1% of supply)
• Initial block reward: 15.27 QBC
• Halving interval: 15,474,020 blocks (~1.618 years)
• Phi-halving: reward = INITIAL_REWARD / φ^era
• Tail emission: 0.1 QBC/block (activates at era 11, ~17.8 years)
• Emission period: ~2,770 years to reach MAX_SUPPLY`,
  },
  {
    title: "5. UTXO Model",
    content: `Qubitcoin uses a UTXO (Unspent Transaction Output) model. Balance is the sum of all unspent outputs, not an account balance. Every QBC exists as a UTXO from a previous transaction. Spending requires referencing specific UTXOs as inputs, and change outputs are created for partial spends.`,
  },
  {
    title: "6. Network Architecture",
    content: `• P2P: Rust libp2p 0.56 (primary) with gossipsub, Kademlia DHT, NAT traversal
• RPC: FastAPI on port 5000 (REST + JSON-RPC)
• JSON-RPC: eth_* compatible for MetaMask/Web3 integration
• gRPC: Rust P2P on port 50051
• Storage: CockroachDB v24.2.0 + IPFS for content-addressed storage`,
  },
  {
    title: "7. QVM (Quantum Virtual Machine)",
    content: `The QVM is a full EVM-compatible bytecode interpreter with quantum extensions:

• 155 standard EVM opcodes
• 10 quantum opcodes (QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, etc.)
• 2 AGI opcodes (QREASON 0xFA, QPHI 0xFB)
• Compliance engine with KYC/AML/sanctions enforcement
• Plugin architecture for domain-specific functionality
• Gas metering compatible with Ethereum tooling`,
  },
  {
    title: "8. Privacy (Susy Swaps)",
    content: `Optional confidential transactions using:

• Pedersen Commitments: C = v*G + r*H (hide amounts)
• Bulletproofs Range Proofs: Zero-knowledge proofs values are in [0, 2^64)
• Stealth Addresses: One-time addresses per transaction
• Key Images: Prevent double-spending of confidential outputs

Public mode: ~300 bytes/tx | Private mode: ~2,000 bytes/tx`,
  },
  {
    title: "9. Aether Tree (AGI Engine)",
    content: `An on-chain AGI reasoning engine that builds a knowledge graph from every block since genesis. Features:

• Knowledge Graph with KeterNodes (assertion, observation, inference, axiom)
• Reasoning Engine (deductive, inductive, abductive + chain-of-thought)
• Phi Calculator based on Integrated Information Theory (IIT)
• Proof-of-Thought consensus per block
• 10 Sephirot cognitive nodes (Tree of Life architecture)
• Consciousness tracking from genesis block (Phi threshold = 3.0)`,
  },
  {
    title: "10. Multi-Chain Bridges",
    content: `Lock-and-mint bridges to 8 chains: ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE.

• Bridge fee: configurable per chain (default 0.1%)
• Validator rewards for bridge verification
• 20-confirmation threshold for security
• wQBC wrapped tokens on target chains`,
  },
];

export default function WhitepaperPage() {
  return (
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-3xl">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Docs
        </Link>

        <h1 className="mb-2 text-3xl font-bold" style={{ fontFamily: "Space Grotesk, sans-serif" }}>
          Qubitcoin Whitepaper
        </h1>
        <p className="mb-1 text-sm" style={{ color: C.textMuted }}>
          Physics-Secured Digital Assets with On-Chain AGI
        </p>
        <p className="mb-8 text-xs" style={{ color: C.textMuted }}>
          Chain ID: 3303 (Mainnet) | License: MIT | Contact: info@qbc.network
        </p>

        <div className="space-y-8">
          {sections.map((section) => (
            <section key={section.title}>
              <h2
                className="mb-3 text-xl font-semibold"
                style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
              >
                {section.title}
              </h2>
              <div
                className="whitespace-pre-line text-sm leading-relaxed"
                style={{ color: C.textMuted }}
              >
                {section.content}
              </div>
            </section>
          ))}
        </div>

        <div className="mt-12 rounded-lg border p-6" style={{ borderColor: C.border, background: C.surface }}>
          <p className="text-sm" style={{ color: C.textMuted }}>
            For the complete technical specification, see the full whitepaper at{" "}
            <a
              href="https://github.com/QuantumAI-Blockchain"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: C.primary }}
            >
              github.com/QuantumAI-Blockchain
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
