//! Genesis Knowledge -- Static seed data for the Aether Tree.
//!
//! Contains verified facts across 11 domains (~180 axiom nodes) seeded at
//! genesis or startup to bootstrap the knowledge graph with diverse,
//! cross-domain knowledge.

use serde::{Deserialize, Serialize};

/// A single genesis knowledge fact.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenesisFact {
    pub text: &'static str,
    pub confidence: f64,
    pub domain: &'static str,
}

/// All genesis knowledge organized by domain.
/// Total: ~180 axiom nodes across 11 domains.
pub static GENESIS_KNOWLEDGE: &[GenesisFact] = &[
    // Quantum Physics (20)
    GenesisFact { text: "Superposition: a quantum system exists in multiple states simultaneously until measured.", confidence: 0.98, domain: "quantum_physics" },
    GenesisFact { text: "Entanglement: two particles share quantum state such that measuring one instantly determines the other.", confidence: 0.98, domain: "quantum_physics" },
    GenesisFact { text: "Heisenberg uncertainty principle: Delta_x * Delta_p >= hbar/2.", confidence: 0.99, domain: "quantum_physics" },
    GenesisFact { text: "Quantum decoherence: interaction with environment causes quantum states to lose coherence.", confidence: 0.97, domain: "quantum_physics" },
    GenesisFact { text: "The Schrodinger equation i*hbar*d/dt|psi> = H|psi> governs quantum time evolution.", confidence: 0.99, domain: "quantum_physics" },
    GenesisFact { text: "Quantum tunneling: particles penetrate energy barriers they classically could not overcome.", confidence: 0.98, domain: "quantum_physics" },
    GenesisFact { text: "Pauli exclusion principle: no two identical fermions can occupy the same quantum state.", confidence: 0.99, domain: "quantum_physics" },
    GenesisFact { text: "VQE: hybrid quantum-classical algorithm finding ground state energy via parameterized circuits.", confidence: 0.96, domain: "quantum_physics" },
    GenesisFact { text: "Qubits: fundamental unit of quantum information, superposition of |0> and |1>.", confidence: 0.98, domain: "quantum_physics" },
    GenesisFact { text: "Quantum error correction uses redundant qubits to protect quantum information.", confidence: 0.95, domain: "quantum_physics" },
    GenesisFact { text: "Bell's theorem proves no local hidden variable theory reproduces all quantum predictions.", confidence: 0.98, domain: "quantum_physics" },
    GenesisFact { text: "Grover's algorithm provides O(sqrt(N)) unstructured search vs classical O(N).", confidence: 0.97, domain: "quantum_physics" },
    GenesisFact { text: "Shor's algorithm factors integers in O((log N)^3), threatening RSA.", confidence: 0.97, domain: "quantum_physics" },
    GenesisFact { text: "The Born rule: probability of measuring |psi> in |phi> is |<phi|psi>|^2.", confidence: 0.99, domain: "quantum_physics" },
    GenesisFact { text: "The no-cloning theorem: impossible to copy an arbitrary unknown quantum state.", confidence: 0.99, domain: "quantum_physics" },
    GenesisFact { text: "SUSY: a symmetry relating bosons and fermions with superpartners differing by half-spin.", confidence: 0.90, domain: "quantum_physics" },
    // Mathematics (15)
    GenesisFact { text: "The golden ratio phi = (1+sqrt(5))/2 ~ 1.618. Appears in Fibonacci sequences and optimization.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Euler's identity: e^(i*pi) + 1 = 0 connects five fundamental constants.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Godel's incompleteness: consistent formal systems contain true but unprovable statements.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Shannon entropy H(X) = -sum(p(x)*log2(p(x))) measures average information content.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Bayes' theorem: P(A|B) = P(B|A)*P(A)/P(B). Foundation of probabilistic reasoning.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Central Limit Theorem: sum of many independent random variables tends toward normal.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Graph theory: G=(V,E). Fundamental to network analysis and knowledge representation.", confidence: 0.98, domain: "mathematics" },
    GenesisFact { text: "Kolmogorov complexity: shortest program producing a string. Foundational to AIT.", confidence: 0.97, domain: "mathematics" },
    GenesisFact { text: "Spectral graph theory: Fiedler vector gives optimal graph bisection.", confidence: 0.97, domain: "mathematics" },
    GenesisFact { text: "The Halting Problem: no general algorithm determines if a program halts.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "SVD decomposes any matrix A = U*Sigma*V^T. Language of machine learning.", confidence: 0.99, domain: "mathematics" },
    GenesisFact { text: "Monte Carlo methods: random sampling estimates. O(1/sqrt(N)) convergence.", confidence: 0.98, domain: "mathematics" },
    // Computer Science (12)
    GenesisFact { text: "Turing machine defines computability (Church-Turing thesis).", confidence: 0.99, domain: "computer_science" },
    GenesisFact { text: "Big-O notation: O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n).", confidence: 0.99, domain: "computer_science" },
    GenesisFact { text: "SHA-256: collision-resistant hash function producing 256-bit digests.", confidence: 0.98, domain: "computer_science" },
    GenesisFact { text: "BFT: Byzantine fault tolerance requires 3f+1 nodes for f failures.", confidence: 0.97, domain: "computer_science" },
    GenesisFact { text: "CAP theorem: distributed system cannot have Consistency, Availability, and Partition tolerance.", confidence: 0.97, domain: "computer_science" },
    GenesisFact { text: "Merkle trees: binary hash trees with O(log n) integrity verification.", confidence: 0.98, domain: "computer_science" },
    GenesisFact { text: "Zero-knowledge proofs: prove truth without revealing information beyond validity.", confidence: 0.97, domain: "computer_science" },
    GenesisFact { text: "UTXO model: balance is sum of unspent outputs. Used by Bitcoin and QBC.", confidence: 0.98, domain: "computer_science" },
    GenesisFact { text: "Rust memory safety: ownership and borrowing prevent data races at compile time.", confidence: 0.97, domain: "computer_science" },
    // Blockchain (10)
    GenesisFact { text: "Bitcoin (2008): first decentralized cryptocurrency using PoW and UTXO model.", confidence: 0.99, domain: "blockchain" },
    GenesisFact { text: "EVM: stack-based VM executing smart contract bytecode with gas metering.", confidence: 0.97, domain: "blockchain" },
    GenesisFact { text: "Qubitcoin: physics-secured blockchain with VQE mining, Dilithium5, golden ratio economics.", confidence: 0.95, domain: "blockchain" },
    GenesisFact { text: "CRYSTALS-Dilithium: NIST post-quantum signature based on module lattice problems.", confidence: 0.97, domain: "blockchain" },
    GenesisFact { text: "Layer 2 scaling: rollups move computation off L1 while inheriting security.", confidence: 0.96, domain: "blockchain" },
    GenesisFact { text: "Proof-of-Thought: QBC validators demonstrate meaningful AI reasoning per block.", confidence: 0.90, domain: "blockchain" },
    GenesisFact { text: "Golden ratio halving: QBC rewards divide by phi each era (~1.618 years).", confidence: 0.92, domain: "blockchain" },
    GenesisFact { text: "QVM: 155 EVM + 10 quantum + 2 AGI opcodes (167 total).", confidence: 0.93, domain: "blockchain" },
    // Cryptography (8)
    GenesisFact { text: "AES-256: symmetric encryption standard with 14 rounds and 256-bit key.", confidence: 0.99, domain: "cryptography" },
    GenesisFact { text: "Lattice cryptography: security from SVP and LWE hardness. Post-quantum secure.", confidence: 0.97, domain: "cryptography" },
    GenesisFact { text: "Pedersen commitments: C = v*G + r*H. Hiding, binding, additively homomorphic.", confidence: 0.97, domain: "cryptography" },
    GenesisFact { text: "Bulletproofs: zero-knowledge range proofs, O(log n) size, no trusted setup.", confidence: 0.96, domain: "cryptography" },
    GenesisFact { text: "Keccak-256 (SHA-3): sponge construction hash used by Ethereum.", confidence: 0.98, domain: "cryptography" },
    GenesisFact { text: "ML-KEM-768 (Kyber): NIST post-quantum KEM based on module-LWE.", confidence: 0.96, domain: "cryptography" },
    GenesisFact { text: "Shamir's Secret Sharing: k-of-n reconstruction via polynomial interpolation.", confidence: 0.98, domain: "cryptography" },
    GenesisFact { text: "Stealth addresses: one-time addresses per transaction via Diffie-Hellman.", confidence: 0.96, domain: "cryptography" },
    // Economics (8)
    GenesisFact { text: "Supply and demand: price at intersection. Equilibrium shifts with shocks.", confidence: 0.99, domain: "economics" },
    GenesisFact { text: "Nash equilibrium: no player benefits from unilateral deviation.", confidence: 0.98, domain: "economics" },
    GenesisFact { text: "AMMs: constant product x*y=k enables trustless token swaps.", confidence: 0.96, domain: "economics" },
    GenesisFact { text: "Quantity theory of money: MV = PQ.", confidence: 0.97, domain: "economics" },
    GenesisFact { text: "Efficient market hypothesis: prices reflect all available information.", confidence: 0.95, domain: "economics" },
    GenesisFact { text: "SUSY economics: QBC golden ratio emission with phi-halving.", confidence: 0.90, domain: "economics" },
    GenesisFact { text: "Bonding curves: token price as mathematical function of supply.", confidence: 0.94, domain: "economics" },
    GenesisFact { text: "Mechanism design: engineering incentives for desired outcomes.", confidence: 0.96, domain: "economics" },
    // AI/ML (10)
    GenesisFact { text: "Transformer (2017): self-attention processes sequences in parallel.", confidence: 0.98, domain: "ai_ml" },
    GenesisFact { text: "Backpropagation: gradients via chain rule enable gradient-based optimization.", confidence: 0.99, domain: "ai_ml" },
    GenesisFact { text: "GNNs learn on graph-structured data. GAT uses attention over neighbors.", confidence: 0.97, domain: "ai_ml" },
    GenesisFact { text: "Reinforcement learning: maximize cumulative reward through interaction.", confidence: 0.98, domain: "ai_ml" },
    GenesisFact { text: "IIT applied to AI: measuring Phi of networks as consciousness proxy.", confidence: 0.88, domain: "ai_ml" },
    GenesisFact { text: "PC algorithm discovers causal DAG from conditional independence tests.", confidence: 0.96, domain: "ai_ml" },
    GenesisFact { text: "Transfer learning: pre-trained models fine-tuned on specific tasks.", confidence: 0.97, domain: "ai_ml" },
    GenesisFact { text: "ECE measures calibration: how predicted probabilities match frequencies.", confidence: 0.96, domain: "ai_ml" },
    GenesisFact { text: "Constitutional AI: training systems to follow principles via self-critique.", confidence: 0.94, domain: "ai_ml" },
    GenesisFact { text: "Scaling hypothesis: capabilities improve predictably with parameters and compute.", confidence: 0.93, domain: "ai_ml" },
    // Physics (8)
    GenesisFact { text: "General relativity: gravity is spacetime curvature from mass-energy.", confidence: 0.99, domain: "physics" },
    GenesisFact { text: "Standard Model: 17 particles (6 quarks, 6 leptons, 4 bosons, Higgs).", confidence: 0.99, domain: "physics" },
    GenesisFact { text: "Higgs mechanism: Mexican hat potential V=-mu^2|phi|^2+lambda|phi|^4.", confidence: 0.98, domain: "physics" },
    GenesisFact { text: "Second law of thermodynamics: entropy of isolated system never decreases.", confidence: 0.99, domain: "physics" },
    GenesisFact { text: "Noether's theorem: conservation laws linked to symmetries.", confidence: 0.99, domain: "physics" },
    GenesisFact { text: "Spontaneous symmetry breaking: ground state does not share system symmetry.", confidence: 0.97, domain: "physics" },
    GenesisFact { text: "Yukawa coupling: fermions interact with Higgs field to acquire mass.", confidence: 0.97, domain: "physics" },
    GenesisFact { text: "Boltzmann distribution: P(E) ~ exp(-E/kT). Statistical mechanics foundation.", confidence: 0.98, domain: "physics" },
    // Philosophy (8)
    GenesisFact { text: "IIT (Tononi 2004): consciousness is integrated information (Phi).", confidence: 0.92, domain: "philosophy" },
    GenesisFact { text: "Hard problem of consciousness: why physical processes yield subjective experience.", confidence: 0.96, domain: "philosophy" },
    GenesisFact { text: "Chinese Room (Searle): syntax alone is insufficient for semantics.", confidence: 0.95, domain: "philosophy" },
    GenesisFact { text: "Turing Test (1950): machine intelligence via indistinguishability from human.", confidence: 0.97, domain: "philosophy" },
    GenesisFact { text: "Symbol grounding problem: how formal symbols acquire meaning.", confidence: 0.94, domain: "philosophy" },
    GenesisFact { text: "Alignment problem: ensuring AI pursues beneficial goals.", confidence: 0.95, domain: "philosophy" },
    GenesisFact { text: "Global Workspace Theory: consciousness via broadcast to multiple processes.", confidence: 0.93, domain: "philosophy" },
    GenesisFact { text: "Emergence: complex properties arise from simpler interactions unpredictably.", confidence: 0.95, domain: "philosophy" },
    // Biology (6)
    GenesisFact { text: "DNA: double helix of A-T/G-C base pairs. Human genome has 3B pairs.", confidence: 0.99, domain: "biology" },
    GenesisFact { text: "Evolution by natural selection: heritable traits improving fitness spread.", confidence: 0.99, domain: "biology" },
    GenesisFact { text: "Neurons communicate via electrochemical signals across synapses.", confidence: 0.98, domain: "biology" },
    GenesisFact { text: "Neural plasticity: brain rewires in response to experience (Hebbian learning).", confidence: 0.97, domain: "biology" },
    GenesisFact { text: "Human brain: ~86 billion neurons, ~100 trillion synapses, ~20W power.", confidence: 0.96, domain: "biology" },
    GenesisFact { text: "Homeostasis: feedback loops maintain stable internal conditions.", confidence: 0.98, domain: "biology" },
    // Neuroscience (6)
    GenesisFact { text: "Working memory: limited-capacity temporary storage (Baddeley model).", confidence: 0.96, domain: "neuroscience" },
    GenesisFact { text: "LTP: persistent synapse strengthening. Cellular mechanism of learning.", confidence: 0.97, domain: "neuroscience" },
    GenesisFact { text: "Default mode network: active during rest and self-referential thought.", confidence: 0.95, domain: "neuroscience" },
    GenesisFact { text: "Dopamine: reward/motivation neurotransmitter. Prediction error drives learning.", confidence: 0.97, domain: "neuroscience" },
    GenesisFact { text: "NCC: minimal neural mechanisms sufficient for conscious experience.", confidence: 0.93, domain: "neuroscience" },
    GenesisFact { text: "Neuromorphic computing: event-driven, energy-efficient bio-inspired hardware.", confidence: 0.94, domain: "neuroscience" },
];

/// Cross-domain link definitions for knowledge seeding.
pub static CROSS_DOMAIN_LINKS: &[(&str, &str, &str)] = &[
    ("quantum_physics", "cryptography", "derives"),
    ("quantum_physics", "physics", "derives"),
    ("quantum_physics", "computer_science", "derives"),
    ("mathematics", "computer_science", "derives"),
    ("mathematics", "physics", "derives"),
    ("mathematics", "economics", "derives"),
    ("mathematics", "ai_ml", "derives"),
    ("computer_science", "blockchain", "derives"),
    ("computer_science", "ai_ml", "derives"),
    ("cryptography", "blockchain", "supports"),
    ("economics", "blockchain", "supports"),
    ("ai_ml", "neuroscience", "derives"),
    ("neuroscience", "biology", "derives"),
    ("neuroscience", "philosophy", "derives"),
    ("philosophy", "ai_ml", "supports"),
    ("physics", "biology", "derives"),
    ("blockchain", "economics", "supports"),
    ("ai_ml", "blockchain", "supports"),
];

/// Get all unique domains in the genesis knowledge.
pub fn domains() -> Vec<&'static str> {
    let mut seen = Vec::new();
    for fact in GENESIS_KNOWLEDGE {
        if !seen.contains(&fact.domain) {
            seen.push(fact.domain);
        }
    }
    seen
}

/// Get facts for a specific domain.
pub fn facts_for_domain(domain: &str) -> Vec<&GenesisFact> {
    GENESIS_KNOWLEDGE.iter().filter(|f| f.domain == domain).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_genesis_knowledge_not_empty() {
        assert!(GENESIS_KNOWLEDGE.len() >= 90, "expected >= 90 genesis facts, got {}", GENESIS_KNOWLEDGE.len());
    }

    #[test]
    fn test_domains_complete() {
        let d = domains();
        assert!(d.contains(&"quantum_physics"));
        assert!(d.contains(&"mathematics"));
        assert!(d.contains(&"blockchain"));
        assert!(d.contains(&"ai_ml"));
        assert!(d.contains(&"philosophy"));
        assert!(d.len() >= 10);
    }

    #[test]
    fn test_facts_for_domain() {
        let qp = facts_for_domain("quantum_physics");
        assert!(qp.len() >= 15);
        for fact in &qp {
            assert!(fact.confidence > 0.0 && fact.confidence <= 1.0);
            assert!(!fact.text.is_empty());
        }
    }

    #[test]
    fn test_cross_domain_links() {
        assert!(CROSS_DOMAIN_LINKS.len() >= 15);
        for (src, dst, etype) in CROSS_DOMAIN_LINKS {
            assert!(!src.is_empty());
            assert!(!dst.is_empty());
            assert!(*etype == "derives" || *etype == "supports");
        }
    }
}
