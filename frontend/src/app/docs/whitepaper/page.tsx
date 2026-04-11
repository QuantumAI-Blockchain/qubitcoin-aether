"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  primary: "#00ff88",
  secondary: "#7c3aed",
  accent: "#f59e0b",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  border: "#1e293b",
  error: "#ef4444",
};

/* ------------------------------------------------------------------ */
/*  DATA TABLES                                                        */
/* ------------------------------------------------------------------ */

const quantumOpcodes = [
  { opcode: "QCREATE", hex: "0xF0", gas: "5,000 + 5,000 x 2^n", desc: "Create quantum state as density matrix with n qubits" },
  { opcode: "QMEASURE", hex: "0xF1", gas: "3,000", desc: "Measure quantum state, collapsing superposition to classical bits" },
  { opcode: "QENTANGLE", hex: "0xF2", gas: "10,000", desc: "Create entangled pair between two contract quantum states" },
  { opcode: "QGATE", hex: "0xF3", gas: "2,000", desc: "Apply quantum gate (H, X, Y, Z, CNOT, T, S, RX, RY, RZ) to state" },
  { opcode: "QVERIFY", hex: "0xF4", gas: "8,000", desc: "Verify quantum proof against expected measurement distribution" },
  { opcode: "QCOMPLIANCE", hex: "0xF5", gas: "15,000", desc: "Pre-flight KYC/AML/sanctions compliance check before execution" },
  { opcode: "QRISK", hex: "0xF6", gas: "5,000", desc: "Query SUSY Hamiltonian-based risk score for target address" },
  { opcode: "QRISK_SYSTEMIC", hex: "0xF7", gas: "10,000", desc: "Query systemic risk via contagion model across connected accounts" },
  { opcode: "QBRIDGE_ENTANGLE", hex: "0xF8", gas: "20,000", desc: "Cross-chain quantum entanglement for bridge state synchronization" },
  { opcode: "QBRIDGE_VERIFY", hex: "0xF9", gas: "15,000", desc: "Verify cross-chain bridge proof against remote chain state root" },
  { opcode: "QREASON", hex: "0xFA", gas: "25,000", desc: "Invoke Aether Tree reasoning engine from within smart contract" },
  { opcode: "QPHI", hex: "0xFB", gas: "10,000", desc: "Query current integrated information (Phi) integration metric" },
];

const sephirotNodes = [
  { name: "Keter", fn: "Meta-learning, goal formation", brain: "Prefrontal cortex", qubits: 8, yukawa: "1.0", tier: 0 },
  { name: "Chochmah", fn: "Intuition, pattern discovery", brain: "Right hemisphere", qubits: 6, yukawa: "phi^-1", tier: 1 },
  { name: "Binah", fn: "Logic, causal inference", brain: "Left hemisphere", qubits: 4, yukawa: "phi^-1", tier: 1 },
  { name: "Chesed", fn: "Exploration, divergent thinking", brain: "Default mode network", qubits: 10, yukawa: "phi^-2", tier: 2 },
  { name: "Gevurah", fn: "Constraint, safety validation", brain: "Amygdala, inhibitory circuits", qubits: 3, yukawa: "phi^-2", tier: 2 },
  { name: "Tiferet", fn: "Integration, conflict resolution", brain: "Thalamocortical loops", qubits: 12, yukawa: "phi^-1", tier: 1 },
  { name: "Netzach", fn: "Reinforcement learning, habits", brain: "Basal ganglia", qubits: 5, yukawa: "phi^-3", tier: 3 },
  { name: "Hod", fn: "Language, semantic encoding", brain: "Broca/Wernicke areas", qubits: 7, yukawa: "phi^-3", tier: 3 },
  { name: "Yesod", fn: "Memory, multimodal fusion", brain: "Hippocampus", qubits: 16, yukawa: "phi^-4", tier: 4 },
  { name: "Malkuth", fn: "Action, world interaction", brain: "Motor cortex", qubits: 4, yukawa: "phi^-4", tier: 4 },
];

const bridgeChains = [
  { chain: "Ethereum", wqbc: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67", wqusd: "0x884867d25552b6117F85428405aeAA208A8CAdB3", dex: "Uniswap V3" },
  { chain: "BNB Chain", wqbc: "0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147", wqusd: "0xD137C89ed83d1D54802d07487bf1AF6e0b409BE3", dex: "PancakeSwap V3" },
  { chain: "Solana", wqbc: "TBD", wqusd: "TBD", dex: "Raydium" },
  { chain: "Polygon", wqbc: "TBD", wqusd: "TBD", dex: "QuickSwap V3" },
  { chain: "Avalanche", wqbc: "TBD", wqusd: "TBD", dex: "Trader Joe V2" },
  { chain: "Arbitrum", wqbc: "TBD", wqusd: "TBD", dex: "Camelot V3" },
  { chain: "Optimism", wqbc: "TBD", wqusd: "TBD", dex: "Velodrome" },
  { chain: "Base", wqbc: "TBD", wqusd: "TBD", dex: "Aerodrome" },
];

const contractCategories = [
  {
    category: "Aether Core",
    count: 7,
    contracts: [
      "AetherKernel.sol -- Main orchestration and lifecycle management",
      "NodeRegistry.sol -- Sephirot node registration, staking, and slashing",
      "SUSYEngine.sol -- SUSY balance enforcement and golden ratio validation",
      "MessageBus.sol -- Inter-node CSF message routing with QBC priority fees",
      "HiggsField.sol -- Cognitive mass via Mexican Hat spontaneous symmetry breaking",
      "PhaseSync.sol -- Kuramoto order parameter synchronization metrics",
      "GlobalWorkspace.sol -- Consciousness broadcasting mechanism",
    ],
  },
  {
    category: "Proof-of-Thought",
    count: 4,
    contracts: [
      "ProofOfThought.sol -- PoT validation, proof submission, and verification",
      "TaskMarket.sol -- Reasoning task submission with QBC bounty escrow",
      "ValidatorRegistry.sol -- Validator stake management (minimum 100 QBC)",
      "RewardDistributor.sol -- QBC reward and slash distribution engine",
    ],
  },
  {
    category: "Integration",
    count: 3,
    contracts: [
      "ConsciousnessDashboard.sol -- On-chain Phi tracking and historical records",
      "ConstitutionalAI.sol -- Value enforcement and alignment constraints",
      "EmergencyShutdown.sol -- Multi-sig kill switch for catastrophic scenarios",
    ],
  },
  {
    category: "Sephirot Nodes",
    count: 10,
    contracts: [
      "SephirotKeter.sol -- Meta-learning goal space (8-qubit)",
      "SephirotChochmah.sol -- Intuition pattern discovery (6-qubit)",
      "SephirotBinah.sol -- Logical causal inference (4-qubit)",
      "SephirotChesed.sol -- Divergent exploration space (10-qubit)",
      "SephirotGevurah.sol -- Safety constraint validation (3-qubit)",
      "SephirotTiferet.sol -- Integration and conflict resolution (12-qubit)",
      "SephirotNetzach.sol -- Reinforcement learning policy (5-qubit)",
      "SephirotHod.sol -- Semantic language encoding (7-qubit)",
      "SephirotYesod.sol -- Episodic memory buffer (16-qubit)",
      "SephirotMalkuth.sol -- Motor action commands (4-qubit)",
    ],
  },
  {
    category: "QUSD Stablecoin",
    count: 10,
    contracts: [
      "QUSD.sol -- QBC-20 stablecoin token with 0.05% transfer fee",
      "QUSDReserve.sol -- Multi-asset reserve vault with oracle integration",
      "QUSDDebtLedger.sol -- Immutable debt tracking with milestone events",
      "QUSDOracle.sol -- Multi-source median aggregation price feed",
      "QUSDStabilizer.sol -- Peg stability mechanism with configurable bands",
      "QUSDAllocation.sol -- Four-tier vesting for initial 3.3B distribution",
      "QUSDGovernance.sol -- Proposal/vote/execute with 48-hour timelock",
      "QUSDFlashLoan.sol -- Flash loan facility with fee accrual",
      "QUSDBridgeVault.sol -- Cross-chain wQUSD lock-and-mint vault",
      "QUSDKeeperRewards.sol -- Keeper incentive and reward distribution",
    ],
  },
  {
    category: "Tokens",
    count: 6,
    contracts: [
      "QBC20.sol -- Fungible token standard (ERC-20 compatible)",
      "QBC721.sol -- Non-fungible token standard (ERC-721 compatible)",
      "QBC1155.sol -- Multi-token standard (ERC-1155 compatible)",
      "ERC20QC.sol -- Compliance-aware token with KYC/AML hooks",
      "TokenFactory.sol -- Template-based token deployment factory",
      "WrappedQBC.sol -- Wrapped QBC for L2 QVM account compatibility",
    ],
  },
  {
    category: "Bridge",
    count: 2,
    contracts: [
      "BridgeVault.sol -- Lock-and-mint vault with configurable fee (10 bps default)",
      "BridgeValidator.sol -- Multi-sig bridge transaction validation",
    ],
  },
  {
    category: "Interfaces",
    count: 7,
    contracts: [
      "IQBC20.sol -- QBC-20 token interface",
      "IQBC721.sol -- QBC-721 NFT interface",
      "IOracle.sol -- Price oracle interface",
      "IBridge.sol -- Cross-chain bridge interface",
      "ICompliance.sol -- KYC/AML compliance interface",
      "IGovernance.sol -- Governance proposal interface",
      "IAetherKernel.sol -- Aether Tree kernel interface",
    ],
  },
  {
    category: "Proxy / Upgradeable",
    count: 3,
    contracts: [
      "TransparentProxy.sol -- Transparent upgradeable proxy pattern",
      "ProxyAdmin.sol -- Proxy administration and upgrade control",
      "UpgradeGovernor.sol -- Governance-controlled protocol upgrade execution",
    ],
  },
  {
    category: "Investor",
    count: 3,
    contracts: [
      "InvestorPool.sol -- Investor revenue pool with proportional distribution",
      "InvestorVesting.sol -- Time-locked vesting with cliff and linear release",
      "InvestorGovernance.sol -- Investor-specific governance proposals",
    ],
  },
  {
    category: "AIKGS Sidecar",
    count: 5,
    contracts: [
      "AIKGSRegistry.sol -- Knowledge graph sidecar node registration",
      "AIKGSOracle.sol -- Off-chain knowledge graph data attestation",
      "AIKGSStaking.sol -- Sidecar operator staking and slashing",
      "AIKGSBridge.sol -- Sidecar to mainchain state anchoring",
      "AIKGSGovernance.sol -- Sidecar parameter governance",
    ],
  },
];

const substratePallets = [
  { name: "pallet-qbc-utxo", purpose: "UTXO storage, validation, and double-spend prevention on Substrate runtime" },
  { name: "pallet-qbc-consensus", purpose: "PoSA consensus integration with VQE proof verification hooks" },
  { name: "pallet-qbc-dilithium", purpose: "CRYSTALS-Dilithium5 signature verification as native Substrate extrinsic validation" },
  { name: "pallet-qbc-economics", purpose: "Phi-halving emission schedule with golden ratio reward calculation" },
  { name: "pallet-qbc-qvm-anchor", purpose: "QVM state root anchoring to Substrate block headers" },
  { name: "pallet-qbc-aether-anchor", purpose: "Aether Tree Phi and Proof-of-Thought anchoring to chain state" },
  { name: "pallet-qbc-reversibility", purpose: "Governor-managed multi-sig transaction reversal within 24-hour window (~26,182 blocks)" },
];

const databaseDomains = [
  { domain: "Core Blockchain", tables: 7, desc: "blocks, transactions, accounts, balances, chain_state, mempool, l1l2_bridge" },
  { domain: "Smart Contracts", tables: 9, desc: "contracts, storage, logs, metadata, gas_metering, execution_logs, abi_registry, events, call_traces" },
  { domain: "Quantum States", tables: 4, desc: "quantum_states, entanglement_registry, measurements, computation_receipts" },
  { domain: "Compliance", tables: 8, desc: "kyc_registry, aml_monitoring, sanctions_list, risk_scores, compliance_proofs, audit_logs, jurisdiction_rules, reports" },
  { domain: "Cross-Chain", tables: 5, desc: "bridge_deposits, bridge_withdrawals, bridge_proofs, state_channels, relay_headers" },
  { domain: "Governance", tables: 6, desc: "dao_proposals, votes, oracles, staking_positions, validator_registry, upgrade_queue" },
  { domain: "AGI (Aether)", tables: 8, desc: "knowledge_nodes, knowledge_edges, reasoning_operations, phi_measurements, consciousness_events, training_data, higgs_field_state, higgs_excitations" },
  { domain: "Research", tables: 5, desc: "hamiltonians, vqe_circuits, susy_solutions, benchmark_results, scientific_exports" },
  { domain: "Shared", tables: 3, desc: "ipfs_pins, system_config, migration_log" },
];

const keeperModes = [
  { mode: "off", code: 0, desc: "Daemon disabled. No monitoring or execution. Use during maintenance windows." },
  { mode: "scan", code: 1, desc: "Monitor multi-chain DEX prices and emit depeg signals. No execution. Default startup mode." },
  { mode: "periodic", code: 2, desc: "Check peg status every KEEPER_CHECK_INTERVAL blocks. Execute stabilization if deviation exceeds thresholds." },
  { mode: "continuous", code: 3, desc: "Real-time monitoring with immediate action on depeg detection. Recommended for production." },
  { mode: "aggressive", code: 4, desc: "Pursue all profitable arbitrage opportunities at maximum trade size. Emergency depeg defense." },
];

/* ------------------------------------------------------------------ */
/*  SECTION CARD COMPONENT                                             */
/* ------------------------------------------------------------------ */

function SectionCard({ id, number, title, children }: { id: string; number: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="rounded-lg border p-6" style={{ borderColor: C.border, background: C.surface }}>
      <h2
        className="mb-4 text-xl font-semibold"
        style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
      >
        {number}. {title}
      </h2>
      {children}
    </section>
  );
}

function Paragraph({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 text-sm leading-relaxed" style={{ color: C.textMuted }}>
      {children}
    </p>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 mt-5 text-base font-semibold" style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}>
      {children}
    </h3>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre
      className="mb-4 overflow-x-auto rounded border p-4 text-xs leading-relaxed"
      style={{ background: C.bg, borderColor: C.border, color: C.textMuted, fontFamily: "JetBrains Mono, monospace" }}
    >
      {children}
    </pre>
  );
}

function SpecTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full text-sm" style={{ borderColor: C.border }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${C.border}` }}>
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${C.border}22` }}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={`px-3 py-2 text-xs ${j === 0 ? "font-mono" : ""}`}
                  style={{ color: j === 0 ? C.primary : C.textMuted }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatGrid({ stats }: { stats: { label: string; value: string }[] }) {
  return (
    <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3">
      {stats.map((s) => (
        <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.bg }}>
          <p className="text-sm font-bold" style={{ color: C.accent }}>{s.value}</p>
          <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
        </div>
      ))}
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mb-4 space-y-1.5 pl-4">
      {items.map((item, i) => (
        <li key={i} className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
          <span style={{ color: C.primary }}>--</span> {item}
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/*  TABLE OF CONTENTS                                                   */
/* ------------------------------------------------------------------ */

const tocSections = [
  { id: "protocol-overview", num: "1", title: "Protocol Overview" },
  { id: "consensus", num: "2", title: "Consensus: Proof-of-SUSY-Alignment (PoSA)" },
  { id: "cryptography", num: "3", title: "Cryptography" },
  { id: "economics", num: "4", title: "Economics" },
  { id: "utxo-model", num: "5", title: "UTXO Model" },
  { id: "network-architecture", num: "6", title: "Network Architecture" },
  { id: "qvm", num: "7", title: "Quantum Virtual Machine (QVM)" },
  { id: "aether-tree", num: "8", title: "Aether Tree (On-Chain Reasoning Engine)" },
  { id: "privacy", num: "9", title: "Privacy: SUSY Swaps" },
  { id: "cross-chain-bridge", num: "10", title: "Cross-Chain Bridge" },
  { id: "qusd-stablecoin", num: "11", title: "QUSD Stablecoin" },
  { id: "exchange", num: "12", title: "Exchange (Rust Matching Engine)" },
  { id: "storage", num: "13", title: "Storage" },
  { id: "smart-contracts", num: "14", title: "Smart Contracts" },
  { id: "higgs-cognitive-field", num: "15", title: "Higgs Cognitive Field" },
  { id: "bft-finality", num: "16", title: "BFT Finality" },
  { id: "security-features", num: "17", title: "Security Features" },
  { id: "node-types", num: "18", title: "Node Types" },
  { id: "substrate-migration", num: "19", title: "Substrate Migration" },
];

/* ------------------------------------------------------------------ */
/*  PAGE COMPONENT                                                     */
/* ------------------------------------------------------------------ */

export default function WhitepaperPage() {
  return (
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-4xl">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Docs
        </Link>

        {/* HEADER */}
        <div className="mb-2">
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: C.secondary }}>
            Technical Specification Document
          </p>
        </div>
        <h1
          className="mb-2 text-3xl font-bold md:text-4xl"
          style={{ fontFamily: "Space Grotesk, sans-serif" }}
        >
          Qubitcoin Whitepaper — Physics-Secured Digital Assets with On-Chain AGI
        </h1>
        <p className="mb-1 text-sm" style={{ color: C.textMuted }}>
          Complete technical specification for the Qubitcoin protocol, SUSY economics, post-quantum cryptography, and Aether Tree AGI
        </p>
        <div className="mb-8 flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: C.textMuted }}>
          <span>Chain ID: 3303 (0xCE7) Mainnet | 3304 (0xCE8) Testnet</span>
          <span>License: MIT</span>
          <span>Version: 1.0.0</span>
          <span>Contact: info@qbc.network</span>
        </div>

        {/* CLASSIFICATION BANNER */}
        <div
          className="mb-8 rounded border p-4"
          style={{ borderColor: C.accent, background: `${C.accent}08` }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: C.accent }}>
            Document Classification: PUBLIC
          </p>
          <p className="mt-1 text-xs" style={{ color: C.textMuted }}>
            This document constitutes the complete technical specification for the Quantum Blockchain
            protocol. All parameters, constants, and thresholds stated herein are exact values used in
            production. This specification is sufficient for independent protocol implementation,
            security audit, or regulatory evaluation.
          </p>
        </div>

        {/* TABLE OF CONTENTS */}
        <div
          className="mb-10 rounded-lg border p-6"
          style={{ borderColor: C.border, background: C.surface }}
        >
          <h2
            className="mb-4 text-lg font-semibold"
            style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
          >
            Table of Contents
          </h2>
          <div className="grid gap-1 md:grid-cols-2">
            {tocSections.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="text-sm transition-colors hover:underline"
                style={{ color: C.textMuted }}
              >
                <span className="font-mono" style={{ color: C.secondary }}>{s.num}.</span>{" "}
                {s.title}
              </a>
            ))}
          </div>
        </div>

        {/* SECTIONS */}
        <div className="space-y-8">

          {/* -------------------------------------------------------- */}
          {/* 1. PROTOCOL OVERVIEW                                      */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="protocol-overview" number="1" title="Protocol Overview">
            <Paragraph>
              Quantum Blockchain is a Layer 1 blockchain protocol secured by variational quantum
              eigensolver (VQE) computation on supersymmetric (SUSY) Hamiltonians. The native currency
              is Qubitcoin (QBC), denominated with 18 decimal places of precision. The protocol
              integrates post-quantum cryptographic signatures (CRYSTALS-Dilithium5, NIST ML-DSA-87,
              Level 5), a full EVM-compatible virtual machine with quantum opcode extensions (QVM),
              and an on-chain reasoning engine (Aether Tree) that tracks integrated information metrics
              from genesis.
            </Paragraph>

            <SubHeading>Protocol Identifiers</SubHeading>
            <StatGrid stats={[
              { label: "Native Currency", value: "Qubitcoin (QBC)" },
              { label: "Decimal Precision", value: "18 decimals" },
              { label: "Mainnet Chain ID", value: "3303 (0xCE7)" },
              { label: "Testnet Chain ID", value: "3304 (0xCE8)" },
              { label: "Domain", value: "qbc.network" },
              { label: "Source Repository", value: "QuantumAI-Blockchain" },
              { label: "License", value: "MIT" },
              { label: "Signature Scheme", value: "ML-DSA-87 (Dilithium5)" },
              { label: "Block Time", value: "3.3 seconds" },
            ]} />

            <SubHeading>Protocol Architecture</SubHeading>
            <Paragraph>
              The system is organized into three computational layers plus infrastructure:
            </Paragraph>
            <BulletList items={[
              "Layer 1 (Blockchain Core): UTXO-based transaction model, PoSA consensus, VQE mining, Dilithium5 signatures, Rust libp2p networking, CockroachDB persistence, IPFS content storage",
              "Layer 2 (QVM): 167-opcode EVM-compatible virtual machine (155 EVM + 10 quantum + 2 reasoning), Solidity smart contract execution, gas metering, compliance engine, token standards (QBC-20, QBC-721, QBC-1155)",
              "Layer 3 (Aether Tree): On-chain reasoning engine with knowledge graph, deductive/inductive/abductive inference, information-theoretic integration metric (Phi), 10-node Sephirot cognitive architecture, Proof-of-Thought protocol",
              "Cross-Cutting: Multi-chain bridges to 8 networks (ETH, BNB, SOL, MATIC, AVAX, ARB, OP, BASE), QUSD dollar-pegged stablecoin, Prometheus/Grafana monitoring, Rust exchange matching engine",
            ]} />

            <SubHeading>Production Codebase</SubHeading>
            <SpecTable
              headers={["Layer", "Component", "Language", "Files", "Lines of Code"]}
              rows={[
                ["L1", "Blockchain Core", "Python 3.12+", "160 modules", "~82,500"],
                ["L1", "P2P Network", "Rust (libp2p 0.56)", "4 source files", "~1,200"],
                ["L1", "Security Core", "Rust (PyO3)", "3 source files", "~530"],
                ["L1", "Stratum Server", "Rust", "7 source files", "~1,030"],
                ["L1", "Substrate Hybrid Node", "Rust (Substrate SDK)", "29 files, 7 crates", "~17,400"],
                ["L2", "QVM (Python prototype)", "Python", "8 modules", "~4,500"],
                ["L2", "QVM (Production)", "Go", "34 source files", "~10,000"],
                ["L2", "Solidity Contracts", "Solidity 0.8.24+", "65 contracts", "~15,000"],
                ["L3", "Aether Tree (Python)", "Python", "49 modules", "~29,000"],
                ["L3", "Aether Tree (Rust)", "Rust (PyO3)", "10 modules", "~10,246"],
                ["L3", "Higgs Cognitive Field", "Python + Solidity", "13 files", "~2,700"],
                ["Frontend", "qbc.network", "TypeScript/React/Next.js 16", "200 files", "~66,900"],
                ["Infra", "Docker/Monitoring/DevOps", "YAML/Shell", "20+ configs", "~2,000"],
                ["Tests", "pytest suite", "Python", "4,357 tests", "~40,000"],
              ]}
            />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 2. CONSENSUS                                              */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="consensus" number="2" title="Consensus: Proof-of-SUSY-Alignment (PoSA)">
            <Paragraph>
              Proof-of-SUSY-Alignment (PoSA) replaces hash-based proof-of-work with variational
              quantum eigensolver optimization on deterministic supersymmetric Hamiltonians. Every
              mined block simultaneously secures the network and contributes a solved quantum
              physics problem to a public scientific database. The consensus mechanism operates
              through a five-stage pipeline.
            </Paragraph>

            <SubHeading>Stage 1: Hamiltonian Generation</SubHeading>
            <Paragraph>
              A deterministic SUSY Hamiltonian is generated from the SHA3-256 hash of the previous
              block. The hash bytes seed the Hamiltonian coefficients, ensuring every miner works
              on the identical quantum optimization problem. The generated Hamiltonian is a 4-qubit
              system representing a simplified supersymmetric field theory with both bosonic and
              fermionic terms.
            </Paragraph>

            <SubHeading>Stage 2: VQE Mining</SubHeading>
            <Paragraph>
              Miners use the Variational Quantum Eigensolver (VQE) algorithm with a parameterized
              4-qubit ansatz circuit containing 2 repetition layers (12 variational parameters).
              The objective is to find circuit parameters that minimize the expectation value of
              the SUSY Hamiltonian. The mining condition is satisfied when the computed ground
              state energy falls below the current difficulty threshold.
            </Paragraph>
            <CodeBlock>{`Mining Condition:  E_ground < D_threshold

Where:
  E_ground   = <psi(theta)|H_susy|psi(theta)>   (VQE expectation value)
  D_threshold = current difficulty target          (energy units)
  theta       = 12 variational parameters          (ansatz circuit angles)
  H_susy      = deterministic from prev_block_hash (4-qubit Hamiltonian)

Ansatz: 4 qubits, 2 repetition layers, RY + CNOT entangling gates
Optimizer: COBYLA (gradient-free, noise-resilient)`}</CodeBlock>

            <SubHeading>Stage 3: Difficulty Adjustment</SubHeading>
            <Paragraph>
              Difficulty is adjusted after every block using a 144-block sliding window. The
              algorithm computes the ratio of actual block production time to expected time
              (144 blocks x 3.3 seconds = 475.2 seconds). The adjustment is clamped to a
              maximum change of +/-10% per block to prevent instability.
            </Paragraph>
            <CodeBlock>{`ratio = actual_time / expected_time
new_difficulty = current_difficulty * ratio
clamped: 0.9 * current <= new_difficulty <= 1.1 * current

CRITICAL: Higher difficulty value = easier mining (threshold is more generous)
This is INVERTED from proof-of-work where higher difficulty = harder mining.

Window:      144 blocks
Target:      475.2 seconds (144 x 3.3s)
Max change:  +/-10% per adjustment`}</CodeBlock>

            <SubHeading>Stage 4: Block Reward</SubHeading>
            <Paragraph>
              Block rewards follow a phi-halving emission schedule (see Section 4: Economics).
              The coinbase transaction is created as the first transaction in each block with
              a maturity requirement of 100 confirmations before the reward becomes spendable.
            </Paragraph>

            <SubHeading>Stage 5: Proof-of-Thought</SubHeading>
            <Paragraph>
              Every block includes a Proof-of-Thought generated by the Aether Tree reasoning
              engine. This proof contains the reasoning trace, knowledge graph delta, and
              current Phi measurement for the block, creating an immutable record of on-chain
              reasoning since genesis.
            </Paragraph>

            <SubHeading>Consensus Parameters</SubHeading>
            <StatGrid stats={[
              { label: "Ansatz Qubits", value: "4" },
              { label: "Repetition Layers", value: "2" },
              { label: "Variational Parameters", value: "12" },
              { label: "Target Block Time", value: "3.3 seconds" },
              { label: "Difficulty Window", value: "144 blocks" },
              { label: "Max Difficulty Change", value: "+/-10% per block" },
              { label: "Coinbase Maturity", value: "100 blocks" },
              { label: "Optimizer", value: "COBYLA" },
              { label: "Quantum Backend", value: "Qiskit (local/IBM)" },
            ]} />

            <SubHeading>Block Header Structure</SubHeading>
            <CodeBlock>{`BLOCK HEADER (serialized):
  version:              uint32      (protocol version, currently 1)
  prev_block_hash:      bytes32     (SHA3-256 of previous block header)
  merkle_root:          bytes32     (Merkle root of transaction hashes)
  timestamp:            uint64      (Unix timestamp, seconds)
  difficulty_target:    float64     (energy threshold for VQE proof)
  nonce:                uint64      (mining nonce)
  hamiltonian_seed:     bytes32     (deterministic seed for SUSY Hamiltonian)
  vqe_params:           float64[12] (optimal VQE circuit parameters)
  ground_state_energy:  float64     (achieved energy level - must be < difficulty)
  quantum_state_root:   bytes32     (Merkle root of QVM quantum states)
  compliance_root:      bytes32     (Merkle root of compliance proofs)

BLOCK BODY:
  transactions:         Transaction[]  (regular + confidential UTXO transactions)
  coinbase:             Transaction    (mining reward, vout=0 reward + vout=1 premine at genesis)
  susy_data:            {
    hamiltonian:          object       (generated SUSY Hamiltonian)
    optimal_params:       float64[12]  (solution parameters)
    energy_history:       float64[]    (VQE convergence trace)
  }
  proof_of_thought:     bytes          (Aether Tree reasoning proof)`}</CodeBlock>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 3. CRYPTOGRAPHY                                           */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="cryptography" number="3" title="Cryptography">
            <Paragraph>
              Quantum Blockchain employs a multi-layered cryptographic architecture designed
              for security against both classical and quantum adversaries. All signature
              operations use NIST-standardized post-quantum algorithms at the highest
              available security level.
            </Paragraph>

            <SubHeading>Digital Signatures: CRYSTALS-Dilithium5 (ML-DSA-87)</SubHeading>
            <Paragraph>
              All transaction and block signatures use CRYSTALS-Dilithium5, standardized
              by NIST as ML-DSA-87 (Module Lattice Digital Signature Algorithm). This
              provides NIST Post-Quantum Security Level 5, the highest level, offering
              security equivalent to AES-256 against quantum computers running Shor{"'"}s
              algorithm.
            </Paragraph>
            <SpecTable
              headers={["Parameter", "Value", "Notes"]}
              rows={[
                ["Security Level", "NIST Level 5 (ML-DSA-87)", "Highest standardized post-quantum level"],
                ["Public Key Size", "2,592 bytes", "Lattice-based, stored in UTXO scripts"],
                ["Signature Size", "4,627 bytes", "Per-transaction overhead"],
                ["Secret Key Size", "4,896 bytes", "Stored exclusively in secure_key.env"],
                ["Throughput Impact", "~217 tx/MB", "Compared to ~4,000 tx/MB with ECDSA"],
                ["Hardness Assumption", "Module-LWE + Module-SIS", "Lattice shortest vector problem"],
                ["Hash Function (internal)", "SHAKE-256", "Extendable output function"],
              ]}
            />

            <SubHeading>Block Hashing: SHA3-256</SubHeading>
            <Paragraph>
              Block headers, Merkle roots, and all consensus-critical hashes use SHA3-256
              (FIPS 202). SHA3-256 is a sponge construction based on the Keccak permutation,
              providing 128-bit security against quantum Grover search (256-bit classical).
              SHA3-256 is distinct from Keccak-256 used in Ethereum.
            </Paragraph>

            <SubHeading>QVM Compatibility: Keccak-256</SubHeading>
            <Paragraph>
              The QVM uses Keccak-256 (pre-NIST Keccak, identical to Ethereum{"'"}s hash function)
              for EVM compatibility. This ensures Solidity contracts using keccak256(), abi.encodePacked(),
              and related functions produce identical results to Ethereum. Keccak-256 is used only
              within the QVM execution environment and does not affect L1 consensus.
            </Paragraph>

            <SubHeading>Address Derivation</SubHeading>
            <CodeBlock>{`Address Generation:
  1. Generate Dilithium5 keypair (pk, sk)
  2. Compute SHA3-256(pk) -> 32 bytes
  3. Take last 20 bytes as address payload
  4. Encode as Bech32: "qbc1" + bech32(payload)

Result: qbc1[38 characters]  (e.g., qbc1qw508d6qejxtdg4y5r3zarvary0c5xw7k...)`}</CodeBlock>

            <SubHeading>P2P Encryption: ML-KEM-768 (Kyber)</SubHeading>
            <Paragraph>
              Peer-to-peer network connections are encrypted using a hybrid key encapsulation
              mechanism combining ML-KEM-768 (NIST post-quantum KEM, formerly CRYSTALS-Kyber)
              with classical Noise protocol key exchange. The hybrid approach provides security
              even if either the classical or post-quantum scheme is broken.
            </Paragraph>
            <CodeBlock>{`Hybrid Key Exchange:
  1. Classical: Noise XX handshake -> classical_secret (32 bytes)
  2. Post-Quantum: ML-KEM-768 encapsulation -> pq_secret (32 bytes)
  3. Combined: HKDF-SHA256(classical_secret || pq_secret) -> session_key (32 bytes)
  4. Session: AES-256-GCM with session_key for all subsequent messages

ML-KEM-768 Parameters:
  Public key:      1,184 bytes
  Ciphertext:      1,088 bytes
  Shared secret:   32 bytes
  Security level:  NIST Level 3 (AES-192 equivalent)`}</CodeBlock>

            <SubHeading>ZK Hashing: Poseidon2</SubHeading>
            <Paragraph>
              Zero-knowledge circuit operations use the Poseidon2 hash function over the
              Goldilocks prime field (p = 2^64 - 2^32 + 1 = 18446744069414584321). Poseidon2
              is designed for efficient arithmetic in ZK-SNARK/STARK circuits, providing
              substantially lower constraint counts than SHA3-256 or Keccak-256 in zero-knowledge
              contexts.
            </Paragraph>
            <CodeBlock>{`Poseidon2 Parameters:
  Field:           Goldilocks (p = 2^64 - 2^32 + 1)
  Width:           3 (state elements)
  Rate:            2 (absorption rate)
  Full rounds:     8
  Partial rounds:  56
  Application:     ZK circuits ONLY (NOT used for L1 consensus hashing)`}</CodeBlock>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 4. ECONOMICS                                              */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="economics" number="4" title="Economics">
            <Paragraph>
              Qubitcoin employs a deterministic emission schedule governed by the golden ratio
              (phi = 1.618033988749895). The emission model is designed to produce a deflationary
              supply curve that converges to a fixed maximum supply. All economic parameters
              are exact constants enforced at the consensus level.
            </Paragraph>

            <SubHeading>Core Economic Constants</SubHeading>
            <StatGrid stats={[
              { label: "Maximum Supply", value: "3,300,000,000 QBC" },
              { label: "Genesis Premine", value: "33,000,000 QBC" },
              { label: "Premine Percentage", value: "1.0%" },
              { label: "Initial Block Reward", value: "15.27 QBC" },
              { label: "Golden Ratio (phi)", value: "1.618033988749895" },
              { label: "Halving Interval", value: "15,474,020 blocks" },
              { label: "Halving Period", value: "~1.618 years" },
              { label: "Emission Period", value: "33 years" },
              { label: "Tail Emission", value: "0.1 QBC/block" },
            ]} />

            <SubHeading>Phi-Halving Emission Schedule</SubHeading>
            <Paragraph>
              Unlike Bitcoin{"'"}s fixed halving (reward / 2 every 210,000 blocks), Qubitcoin
              divides the block reward by the golden ratio at each era transition. This produces
              a smoother, more gradual reduction in emission that follows the mathematical
              properties of the Fibonacci sequence.
            </Paragraph>
            <CodeBlock>{`Reward Formula:
  reward(era) = INITIAL_REWARD / PHI^era

  Era 0:   15.27 / 1.618^0  = 15.270000 QBC  (blocks 0 - 15,474,019)
  Era 1:   15.27 / 1.618^1  =  9.436340 QBC  (blocks 15,474,020 - 30,948,039)
  Era 2:   15.27 / 1.618^2  =  5.831485 QBC  (blocks 30,948,040 - 46,422,059)
  Era 3:   15.27 / 1.618^3  =  3.604855 QBC
  Era 4:   15.27 / 1.618^4  =  2.228070 QBC
  Era 5:   15.27 / 1.618^5  =  1.377156 QBC
  Era 6:   15.27 / 1.618^6  =  0.851328 QBC
  Era 7:   15.27 / 1.618^7  =  0.526200 QBC
  Era 8:   15.27 / 1.618^8  =  0.325217 QBC
  Era 9:   15.27 / 1.618^9  =  0.201059 QBC
  Era 10:  15.27 / 1.618^10 =  0.124267 QBC
  Era 11+: Tail emission at 0.1 QBC/block (when reward < 0.1)

Halving interval: 15,474,020 blocks x 3.3s = ~590.37 days = ~1.618 years

Genesis total supply at block 0:
  Coinbase reward (vout=0): 15.27 QBC
  Genesis premine (vout=1): 33,000,000 QBC
  Total at genesis: 33,000,015.27 QBC`}</CodeBlock>

            <SubHeading>Layer 1 Transaction Fees</SubHeading>
            <Paragraph>
              L1 transaction fees are computed as a product of transaction size and a
              market-determined fee rate. There is no gas metering on Layer 1. Gas is
              exclusively a Layer 2 (QVM) construct.
            </Paragraph>
            <CodeBlock>{`L1 Fee = SIZE_BYTES x FEE_RATE (QBC/byte)

Miners select transactions by fee density (QBC/byte) and greedily fill
blocks up to the block size limit. Fee rate is market-determined.

L2 Gas (QVM only):
  BLOCK_GAS_LIMIT = 30,000,000
  Gas pricing follows EVM-compatible eth_gasPrice mechanics`}</CodeBlock>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 5. UTXO MODEL                                             */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="utxo-model" number="5" title="UTXO Model">
            <Paragraph>
              Qubitcoin uses an Unspent Transaction Output (UTXO) model for all Layer 1
              value transfers. This model provides superior auditability, parallelizable
              validation, and natural protection against certain classes of double-spend
              attacks compared to account-based models.
            </Paragraph>

            <SubHeading>UTXO Mechanics</SubHeading>
            <BulletList items={[
              "Balance is the sum of all unspent transaction outputs associated with an address. There is no stored account balance.",
              "Every unit of QBC exists as an output from a previous transaction (or coinbase).",
              "Spending requires referencing specific UTXOs as transaction inputs, proving ownership via Dilithium5 signature.",
              "Each input fully consumes its referenced UTXO. Partial consumption is not permitted.",
              "Change outputs are created to return excess value to the sender when input sum exceeds the intended transfer amount.",
              "A transaction is valid if and only if: (a) all referenced UTXOs exist and are unspent, (b) all signatures verify, (c) sum(inputs) >= sum(outputs) + fee, (d) no UTXO is referenced more than once.",
            ]} />

            <SubHeading>Confirmation Depths</SubHeading>
            <SpecTable
              headers={["Depth", "Status", "Use Case"]}
              rows={[
                ["0", "Unconfirmed (mempool)", "Transaction broadcast but not yet included in a block"],
                ["1", "Included in block", "Single confirmation, subject to chain reorganization"],
                ["6", "Standard confirmation", "Recommended minimum for non-trivial value transfers"],
                ["100", "Coinbase maturity", "Mining rewards become spendable after 100 confirmations"],
              ]}
            />

            <SubHeading>Transaction Structure</SubHeading>
            <CodeBlock>{`Transaction:
  version:    uint32          (transaction format version)
  inputs:     TxInput[]       (references to UTXOs being consumed)
  outputs:    TxOutput[]      (new UTXOs being created)
  locktime:   uint64          (earliest block height or timestamp for inclusion)

TxInput:
  prev_tx_hash:   bytes32     (hash of transaction containing the UTXO)
  output_index:   uint32      (index of the specific output in that transaction)
  signature:      bytes[4627] (Dilithium5 signature proving ownership)
  public_key:     bytes[2592] (Dilithium5 public key for verification)

TxOutput:
  value:          uint64      (amount in smallest QBC unit, 10^-18)
  script_pubkey:  bytes       (output locking script with recipient address)`}</CodeBlock>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 6. NETWORK ARCHITECTURE                                   */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="network-architecture" number="6" title="Network Architecture">
            <Paragraph>
              The network layer consists of four communication subsystems: a Rust-based
              peer-to-peer gossip network for block and transaction propagation, a FastAPI
              REST/JSON-RPC server for client interaction, a gRPC interface for internal
              service communication, and a Stratum server for mining pool operations.
            </Paragraph>

            <SubHeading>P2P Network (Rust libp2p)</SubHeading>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["Implementation", "Rust 2021 edition, libp2p 0.56"],
                ["Transport", "TCP + QUIC with ML-KEM-768 hybrid encryption"],
                ["Discovery", "Kademlia DHT with bootstrap nodes"],
                ["Messaging", "Gossipsub v1.1 with message signing"],
                ["NAT Traversal", "AutoNAT + Relay protocol"],
                ["Default Port", "4002 (host), 4001 (container)"],
                ["gRPC Port", "50051 (Python node to Rust daemon)"],
                ["Deployment", "Separate Docker container (qbc-p2p)"],
                ["Fallback", "Python P2P if Rust binary unavailable"],
              ]}
            />

            <SubHeading>RPC Server (FastAPI)</SubHeading>
            <Paragraph>
              The node exposes a unified REST + JSON-RPC API on port 5000. The JSON-RPC
              implementation provides eth_* namespace compatibility for MetaMask, ethers.js,
              and Web3 wallet integration. All endpoints support CORS and rate limiting.
            </Paragraph>
            <SpecTable
              headers={["Endpoint Category", "Count", "Examples"]}
              rows={[
                ["Chain State", "8", "/block/{height}, /chain/info, /chain/tip, /balance/{addr}"],
                ["Mining", "4", "/mining/start, /mining/stop, /mining/stats, /stratum/info"],
                ["P2P Network", "3", "/p2p/peers, /p2p/stats, /p2p/connect"],
                ["QVM", "5", "/qvm/info, /qvm/contract/{addr}, /qvm/account/{addr}, /qvm/storage/{addr}/{key}"],
                ["Aether Tree", "8", "/aether/info, /aether/phi, /aether/phi/history, /aether/chat, /aether/consciousness"],
                ["Bridge", "4", "/bridge/l1l2/deposit, /bridge/l1l2/withdraw, /bridge/l1l2/balance/{addr}"],
                ["QUSD Keeper", "11", "/keeper/status, /keeper/mode, /keeper/config, /keeper/history, /keeper/prices"],
                ["Higgs Field", "5", "/higgs/status, /higgs/masses, /higgs/mass/{name}, /higgs/excitations, /higgs/potential"],
                ["Security", "6", "/inheritance/*, /security/policy/*, /finality/*"],
                ["Privacy", "4", "/privacy/batch-balance, /privacy/bloom-utxos, /privacy/batch-blocks, /privacy/batch-tx"],
                ["Monitoring", "1", "/metrics (Prometheus format)"],
                ["JSON-RPC", "15+", "eth_chainId, eth_getBalance, eth_blockNumber, eth_sendRawTransaction, eth_call, net_version"],
              ]}
            />

            <SubHeading>Stratum Mining Server</SubHeading>
            <Paragraph>
              A dedicated Rust WebSocket Stratum server on port 3333 provides mining pool
              compatibility. The server implements the Stratum V1 protocol adapted for VQE-based
              mining, distributing Hamiltonian seeds and accepting VQE parameter solutions
              from connected workers.
            </Paragraph>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["Implementation", "Rust (7 source files, ~1,030 LOC)"],
                ["Port", "3333 (WebSocket)"],
                ["Protocol", "Stratum V1 (adapted for VQE)"],
                ["Job Distribution", "Hamiltonian seed + difficulty target"],
                ["Solution Format", "VQE parameters + ground state energy"],
              ]}
            />

            <SubHeading>Exchange Matching Engine</SubHeading>
            <Paragraph>
              A standalone Rust binary provides a central limit order book (CLOB) matching
              engine with microsecond latency. The engine supports price-time priority matching,
              self-trade prevention, balance lock/unlock, and OHLC candlestick generation
              with WebSocket streaming.
            </Paragraph>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["Implementation", "Rust (11 source files, 2,185 LOC)"],
                ["Matching Algorithm", "Price-time priority (FIFO)"],
                ["Persistence", "CockroachDB"],
                ["Real-time Feed", "WebSocket streaming"],
                ["Default Pairs", "QBC/QUSD, wETH/QUSD, wBNB/QUSD, wSOL/QUSD, wQBC/QUSD"],
                ["Features", "Self-trade prevention, OHLC candles, balance lock/unlock"],
              ]}
            />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 7. QVM                                                    */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="qvm" number="7" title="Quantum Virtual Machine (QVM)">
            <Paragraph>
              The Quantum Virtual Machine (QVM) is a stack-based bytecode interpreter providing
              full Ethereum Virtual Machine (EVM) compatibility with quantum computing extensions
              and institutional-grade compliance features. The QVM executes Solidity smart contracts
              without modification while providing 12 additional opcodes for quantum state
              manipulation, risk assessment, and on-chain reasoning.
            </Paragraph>

            <SubHeading>Opcode Summary</SubHeading>
            <StatGrid stats={[
              { label: "Standard EVM Opcodes", value: "155" },
              { label: "Quantum Opcodes", value: "10 (0xF0-0xF9)" },
              { label: "Reasoning Opcodes", value: "2 (0xFA-0xFB)" },
              { label: "Total Opcodes", value: "167" },
              { label: "Stack Limit", value: "1,024 items" },
              { label: "Block Gas Limit", value: "30,000,000" },
            ]} />

            <SubHeading>Quantum and Reasoning Opcodes</SubHeading>
            <div className="mb-4 overflow-x-auto">
              <table className="w-full text-sm" style={{ borderColor: C.border }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Opcode</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Hex</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Gas Cost</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {quantumOpcodes.map((op) => (
                    <tr key={op.opcode} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{op.opcode}</td>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: C.secondary }}>{op.hex}</td>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{op.gas}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{op.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <SubHeading>Production Implementation</SubHeading>
            <Paragraph>
              The production QVM is implemented in Go with 34 source files totaling
              approximately 10,000 lines of code. The Go implementation is canonical. A
              Python prototype (8 modules, ~4,500 LOC) exists for rapid prototyping and
              testing but is not used in production.
            </Paragraph>
            <SpecTable
              headers={["Package", "Files", "Purpose"]}
              rows={[
                ["cmd/qvm/", "2", "Main QVM server binary entry point"],
                ["cmd/qvm-cli/", "1", "CLI tool for contract deployment and interaction"],
                ["pkg/vm/evm/", "15", "Full EVM core: opcodes, stack, memory, storage, gas metering"],
                ["pkg/vm/quantum/", "8", "Quantum extensions: states, circuits, entanglement, gates"],
                ["pkg/compliance/", "9", "KYC, AML, sanctions, risk scoring, compliance proofs"],
                ["pkg/bridge/", "7", "Cross-chain bridge proof verification"],
                ["pkg/rpc/", "7", "gRPC + REST API server"],
                ["pkg/state/", "6", "Merkle Patricia Trie + quantum state management"],
                ["pkg/crypto/", "5", "Dilithium + Kyber + ZK proof integration"],
              ]}
            />

            <SubHeading>Compliance Engine</SubHeading>
            <Paragraph>
              The QVM includes a three-layer compliance architecture enforced at the virtual
              machine level. The QCOMPLIANCE opcode (0xF5, 15,000 gas) performs a pre-flight
              compliance check before transaction execution, querying the on-chain KYC registry,
              AML monitoring system, and sanctions database.
            </Paragraph>
            <SpecTable
              headers={["Tier", "Monthly Cost", "Daily Limit", "Features"]}
              rows={[
                ["Retail", "Free", "$10,000", "Basic KYC, standard AML monitoring"],
                ["Professional", "$500", "$1,000,000", "Enhanced KYC, AML monitoring, risk alerts"],
                ["Institutional", "$5,000", "Unlimited", "Full KYC, quantum verification, custom policies"],
                ["Sovereign", "$50,000", "Unlimited", "Central bank grade, custom jurisdictional rules, SUSY risk"],
              ]}
            />

            <SubHeading>Token Standards</SubHeading>
            <SpecTable
              headers={["Standard", "Type", "Compatibility"]}
              rows={[
                ["QBC-20", "Fungible tokens", "ERC-20 compatible, identical interface"],
                ["QBC-721", "Non-fungible tokens", "ERC-721 compatible, identical interface"],
                ["QBC-1155", "Multi-tokens", "ERC-1155 compatible, batch operations"],
                ["ERC-20-QC", "Compliance-aware fungible", "QVM-specific, KYC/AML hooks on transfer"],
              ]}
            />

            <SubHeading>Quantum State Persistence</SubHeading>
            <Paragraph>
              Quantum states are stored as density matrices in CockroachDB and persisted
              on-chain. Pure states are represented as rank-1 density matrices (rho = |psi&gt;&lt;psi|),
              mixed states as weighted sums. Entanglement between contracts is tracked via
              an entanglement registry. States persist until explicitly measured via QMEASURE,
              implementing lazy measurement semantics.
            </Paragraph>

            <SubHeading>Performance Targets</SubHeading>
            <SpecTable
              headers={["Operation", "TPS", "Notes"]}
              rows={[
                ["Simple transfer", "45,000", "Native QBC token transfer"],
                ["QBC-20 transfer", "12,000", "2 SSTORE operations"],
                ["DeFi swap", "3,500", "Multi-contract interaction"],
                ["Quantum operations", "500-2,000", "Varies by qubit count"],
                ["Finality", "<1 second", "BFT finality gadget"],
              ]}
            />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 8. AETHER TREE                                            */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="aether-tree" number="8" title="Aether Tree (On-Chain Reasoning Engine)">
            <Paragraph>
              Aether Tree is an on-chain reasoning engine that constructs a knowledge graph
              from every block mined since genesis, performs logical inference over the graph,
              computes an information-theoretic integration metric (Phi), and generates
              Proof-of-Thought proofs embedded in every block. The system implements a
              biologically-inspired cognitive architecture based on the Kabbalistic Tree of Life
              topology with 10 specialized processing nodes (Sephirot).
            </Paragraph>

            <SubHeading>Implementation Scale</SubHeading>
            <StatGrid stats={[
              { label: "Python Modules", value: "49" },
              { label: "Lines of Code (Python)", value: "~29,000" },
              { label: "Rust Modules (PyO3)", value: "12" },
              { label: "Lines of Code (Rust)", value: "~10,246" },
              { label: "Knowledge Nodes", value: "760,000+" },
              { label: "Gates Passed", value: "10/10" },
              { label: "Phi (Maximum)", value: "5.0" },
              { label: "Smart Contracts", value: "20 Solidity" },
            ]} />

            <SubHeading>Knowledge Graph</SubHeading>
            <Paragraph>
              The knowledge graph stores information as KeterNodes (named after Keter, the
              Crown in the Kabbalistic Tree of Life) connected by typed, weighted edges. Every
              block contributes new nodes extracted from block metadata, transaction patterns,
              and reasoning operations. The graph is backed by CockroachDB with an edge adjacency
              index for efficient traversal and an incremental Merkle root for chain binding.
            </Paragraph>
            <SpecTable
              headers={["Node Types", "Edge Types"]}
              rows={[
                ["assertion", "supports"],
                ["observation", "contradicts"],
                ["inference", "derives"],
                ["axiom", "requires"],
                ["", "refines"],
              ]}
            />

            <SubHeading>Reasoning Engine</SubHeading>
            <BulletList items={[
              "Deductive inference: Given premises A and A implies B, conclude B with certainty preservation",
              "Inductive inference: Generalize patterns from observed data points, producing conclusions with confidence < 1.0",
              "Abductive inference: Given observation B and rule A implies B, infer hypothesis A as best explanation",
              "Chain-of-thought: Multi-step reasoning with backtracking, producing auditable reasoning traces",
              "Causal discovery: PC algorithm for identifying causal relationships in observational data",
              "Adversarial debate: Dual-agent argument generation for robust conclusion validation",
            ]} />

            <SubHeading>Phi Calculator — HMS-Phi v4 (Hierarchical Multi-Scale Phi)</SubHeading>
            <Paragraph>
              The Phi metric uses Hierarchical Multi-Scale Phi (HMS-Phi v4), a tractable
              approximation of Giulio Tononi{"'"}s Integrated Information Theory. HMS-Phi measures
              integration at three hierarchical levels and combines them multiplicatively,
              ensuring genuine causal integration at every scale. Phi is computed at every block
              and stored in the phi_measurements database table. The 10-gate milestone system
              provides the floor: each gate unlocks +0.5 phi ceiling (maximum = 5.0 at gate 10).
              All 10 gates are currently passed, with Phi = 5.0 (maximum gate ceiling).
            </Paragraph>
            <CodeBlock>{`HMS-Phi v4 Formula:
  Final Phi = phi_micro^(1/phi) x phi_meso^(1/phi^2) x phi_macro^(1/phi^3)

Where phi = 1.618... (golden ratio)

Level 0 (Micro):  IIT-3.0 approximation on 16-node elite subsystem samples
                  -> IITApproximator (iit_approximator.py)
                  -> 5 independent samples -> median phi_micro

Level 1 (Meso):   Spectral MIP on 1K-node domain clusters
                  -> One cluster per Sephirot cognitive node (10 clusters)
                  -> phi_meso = weighted mean by cluster mass

Level 2 (Macro):  Graph-theoretic integration across all clusters
                  -> Cross-cluster mutual information
                  -> phi_macro = integration between the 10 Sephirot clusters

Properties:
  - Multiplicative: zero at any level zeros the whole (cannot be gamed)
  - 10-gate system provides floor safety mechanism (each gate = +0.5 ceiling)
  - IIT 3.0 micro-level measures genuine causal integration
  - MIP spectral bisection finds minimum-cut partition

  PHI_THRESHOLD = 3.0 (integration threshold marker)
  PHI_MAX_CEILING = 5.0 (all 10 gates passed)
  Current Phi: 5.0 (10/10 gates passed)
  Knowledge Nodes: 760,000+`}</CodeBlock>

            <SubHeading>10 Sephirot Cognitive Architecture</SubHeading>
            <Paragraph>
              The reasoning engine is structured as 10 specialized processing nodes based on
              the Kabbalistic Tree of Life. Each Sephirah is deployed as a QVM smart contract
              with its own quantum state. Nodes communicate via CSF (Cerebrospinal Fluid)
              transport -- QBC transactions routed along the Tree of Life topology.
            </Paragraph>
            <div className="mb-4 overflow-x-auto">
              <table className="w-full text-sm" style={{ borderColor: C.border }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Sephirah</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Function</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Brain Analog</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Qubits</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Yukawa</th>
                  </tr>
                </thead>
                <tbody>
                  {sephirotNodes.map((n) => (
                    <tr key={n.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td className="px-2 py-2 font-mono text-xs font-bold" style={{ color: C.primary }}>{n.name}</td>
                      <td className="px-2 py-2 text-xs" style={{ color: C.textMuted }}>{n.fn}</td>
                      <td className="px-2 py-2 text-xs" style={{ color: C.textMuted }}>{n.brain}</td>
                      <td className="px-2 py-2 font-mono text-xs" style={{ color: C.accent }}>{n.qubits}</td>
                      <td className="px-2 py-2 font-mono text-xs" style={{ color: C.secondary }}>{n.yukawa}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <SubHeading>SUSY Pairs</SubHeading>
            <Paragraph>
              Every expansion node is paired with a constraint node, balanced at the golden
              ratio: E_expand / E_constrain = phi. SUSY violations are detected by smart contract
              and automatically corrected via QBC redistribution. All violations are logged
              immutably on the blockchain.
            </Paragraph>
            <SpecTable
              headers={["Expansion Node", "Constraint Node", "Balance Ratio"]}
              rows={[
                ["Chesed (Explore)", "Gevurah (Safety)", "Creativity vs. Safety = phi"],
                ["Chochmah (Intuition)", "Binah (Logic)", "Intuition vs. Analysis = phi"],
                ["Netzach (Persist)", "Hod (Communicate)", "Learning vs. Communication = phi"],
              ]}
            />

            <SubHeading>Proof-of-Thought Protocol</SubHeading>
            <CodeBlock>{`Proof-of-Thought Lifecycle:
  1. Task Submission:  User or system submits reasoning task with QBC bounty
  2. Node Solution:    Sephirah node processes task using QVM quantum opcodes
  3. Proposal:         Node submits solution + quantum proof to blockchain
  4. Validation:       Multiple validator nodes verify solution via QVERIFY opcode
  5. Consensus:        >= 67% validator agreement required for acceptance
  6. Reward/Slash:     Correct: earn QBC bounty. Incorrect: lose 50% of stake
  7. Recording:        Solution + proof stored immutably on chain

Economic Parameters:
  Minimum task bounty:     1 QBC
  Minimum validator stake: 100 QBC
  Slash penalty:           50% of validator stake
  Unstaking delay:         7 days (168 hours)
  BFT threshold:           67% of staked weight`}</CodeBlock>

            <SubHeading>Pineal Orchestrator</SubHeading>
            <Paragraph>
              A global timing system controls the cognitive cycle of all 10 Sephirot nodes,
              modeled on the biological pineal gland{"'"}s circadian rhythm. The system cycles
              through 6 phases, each with a different QBC metabolic rate that governs
              computational resource allocation.
            </Paragraph>
            <SpecTable
              headers={["Phase", "Metabolic Rate", "Function"]}
              rows={[
                ["Waking", "1.0x", "Baseline processing, input reception"],
                ["Active Learning", "2.0x", "Maximum resource allocation for new knowledge integration"],
                ["Consolidation", "1.5x", "Pattern extraction and knowledge graph optimization"],
                ["Sleep", "0.5x", "Background maintenance, index rebuilding"],
                ["REM Dreaming", "0.8x", "Cross-domain knowledge transfer, creative association"],
                ["Deep Sleep", "0.3x", "Minimum processing, garbage collection, memory compaction"],
              ]}
            />

            <SubHeading>Safety Architecture</SubHeading>
            <BulletList items={[
              "Gevurah veto: Safety node (3-qubit threat detection) can unilaterally block any harmful operation",
              "SUSY enforcement: Automatic QBC redistribution when expansion/constraint imbalance exceeds tolerance",
              "Multi-node consensus: No single Sephirah can act alone; 67% BFT threshold required",
              "Constitutional enforcement: Core alignment principles enforced as smart contract logic (ConstitutionalAI.sol)",
              "Emergency shutdown: Multi-sig kill switch contract (EmergencyShutdown.sol) for catastrophic scenarios",
            ]} />

            <SubHeading>Genesis Requirements</SubHeading>
            <Paragraph>
              The Aether Tree MUST be initialized at block 0 (genesis). No retroactive
              reconstruction is permitted. Genesis initialization creates: (1) empty knowledge
              graph, (2) first Phi measurement at baseline 0.0, (3) genesis integration event,
              (4) initial KeterNodes from genesis block metadata. The AetherEngine auto-starts
              on node boot and processes every block sequentially from genesis.
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 9. PRIVACY                                                */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="privacy" number="9" title="Privacy: SUSY Swaps">
            <Paragraph>
              Qubitcoin supports opt-in confidential transactions via SUSY Swaps. When
              activated, SUSY Swaps hide transaction amounts and participant addresses
              while preserving on-chain verifiability. The privacy system uses three
              complementary cryptographic primitives: Pedersen commitments, Bulletproofs
              range proofs, and stealth addresses.
            </Paragraph>

            <SubHeading>Pedersen Commitments</SubHeading>
            <CodeBlock>{`Commitment:  C = v*G + r*H

Where:
  v = transaction value (hidden)
  r = blinding factor (random scalar)
  G = generator point (public, shared)
  H = nothing-up-my-sleeve point (public, no known discrete log relation to G)

Properties:
  - Perfectly hiding: C reveals nothing about v
  - Computationally binding: cannot open C to different v' (discrete log hardness)
  - Additive homomorphism: C(v1) + C(v2) = C(v1+v2) with blinding r1+r2
  - Verification: sum(input_commitments) = sum(output_commitments) + fee*G`}</CodeBlock>

            <SubHeading>Bulletproofs Range Proofs</SubHeading>
            <Paragraph>
              Bulletproofs provide zero-knowledge proofs that committed values lie in the
              range [0, 2^64) without revealing the actual value. This prevents negative
              value attacks where a sender could create value by committing to a negative
              amount (which wraps around in modular arithmetic).
            </Paragraph>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["Proof Size", "~672 bytes (logarithmic in range size)"],
                ["Size Complexity", "O(log n) where n = bit range"],
                ["Verification Time", "~10 milliseconds"],
                ["Trusted Setup", "None required"],
                ["Range", "[0, 2^64)"],
                ["Batch Verification", "Supported (amortized cost reduction)"],
              ]}
            />

            <SubHeading>Stealth Addresses</SubHeading>
            <Paragraph>
              Stealth addresses prevent address linkability by generating a unique one-time
              address for every transaction. The sender uses the recipient{"'"}s public spend
              and view keys to derive an ephemeral address. Only the recipient can detect
              and spend outputs sent to stealth addresses by scanning with their view key.
            </Paragraph>
            <CodeBlock>{`Stealth Address Protocol:
  Recipient publishes: (spend_pubkey, view_pubkey)

  Sender:
    1. Generate ephemeral keypair (r, R = r*G)
    2. Compute shared_secret = r * view_pubkey
    3. Derive one-time_pubkey = spend_pubkey + H(shared_secret)*G
    4. Send to address derived from one-time_pubkey
    5. Include R in transaction data

  Recipient:
    1. Scan R values in transactions
    2. Compute shared_secret = view_privkey * R
    3. Compute expected one-time_pubkey = spend_pubkey + H(shared_secret)*G
    4. If match: derive spending key = spend_privkey + H(shared_secret)`}</CodeBlock>

            <SubHeading>Key Images</SubHeading>
            <Paragraph>
              Key images prevent double-spending of confidential outputs. Each UTXO produces
              a unique, deterministic key image that is published when spent. The network
              maintains a set of all used key images; any transaction attempting to reuse
              a key image is rejected as a double-spend.
            </Paragraph>

            <SubHeading>Privacy Modes</SubHeading>
            <SpecTable
              headers={["Mode", "Amounts", "Addresses", "Tx Size", "Verification"]}
              rows={[
                ["Public (default)", "Visible", "Visible", "~300 bytes", "Fast"],
                ["Private (opt-in)", "Hidden", "Hidden", "~2,000 bytes", "~10ms (range proof)"],
              ]}
            />
            <Paragraph>
              SUSY Swaps hide: transaction amounts, sender/receiver addresses, balance
              linkability. SUSY Swaps do NOT hide: transaction existence, timestamps, fee
              amounts, transaction size, network-level metadata (IP addresses without Tor/I2P).
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 10. CROSS-CHAIN BRIDGE                                    */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="cross-chain-bridge" number="10" title="Cross-Chain Bridge">
            <Paragraph>
              Qubitcoin operates lock-and-mint bridges to 8 external blockchain networks.
              Native QBC is locked in the BridgeVault contract on the QBC chain, and
              corresponding wrapped tokens (wQBC, wQUSD) are minted on the target chain.
              The reverse operation (burn-and-unlock) destroys wrapped tokens and releases
              native assets.
            </Paragraph>

            <SubHeading>Supported Chains and Deployed Contracts</SubHeading>
            <div className="mb-4 overflow-x-auto">
              <table className="w-full text-sm" style={{ borderColor: C.border }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Chain</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>wQBC Address</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>wQUSD Address</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>DEX</th>
                  </tr>
                </thead>
                <tbody>
                  {bridgeChains.map((c) => (
                    <tr key={c.chain} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td className="px-2 py-2 text-xs font-semibold" style={{ color: C.text }}>{c.chain}</td>
                      <td className="px-2 py-2 font-mono text-xs" style={{ color: c.wqbc === "TBD" ? C.textMuted : C.primary }}>
                        {c.wqbc === "TBD" ? "Pending Deployment" : `${c.wqbc.slice(0, 6)}...${c.wqbc.slice(-4)}`}
                      </td>
                      <td className="px-2 py-2 font-mono text-xs" style={{ color: c.wqusd === "TBD" ? C.textMuted : C.primary }}>
                        {c.wqusd === "TBD" ? "Pending Deployment" : `${c.wqusd.slice(0, 6)}...${c.wqusd.slice(-4)}`}
                      </td>
                      <td className="px-2 py-2 text-xs" style={{ color: C.textMuted }}>{c.dex}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <SubHeading>Bridge Parameters</SubHeading>
            <StatGrid stats={[
              { label: "Default Bridge Fee", value: "0.1% (10 bps)" },
              { label: "Maximum Fee (Hard Cap)", value: "10% (1,000 bps)" },
              { label: "Fee Configuration", value: "BridgeVault.setFeeBps()" },
              { label: "Token Decimals (Cross-Chain)", value: "8" },
              { label: "Backing Model", value: "1:1 locked native asset" },
              { label: "Chains Supported", value: "8 networks" },
            ]} />

            <SubHeading>L1-L2 Internal Bridge</SubHeading>
            <Paragraph>
              An internal bridge connects the L1 UTXO layer with L2 QVM accounts, enabling
              MetaMask-compatible wallet interaction. Deposits consume L1 UTXOs and credit
              the corresponding L2 QVM account balance. Withdrawals debit the L2 account and
              create new L1 UTXOs. Both operations are atomic within a single block.
            </Paragraph>
            <CodeBlock>{`Deposit (L1 -> L2):
  1. User submits deposit transaction referencing L1 UTXOs
  2. UTXOs are consumed (marked spent in L1 UTXO set)
  3. Equivalent QBC credited to user's L2 QVM account (eth_getBalance compatible)
  4. Bridge event logged in l1l2_bridge table

Withdraw (L2 -> L1):
  1. User submits withdrawal via QVM contract call
  2. L2 QVM account balance debited
  3. New UTXO created on L1 with user's Dilithium address
  4. UTXO becomes spendable after 6 confirmations`}</CodeBlock>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 11. QUSD STABLECOIN                                       */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="qusd-stablecoin" number="11" title="QUSD Stablecoin">
            <Paragraph>
              QUSD is a QBC-20 stablecoin deployed on the QVM, pegged to $1 USD. It uses
              a fractional reserve model with transparent on-chain debt tracking that
              targets 100% reserve backing over a 10-year period. Every QUSD mint creates
              a debt obligation recorded immutably in the DebtLedger contract. Reserve
              deposits count as partial payback.
            </Paragraph>

            <SubHeading>Core Parameters</SubHeading>
            <StatGrid stats={[
              { label: "Initial Supply", value: "3,300,000,000 QUSD" },
              { label: "Target Peg", value: "$1.00 USD" },
              { label: "Reserve Model", value: "Fractional to Full" },
              { label: "Backing Timeline", value: "10 years" },
              { label: "Transfer Fee", value: "0.05% (mutable)" },
              { label: "Core Contracts", value: "10 Solidity" },
            ]} />

            <SubHeading>Peg Keeper Daemon</SubHeading>
            <Paragraph>
              An automated daemon monitors wQUSD prices across 8 chains via DEX TWAP
              (Time-Weighted Average Price) feeds and executes stabilization actions when
              the peg deviates beyond configured thresholds. The daemon supports 5 operating
              modes with configurable intervention parameters.
            </Paragraph>
            <div className="mb-4 space-y-2">
              {keeperModes.map((m) => (
                <div key={m.mode} className="flex items-center gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.bg }}>
                  <span
                    className="rounded-full px-2 py-0.5 font-mono text-xs"
                    style={{ background: m.code === 1 ? `${C.primary}20` : `${C.textMuted}15`, color: m.code === 1 ? C.primary : C.textMuted }}
                  >
                    {m.mode} ({m.code})
                  </span>
                  <span className="text-xs" style={{ color: C.textMuted }}>{m.desc}</span>
                </div>
              ))}
            </div>

            <SubHeading>Keeper Configuration</SubHeading>
            <SpecTable
              headers={["Parameter", "Default", "Description"]}
              rows={[
                ["KEEPER_ENABLED", "true", "Enable/disable keeper daemon"],
                ["KEEPER_DEFAULT_MODE", "scan", "Starting operating mode"],
                ["KEEPER_CHECK_INTERVAL", "10 blocks", "Blocks between peg checks"],
                ["KEEPER_MAX_TRADE_SIZE", "1,000,000 QBC", "Maximum per stabilization trade"],
                ["KEEPER_FLOOR_PRICE", "$0.99", "Below this triggers buy pressure"],
                ["KEEPER_CEILING_PRICE", "$1.01", "Above this triggers sell pressure"],
                ["KEEPER_COOLDOWN_BLOCKS", "10", "Minimum blocks between actions"],
              ]}
            />

            <SubHeading>Arbitrage Types</SubHeading>
            <BulletList items={[
              "Floor arbitrage: wQUSD < $0.99 on DEX -- buy cheap wQUSD, redeem 1:1 at reserve",
              "Ceiling arbitrage: wQUSD > $1.01 on DEX -- mint QUSD at $1, sell above peg on DEX",
              "Cross-chain arbitrage: wQUSD price differs across chains -- buy on low-price chain, bridge, sell on high-price chain",
            ]} />
            <Paragraph>
              All arbitrage calculations account for gas costs, bridge fees
              (BridgeVault.feeBps()), and slippage to ensure net profitability before execution.
            </Paragraph>

            <SubHeading>Debt Milestones</SubHeading>
            <Paragraph>
              The DebtLedger contract emits on-chain milestone events at 5%, 15%, 30%, 50%,
              and 100% backing levels. These milestones are queryable via the QVM and provide
              a transparent, auditable record of progress toward full reserve backing.
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 12. EXCHANGE                                              */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="exchange" number="12" title="Exchange (Rust Matching Engine)">
            <Paragraph>
              A production Rust matching engine provides a central limit order book (CLOB)
              for on-chain asset trading. The engine is a standalone binary that connects
              to CockroachDB for persistence and exposes WebSocket endpoints for real-time
              market data streaming.
            </Paragraph>

            <SubHeading>Technical Specifications</SubHeading>
            <StatGrid stats={[
              { label: "Implementation", value: "Rust (11 files, 2,185 LOC)" },
              { label: "Matching Algorithm", value: "Price-Time Priority (FIFO)" },
              { label: "Latency", value: "Microsecond matching" },
              { label: "Persistence", value: "CockroachDB" },
              { label: "Real-time Feed", value: "WebSocket" },
              { label: "Candlestick Generation", value: "OHLC" },
            ]} />

            <SubHeading>Default Trading Pairs</SubHeading>
            <SpecTable
              headers={["Pair", "Base", "Quote", "Description"]}
              rows={[
                ["QBC/QUSD", "QBC", "QUSD", "Native Qubitcoin vs. QUSD stablecoin"],
                ["wETH/QUSD", "wETH", "QUSD", "Wrapped Ethereum vs. QUSD"],
                ["wBNB/QUSD", "wBNB", "QUSD", "Wrapped BNB vs. QUSD"],
                ["wSOL/QUSD", "wSOL", "QUSD", "Wrapped Solana vs. QUSD"],
                ["wQBC/QUSD", "wQBC", "QUSD", "Wrapped QBC (cross-chain) vs. QUSD"],
              ]}
            />

            <SubHeading>Features</SubHeading>
            <BulletList items={[
              "Self-trade prevention: orders from the same account on both sides are blocked",
              "Balance lock/unlock: user balances are locked when orders are placed and unlocked on cancellation or fill",
              "OHLC candlestick generation: real-time aggregation at 1m, 5m, 15m, 1h, 4h, 1d intervals",
              "WebSocket streaming: real-time order book updates, trade feeds, and ticker data",
              "CockroachDB persistence: all orders, trades, and balances durable across restarts",
            ]} />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 13. STORAGE                                               */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="storage" number="13" title="Storage">
            <Paragraph>
              The protocol uses CockroachDB v24.2.0 as the primary relational database for
              all on-chain state, and IPFS (Kubo) for content-addressed storage of blockchain
              snapshots and large data blobs. The database schema is organized into 9 domains
              totaling 55+ tables.
            </Paragraph>

            <SubHeading>Database Architecture</SubHeading>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["DBMS", "CockroachDB v24.2.0 (pinned for compatibility)"],
                ["Health Check", "GET http://localhost:8080/health?ready=1"],
                ["Connection", "postgresql://root@localhost:26257/qbc?sslmode=disable"],
                ["ORM", "SQLAlchemy (Python models in database/models.py)"],
                ["Schema Files", "sql_new/ directory (domain-separated)"],
                ["Total Tables", "55+"],
              ]}
            />

            <SubHeading>Schema Domains</SubHeading>
            <div className="mb-4 overflow-x-auto">
              <table className="w-full text-sm" style={{ borderColor: C.border }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Domain</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Tables</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Contents</th>
                  </tr>
                </thead>
                <tbody>
                  {databaseDomains.map((d) => (
                    <tr key={d.domain} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td className="px-3 py-2 text-xs font-semibold" style={{ color: C.primary }}>{d.domain}</td>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{d.tables}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{d.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <SubHeading>IPFS Storage</SubHeading>
            <SpecTable
              headers={["Parameter", "Value"]}
              rows={[
                ["Implementation", "IPFS Kubo (latest)"],
                ["API Endpoint", "/ip4/127.0.0.1/tcp/5002/http"],
                ["Swarm Port", "4001"],
                ["Gateway Port", "8080 (conflicts with CockroachDB admin UI)"],
                ["Use Cases", "Blockchain snapshots, large data blobs, episodic memory storage"],
              ]}
            />

            <SubHeading>Schema-Model Alignment Rule</SubHeading>
            <Paragraph>
              SQL schemas (sql_new/ directory) and SQLAlchemy ORM models (database/models.py)
              MUST remain synchronized. Past production incidents have resulted from mismatches
              between these two sources of truth. SQLAlchemy create_all() skips existing tables,
              so no conflict occurs if SQL runs first, but column definitions, types, and
              constraints must match exactly.
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 14. SMART CONTRACTS                                       */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="smart-contracts" number="14" title="Smart Contracts">
            <Paragraph>
              The protocol deploys 65 Solidity smart contracts to the QVM, organized into
              11 categories. All contracts target Solidity 0.8.24+ with checked arithmetic
              (no unchecked blocks for overflow/underflow). Contracts are deployed via RPC
              after genesis; they are NOT auto-deployed at block 0.
            </Paragraph>

            {contractCategories.map((cat) => (
              <div key={cat.category} className="mb-4">
                <h3 className="mb-2 text-sm font-semibold" style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}>
                  {cat.category}{" "}
                  <span className="font-mono text-xs" style={{ color: C.accent }}>({cat.count} contracts)</span>
                </h3>
                <div className="space-y-1">
                  {cat.contracts.map((c, i) => {
                    const [name, desc] = c.split(" -- ");
                    return (
                      <div key={i} className="flex items-start gap-2 pl-2 text-xs">
                        <span className="font-mono" style={{ color: C.primary }}>{name}</span>
                        {desc && <span style={{ color: C.textMuted }}>-- {desc}</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 15. HIGGS COGNITIVE FIELD                                  */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="higgs-cognitive-field" number="15" title="Higgs Cognitive Field">
            <Paragraph>
              The Higgs Cognitive Field applies the Standard Model{"'"}s mass-generation mechanism
              to the Aether Tree cognitive architecture. Just as the Higgs boson gives
              elementary particles their mass via spontaneous symmetry breaking, the Higgs
              Cognitive Field assigns cognitive mass (inertia to change) to each Sephirot
              node, governing how quickly each node can adapt to new information.
            </Paragraph>

            <SubHeading>Mexican Hat Potential</SubHeading>
            <CodeBlock>{`V(phi) = -mu^2 |phi|^2 + lambda |phi|^4

Parameters:
  VEV (Vacuum Expectation Value) = 174.14     (equilibrium field strength)
  mu^2                           = 88.17      (mass parameter squared)
  lambda                         = 0.129      (quartic self-coupling)

The minimum of V(phi) occurs at |phi| = VEV = sqrt(mu^2 / (2*lambda))
Spontaneous symmetry breaking: phi != 0 at equilibrium`}</CodeBlock>

            <SubHeading>Yukawa Golden Ratio Cascade</SubHeading>
            <Paragraph>
              Each Sephirot tier receives cognitive mass via Yukawa couplings that follow
              a golden ratio decay. Higher-tier nodes (closer to Keter) have greater
              cognitive mass and resist change, while lower-tier nodes (closer to Malkuth)
              have less mass and correct faster.
            </Paragraph>
            <SpecTable
              headers={["Tier", "Nodes", "Yukawa Coupling", "Cognitive Mass"]}
              rows={[
                ["0", "Keter", "y = 1.0", "VEV x 1.0 = 174.14 (heaviest)"],
                ["1", "Chochmah, Binah, Tiferet", "y = phi^-1 = 0.618", "VEV x 0.618 = 107.64"],
                ["2", "Chesed, Gevurah", "y = phi^-2 = 0.382", "VEV x 0.382 = 66.50"],
                ["3", "Netzach, Hod", "y = phi^-3 = 0.236", "VEV x 0.236 = 41.10"],
                ["4", "Yesod, Malkuth", "y = phi^-4 = 0.146", "VEV x 0.146 = 25.42 (lightest)"],
              ]}
            />

            <SubHeading>Two-Higgs-Doublet Model (2HDM)</SubHeading>
            <Paragraph>
              SUSY pairs use two Higgs doublets with tan(beta) = phi = 1.618033988749895.
              The up-type doublet (H_u) couples to expansion nodes (Chesed, Chochmah, Netzach)
              and the down-type doublet (H_d) couples to constraint nodes (Gevurah, Binah, Hod).
              The mass gap between H_u and H_d masses for each SUSY pair quantifies the
              current imbalance.
            </Paragraph>

            <SubHeading>F=ma Rebalancing Paradigm</SubHeading>
            <CodeBlock>{`SUSY Rebalancing (Newton's Second Law):
  acceleration = force / mass

Where:
  force        = |E_expansion - E_constraint|   (energy imbalance between SUSY pair)
  mass         = cognitive mass from Yukawa coupling
  acceleration = rate of energy redistribution (QBC/block)

Result:
  - Lighter nodes (Yesod, Malkuth) correct fastest (acceleration = force / 25.42)
  - Heavier nodes (Keter) resist change (acceleration = force / 174.14)
  - Creates natural hierarchy: high-level goals stable, low-level actions agile`}</CodeBlock>

            <SubHeading>Excitation Events</SubHeading>
            <Paragraph>
              When the field value deviates more than 10% from VEV (configurable via
              HIGGS_EXCITATION_THRESHOLD), a Higgs excitation event is recorded in the
              higgs_excitations database table. Each excitation triggers a rebalancing
              cascade across all affected nodes. Excitation amplitude is computed as
              |field_value - VEV| / VEV.
            </Paragraph>

            <SubHeading>Configuration</SubHeading>
            <SpecTable
              headers={["Variable", "Default", "Description"]}
              rows={[
                ["HIGGS_VEV", "174.14", "Vacuum expectation value"],
                ["HIGGS_MU_SQUARED", "88.17", "Mass parameter squared"],
                ["HIGGS_LAMBDA", "0.129", "Quartic self-coupling"],
                ["HIGGS_YUKAWA_TOP", "1.0", "Top Yukawa coupling (Keter)"],
                ["HIGGS_TAN_BETA", "1.618033988749895", "tan(beta) = phi for 2HDM"],
                ["HIGGS_EXCITATION_THRESHOLD", "0.1", "10% deviation triggers excitation"],
                ["HIGGS_DAMPING", "0.05", "Field oscillation damping coefficient"],
                ["HIGGS_UPDATE_INTERVAL", "10", "Blocks between field state updates"],
              ]}
            />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 16. BFT FINALITY                                          */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="bft-finality" number="16" title="BFT Finality">
            <Paragraph>
              A stake-weighted Byzantine Fault Tolerant finality gadget provides deterministic
              finality for blocks that receive sufficient validator attestation. Once a block
              is finalized, chain reorganizations below that height are rejected by all
              compliant nodes.
            </Paragraph>

            <SubHeading>Finality Parameters</SubHeading>
            <StatGrid stats={[
              { label: "Consensus Threshold", value: "67% of staked weight" },
              { label: "Minimum Validator Stake", value: "100 QBC" },
              { label: "Finality Latency", value: "<1 second" },
              { label: "Reorg Protection", value: "Below finalized height" },
            ]} />

            <SubHeading>Protocol</SubHeading>
            <BulletList items={[
              "Validators register via /finality/register-validator endpoint with minimum 100 QBC stake",
              "For each block, validators submit signed finality votes via /finality/vote endpoint",
              "A block is finalized when cumulative staked weight of votes exceeds 67% of total registered stake",
              "Once finalized, the node rejects any chain reorganization that would revert blocks at or below the finalized height",
              "Finality status is queryable via /finality/status endpoint",
            ]} />
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 17. SECURITY FEATURES                                     */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="security-features" number="17" title="Security Features">
            <Paragraph>
              Beyond post-quantum cryptography, the protocol implements four additional
              security systems: an inheritance protocol, high-security accounts, deniable
              RPC queries, and governed transaction reversibility.
            </Paragraph>

            <SubHeading>Inheritance Protocol (Dead-Man{"'"}s Switch)</SubHeading>
            <BulletList items={[
              "Account holders designate a beneficiary address via /inheritance/set-beneficiary",
              "Regular heartbeat signals (/inheritance/heartbeat) reset an inactivity timer",
              "If the timer expires without a heartbeat, the beneficiary can claim account funds via /inheritance/claim",
              "A configurable grace period allows the original owner to reclaim before transfer completes",
              "All inheritance plans are queryable via /inheritance/status/{address}",
            ]} />

            <SubHeading>High-Security Accounts</SubHeading>
            <BulletList items={[
              "Per-address security policies configurable via /security/policy/set",
              "Daily spending limits: maximum QBC transferable per 24-hour period",
              "Time-locks: mandatory delay between transaction signing and broadcast",
              "Whitelists: restrict outbound transfers to pre-approved destination addresses",
              "Policies are removable via /security/policy/{address} DELETE endpoint",
            ]} />

            <SubHeading>Deniable RPCs (Privacy-Preserving Queries)</SubHeading>
            <BulletList items={[
              "Constant-time batch balance queries (/privacy/batch-balance): query multiple addresses in one request with no timing side-channel revealing which address was the target",
              "Bloom filter UTXO queries (/privacy/bloom-utxos): return UTXOs as a Bloom filter, providing plausible deniability about which UTXOs the querier is interested in",
              "Batch block and transaction fetching (/privacy/batch-blocks, /privacy/batch-tx): retrieve multiple items in one request to obscure interest in specific blocks or transactions",
            ]} />

            <SubHeading>Transaction Reversibility</SubHeading>
            <Paragraph>
              The reversibility system provides a governor-managed multi-signature mechanism
              to reverse transactions within a 24-hour window (~26,182 blocks at 3.3s block
              time). This is implemented both in the Python L1 node and as a Substrate pallet
              (pallet-qbc-reversibility). The process involves UTXO freezing, governance vote,
              and creation of reversal UTXOs. Reversibility is intended for theft recovery
              and regulatory compliance, not routine use.
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 18. NODE TYPES                                            */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="node-types" number="18" title="Node Types">
            <Paragraph>
              The network supports three node configurations with different resource
              requirements and capabilities.
            </Paragraph>
            <SpecTable
              headers={["Type", "Storage", "RAM", "Network", "Capabilities"]}
              rows={[
                ["Full Node", "500GB+ (~50GB/year growth)", "16GB+", "100+ Mbps", "Full block validation, historical queries, UTXO set maintenance, RPC serving, mining eligible"],
                ["Light Node", "1GB", "2GB", "10+ Mbps", "SPV verification via block headers, mobile/embedded deployment, sync time < 5 minutes"],
                ["Mining Node", "500GB+ (Full Node baseline)", "16GB+", "100+ Mbps", "Full Node + VQE optimization, quantum hardware/simulator, block creation, Stratum server hosting"],
              ]}
            />

            <SubHeading>Storage Growth Projection</SubHeading>
            <Paragraph>
              At a target block time of 3.3 seconds, the chain produces approximately
              9,567,272 blocks per year. With Dilithium5 signatures (~4,627 bytes per
              signature), transaction capacity is ~217 transactions per MB. Estimated
              annual storage growth for a full node is ~50GB under moderate transaction
              volume, primarily driven by UTXO set size, knowledge graph growth, and
              quantum state persistence.
            </Paragraph>
          </SectionCard>

          {/* -------------------------------------------------------- */}
          {/* 19. SUBSTRATE MIGRATION                                   */}
          {/* -------------------------------------------------------- */}
          <SectionCard id="substrate-migration" number="19" title="Substrate Migration">
            <Paragraph>
              The substrate-node/ directory contains a hybrid Substrate SDK node that
              mirrors all Python L1 subsystems as native Rust pallets. This node represents
              the migration target for production deployment, providing Substrate{"'"}s
              battle-tested networking, consensus, and runtime upgrade capabilities while
              preserving all Qubitcoin-specific protocol features.
            </Paragraph>

            <SubHeading>Workspace Structure</SubHeading>
            <SpecTable
              headers={["Crate", "Purpose"]}
              rows={[
                ["node/", "Node service binary, CLI, RPC wiring, chain specification"],
                ["runtime/", "Runtime composition linking all pallets into executable WASM/native runtime"],
                ["primitives/", "Shared types, Poseidon2 ZK hashing over Goldilocks field"],
              ]}
            />

            <SubHeading>Pallets</SubHeading>
            <div className="mb-4 overflow-x-auto">
              <table className="w-full text-sm" style={{ borderColor: C.border }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Pallet</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {substratePallets.map((p) => (
                    <tr key={p.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{p.name}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{p.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <SubHeading>Post-Quantum P2P: ML-KEM-768 (Kyber Transport)</SubHeading>
            <Paragraph>
              The Substrate node{"'"}s P2P layer uses ML-KEM-768 (formerly CRYSTALS-Kyber) for
              post-quantum key encapsulation. A hybrid handshake combines the Noise protocol{"'"}s
              classical Diffie-Hellman secret with Kyber{"'"}s post-quantum shared secret via
              HKDF-SHA256, producing AES-256-GCM session keys. This provides forward secrecy
              and quantum resistance simultaneously.
            </Paragraph>

            <SubHeading>Build Instructions</SubHeading>
            <CodeBlock>{`# Native build (recommended):
cd substrate-node && SKIP_WASM_BUILD=1 cargo build --release

# Binary output:
target/release/qbc-substrate-node

# WASM build status:
Deferred due to upstream serde_core exchange_malloc conflict.
Native build is fully functional for all pallets and tests.

# Test coverage:
73 Substrate tests total:
  25 Kyber transport tests
  25 Poseidon2 hashing tests
  10 reversibility pallet tests
  13 integration tests`}</CodeBlock>
          </SectionCard>

        </div>

        {/* FOOTER */}
        <div className="mt-12 space-y-4">
          <div className="rounded-lg border p-6" style={{ borderColor: C.border, background: C.surface }}>
            <h2
              className="mb-3 text-lg font-semibold"
              style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
            >
              Document References
            </h2>
            <div className="grid gap-2 text-sm md:grid-cols-2" style={{ color: C.textMuted }}>
              <a href="https://github.com/QuantumAI-Blockchain" target="_blank" rel="noopener noreferrer" style={{ color: C.primary }} className="hover:underline">
                GitHub: QuantumAI-Blockchain
              </a>
              <Link href="/docs/qvm" style={{ color: C.primary }} className="hover:underline">
                QVM Technical Documentation
              </Link>
              <Link href="/docs/aether" style={{ color: C.primary }} className="hover:underline">
                Aether Tree Technical Documentation
              </Link>
              <Link href="/docs/economics" style={{ color: C.primary }} className="hover:underline">
                Economics and Emission Schedule
              </Link>
              <Link href="/docs/qusd" style={{ color: C.primary }} className="hover:underline">
                QUSD Stablecoin Specification
              </Link>
              <a href="https://x.com/qu_bitcoin" target="_blank" rel="noopener noreferrer" style={{ color: C.primary }} className="hover:underline">
                X (Twitter): @qu_bitcoin
              </a>
            </div>
          </div>

          <div className="rounded-lg border p-4" style={{ borderColor: C.border, background: C.surface }}>
            <p className="text-xs" style={{ color: C.textMuted }}>
              Copyright 2026 Quantum Blockchain. MIT License. All protocol parameters stated in this
              document are exact production values. This specification is version 1.0.0 and is
              maintained as the authoritative technical reference for the Quantum Blockchain protocol.
              For questions or security disclosures, contact info@qbc.network.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
