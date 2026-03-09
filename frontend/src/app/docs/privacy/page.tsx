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

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2
        className="mb-3 text-xl font-semibold"
        style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
      >
        {title}
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
    <h3
      className="mb-2 mt-4 text-base font-semibold"
      style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}
    >
      {children}
    </h3>
  );
}

const privacyModes = [
  {
    mode: "Public (Default)",
    amounts: "Visible",
    addresses: "Visible",
    txSize: "~300 bytes",
    verification: "Fast",
  },
  {
    mode: "Private (Opt-In)",
    amounts: "Hidden",
    addresses: "Hidden",
    txSize: "~2,000 bytes",
    verification: "~10ms (range proof)",
  },
];

const components = [
  {
    name: "Pedersen Commitments",
    formula: "C = v\u00B7G + r\u00B7H",
    description:
      "Cryptographic commitments that hide transaction amounts while preserving additive homomorphism. The sum of input commitments equals the sum of output commitments, allowing validators to confirm that no QBC was created or destroyed without revealing the actual values.",
  },
  {
    name: "Bulletproofs Range Proofs",
    formula: "~672 bytes, O(log n), no trusted setup",
    description:
      "Zero-knowledge proofs that committed values fall within [0, 2\u2076\u2074) without revealing the value itself. Bulletproofs are non-interactive, require no trusted setup ceremony, and produce compact proofs that scale logarithmically with the number of outputs.",
  },
  {
    name: "Stealth Addresses",
    formula: "Spend key + View key \u2192 One-time address",
    description:
      "One-time addresses generated per transaction prevent address linkability. The sender uses the recipient\u2019s spend and view public keys combined with an ephemeral secret to derive a unique destination address. Only the recipient can detect and spend the funds.",
  },
  {
    name: "Key Images",
    formula: "I = x\u00B7H(P)",
    description:
      "Cryptographic construct derived from the private key and a hash of the public key. Each confidential output produces a unique key image that is published when spent, preventing double-spending of private outputs without revealing which output was consumed.",
  },
];

const deniableEndpoints = [
  {
    endpoint: "POST /privacy/batch-balance",
    description: "Query multiple address balances in a single request with constant-time response, preventing timing side-channels.",
  },
  {
    endpoint: "POST /privacy/bloom-utxos",
    description: "Returns UTXOs as a Bloom filter rather than exact matches, providing plausible deniability for which UTXOs belong to the requester.",
  },
  {
    endpoint: "POST /privacy/batch-blocks",
    description: "Fetch multiple blocks in one request to mask which specific block the client is interested in.",
  },
  {
    endpoint: "POST /privacy/batch-tx",
    description: "Fetch multiple transactions in a single request to prevent observation of which transaction the client is tracking.",
  },
];

export default function PrivacyPage() {
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

        <h1
          className="mb-2 text-3xl font-bold"
          style={{ fontFamily: "Space Grotesk, sans-serif" }}
        >
          Privacy &amp; SUSY Swaps
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          Opt-in confidential transactions for the Quantum Blockchain &mdash; hide amounts and
          addresses while maintaining full verifiability
        </p>

        {/* Overview */}
        <SectionCard title="Overview">
          <Paragraph>
            Quantum Blockchain supports opt-in privacy through SUSY Swaps &mdash; confidential
            transactions that hide amounts and addresses while maintaining cryptographic
            verifiability. Privacy is not mandatory; users choose between public and private
            transaction modes on a per-transaction basis. Public transactions remain the default
            for maximum transparency and auditability.
          </Paragraph>
          <Paragraph>
            The privacy system is built on three well-established cryptographic primitives:
            Pedersen commitments for amount hiding, Bulletproofs for range verification, and
            stealth addresses for address unlinkability. Together they provide strong privacy
            guarantees without requiring a trusted setup or compromising network security.
          </Paragraph>
        </SectionCard>

        {/* Privacy Modes */}
        <SectionCard title="Transaction Modes">
          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: C.border }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: C.surface }}>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Mode</th>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Amounts</th>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Addresses</th>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Tx Size</th>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Verification</th>
                </tr>
              </thead>
              <tbody>
                {privacyModes.map((row) => (
                  <tr key={row.mode} className="border-t" style={{ borderColor: C.border }}>
                    <td className="px-4 py-2 font-semibold" style={{ color: C.text }}>{row.mode}</td>
                    <td className="px-4 py-2" style={{ color: C.textMuted }}>{row.amounts}</td>
                    <td className="px-4 py-2" style={{ color: C.textMuted }}>{row.addresses}</td>
                    <td className="px-4 py-2 font-mono text-xs" style={{ color: C.textMuted }}>{row.txSize}</td>
                    <td className="px-4 py-2" style={{ color: C.textMuted }}>{row.verification}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        {/* Cryptographic Components */}
        <SectionCard title="Cryptographic Components">
          <div className="space-y-4">
            {components.map((comp) => (
              <div
                key={comp.name}
                className="rounded-lg border p-4"
                style={{ background: C.surface, borderColor: C.border }}
              >
                <div className="mb-2 flex flex-wrap items-center gap-3">
                  <h3
                    className="text-base font-semibold"
                    style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}
                  >
                    {comp.name}
                  </h3>
                  <code
                    className="rounded px-2 py-0.5 text-xs"
                    style={{ background: `${C.primary}15`, color: C.primary }}
                  >
                    {comp.formula}
                  </code>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
                  {comp.description}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>

        {/* How SUSY Swaps Work */}
        <SectionCard title="How SUSY Swaps Work">
          <SubHeading>1. Commitment Phase</SubHeading>
          <Paragraph>
            The sender creates Pedersen commitments for each output amount. A commitment
            C = v&middot;G + r&middot;H binds the sender to the value v using blinding factor r,
            without revealing v. The blinding factors are chosen so that the sum of input
            commitments minus the sum of output commitments equals zero, proving conservation
            of value.
          </Paragraph>

          <SubHeading>2. Range Proof Generation</SubHeading>
          <Paragraph>
            For each output commitment, a Bulletproof range proof is generated demonstrating
            that the committed value is non-negative and less than 2&sup3;&sup2;. This prevents
            the creation of negative outputs that would effectively mint new QBC. Each proof is
            approximately 672 bytes regardless of the value range.
          </Paragraph>

          <SubHeading>3. Stealth Address Derivation</SubHeading>
          <Paragraph>
            The sender generates an ephemeral keypair and combines it with the recipient&apos;s
            public spend and view keys to derive a one-time stealth address. The ephemeral
            public key is included in the transaction. Only the recipient, scanning with their
            view key, can identify incoming payments and reconstruct the private key needed to
            spend.
          </Paragraph>

          <SubHeading>4. Key Image Publication</SubHeading>
          <Paragraph>
            When spending a private output, the sender publishes the key image I = x&middot;H(P).
            The network checks that this key image has never appeared before, preventing
            double-spending. The key image is deterministic for a given output, so the same
            output always produces the same image, but it is computationally infeasible to
            link a key image back to its source output.
          </Paragraph>

          <SubHeading>5. Verification</SubHeading>
          <Paragraph>
            Validators verify: (a) all Bulletproof range proofs are valid, (b) commitments
            balance (inputs = outputs + fee), (c) no key image has been seen before, and
            (d) the transaction signature is valid. The entire verification takes approximately
            10 milliseconds per transaction.
          </Paragraph>
        </SectionCard>

        {/* What Is Hidden / Not Hidden */}
        <SectionCard title="Privacy Guarantees">
          <div className="grid gap-4 sm:grid-cols-2">
            <div
              className="rounded-lg border p-4"
              style={{ background: C.surface, borderColor: C.border }}
            >
              <h3
                className="mb-2 text-sm font-semibold"
                style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}
              >
                Hidden (Private Mode)
              </h3>
              <ul className="space-y-1.5 text-sm" style={{ color: C.textMuted }}>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.primary }} />
                  Transaction amounts
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.primary }} />
                  Sender and receiver addresses
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.primary }} />
                  Balance linkability between transactions
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.primary }} />
                  UTXO ownership graph
                </li>
              </ul>
            </div>
            <div
              className="rounded-lg border p-4"
              style={{ background: C.surface, borderColor: C.border }}
            >
              <h3
                className="mb-2 text-sm font-semibold"
                style={{ color: C.accent, fontFamily: "Space Grotesk, sans-serif" }}
              >
                Visible (Always)
              </h3>
              <ul className="space-y-1.5 text-sm" style={{ color: C.textMuted }}>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.accent }} />
                  Transaction existence on-chain
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.accent }} />
                  Block timestamps
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.accent }} />
                  Fee amounts (paid publicly)
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: C.accent }} />
                  Transaction size and network metadata
                </li>
              </ul>
            </div>
          </div>
        </SectionCard>

        {/* Deniable RPC Endpoints */}
        <SectionCard title="Deniable RPC Endpoints">
          <Paragraph>
            Even querying the blockchain can leak information about which addresses or
            transactions a user is interested in. Quantum Blockchain provides four
            privacy-preserving RPC endpoints that use batching and probabilistic data
            structures to prevent observation of query patterns.
          </Paragraph>
          <div className="space-y-3">
            {deniableEndpoints.map((ep) => (
              <div
                key={ep.endpoint}
                className="rounded-lg border p-4"
                style={{ background: C.surface, borderColor: C.border }}
              >
                <code
                  className="mb-1.5 block text-xs font-semibold"
                  style={{ color: C.secondary }}
                >
                  {ep.endpoint}
                </code>
                <p className="text-sm" style={{ color: C.textMuted }}>
                  {ep.description}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Implementation Files */}
        <SectionCard title="Implementation">
          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: C.border }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: C.surface }}>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Module</th>
                  <th className="px-4 py-2 text-left font-semibold" style={{ color: C.primary }}>Purpose</th>
                </tr>
              </thead>
              <tbody style={{ color: C.textMuted }}>
                <tr className="border-t" style={{ borderColor: C.border }}>
                  <td className="px-4 py-2 font-mono text-xs">privacy/commitments.py</td>
                  <td className="px-4 py-2">Pedersen commitment creation, verification, and blinding factor management</td>
                </tr>
                <tr className="border-t" style={{ borderColor: C.border }}>
                  <td className="px-4 py-2 font-mono text-xs">privacy/range_proofs.py</td>
                  <td className="px-4 py-2">Bulletproofs generation and batch verification</td>
                </tr>
                <tr className="border-t" style={{ borderColor: C.border }}>
                  <td className="px-4 py-2 font-mono text-xs">privacy/stealth.py</td>
                  <td className="px-4 py-2">Stealth address generation, scanning, and key derivation</td>
                </tr>
                <tr className="border-t" style={{ borderColor: C.border }}>
                  <td className="px-4 py-2 font-mono text-xs">privacy/susy_swap.py</td>
                  <td className="px-4 py-2">Confidential transaction builder and SUSY swap orchestration</td>
                </tr>
              </tbody>
            </table>
          </div>
        </SectionCard>

        {/* Use in Wallet */}
        <SectionCard title="Using Private Transactions">
          <Paragraph>
            SUSY Swaps are accessed through the Quantum Blockchain wallet. When constructing
            a transaction, toggle the privacy mode to &quot;Private&quot; to create a confidential
            transaction. The wallet handles commitment generation, range proof creation, and
            stealth address derivation automatically. Recipients scan for incoming stealth
            payments using their view key.
          </Paragraph>
          <div className="mt-4 flex justify-center">
            <Link
              href="/wallet"
              className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-bold transition-colors"
              style={{ background: `${C.secondary}30`, color: C.secondary }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              Open Wallet
            </Link>
          </div>
        </SectionCard>
      </div>
    </main>
  );
}
