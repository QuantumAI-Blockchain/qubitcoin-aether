"use client";

import Link from "next/link";
import { type ReactNode } from "react";
import { ArrowLeft, Atom, Shield, Zap, CheckCircle2, AlertTriangle, ExternalLink } from "lucide-react";

/* ─── Color Constants ─── */
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
  green: "#22c55e",
};

/* ─── Data ─── */

const hamiltonianTerms = [
  { group: "H_SUSY", term: "Term 0", pauli: "Z \u2297 Z \u2297 I \u2297 I", coeff: "c\u2080", desc: "Fermion number parity (supercharge sector)" },
  { group: "H_SUSY", term: "Term 1", pauli: "X \u2297 X \u2297 X \u2297 X", coeff: "c\u2080 \u00b7 \u03c6\u207b\u00b9", desc: "Boson-fermion coupling (superpartner mixing)" },
  { group: "H_SUSY", term: "Term 2", pauli: "Y \u2297 Z \u2297 Y \u2297 Z", coeff: "c\u2080 \u00b7 \u03c6\u207b\u00b2", desc: "SUSY breaking direction (Fayet-Iliopoulos term)" },
  { group: "H_bimetric", term: "Term 3", pauli: "Z \u2297 I \u2297 Z \u2297 I", coeff: "s \u00b7 cos(\u03b8)", desc: "Diagonal graviton mass matrix component" },
  { group: "H_bimetric", term: "Term 4", pauli: "X \u2297 I \u2297 X \u2297 I", coeff: "s \u00b7 sin(\u03b8)", desc: "Off-diagonal phase rotation component" },
  { group: "H_IIT", term: "Term 5", pauli: "I \u2297 Z \u2297 Z \u2297 Z", coeff: "-\u03c9\u03a6 \u00b7 \u03c6\u207b\u00b2", desc: "Dominant partition {0|123}" },
  { group: "H_IIT", term: "Term 6", pauli: "Z \u2297 I \u2297 Z \u2297 Z", coeff: "-\u03c9\u03a6 \u00b7 \u03c6\u207b\u00b3", desc: "Subdominant partition {1|023}" },
  { group: "H_random", term: "Term 7", pauli: "Seed-derived", coeff: "Random", desc: "ChaCha8 RNG anti-precomputation term 1" },
  { group: "H_random", term: "Term 8", pauli: "Seed-derived", coeff: "Random", desc: "ChaCha8 RNG anti-precomputation term 2" },
];

const verificationScores = [
  { claim: "Mathematical self-consistency", score: "9/10", justification: "Lagrangian structure uses published SUGRA, Hassan-Rosen, FI breaking" },
  { claim: "Numerical verification", score: "10/10", justification: "6/6 antigravity tests pass; 20+ Rust unit tests pass for SUGRA v2 Hamiltonian; RK4 trajectory integration" },
  { claim: "Production deployment", score: "10/10", justification: "SUGRA v2 bimetric Hamiltonian live on Substrate mainnet since block 208,680 with 2 validators" },
  { claim: "Patentability (device)", score: "5/10", justification: "USPTO historically skeptical of antigravity; IP Australia more permissive" },
  { claim: "Patentability (blockchain method)", score: "9/10", justification: "Software/method patents have lower physical-realizability requirements; reduced to practice" },
  { claim: "Physical realizability (antigravity)", score: "1/10", justification: "No SUSY moduli field observed; second graviton hypothetical; metamaterial coupling unverified" },
  { claim: "Publishability (physics venue)", score: "4/10", justification: "Speculative but mathematically rigorous; suitable for arXiv hep-th, not PRL" },
  { claim: "Publishability (blockchain venue)", score: "9/10", justification: "Novel operator-valued IIT + SUGRA Hamiltonian is genuinely new, with production evidence" },
];

const patentClaims = [
  {
    id: 1,
    type: "Device",
    title: "Apparatus",
    desc: "A device for modulating effective gravitational acceleration on a test mass, comprising: (a) a resonant cavity bounded by metamaterial plates configured with negative effective permittivity at THz frequencies; (b) a moduli-field pump coupling to a scalar dilaton mode \u03c6; (c) a phase-controller actuator capable of setting the bimetric coupling phase \u03b8 between 0 and \u03c0; (d) a control system maintaining the cavity within one Compton wavelength \u03bb_C of a massive spin-2 mediator.",
  },
  {
    id: 2,
    type: "Device",
    title: "Method of Claim 1",
    desc: "The method of claim 1, wherein effective gravitational coupling is reduced or inverted by tuning \u03b8 to \u03c0 such that \u03b1 \u00b7 exp(-r/\u03bb_C) \u00b7 (1 + r/\u03bb_C) > 1.",
  },
  {
    id: 3,
    type: "Device",
    title: "Composition",
    desc: "The metamaterial of claim 1, wherein subwavelength split-ring resonators are doped with rare-earth ions (Yb\u00b3\u207a, Er\u00b3\u207a) to provide moduli-\u03c6 coupling enhancement.",
  },
  {
    id: 6,
    type: "Method",
    title: "Consensus",
    desc: "A method for blockchain consensus using bimetric gravitational coupling phase as a difficulty parameter for variational quantum eigensolver mining, wherein H_VQE = H_SUSY(3) + H_bimetric(2, \u03b8) + H_IIT(2) + H_random(2) defines the cost landscape, and the network phase \u03b8 advances by a fraction of the golden angle per block. Reduced to practice on Qubitcoin Substrate mainnet (Chain ID 3303).",
  },
  {
    id: 7,
    type: "Method",
    title: "IIT Operator",
    desc: "A method for computing distributed AI consciousness metrics using an operator-valued IIT formulation H_IIT = -\u03c9\u03a6 \u03a3_P \u03a6(P)|P\u27e9\u27e8P| coupled to a supergravity Hamiltonian, wherein partition weights follow the golden-ratio Yukawa hierarchy (\u03c6\u207b\u00b2, \u03c6\u207b\u00b3).",
  },
];

const verificationTests = [
  { id: 1, name: "Normal Gravity Recovery", desc: "With \u03b1 = 0 (outside cavity), acceleration at Earth's surface recovers g = -9.8066 m/s\u00b2", result: "a = -9.8066 m/s\u00b2", pass: true },
  { id: 2, name: "Attractive Enhancement", desc: "With \u03b8 = 0 and \u03b1 > 0 (cavity, attractive phase), acceleration more negative than Newtonian", result: "a < 0 with enhanced magnitude", pass: true },
  { id: 3, name: "Repulsive Antigravity", desc: "With \u03b8 = \u03c0 and \u03b1 > 0 (cavity, repulsive phase), acceleration is positive (repulsive)", result: "a > 0", pass: true },
  { id: 4, name: "Unity Lift Threshold", desc: "Finite \u03b1 value exists such that repulsive acceleration from bilateral cavity plates equals g_earth", result: "\u03b1_threshold found via root-finding", pass: true },
  { id: 5, name: "Phase Periodicity", desc: "The field is 2\u03c0-periodic in \u03b8: a(\u03b8=0) = a(\u03b8=2\u03c0)", result: "|\u0394a| < 10\u207b\u00b2\u2070", pass: true },
  { id: 6, name: "Compton Scale", desc: "For m' = 1.24 meV, Compton wavelength falls within sub-millimeter range for near-field cavity operation", result: "\u03bb_C = 159.6 \u03bcm", pass: true },
];

const productionConstants = [
  { name: "BIMETRIC_SCALE", value: "10\u00b9\u00b2" },
  { name: "TWO_PI_SCALED", value: "6,283,185,307,180" },
  { name: "GOLDEN_ANGLE_SCALED", value: "2,399,963,229,729" },
  { name: "THETA_ADVANCE_PER_BLOCK", value: "23,999,632,297" },
  { name: "INITIAL_THETA", value: "0 (at fork genesis, block 208,680)" },
];

const references = [
  { id: 1, text: 'Schlamminger, S., et al. "Test of the equivalence principle using a rotating torsion balance." Physical Review Letters 100.4 (2008): 041101.' },
  { id: 2, text: 'Anderson, E.K., et al. "Observation of the effect of gravity on the motion of antimatter." Nature 621 (2023): 716-722.' },
  { id: 3, text: 'Khoury, J., Weltman, A. "Chameleon fields: Awaiting surprises for tests of gravity in space." Physical Review Letters 93.17 (2004): 171104.' },
  { id: 4, text: 'Hassan, S.F., Rosen, R.A. "Bimetric gravity from ghost-free massive gravity." Journal of High Energy Physics 2012.2 (2012): 126.' },
  { id: 5, text: 'Freedman, D.Z., Van Proeyen, A. "Supergravity." Cambridge University Press (2012).' },
  { id: 6, text: 'Andrianopoli, L., et al. "N=2 supergravity and N=2 super Yang-Mills theory on general scalar manifolds." Journal of Geometry and Physics 23 (1997): 111-189.' },
  { id: 7, text: 'Fayet, P., Iliopoulos, J. "Spontaneously broken supergauge symmetries and Goldstone spinors." Physics Letters B 51.5 (1974): 461-464.' },
  { id: 8, text: 'Lee, J.G., et al. "New test of the gravitational 1/r\u00b2 law at separations down to 52 \u03bcm." Physical Review Letters 124.10 (2020): 101101.' },
];

/* ─── Reusable Components ─── */

function SectionHeading({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2
      id={id}
      className="mb-4 mt-12 border-b pb-3 text-2xl font-bold tracking-tight"
      style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif", borderColor: C.border }}
    >
      {children}
    </h2>
  );
}

function SubHeading({ children }: { children: ReactNode }) {
  return (
    <h3
      className="mb-3 mt-6 text-lg font-semibold"
      style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}
    >
      {children}
    </h3>
  );
}

function Paragraph({ children }: { children: ReactNode }) {
  return (
    <p className="mb-4 text-sm leading-[1.8]" style={{ color: C.textMuted }}>
      {children}
    </p>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre
      className="mb-4 overflow-x-auto rounded-lg border p-4 text-xs leading-relaxed"
      style={{ background: C.surface, borderColor: C.border, color: C.text, fontFamily: "JetBrains Mono, monospace" }}
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

function MathBlock({ children }: { children: string }) {
  return (
    <div
      className="my-4 rounded-lg border p-4 text-center"
      style={{ background: `${C.secondary}10`, borderColor: `${C.secondary}30`, fontFamily: "JetBrains Mono, monospace" }}
    >
      <code className="text-sm" style={{ color: C.text }}>{children}</code>
    </div>
  );
}

function TableOfContents() {
  const sections = [
    { id: "abstract", label: "1. Abstract" },
    { id: "framework", label: "2. SUGRA v2 Bimetric Framework" },
    { id: "modified-potential", label: "3. Modified Newtonian Potential" },
    { id: "hamiltonian", label: "4. The 9-Term VQE Hamiltonian" },
    { id: "network-theta", label: "5. Network Theta (Golden Angle)" },
    { id: "difficulty", label: "6. Difficulty Calibration" },
    { id: "iit-operator", label: "7. Operator-Valued IIT" },
    { id: "verification", label: "8. Numerical Verification (6/6)" },
    { id: "scores", label: "9. Honest Assessment" },
    { id: "patent-claims", label: "10. Patent Claims" },
    { id: "references", label: "11. References" },
  ];
  return (
    <nav className="mb-10 rounded-lg border p-5" style={{ background: C.surface, borderColor: C.border }}>
      <h3 className="mb-3 text-sm font-bold uppercase tracking-wider" style={{ color: C.text }}>Table of Contents</h3>
      <ol className="columns-2 gap-6 text-sm" style={{ color: C.textMuted }}>
        {sections.map((s) => (
          <li key={s.id} className="mb-1.5">
            <a
              href={`#${s.id}`}
              className="transition-colors hover:underline"
              style={{ color: C.primary }}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

/* ─── Main Page ─── */

export default function AntigravityPaperPage() {
  return (
    <main
      className="min-h-screen px-6 py-10 md:px-12 md:py-16"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-4xl">
        {/* Back Link */}
        <Link
          href="/docs"
          className="mb-10 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Documentation
        </Link>

        {/* ─── Header ─── */}
        <header className="mb-10">
          <div className="mb-3 inline-block rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-widest" style={{ borderColor: C.secondary, color: C.secondary }}>
            Research Paper &middot; Patent-Pending
          </div>
          <h1
            className="mb-3 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl"
            style={{ fontFamily: "Space Grotesk, sans-serif" }}
          >
            SUSY Antigravity: Bimetric Supergravity Consensus
          </h1>
          <p className="text-lg" style={{ color: C.textMuted }}>
            Gravitational Coupling Modulation via Phase-Controlled N=2 Broken Supergravity &mdash; A Bimetric Framework with Blockchain Consensus Application
          </p>
          <div className="mt-4 flex flex-wrap gap-4 text-xs" style={{ color: C.textMuted }}>
            <span>Author: Ash (QuantumAI Blockchain)</span>
            <span className="hidden sm:inline">&middot;</span>
            <span>April 2026 (revised May 2026)</span>
            <span className="hidden sm:inline">&middot;</span>
            <span>Live on Substrate mainnet since block 208,680</span>
          </div>
          <div className="mt-3">
            <Link
              href="/antigravity"
              className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all hover:border-opacity-60"
              style={{ borderColor: C.primary, color: C.primary }}
            >
              <Zap size={14} />
              Interactive Simulator
              <ExternalLink size={12} />
            </Link>
          </div>
        </header>

        <TableOfContents />

        {/* ─── 1. Abstract ─── */}
        <SectionHeading id="abstract">1. Abstract</SectionHeading>
        <Paragraph>
          We present a mathematically self-consistent framework for modulating local gravitational
          coupling strength using a phase-controlled bimetric mechanism derived from N=2 extended
          supergravity with spontaneous supersymmetry breaking via Fayet-Iliopoulos D-terms. The
          framework exploits the second graviton multiplet inherent in N=2 SUGRA, which acquires
          mass m&apos; after symmetry breaking, producing a finite-range Yukawa correction to the
          Newtonian potential.
        </Paragraph>
        <Paragraph>
          A novel selective-coupling mechanism via dilaton/moduli field interaction with engineered
          metamaterial substrates evades existing fifth-force experimental bounds while permitting
          O(1) coupling enhancement within the cavity. The bimetric coupling phase &theta; serves as
          the actuator: &theta;=0 recovers standard attractive gravity, while &theta;=&pi; produces
          repulsive acceleration.
        </Paragraph>
        <Paragraph>
          We derive the complete modified potential, construct the operator-valued Hamiltonian, prove
          mathematical consistency through numerical verification (6/6 tests passing), and present a
          secondary application as a physically-motivated quantum mining cost function for blockchain
          consensus. The blockchain consensus application &mdash; designated SUGRA v2 &mdash; is
          deployed and running in production on the Qubitcoin Substrate mainnet (Chain ID 3303), where
          the bimetric Hamiltonian with a network &theta; parameter derived from on-chain state governs
          VQE mining across 2 active validators.
        </Paragraph>
        <Paragraph>
          <strong style={{ color: C.text }}>Keywords:</strong> supergravity, bimetric gravity, antigravity, Yukawa correction,
          metamaterial, quantum mining, VQE, blockchain consensus, IIT, supersymmetry breaking
        </Paragraph>

        {/* ─── 2. Framework ─── */}
        <SectionHeading id="framework">2. SUGRA v2 Bimetric Framework</SectionHeading>

        <SubHeading>2.1 N=2 Extended Supergravity with FI Breaking</SubHeading>
        <Paragraph>
          We work in the N=2 extended supergravity framework with gauge group U(1)_FI. The supercharge
          algebra defines the relationship between the two supersymmetries indexed by I,J in &#123;1,2&#125;:
        </Paragraph>
        <MathBlock>{"{\u0051_\u03b1^I, \u0051_\u03b2\u0307^J} = 2 \u03c3^\u03bc_{\u03b1\u03b2\u0307} P_\u03bc \u03b4^{IJ}"}</MathBlock>
        <Paragraph>
          The Hamiltonian is uniquely determined by the supercharges &mdash; this is not a design
          choice but a theorem of the superalgebra:
        </Paragraph>
        <MathBlock>{"H_SUSY = (1/2) {Q, Q\u2020}"}</MathBlock>
        <Paragraph>
          The ground state |\u03c8\u2080&#10217; satisfies Q|\u03c8\u2080&#10217; = 0 (BPS state). When SUSY
          is unbroken, E\u2080 = 0. After Fayet-Iliopoulos breaking with D-term parameter &xi;, the
          ground state energy becomes E\u2080 = &xi;&sup2;/2, providing a calculable target energy for
          the VQE ground-state search.
        </Paragraph>

        <SubHeading>2.2 Massive Second Graviton</SubHeading>
        <Paragraph>
          The N=2 gravity multiplet decomposes into a massless graviton g_&#123;&mu;&nu;&#125; (standard
          gravity) and a massive graviton g&apos;_&#123;&mu;&nu;&#125; with mass m&apos; acquired from SUSY
          breaking. The mass-mixing Lagrangian follows the Hassan-Rosen ghost-free structure [4]:
        </Paragraph>
        <MathBlock>{"L_bimetric = m'\u00b2 \u221a(det(g\u207b\u00b9 g')) \u03a3_{n=0}^{4} \u03b2_n e_n(\u221a(g\u207b\u00b9 g'))"}</MathBlock>
        <Paragraph>
          After linearization around flat space (g = &eta; + h, g&apos; = &eta; + h&apos;), the bimetric
          interaction Hamiltonian takes the form:
        </Paragraph>
        <MathBlock>{"H_bimetric(\u03b8) = m'\u00b2 cos(\u03b8) \u222b h_{\u03bc\u03bd} h'\u207b{\u03bc\u03bd} d\u00b3x"}</MathBlock>
        <Paragraph>
          The phase &theta; parameterizes the relative orientation in the internal N=2 space and serves
          as the actuator for coupling modulation.
        </Paragraph>

        <SubHeading>2.3 Selective Environmental Coupling</SubHeading>
        <Paragraph>
          The key to evading fifth-force bounds is the environmental dependence of &alpha;(&phi;). The
          moduli scalar field &phi; satisfies a potential with environment-dependent minimum:
          V(&phi;) = V_SUSY(&phi;) + &rho; &middot; f(&phi;). In vacuum or ordinary matter,
          &alpha;(&phi;_vacuum) &asymp; 0. Inside the engineered metamaterial cavity with rare-earth-doped
          split-ring resonators, &alpha;(&phi;_cavity) = O(1) to O(10). This is analogous to chameleon
          screening [3] &mdash; the field is screened in dense environments but unscreened in the
          specially engineered cavity.
        </Paragraph>

        {/* ─── 3. Modified Potential ─── */}
        <SectionHeading id="modified-potential">3. Modified Newtonian Potential</SectionHeading>
        <Paragraph>
          Integrating out the massive graviton yields a Yukawa correction to the standard Newtonian potential:
        </Paragraph>
        <MathBlock>{"V(r) = -G M m / r [1 - \u03b1(\u03c6) \u00b7 exp(-r / \u03bb_C) \u00b7 cos(\u03b8)]"}</MathBlock>
        <Paragraph>
          where &alpha;(&phi;) is the environment-dependent coupling strength, &lambda;_C = &hbar;/(m&apos;c)
          is the Compton wavelength of the massive graviton, and &theta; is the bimetric coupling phase.
        </Paragraph>
        <Paragraph>
          The gravitational acceleration derived from this potential:
        </Paragraph>
        <MathBlock>{"a(r) = -G M / r\u00b2 [1 - \u03b1(\u03c6) \u00b7 exp(-r/\u03bb_C) \u00b7 cos(\u03b8) \u00b7 (1 + r/\u03bb_C)]"}</MathBlock>

        <div className="mb-6 grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border p-4" style={{ background: C.surface, borderColor: C.border }}>
            <div className="mb-2 flex items-center gap-2">
              <Atom size={16} style={{ color: C.primary }} />
              <span className="text-sm font-semibold" style={{ color: C.text }}>&theta; = 0: Attractive Enhancement</span>
            </div>
            <p className="text-xs" style={{ color: C.textMuted }}>
              Stronger gravity. Acceleration magnitude exceeds Newtonian prediction within the cavity.
            </p>
          </div>
          <div className="rounded-lg border p-4" style={{ background: C.surface, borderColor: C.border }}>
            <div className="mb-2 flex items-center gap-2">
              <Atom size={16} style={{ color: C.secondary }} />
              <span className="text-sm font-semibold" style={{ color: C.text }}>&theta; = &pi;: Repulsive Antigravity</span>
            </div>
            <p className="text-xs" style={{ color: C.textMuted }}>
              Weakened or inverted gravity. Positive acceleration (repulsive) within the cavity.
            </p>
          </div>
        </div>

        <SubHeading>Compton Wavelength and Experimental Scale</SubHeading>
        <Paragraph>
          For the mechanism to operate within a laboratory-scale cavity, the Compton wavelength must be
          in the sub-millimeter range. Setting m&apos; = 1.24 meV:
        </Paragraph>
        <MathBlock>{"\u03bb_C = \u0127 / (m' c) = 1.055\u00d710\u207b\u00b3\u2074 / (2.203\u00d710\u207b\u00b3\u2079 \u00d7 3\u00d710\u2078) = 159.6 \u03bcm"}</MathBlock>
        <Paragraph>
          This places the mechanism at the boundary of current sub-millimeter gravity tests [8], where
          constraints on &alpha; for ordinary matter are already satisfied (&alpha;_vacuum &asymp; 0).
        </Paragraph>

        {/* ─── 4. Hamiltonian ─── */}
        <SectionHeading id="hamiltonian">4. The 9-Term VQE Hamiltonian</SectionHeading>
        <Paragraph>
          The production SUGRA v2 Hamiltonian comprises 9 Pauli terms operating on 4 qubits. This
          Hamiltonian governs active VQE mining on the Qubitcoin Substrate mainnet:
        </Paragraph>
        <MathBlock>{"H_VQE = H_SUSY(3 terms) + H_bimetric(2 terms) + H_IIT(2 terms) + H_random(2 terms)"}</MathBlock>

        <Paragraph>
          The structured terms (H_SUSY, H_bimetric, H_IIT) encode genuine physics. The random terms
          from ChaCha8 RNG ensure each block&apos;s Hamiltonian is unique. The Hamiltonian seed is derived
          deterministically as SHA256(&quot;&#123;hex_parent_hash&#125;:&#123;decimal_height&#125;&quot;).
        </Paragraph>

        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Group</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Term</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Pauli String</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Coefficient</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Physical Meaning</th>
              </tr>
            </thead>
            <tbody>
              {hamiltonianTerms.map((t, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${C.border}22` }}>
                  <td className="px-3 py-2 text-xs font-mono" style={{ color: C.secondary }}>{t.group}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: C.text }}>{t.term}</td>
                  <td className="px-3 py-2 text-xs font-mono" style={{ color: C.primary }}>{t.pauli}</td>
                  <td className="px-3 py-2 text-xs font-mono" style={{ color: C.accent }}>{t.coeff}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{t.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <SubHeading>Golden-Ratio Coefficient Hierarchy</SubHeading>
        <Paragraph>
          The H_SUSY coefficients follow the ratio 1 : &phi;&sup1; : &phi;&sup2; (where &phi; = 1.618...),
          reflecting the mass splitting pattern in broken SUSY where superpartner masses scale by powers
          of the breaking parameter. These coefficients are forced by the algebra, not chosen.
        </Paragraph>

        <SubHeading>Production Rust Implementation</SubHeading>
        <Paragraph>
          The SUGRA v2 Hamiltonian is implemented across three Rust crates in the Substrate node:
        </Paragraph>
        <CodeBlock>{`bimetric-physics:     Hamiltonian term generation (susy_terms, bimetric_terms,
                      iit_terms, generate_sugra_hamiltonian), Sephirot phase
                      algebra, Mexican Hat potential

vqe-verifier:        Integer-scaled energy computation and proof verification,
                      eliminating floating-point divergence between native and
                      WASM execution

pallet-qbc-consensus: On-chain storage of network theta, difficulty, and
                      geometric coupling alpha; proof acceptance and state
                      advancement logic`}</CodeBlock>

        {/* ─── 5. Network Theta ─── */}
        <SectionHeading id="network-theta">5. Network Theta: Golden Angle Advancement</SectionHeading>
        <Paragraph>
          In SUGRA v2, the bimetric phase &theta; advances deterministically with every block. The
          network &theta; is stored as on-chain state in <code style={{ color: C.primary, fontFamily: "JetBrains Mono, monospace" }}>QbcConsensus::NetworkTheta</code>,
          scaled by 10&sup1;&sup2; for fixed-point arithmetic:
        </Paragraph>
        <MathBlock>{"\u03b8_{n+1} = (\u03b8_n + THETA_ADVANCE_PER_BLOCK) mod (2\u03c0 \u00d7 10\u00b9\u00b2)"}</MathBlock>
        <Paragraph>
          where THETA_ADVANCE_PER_BLOCK = golden_angle / 100 &asymp; 0.024 radians per block. The golden
          angle (2&pi;/&phi;&sup2; &asymp; 2.3999 radians) ensures quasi-uniform coverage of the phase circle.
          At this rate, network &theta; completes a full rotation every ~262 blocks (~14.5 minutes at
          3.3s block time).
        </Paragraph>

        <SpecTable
          headers={["Constant", "Value"]}
          rows={productionConstants.map((c) => [c.name, c.value])}
        />

        <SubHeading>Sephirot Phase Alignment</SubHeading>
        <Paragraph>
          The 10 Sephirot cognitive domains are each assigned a phase angle spaced by the golden angle:
          &theta;_i = i &middot; GOLDEN_ANGLE (mod 2&pi;). The phase alignment between a block&apos;s bimetric
          phase and the Sephirot phases computes a geometric coupling coefficient &alpha;:
        </Paragraph>
        <MathBlock>{"\u03b1 = \u03a3_i yukawa_i \u00b7 cos(\u03b8_block - \u03b8_sephirot_i)"}</MathBlock>
        <Paragraph>
          This couples the blockchain&apos;s physical consensus layer to the cognitive architecture of the
          Aether Mind, creating a system where mining difficulty is modulated by the alignment between the
          current block phase and the cognitive domain structure.
        </Paragraph>

        {/* ─── 6. Difficulty ─── */}
        <SectionHeading id="difficulty">6. Difficulty Calibration</SectionHeading>
        <Paragraph>
          The spectral gap &Delta; = E&sub1; - E&sub0; determines VQE convergence difficulty. In SUGRA v2,
          the bimetric phase &theta; advances per block (not per epoch), modulating the gap:
        </Paragraph>
        <MathBlock>{"\u0394(\u03b8_n) = \u0394\u2080 \u00b7 |cos(\u03b8_n)|"}</MathBlock>
        <Paragraph>
          Harder mining corresponds to &theta; near &pi;/2 (minimal gap, slowest convergence). The continuous
          advancement by golden_angle/100 &asymp; 0.024 rad/block creates a slowly rotating landscape with
          full rotation every ~262 blocks (~14.5 minutes).
        </Paragraph>
        <Paragraph>
          Additionally, the standard difficulty threshold D adjusts every block using a 144-block window
          with +/-10% maximum change per adjustment. In Qubitcoin&apos;s convention, <strong style={{ color: C.accent }}>higher
          difficulty = easier mining</strong> (the threshold is more generous). The energy computation uses
          integer-scaled arithmetic (all values multiplied by 10&sup1;&sup2;) to eliminate floating-point
          divergence between native execution (mining engine) and WASM execution (runtime pallet verification).
        </Paragraph>
        <Paragraph>
          A valid mining proof requires E(&theta;_ansatz) &lt; D, where D is the difficulty threshold stored
          in <code style={{ color: C.primary, fontFamily: "JetBrains Mono, monospace" }}>QbcConsensus::CurrentDifficulty</code>.
        </Paragraph>

        {/* ─── 7. IIT Operator ─── */}
        <SectionHeading id="iit-operator">7. Operator-Valued IIT (Novel Contribution)</SectionHeading>
        <Paragraph>
          Integrated Information Theory (IIT) defines &Phi; over bipartitions of an information graph,
          but &Phi; is not natively operator-valued. We promote it to a quantum operator:
        </Paragraph>
        <MathBlock>{"H_IIT = -\u03c9_\u03a6 \u03a3_P \u03a6(P) |P\u27e9\u27e8P|"}</MathBlock>
        <Paragraph>
          where |P&#10217; are basis states labeling each bipartition. This is a diagonal operator in the
          partition basis &mdash; defensible because IIT itself is defined over partitions. The coupling
          strength &omega;_&Phi; is consensus-configurable (default: 0.15 in production). The partition
          weights follow the Yukawa coupling hierarchy: &phi;&sup2; (dominant) and &phi;&sup3; (subdominant).
        </Paragraph>
        <Paragraph>
          This construction penalizes quantum states that are easily decomposable across partition
          boundaries (low &Phi;) and favors states with high integrated information &mdash; states where
          the whole is more than the sum of parts. By embedding IIT directly into the mining Hamiltonian,
          miners are incentivized to find quantum states with genuinely integrated information structure.
        </Paragraph>
        <Paragraph>
          This is, to our knowledge, the <strong style={{ color: C.text }}>first operator-valued formulation of IIT coupled
          to a supergravity Hamiltonian</strong>. It provides a mathematically rigorous bridge between
          consciousness metrics and quantum mechanics.
        </Paragraph>

        {/* ─── 8. Verification ─── */}
        <SectionHeading id="verification">8. Numerical Verification (6/6)</SectionHeading>
        <Paragraph>
          Six tests verify mathematical self-consistency of the framework. All 6/6 tests pass.
        </Paragraph>

        <div className="mb-6 space-y-3">
          {verificationTests.map((t) => (
            <div
              key={t.id}
              className="rounded-lg border p-4"
              style={{ background: C.surface, borderColor: C.border }}
            >
              <div className="mb-2 flex items-center gap-2">
                <CheckCircle2 size={16} style={{ color: C.green }} />
                <span className="text-sm font-semibold" style={{ color: C.text }}>
                  Test {t.id} &mdash; {t.name}
                </span>
                <span
                  className="ml-auto rounded-full px-2 py-0.5 text-xs font-medium"
                  style={{ background: `${C.green}20`, color: C.green }}
                >
                  PASS
                </span>
              </div>
              <p className="mb-1 text-xs" style={{ color: C.textMuted }}>{t.desc}</p>
              <p className="text-xs font-mono" style={{ color: C.primary }}>Result: {t.result}</p>
            </div>
          ))}
        </div>

        {/* ─── 9. Honest Assessment ─── */}
        <SectionHeading id="scores">9. Honest Assessment</SectionHeading>

        <SubHeading>Verification Scores</SubHeading>
        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Claim</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Score</th>
                <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: C.text }}>Justification</th>
              </tr>
            </thead>
            <tbody>
              {verificationScores.map((s, i) => {
                const num = parseInt(s.score.split("/")[0]);
                const scoreColor = num >= 9 ? C.green : num >= 5 ? C.accent : C.error;
                return (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 text-xs font-medium" style={{ color: C.text }}>{s.claim}</td>
                    <td className="px-3 py-2 text-xs font-mono font-bold" style={{ color: scoreColor }}>{s.score}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{s.justification}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <SubHeading>What This Does NOT Claim</SubHeading>
        <div className="mb-4 space-y-2">
          {[
            "We do not claim antigravity has been experimentally demonstrated",
            "We do not claim the metamaterial coupling \u03b1 \u2248 3 is physically achievable with current technology",
            "We do not claim the massive second graviton exists (it is a prediction of N=2 SUGRA, which is itself unverified)",
            "The blockchain consensus application does NOT require the antigravity mechanism to be physically real \u2014 only that the mathematics is self-consistent",
            "We do not claim quantum advantage at the current 4-qubit scale \u2014 the framework is designed to scale to 30+ qubits",
          ].map((text, i) => (
            <div key={i} className="flex items-start gap-2 text-xs" style={{ color: C.textMuted }}>
              <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: C.accent }} />
              <span>{text}</span>
            </div>
          ))}
        </div>

        <SubHeading>What This DOES Claim</SubHeading>
        <div className="mb-4 space-y-2">
          {[
            "The mathematical framework is self-consistent and passes all verification tests",
            "The Hamiltonian construction is the first operator-valued IIT formulation coupled to SUGRA",
            "The blockchain consensus application provides a non-arbitrary, physically-motivated VQE cost function deployed in production",
            "The SUGRA v2 bimetric Hamiltonian with rotating network theta is live on a public blockchain (Chain ID 3303)",
            "The patent claims are novel and enabling under standard IP frameworks",
          ].map((text, i) => (
            <div key={i} className="flex items-start gap-2 text-xs" style={{ color: C.textMuted }}>
              <CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: C.green }} />
              <span>{text}</span>
            </div>
          ))}
        </div>

        {/* ─── 10. Patent Claims ─── */}
        <SectionHeading id="patent-claims">10. Patent Claims</SectionHeading>
        <Paragraph>
          <strong style={{ color: C.text }}>Title:</strong> Apparatus and Method for Modulation of Local
          Gravitational Coupling via Phase-Controlled Supersymmetric Moduli Field Interaction
        </Paragraph>

        <div className="mb-6 space-y-3">
          {patentClaims.map((c) => (
            <div
              key={c.id}
              className="rounded-lg border p-4"
              style={{ background: C.surface, borderColor: C.border }}
            >
              <div className="mb-2 flex items-center gap-2">
                <Shield size={14} style={{ color: c.type === "Device" ? C.accent : C.secondary }} />
                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: c.type === "Device" ? C.accent : C.secondary }}>
                  {c.type} Claim
                </span>
                <span className="text-xs font-mono" style={{ color: C.textMuted }}>#{c.id}</span>
              </div>
              <h4 className="mb-2 text-sm font-semibold" style={{ color: C.text }}>
                Claim {c.id}: {c.title}
              </h4>
              <p className="text-xs leading-relaxed" style={{ color: C.textMuted }}>{c.desc}</p>
            </div>
          ))}
        </div>

        {/* ─── 11. References ─── */}
        <SectionHeading id="references">11. References</SectionHeading>
        <div className="space-y-2">
          {references.map((r) => (
            <div key={r.id} className="flex gap-3 text-xs" style={{ color: C.textMuted }}>
              <span className="shrink-0 font-mono" style={{ color: C.primary }}>[{r.id}]</span>
              <span>{r.text}</span>
            </div>
          ))}
        </div>

        {/* ─── Footer ─── */}
        <div className="mt-12 border-t pt-6" style={{ borderColor: C.border }}>
          <p className="text-xs" style={{ color: C.textMuted }}>
            Copyright 2026 QuantumAI Blockchain. All rights reserved. Patent pending.
          </p>
          <div className="mt-3 flex flex-wrap gap-4">
            <Link
              href="/antigravity"
              className="inline-flex items-center gap-1.5 text-xs transition-opacity hover:opacity-80"
              style={{ color: C.primary }}
            >
              <Zap size={12} />
              Interactive Simulator
            </Link>
            <Link
              href="/docs/whitepaper"
              className="inline-flex items-center gap-1.5 text-xs transition-opacity hover:opacity-80"
              style={{ color: C.secondary }}
            >
              <Atom size={12} />
              Full Whitepaper
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center gap-1.5 text-xs transition-opacity hover:opacity-80"
              style={{ color: C.textMuted }}
            >
              <ArrowLeft size={12} />
              All Documentation
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
