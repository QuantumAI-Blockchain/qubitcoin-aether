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
};

const chains = [
  { name: "Ethereum", id: 1, native: "ETH", explorer: "etherscan.io", wQBC: "0xB7c8…Fa67", wQUSD: "0x8848…CAdB3", color: "#627eea" },
  { name: "BNB Chain", id: 56, native: "BNB", explorer: "bscscan.com", wQBC: "0xA8dA…6147", wQUSD: "0xD137…BE3", color: "#f3ba2f" },
  { name: "Polygon", id: 137, native: "MATIC", explorer: "polygonscan.com", wQBC: "0xB7c8…Fa67", wQUSD: "0x8848…CAdB3", color: "#8247e5" },
  { name: "Arbitrum", id: 42161, native: "ETH", explorer: "arbiscan.io", wQBC: "0xB7c8…Fa67", wQUSD: "0x8848…CAdB3", color: "#28a0f0" },
  { name: "Optimism", id: 10, native: "ETH", explorer: "optimistic.etherscan.io", wQBC: "0xB7c8…Fa67", wQUSD: "0xA8dA…6147", color: "#ff0420" },
  { name: "Avalanche", id: 43114, native: "AVAX", explorer: "snowtrace.io", wQBC: "0xB7c8…Fa67", wQUSD: "0x8848…CAdB3", color: "#e84142" },
  { name: "Base", id: 8453, native: "ETH", explorer: "basescan.org", wQBC: "0x14Db…78AD", wQUSD: "0x1268…7992", color: "#0052ff" },
];

const contracts = [
  { name: "QuantumBridgeVault.sol", deployed: "Per external chain", purpose: "Locks native tokens (ETH/BNB/MATIC/AVAX), emits Poseidon2 commitments, unlocks via ZK proof" },
  { name: "ZKBridgeVerifier.sol", deployed: "Both QBC + external", purpose: "Verifies Poseidon2 ZK state proofs with Merkle inclusion, multi-prover confirmation" },
  { name: "BridgeMinter.sol", deployed: "QBC chain", purpose: "Mints wrapped assets (wETH, wBNB, wMATIC, wAVAX) on proof verification, burns for reverse bridge" },
  { name: "WrappedAsset.sol", deployed: "QBC chain (per asset)", purpose: "Universal ERC-20 wrapped token template with proof-tracked minting" },
  { name: "BridgeVault.sol", deployed: "QBC chain", purpose: "Original vault — locks QBC for wQBC minting on external chains (multi-sig relayers)" },
  { name: "wQBC.sol", deployed: "All 7 external chains", purpose: "Wrapped Qubitcoin ERC-20 token — 1:1 backed by locked QBC" },
];

const wrappedAssets = [
  { symbol: "wETH", name: "Wrapped Ether", decimals: 18, source: "Ethereum, Arbitrum, Optimism, Base" },
  { symbol: "wBNB", name: "Wrapped BNB", decimals: 18, source: "BNB Chain" },
  { symbol: "wMATIC", name: "Wrapped MATIC", decimals: 18, source: "Polygon" },
  { symbol: "wAVAX", name: "Wrapped AVAX", decimals: 18, source: "Avalanche" },
];

const securityFeatures = [
  "Poseidon2 ZK hash-based state proofs — prove lock/burn events without trusting relayers",
  "Dilithium5 (NIST Level 5) post-quantum signatures on all proof submissions",
  "Multi-prover confirmation — configurable threshold before minting/unlocking",
  "24-hour timelock on vault admin operations (verifier changes, fee updates)",
  "Guardian role for emergency pause — separate from owner for defense-in-depth",
  "Replay protection via proof hash tracking — each proof can only be used once",
  "Merkle inclusion proofs against cross-chain state roots",
  "Emergency withdraw function (requires paused state + owner authorization)",
];

export default function BridgePage() {
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
          ZK Bridge
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          Quantum-secure cross-chain bridge with Poseidon2 ZK proofs and Dilithium5 post-quantum signatures
        </p>

        {/* Overview */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Overview
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The Quantum Bridge connects QBC to 7 EVM chains using a trustless lock-and-mint architecture
            secured by zero-knowledge proofs. When tokens are locked on an external chain, a ZK proof of the
            lock event is generated using Poseidon2 hashing and verified on-chain before wrapped tokens are
            minted on QBC. The reverse flow (burn on QBC, unlock on external chain) uses the same proof system.
            All proof submissions require Dilithium5 post-quantum signatures, making the bridge secure against
            both classical and quantum computing attacks.
          </p>
        </section>

        {/* Key Stats */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Key Stats
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {[
              { label: "Supported Chains", value: "7 EVM" },
              { label: "Proof System", value: "Poseidon2 ZK" },
              { label: "Signatures", value: "Dilithium5" },
              { label: "Bridge Fee", value: "0.1% (configurable)" },
              { label: "Contracts", value: "6 Solidity" },
              { label: "Backing", value: "1:1 locked" },
              { label: "Admin Timelock", value: "24 hours" },
              { label: "Token Decimals", value: "wQBC/wQUSD = 8" },
              { label: "Chain ID", value: "QBC: 3303" },
            ].map((c) => (
              <div key={c.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{c.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{c.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Architecture */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Architecture
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Two flows: bridging external assets into QBC (lock/mint) and bridging QBC assets out (burn/unlock).
          </p>

          {/* Lock/Mint Flow */}
          <div className="mb-4 rounded-lg border p-4" style={{ borderColor: C.border, background: C.surface }}>
            <h3 className="mb-2 text-sm font-bold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
              External &rarr; QBC (Lock &amp; Mint)
            </h3>
            <div className="space-y-2">
              {[
                "User deposits ETH/BNB/MATIC/AVAX into QuantumBridgeVault on the external chain",
                "Vault emits Locked event with Poseidon2 commitment: H(sender, amount, nonce, chainId)",
                "ZK Prover generates Poseidon2 state proof of the lock event with Merkle inclusion",
                "Prover submits proof to ZKBridgeVerifier on QBC chain (signed with Dilithium5)",
                "Multiple provers confirm the same proof (configurable threshold)",
                "Verifier calls BridgeMinter.mintFromProof() to mint wETH/wBNB/wMATIC/wAVAX on QBC",
              ].map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="mt-0.5 text-xs font-mono font-bold" style={{ color: C.secondary }}>{i + 1}</span>
                  <span className="text-xs" style={{ color: C.textMuted }}>{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Burn/Unlock Flow */}
          <div className="rounded-lg border p-4" style={{ borderColor: C.border, background: C.surface }}>
            <h3 className="mb-2 text-sm font-bold" style={{ color: C.accent, fontFamily: "Space Grotesk, sans-serif" }}>
              QBC &rarr; External (Burn &amp; Unlock)
            </h3>
            <div className="space-y-2">
              {[
                "User calls BridgeMinter.burn() specifying destination chain and recipient address",
                "BridgeMinter burns wrapped tokens and emits Burned event with Poseidon2 commitment",
                "ZK Prover generates state proof of the burn event on QBC",
                "Prover submits proof to ZKBridgeVerifier on the external chain (Dilithium5 signed)",
                "Verifier calls QuantumBridgeVault.unlock() to release native tokens to recipient",
              ].map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="mt-0.5 text-xs font-mono font-bold" style={{ color: C.secondary }}>{i + 1}</span>
                  <span className="text-xs" style={{ color: C.textMuted }}>{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Architecture Diagram */}
          <div className="mt-4 rounded border p-4 font-mono text-xs leading-relaxed" style={{ borderColor: C.border, background: C.surface, color: C.textMuted }}>
            <pre>{`EXTERNAL CHAIN                          QBC CHAIN (3303)
┌──────────────────────┐          ┌──────────────────────┐
│  QuantumBridgeVault  │          │    BridgeMinter      │
│  (lock native tokens)│          │  (mint/burn wTokens) │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                  │
           │    ZK Proof (Poseidon2)          │
           │    + Dilithium5 Signature        │
           │                                  │
┌──────────▼───────────┐          ┌──────────▼───────────┐
│  ZKBridgeVerifier    │◄────────►│  ZKBridgeVerifier    │
│  (verify + unlock)   │          │  (verify + mint)     │
└──────────────────────┘          └──────────────────────┘`}</pre>
          </div>
        </section>

        {/* Supported Chains */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Supported Chains
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Chain</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>ID</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Native</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>wQBC</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>wQUSD</th>
                </tr>
              </thead>
              <tbody>
                {chains.map((ch) => (
                  <tr key={ch.id} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-semibold" style={{ color: ch.color }}>{ch.name}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.textMuted }}>{ch.id}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{ch.native}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{ch.wQBC}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{ch.wQUSD}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Wrapped Assets on QBC */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Wrapped Assets on QBC
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Native tokens locked in QuantumBridgeVault on external chains are represented as wrapped ERC-20
            tokens on QBC, minted by the BridgeMinter contract.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Symbol</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Name</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Decimals</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Source Chains</th>
                </tr>
              </thead>
              <tbody>
                {wrappedAssets.map((a) => (
                  <tr key={a.symbol} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs font-bold" style={{ color: C.accent }}>{a.symbol}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.text }}>{a.name}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.textMuted }}>{a.decimals}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{a.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Smart Contracts */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Smart Contracts
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Contract</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Deployed On</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Purpose</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <tr key={c.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{c.name}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.accent }}>{c.deployed}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{c.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ZK Proof System */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            ZK Proof System
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The bridge uses Poseidon2 hashing for ZK-friendly state proofs. Poseidon2 is designed specifically
            for zero-knowledge circuits, operating over the Goldilocks field (p = 2^64 - 2^32 + 1) with
            significantly lower circuit costs than Keccak or SHA3. The proof encodes:
          </p>
          <div className="rounded-lg border p-4 font-mono text-xs" style={{ borderColor: C.border, background: C.surface, color: C.primary }}>
            Poseidon2(sender, amount, nonce, sourceChainId, destChainId) = commitment
          </div>
          <p className="mt-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The commitment is included in the Lock/Burn event on the source chain. The ZK prover generates
            a proof that this commitment exists in the source chain state tree (Merkle inclusion proof)
            and that the Poseidon2 hash is correctly computed. The on-chain verifier checks both the
            proof validity and the Merkle path against the latest state root.
          </p>
        </section>

        {/* Security */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Security Features
          </h2>
          <div className="space-y-2">
            {securityFeatures.map((item, i) => (
              <div key={i} className="flex items-start gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span className="mt-0.5 text-xs font-mono font-bold" style={{ color: C.secondary }}>{i + 1}</span>
                <span className="text-sm" style={{ color: C.textMuted }}>{item}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Existing Bridge (wQBC/wQUSD) */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Existing Bridge (wQBC &amp; wQUSD)
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The original BridgeVault on QBC chain locks QBC and QUSD, with wrapped tokens (wQBC, wQUSD)
            deployed on all 7 external chains. Multi-sig relayers (minimum 3) confirm cross-chain transactions.
            Every wQBC is backed 1:1 by locked QBC. Uniswap V3 liquidity pools are live on all chains
            for trading wQBC and wQUSD.
          </p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "wQBC Chains", value: "7 live" },
              { label: "wQUSD Chains", value: "7 live" },
              { label: "Uniswap V3 Pools", value: "11 pools" },
              { label: "Bridge Fee", value: "0.1%" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.secondary }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Liquidity Pools */}
        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Uniswap V3 Liquidity Pools
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Live trading pools for wQBC and wQUSD across all 7 chains. Target price: 1 QBC = $0.25.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Chain</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Pair</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Fee</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { chain: "Ethereum", pair: "wQBC/WETH", fee: "0.3%" },
                  { chain: "Ethereum", pair: "wQUSD/USDC", fee: "0.05%" },
                  { chain: "BNB Chain", pair: "wQBC/WBNB", fee: "0.3%" },
                  { chain: "Polygon", pair: "wQBC/wQUSD", fee: "0.3%" },
                  { chain: "Arbitrum", pair: "wQBC/WETH", fee: "0.3%" },
                  { chain: "Optimism", pair: "wQBC/WETH", fee: "0.3%" },
                  { chain: "Avalanche", pair: "wQBC/WAVAX", fee: "0.3%" },
                  { chain: "Base", pair: "wQBC/WETH", fee: "0.3%" },
                ].map((p, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2" style={{ color: C.text }}>{p.chain}</td>
                    <td className="px-3 py-2 font-mono text-xs font-bold" style={{ color: C.primary }}>{p.pair}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{p.fee}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex justify-center">
            <Link
              href="/bridge"
              className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-bold transition-colors"
              style={{ background: `${C.secondary}30`, color: C.secondary }}
            >
              Open Bridge
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
