//! Domain keyword mapping and classification for knowledge nodes.

use std::collections::{HashMap, HashSet};

/// Domain keyword sets for auto-classification of knowledge nodes.
pub fn domain_keywords() -> HashMap<&'static str, HashSet<&'static str>> {
    let mut m: HashMap<&str, HashSet<&str>> = HashMap::new();

    m.insert(
        "quantum_physics",
        [
            "qubit",
            "quantum",
            "superposition",
            "entanglement",
            "decoherence",
            "hamiltonian",
            "vqe",
            "qiskit",
            "photon",
            "wave",
            "particle",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "mathematics",
        [
            "theorem",
            "proof",
            "algebra",
            "topology",
            "geometry",
            "calculus",
            "prime",
            "fibonacci",
            "equation",
            "integral",
            "matrix",
            "vector",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "computer_science",
        [
            "algorithm",
            "compiler",
            "database",
            "hash",
            "binary",
            "complexity",
            "turing",
            "sorting",
            "graph_theory",
            "recursion",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "blockchain",
        [
            "block",
            "transaction",
            "consensus",
            "mining",
            "utxo",
            "merkle",
            "ledger",
            "token",
            "smart_contract",
            "defi",
            "bridge",
            "staking",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "cryptography",
        [
            "encryption",
            "signature",
            "dilithium",
            "lattice",
            "zero_knowledge",
            "zkp",
            "aes",
            "rsa",
            "cipher",
            "post_quantum",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "philosophy",
        [
            "consciousness",
            "qualia",
            "epistemology",
            "ethics",
            "ontology",
            "kabbalah",
            "sephirot",
            "phenomenology",
            "mind",
            "metaphysics",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "biology",
        [
            "neuron", "dna", "gene", "evolution", "cell", "protein", "ecology", "organism",
            "neural", "brain", "synapse",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "physics",
        [
            "relativity",
            "gravity",
            "thermodynamics",
            "entropy",
            "energy",
            "electromagnetism",
            "nuclear",
            "optics",
            "cosmology",
            "dark_matter",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "economics",
        [
            "market",
            "inflation",
            "monetary",
            "gdp",
            "trade",
            "supply_demand",
            "fiscal",
            "currency",
            "game_theory",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "ai_ml",
        [
            "transformer",
            "neural_network",
            "reinforcement",
            "gradient",
            "backpropagation",
            "llm",
            "attention",
            "embedding",
            "training",
            "inference",
        ]
        .into_iter()
        .collect(),
    );

    m
}

/// Classify a knowledge node's domain from its content.
///
/// Scans all text values in the content dict against keyword sets.
/// Returns the best-matching domain or "general" if no strong match.
pub fn classify_domain(content: &HashMap<String, String>) -> String {
    let text: String = content
        .values()
        .map(|v| v.to_lowercase())
        .collect::<Vec<_>>()
        .join(" ");
    let text = text.replace('-', "_").replace('.', " ");
    let words: HashSet<&str> = text.split_whitespace().collect();

    let keywords = domain_keywords();
    let mut best_domain = "general";
    let mut best_score: usize = 0;

    for (domain, kw_set) in &keywords {
        let score = words.iter().filter(|w| kw_set.contains(*w)).count();
        if score > best_score {
            best_score = score;
            best_domain = domain;
        }
    }

    best_domain.to_string()
}
