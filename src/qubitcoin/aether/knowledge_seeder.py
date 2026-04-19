"""
Knowledge Seeder — Background LLM learning for Aether Tree

Continuously queries LLMs with domain-spanning master prompts and feeds
responses into the knowledge graph via KnowledgeDistiller.  Rate-limit
safe with configurable caps, cooldowns, and adapter fallback.

Usage:
    seeder = KnowledgeSeeder(llm_manager, db_manager)
    seeder.start()   # background daemon thread
    seeder.stop()
    seeder.seed_once("quantum_physics")   # manual / testing
    seeder.get_stats()
"""
import random
import threading
import time
import urllib.parse
import urllib.request
import json as _json
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

# ── Topic list (try expanded module first, fallback to inline) ────────────────
# Used by internet workers to mine grounded factual knowledge without LLM.
try:
    from ._seeder_topics import TOPICS_BY_DOMAIN as _EXPANDED_TOPICS
except ImportError:
    _EXPANDED_TOPICS = None

_WIKI_TOPICS_BY_DOMAIN_INLINE: Dict[str, List[str]] = {
    "quantum_physics": [
        "Quantum entanglement", "Superposition principle", "Wave function",
        "Quantum decoherence", "Bell's theorem", "Quantum tunnelling",
        "Schrödinger equation", "Quantum field theory", "Planck constant",
        "Heisenberg uncertainty principle", "Quantum computing",
        "Quantum teleportation", "Bose–Einstein condensate",
        "Quantum chromodynamics", "Quantum electrodynamics",
        "Pauli exclusion principle", "Dirac equation",
        "Feynman diagram", "Path integral formulation",
        "Density matrix", "Quantum state", "Hilbert space",
        "Spin (physics)", "Quantum harmonic oscillator",
        "Quantum key distribution", "Quantum error correction",
        "Topological quantum computer", "Majorana fermion",
        "Quantum supremacy", "Variational quantum eigensolver",
        "Quantum annealing", "Adiabatic quantum computation",
        "Quantum walk", "Grover's algorithm", "Shor's algorithm",
        "No-cloning theorem", "Quantum Zeno effect",
        "EPR paradox", "Many-worlds interpretation",
        "Copenhagen interpretation", "Pilot wave theory",
        "Wigner's friend", "Delayed-choice quantum eraser",
        "Quantum thermodynamics", "Quantum biology",
        "Casimir effect", "Lamb shift", "Vacuum state",
        "Squeezed coherent state", "Quantum noise",
    ],
    "ai_machine_learning": [
        "Transformer (deep learning)", "Reinforcement learning",
        "Neural network", "Large language model", "Backpropagation",
        "Attention mechanism", "Convolutional neural network",
        "Generative adversarial network", "Knowledge graph",
        "Artificial general intelligence", "Recurrent neural network",
        "Long short-term memory", "Graph neural network",
        "Variational autoencoder", "Diffusion model",
        "Self-supervised learning", "Transfer learning",
        "Meta-learning (computer science)", "Few-shot learning",
        "Federated learning", "Neural architecture search",
        "Mixture of experts", "Reward shaping",
        "Proximal policy optimization", "Monte Carlo tree search",
        "AlphaGo", "GPT-4", "BERT (language model)",
        "Word2vec", "Embedding", "Tokenization (data security)",
        "Perceptron", "Activation function", "Batch normalization",
        "Dropout (neural networks)", "Gradient descent",
        "Stochastic gradient descent", "Adam (optimizer)",
        "Overfitting", "Cross-validation (statistics)",
        "Precision and recall", "F-score", "ROC curve",
        "Decision tree learning", "Random forest",
        "Support-vector machine", "K-nearest neighbors algorithm",
        "Principal component analysis", "Dimensionality reduction",
        "Autoencoder", "Boltzmann machine",
    ],
    "mathematics": [
        "Gödel's incompleteness theorems", "Riemann hypothesis",
        "Topology", "Category theory", "Information theory",
        "Fourier analysis", "Prime number", "Golden ratio",
        "Graph theory", "Bayesian inference", "Linear algebra",
        "Eigenvalues and eigenvectors", "Matrix (mathematics)",
        "Tensor", "Differential equation", "Partial differential equation",
        "Calculus", "Real analysis", "Complex analysis",
        "Abstract algebra", "Group theory", "Ring (mathematics)",
        "Field (mathematics)", "Vector space", "Metric space",
        "Banach space", "Measure (mathematics)", "Lebesgue measure",
        "Probability theory", "Stochastic process",
        "Markov chain", "Martingale (probability theory)",
        "Random variable", "Central limit theorem",
        "Law of large numbers", "Monte Carlo method",
        "Numerical analysis", "Finite element method",
        "Optimization (mathematics)", "Convex optimization",
        "Lagrange multiplier", "Variational principle",
        "Functional analysis", "Operator theory",
        "Spectral theory", "Fourier transform",
        "Laplace transform", "Wavelet", "Set theory",
        "Zermelo–Fraenkel set theory", "Continuum hypothesis",
    ],
    "philosophy_of_mind": [
        "Consciousness", "Integrated information theory",
        "Hard problem of consciousness", "Qualia",
        "Functionalism (philosophy of mind)", "Emergentism",
        "Global workspace theory", "Embodied cognition",
        "Theory of mind", "Philosophical zombie",
        "Chinese room", "Turing test", "Mary's room",
        "Epiphenomenalism", "Panpsychism", "Dualism (philosophy of mind)",
        "Identity theory of mind", "Eliminative materialism",
        "Multiple realizability", "Intentionality",
        "Mental representation", "Propositional attitude",
        "Free will", "Determinism", "Compatibilism",
        "Philosophy of perception", "Phenomenology (philosophy)",
        "Edmund Husserl", "Martin Heidegger",
        "Maurice Merleau-Ponty", "Daniel Dennett",
        "David Chalmers", "John Searle", "Jerry Fodor",
        "Cognitive science", "Computational theory of mind",
        "Connectionism", "Symbol grounding problem",
        "Binding problem", "Neural correlates of consciousness",
        "Access consciousness", "Higher-order theories of consciousness",
        "Orchestrated objective reduction", "Attention",
        "Blindsight", "Split-brain", "Thought experiment",
        "Personal identity", "Self-awareness", "Sentience",
        "Sapience", "Artificial consciousness",
    ],
    "neuroscience": [
        "Neuroplasticity", "Default mode network", "Long-term potentiation",
        "Cerebrospinal fluid", "Hippocampus", "Prefrontal cortex",
        "Synaptic pruning", "Mirror neuron", "Neurogenesis",
        "Brain–computer interface", "Neurotransmitter",
        "Dopamine", "Serotonin", "GABA", "Glutamate (neurotransmitter)",
        "Action potential", "Synapse", "Axon", "Dendrite",
        "Glial cell", "Astrocyte", "Myelin",
        "Cerebral cortex", "Amygdala", "Thalamus",
        "Cerebellum", "Basal ganglia", "Broca's area",
        "Wernicke's area", "Connectome", "Diffusion MRI",
        "Functional magnetic resonance imaging",
        "Electroencephalography", "Magnetoencephalography",
        "Optogenetics", "Cortical column",
        "Neural oscillation", "Gamma wave", "Theta wave",
        "Sleep", "Rapid eye movement sleep", "Memory consolidation",
        "Working memory", "Episodic memory", "Semantic memory",
        "Procedural memory", "Hebbian theory",
        "Spike-timing-dependent plasticity", "Neural coding",
        "Population coding", "Place cell", "Grid cell",
    ],
    "physics_general": [
        "Standard Model", "General relativity", "Quantum chromodynamics",
        "Dark matter", "Dark energy", "String theory",
        "Supersymmetry", "Higgs boson", "Black hole", "Entropy",
        "Special relativity", "Spacetime", "Lorentz transformation",
        "Gravitational wave", "Neutron star", "Pulsar",
        "White dwarf", "Supernova", "Cosmic microwave background",
        "Big Bang", "Cosmic inflation", "Hubble's law",
        "Redshift", "Olbers's paradox", "Hawking radiation",
        "Black hole thermodynamics", "Bekenstein–Hawking entropy",
        "Holographic principle", "AdS/CFT correspondence",
        "Gauge theory", "Yang–Mills theory", "Quantum gravity",
        "Loop quantum gravity", "Twistor theory",
        "Kaluza–Klein theory", "Grand Unified Theory",
        "CP violation", "Neutrino oscillation", "Lepton",
        "Quark", "Gluon", "W and Z bosons", "Photon",
        "Fermion", "Boson", "Baryogenesis", "Antimatter",
        "Nuclear physics", "Nuclear fusion", "Nuclear fission",
        "Plasma (physics)", "Condensed matter physics",
    ],
    "cryptography": [
        "Elliptic-curve cryptography", "Zero-knowledge proof",
        "Lattice-based cryptography", "Hash function",
        "Public-key cryptography", "Merkle tree", "Byzantine fault tolerance",
        "Post-quantum cryptography", "Homomorphic encryption", "Dilithium (cryptography)",
        "RSA (cryptosystem)", "Advanced Encryption Standard",
        "SHA-2", "SHA-3", "Keccak (hash function)",
        "Digital signature", "Certificate authority",
        "Transport Layer Security", "Diffie–Hellman key exchange",
        "Elliptic-curve Diffie–Hellman", "Key derivation function",
        "Password hashing", "Bcrypt", "Argon2",
        "Block cipher", "Stream cipher", "One-time pad",
        "Cryptographic nonce", "Initialization vector",
        "Authenticated encryption", "Message authentication code",
        "HMAC", "Commitment scheme", "Oblivious transfer",
        "Secure multi-party computation", "Secret sharing",
        "Shamir's secret sharing", "Threshold cryptosystem",
        "Ring signature", "Group signature", "Blind signature",
        "Pedersen commitment", "Bulletproofs",
        "ZK-SNARK", "ZK-STARK", "Verkle tree",
        "Accumulator (cryptography)", "Verifiable random function",
        "Verifiable delay function", "Randomness extractor",
        "Entropy (computing)", "Side-channel attack",
    ],
    "blockchain_fundamentals": [
        "Blockchain", "Bitcoin", "Ethereum", "Smart contract",
        "Proof of work", "Decentralized finance",
        "Unspent transaction output", "Consensus mechanism",
        "Cross-chain interoperability", "Layer 2 blockchain solution",
        "Proof of stake", "Delegated proof of stake",
        "Bitcoin network", "Lightning Network",
        "Ethereum 2.0", "Solidity (programming language)",
        "Decentralized application", "Decentralized autonomous organization",
        "Non-fungible token", "ERC-20", "ERC-721",
        "Automated market maker", "Liquidity pool",
        "Yield farming", "Flash loan", "Reentrancy attack",
        "51% attack", "Sybil attack", "Front running",
        "Maximal extractable value", "Gas (Ethereum)",
        "Merkle Patricia trie", "State channel",
        "Plasma (blockchain)", "Optimistic rollup", "ZK-rollup",
        "Cosmos (blockchain)", "Polkadot (blockchain)",
        "Avalanche (blockchain platform)", "Solana",
        "Cardano (blockchain platform)", "Polygon (blockchain)",
        "Chainlink", "The Graph (blockchain)",
        "Aave", "Uniswap", "MakerDAO", "Compound (finance)",
        "Stablecoin", "Central bank digital currency",
    ],
    "complexity_science": [
        "Emergence", "Complex system", "Self-organization",
        "Chaos theory", "Cellular automaton", "Phase transition",
        "Attractor", "Feedback", "Scale-free network", "Swarm intelligence",
        "Butterfly effect", "Lorenz system", "Fractal",
        "Mandelbrot set", "Power law", "Zipf's law",
        "Percolation theory", "Criticality (physics)",
        "Self-organized criticality", "Sandpile model",
        "Agent-based model", "Cellular automaton",
        "Game of Life", "Wolfram's classification",
        "Artificial life", "Autopoiesis", "Dissipative system",
        "Bifurcation theory", "Lyapunov exponent",
        "Strange attractor", "Ergodic theory",
        "Dynamical system", "Nonlinear system",
        "Predator–prey equations", "Logistic map",
        "Turing pattern", "Reaction–diffusion system",
        "Small-world network", "Preferential attachment",
        "Network science", "Community structure",
        "Robustness of complex networks", "Cascading failure",
        "Resilience (network)", "Multi-agent system",
        "Ant colony optimization", "Genetic algorithm",
        "Particle swarm optimization", "Simulated annealing",
    ],
    "information_theory": [
        "Shannon entropy", "Channel capacity", "Kolmogorov complexity",
        "Data compression", "Mutual information", "Entropy (information theory)",
        "Error correction code", "Algorithmic information theory",
        "Minimum description length", "Coding theory",
        "Huffman coding", "Arithmetic coding", "Lempel–Ziv",
        "Reed–Solomon error correction", "Turbo code", "LDPC code",
        "Source coding theorem", "Noisy-channel coding theorem",
        "Rate–distortion theory", "Differential entropy",
        "Conditional entropy", "Joint entropy",
        "Kullback–Leibler divergence", "Cross-entropy",
        "Fisher information", "Cramér–Rao bound",
        "Maximum entropy probability distribution",
        "Principle of maximum entropy", "Jaynes–Cummings model",
        "Quantum information science", "Quantum entropy",
        "Von Neumann entropy", "Holevo's theorem",
        "Quantum channel", "Quantum error correction",
        "No-communication theorem", "Quantum mutual information",
        "Rényi entropy", "Tsallis entropy",
        "Transfer entropy", "Granger causality",
        "Directed information", "Causal entropy",
        "Information bottleneck method", "Sufficient statistic",
        "Minimal sufficient statistic", "Exponential family",
        "Maximum likelihood estimation", "Expectation-maximization algorithm",
    ],
    # ── NEW DOMAINS for massive coverage ──────────────────────────────────
    "computer_science": [
        "Algorithm", "Data structure", "Computational complexity theory",
        "P versus NP problem", "Turing machine", "Lambda calculus",
        "Automata theory", "Compiler", "Operating system",
        "Distributed computing", "Parallel computing", "Cloud computing",
        "Virtualization", "Container (computing)", "Kubernetes",
        "Microservices", "REST", "GraphQL", "WebSocket",
        "Database", "Relational database", "NoSQL", "SQL",
        "B-tree", "Hash table", "Red–black tree",
        "Binary search tree", "Heap (data structure)",
        "Dijkstra's algorithm", "A* search algorithm",
        "Dynamic programming", "Divide-and-conquer algorithm",
        "Sorting algorithm", "Quicksort", "Merge sort",
        "MapReduce", "Apache Spark", "Apache Kafka",
        "Consensus (computer science)", "Paxos (computer science)",
        "Raft (algorithm)", "CAP theorem", "ACID",
        "Two-phase commit protocol", "Eventual consistency",
        "Conflict-free replicated data type", "Vector clock",
        "Bloom filter", "Count–min sketch", "HyperLogLog",
        "Consistent hashing", "Load balancing (computing)",
    ],
    "biology_evolution": [
        "Evolution", "Natural selection", "Genetic drift",
        "Speciation", "Phylogenetics", "Molecular evolution",
        "DNA", "RNA", "Protein", "Gene expression",
        "Epigenetics", "CRISPR gene editing", "Genome",
        "Proteome", "Metabolome", "Systems biology",
        "Synthetic biology", "Bioinformatics",
        "Molecular biology", "Cell (biology)", "Mitosis",
        "Meiosis", "Stem cell", "Cell signaling",
        "Apoptosis", "Telomere", "Chromosome",
        "Mutation", "Horizontal gene transfer",
        "Endosymbiont", "Mitochondrion", "Chloroplast",
        "Photosynthesis", "Cellular respiration",
        "Enzyme", "Catalysis", "Protein folding",
        "Prion", "Virus", "Bacteriophage",
        "Antibiotic resistance", "Microbiome",
        "Ecosystem", "Biodiversity", "Trophic level",
        "Food web", "Symbiosis", "Coevolution",
        "Convergent evolution", "Adaptive radiation",
    ],
    "economics_game_theory": [
        "Game theory", "Nash equilibrium", "Prisoner's dilemma",
        "Mechanism design", "Auction theory", "Public goods game",
        "Tragedy of the commons", "Free-rider problem",
        "Principal–agent problem", "Moral hazard",
        "Adverse selection", "Signaling (economics)",
        "Market failure", "Externality", "Pareto efficiency",
        "General equilibrium theory", "Arrow's impossibility theorem",
        "Rational choice theory", "Bounded rationality",
        "Prospect theory", "Behavioral economics",
        "Nudge theory", "Loss aversion", "Endowment effect",
        "Keynesian economics", "Monetarism", "Austrian School",
        "Modern monetary theory", "Inflation", "Deflation",
        "Central bank", "Monetary policy", "Fiscal policy",
        "Supply and demand", "Market equilibrium",
        "Oligopoly", "Monopoly", "Perfect competition",
        "Price elasticity of demand", "Consumer surplus",
        "Comparative advantage", "International trade",
        "Exchange rate", "Balance of payments",
        "Gini coefficient", "Human Development Index",
        "Gross domestic product", "Purchasing power parity",
        "Financial market", "Stock market", "Bond market",
    ],
    "philosophy_general": [
        "Epistemology", "Ontology", "Metaphysics", "Logic",
        "Ethics", "Aesthetics", "Philosophy of science",
        "Philosophy of language", "Philosophy of mathematics",
        "Analytic philosophy", "Continental philosophy",
        "Existentialism", "Nihilism", "Absurdism",
        "Pragmatism", "Empiricism", "Rationalism",
        "Idealism", "Materialism", "Realism",
        "Nominalism", "Constructivism (philosophy of mathematics)",
        "Falsifiability", "Thomas Kuhn", "Paradigm shift",
        "Occam's razor", "Logical positivism", "Verificationism",
        "Modal logic", "Possible world", "Counterfactual conditional",
        "Trolley problem", "Utilitarianism", "Deontological ethics",
        "Virtue ethics", "Consequentialism", "Social contract",
        "Justice as Fairness", "Veil of ignorance",
        "Categorical imperative", "Moral relativism",
        "Natural law", "Stoicism", "Epicureanism",
        "Taoism", "Confucianism", "Buddhism",
        "Vedanta", "Zen", "Kabbalah", "Tree of Life (Kabbalah)",
    ],
    "cognitive_science": [
        "Cognitive psychology", "Perception", "Attention",
        "Pattern recognition (psychology)", "Problem solving",
        "Decision-making", "Heuristic", "Cognitive bias",
        "Confirmation bias", "Anchoring effect",
        "Availability heuristic", "Dunning–Kruger effect",
        "Language acquisition", "Noam Chomsky",
        "Universal grammar", "Sapir–Whorf hypothesis",
        "Mental model", "Schema (psychology)",
        "Dual process theory", "System 1 and System 2",
        "Metacognition", "Executive functions",
        "Cognitive load theory", "Chunking (psychology)",
        "Distributed cognition", "Situated cognition",
        "Predictive coding", "Bayesian brain",
        "Active inference", "Free energy principle",
        "Karl Friston", "Embodied cognition",
        "Extended mind thesis", "4E cognition",
        "Mirror neuron system", "Social cognition",
        "Empathy", "Emotion", "Affect (psychology)",
        "Motivation", "Intrinsic motivation",
        "Flow (psychology)", "Peak experience",
        "Altered state of consciousness", "Meditation",
        "Mindfulness", "Hypnosis", "Synesthesia",
        "Creativity", "Divergent thinking", "Insight",
    ],
    "engineering_systems": [
        "Control theory", "Cybernetics", "Systems engineering",
        "Signal processing", "Digital signal processing",
        "Fourier transform", "Kalman filter",
        "PID controller", "State-space representation",
        "Transfer function", "Bode plot", "Nyquist stability criterion",
        "Feedback", "Negative feedback", "Positive feedback",
        "Servo (mechanism)", "Robotics", "Actuator",
        "Sensor", "Internet of things", "Embedded system",
        "Field-programmable gate array", "Application-specific integrated circuit",
        "Von Neumann architecture", "Harvard architecture",
        "RISC", "ARM architecture", "x86",
        "Graphics processing unit", "Tensor Processing Unit",
        "Neuromorphic engineering", "Memristor",
        "Photonics", "Optical fiber", "Quantum dot",
        "Nanotechnology", "Molecular machine",
        "3D printing", "Additive manufacturing",
        "Renewable energy", "Solar cell", "Wind power",
        "Nuclear power", "Fusion power", "Tokamak",
        "Superconductivity", "High-temperature superconductivity",
        "Quantum sensor", "Atomic clock",
        "Global Positioning System", "Satellite navigation",
        "Space elevator", "Dyson sphere",
    ],
}

# Use expanded topics if available (3000+ topics), else use inline (885 topics)
_WIKI_TOPICS_BY_DOMAIN: Dict[str, List[str]] = (
    _EXPANDED_TOPICS if _EXPANDED_TOPICS else _WIKI_TOPICS_BY_DOMAIN_INLINE
)

# ArXiv search terms by domain (maps to ArXiv category codes)
_ARXIV_QUERIES: List[Dict[str, str]] = [
    # ── Quantum physics & computing (30) ──────────────────────────────────
    {"term": "quantum computing entanglement", "cat": "quant-ph"},
    {"term": "quantum error correction surface code", "cat": "quant-ph"},
    {"term": "variational quantum eigensolver molecular", "cat": "quant-ph"},
    {"term": "quantum supremacy advantage", "cat": "quant-ph"},
    {"term": "topological quantum computing", "cat": "quant-ph"},
    {"term": "quantum key distribution security", "cat": "quant-ph"},
    {"term": "quantum machine learning kernel", "cat": "quant-ph"},
    {"term": "quantum simulation many-body", "cat": "quant-ph"},
    {"term": "quantum annealing optimization", "cat": "quant-ph"},
    {"term": "quantum walk algorithm", "cat": "quant-ph"},
    {"term": "quantum channel capacity", "cat": "quant-ph"},
    {"term": "quantum metrology sensing", "cat": "quant-ph"},
    {"term": "boson sampling photonic", "cat": "quant-ph"},
    {"term": "quantum network repeater", "cat": "quant-ph"},
    {"term": "quantum thermodynamics engine", "cat": "quant-ph"},
    {"term": "quantum coherence decoherence", "cat": "quant-ph"},
    {"term": "measurement-based quantum computation", "cat": "quant-ph"},
    {"term": "quantum state tomography", "cat": "quant-ph"},
    {"term": "quantum optimal control", "cat": "quant-ph"},
    {"term": "trapped ion quantum processor", "cat": "quant-ph"},
    {"term": "superconducting qubit architecture", "cat": "quant-ph"},
    {"term": "quantum random number generation", "cat": "quant-ph"},
    {"term": "adiabatic quantum computation", "cat": "quant-ph"},
    {"term": "quantum spin liquid", "cat": "quant-ph"},
    {"term": "quantum entanglement entropy", "cat": "quant-ph"},
    {"term": "quantum information scrambling", "cat": "quant-ph"},
    {"term": "fault-tolerant quantum gate", "cat": "quant-ph"},
    {"term": "quantum chemistry simulation", "cat": "quant-ph"},
    {"term": "Majorana fermion braiding", "cat": "quant-ph"},
    {"term": "quantum dot qubit", "cat": "quant-ph"},
    # ── AI & Machine Learning (50) ────────────────────────────────────────
    {"term": "large language model reasoning", "cat": "cs.AI"},
    {"term": "reinforcement learning planning", "cat": "cs.AI"},
    {"term": "neural network interpretability", "cat": "cs.LG"},
    {"term": "knowledge graph embedding", "cat": "cs.LG"},
    {"term": "graph neural network", "cat": "cs.LG"},
    {"term": "transformer attention mechanism", "cat": "cs.LG"},
    {"term": "diffusion model generative", "cat": "cs.LG"},
    {"term": "meta-learning few-shot", "cat": "cs.LG"},
    {"term": "federated learning privacy", "cat": "cs.LG"},
    {"term": "multi-agent reinforcement learning", "cat": "cs.AI"},
    {"term": "artificial general intelligence", "cat": "cs.AI"},
    {"term": "neuro-symbolic reasoning", "cat": "cs.AI"},
    {"term": "causal representation learning", "cat": "cs.LG"},
    {"term": "self-supervised contrastive learning", "cat": "cs.LG"},
    {"term": "vision transformer image recognition", "cat": "cs.CV"},
    {"term": "object detection YOLO", "cat": "cs.CV"},
    {"term": "3D point cloud deep learning", "cat": "cs.CV"},
    {"term": "neural radiance field NeRF", "cat": "cs.CV"},
    {"term": "text-to-image generation", "cat": "cs.CV"},
    {"term": "natural language inference entailment", "cat": "cs.CL"},
    {"term": "machine translation multilingual", "cat": "cs.CL"},
    {"term": "speech recognition end-to-end", "cat": "cs.CL"},
    {"term": "question answering retrieval augmented", "cat": "cs.CL"},
    {"term": "code generation program synthesis", "cat": "cs.CL"},
    {"term": "continual learning catastrophic forgetting", "cat": "cs.LG"},
    {"term": "neural architecture search AutoML", "cat": "cs.LG"},
    {"term": "Bayesian deep learning uncertainty", "cat": "cs.LG"},
    {"term": "world model planning", "cat": "cs.AI"},
    {"term": "reward shaping alignment", "cat": "cs.AI"},
    {"term": "AI safety alignment RLHF", "cat": "cs.AI"},
    {"term": "mixture of experts scaling", "cat": "cs.LG"},
    {"term": "state space model sequence", "cat": "cs.LG"},
    {"term": "normalizing flow density estimation", "cat": "cs.LG"},
    {"term": "energy-based model contrastive", "cat": "cs.LG"},
    {"term": "robotics manipulation reinforcement", "cat": "cs.RO"},
    {"term": "autonomous driving perception planning", "cat": "cs.RO"},
    {"term": "multi-modal learning vision language", "cat": "cs.CV"},
    {"term": "adversarial robustness attack defense", "cat": "cs.LG"},
    {"term": "pruning quantization efficient inference", "cat": "cs.LG"},
    {"term": "emergent abilities language model", "cat": "cs.CL"},
    {"term": "chain of thought prompting reasoning", "cat": "cs.AI"},
    {"term": "graph transformer molecular property", "cat": "cs.LG"},
    {"term": "equivariant neural network symmetry", "cat": "cs.LG"},
    {"term": "active learning annotation efficient", "cat": "cs.LG"},
    # ── Neuroscience & consciousness (20) ─────────────────────────────────
    {"term": "integrated information theory consciousness", "cat": "q-bio.NC"},
    {"term": "neural correlates consciousness", "cat": "q-bio.NC"},
    {"term": "predictive coding brain", "cat": "q-bio.NC"},
    {"term": "connectome mapping brain", "cat": "q-bio.NC"},
    {"term": "free energy principle active inference", "cat": "q-bio.NC"},
    {"term": "global workspace theory attention", "cat": "q-bio.NC"},
    {"term": "synaptic plasticity learning memory", "cat": "q-bio.NC"},
    {"term": "neural oscillation gamma synchrony", "cat": "q-bio.NC"},
    {"term": "computational neuroscience spiking", "cat": "q-bio.NC"},
    {"term": "brain-computer interface neural decoding", "cat": "q-bio.NC"},
    {"term": "prefrontal cortex decision making", "cat": "q-bio.NC"},
    {"term": "hippocampal memory replay consolidation", "cat": "q-bio.NC"},
    {"term": "cortical hierarchy visual processing", "cat": "q-bio.NC"},
    {"term": "neuromodulation dopamine reward", "cat": "q-bio.NC"},
    {"term": "neuromorphic computing spike-based", "cat": "q-bio.NC"},
    {"term": "default mode network resting state", "cat": "q-bio.NC"},
    {"term": "neural coding population dynamics", "cat": "q-bio.NC"},
    {"term": "thalamus cortex loop sensory", "cat": "q-bio.NC"},
    {"term": "glial cell astrocyte function", "cat": "q-bio.NC"},
    {"term": "optogenetics circuit manipulation", "cat": "q-bio.NC"},
    # ── Cryptography & security (20) ──────────────────────────────────────
    {"term": "blockchain consensus scalability", "cat": "cs.CR"},
    {"term": "zero knowledge proof scalable", "cat": "cs.CR"},
    {"term": "post-quantum cryptography lattice", "cat": "cs.CR"},
    {"term": "homomorphic encryption computation", "cat": "cs.CR"},
    {"term": "secure multi-party computation", "cat": "cs.CR"},
    {"term": "verifiable computation blockchain", "cat": "cs.CR"},
    {"term": "decentralized identity self-sovereign", "cat": "cs.CR"},
    {"term": "zk-SNARK zk-STARK recursive", "cat": "cs.CR"},
    {"term": "threshold signature distributed key", "cat": "cs.CR"},
    {"term": "formal verification smart contract", "cat": "cs.CR"},
    {"term": "MEV flashbot auction mechanism", "cat": "cs.CR"},
    {"term": "layer-2 rollup validity proof", "cat": "cs.CR"},
    {"term": "sharding cross-shard transaction", "cat": "cs.CR"},
    {"term": "DeFi protocol security audit", "cat": "cs.CR"},
    {"term": "consensus BFT byzantine fault", "cat": "cs.DC"},
    {"term": "peer-to-peer network gossip protocol", "cat": "cs.DC"},
    {"term": "oblivious RAM private retrieval", "cat": "cs.CR"},
    {"term": "attribute-based encryption access control", "cat": "cs.CR"},
    {"term": "functional encryption predicate", "cat": "cs.CR"},
    {"term": "quantum-resistant digital signature", "cat": "cs.CR"},
    # ── Mathematics & statistics (25) ─────────────────────────────────────
    {"term": "causal inference discovery", "cat": "stat.ML"},
    {"term": "topological data analysis", "cat": "math.AT"},
    {"term": "information geometry statistical manifold", "cat": "math.ST"},
    {"term": "category theory applied mathematics", "cat": "math.CT"},
    {"term": "spectral graph theory clustering", "cat": "math.SP"},
    {"term": "optimal transport machine learning", "cat": "stat.ML"},
    {"term": "algebraic topology homology cohomology", "cat": "math.AT"},
    {"term": "Riemannian geometry manifold", "cat": "math.DG"},
    {"term": "stochastic differential equation", "cat": "math.PR"},
    {"term": "random matrix theory eigenvalue", "cat": "math.PR"},
    {"term": "combinatorial optimization approximation", "cat": "math.CO"},
    {"term": "number theory prime distribution", "cat": "math.NT"},
    {"term": "functional analysis operator theory", "cat": "math.FA"},
    {"term": "ergodic theory dynamical systems", "cat": "math.DS"},
    {"term": "convex optimization interior point", "cat": "math.OC"},
    {"term": "harmonic analysis wavelet transform", "cat": "math.CA"},
    {"term": "algebraic geometry scheme variety", "cat": "math.AG"},
    {"term": "representation theory group algebra", "cat": "math.RT"},
    {"term": "numerical analysis finite element", "cat": "math.NA"},
    {"term": "graph theory extremal combinatorial", "cat": "math.CO"},
    {"term": "probability martingale stochastic process", "cat": "math.PR"},
    {"term": "logic model theory computability", "cat": "math.LO"},
    {"term": "differential equation dynamical system", "cat": "math.DS"},
    {"term": "measure theory integration", "cat": "math.CA"},
    {"term": "homotopy type theory foundations", "cat": "math.CT"},
    # ── Physics (25) ──────────────────────────────────────────────────────
    {"term": "complex network dynamics emergence", "cat": "nlin.AO"},
    {"term": "self-organized criticality", "cat": "cond-mat.stat-mech"},
    {"term": "information thermodynamics entropy", "cat": "cond-mat.stat-mech"},
    {"term": "string theory landscape swampland", "cat": "hep-th"},
    {"term": "supersymmetry SUSY breaking", "cat": "hep-ph"},
    {"term": "black hole information paradox", "cat": "hep-th"},
    {"term": "holographic principle AdS/CFT", "cat": "hep-th"},
    {"term": "dark matter candidate detection", "cat": "hep-ph"},
    {"term": "neutrino mass oscillation", "cat": "hep-ph"},
    {"term": "gravitational wave detection LIGO", "cat": "gr-qc"},
    {"term": "loop quantum gravity spin foam", "cat": "gr-qc"},
    {"term": "cosmic inflation primordial", "cat": "astro-ph"},
    {"term": "dark energy cosmological constant", "cat": "astro-ph"},
    {"term": "neutron star equation of state", "cat": "astro-ph"},
    {"term": "topological insulator surface state", "cat": "cond-mat.mes-hall"},
    {"term": "high temperature superconductor cuprate", "cat": "cond-mat.supr-con"},
    {"term": "phase transition critical phenomena", "cat": "cond-mat.stat-mech"},
    {"term": "Bose-Einstein condensate ultracold", "cat": "cond-mat.quant-gas"},
    {"term": "spintronics magnetoresistance", "cat": "cond-mat.mtrl-sci"},
    {"term": "metamaterial photonic crystal", "cat": "physics.optics"},
    {"term": "plasma physics fusion confinement", "cat": "physics.plasm-ph"},
    {"term": "turbulence fluid dynamics Navier-Stokes", "cat": "physics.flu-dyn"},
    {"term": "nonlinear dynamics chaos bifurcation", "cat": "nlin.CD"},
    {"term": "lattice gauge theory simulation", "cat": "hep-lat"},
    {"term": "quantum gravity phenomenology", "cat": "gr-qc"},
    # ── Biology & evolution (20) ──────────────────────────────────────────
    {"term": "evolutionary dynamics cooperation", "cat": "q-bio.PE"},
    {"term": "gene regulatory network inference", "cat": "q-bio.MN"},
    {"term": "protein structure prediction", "cat": "q-bio.BM"},
    {"term": "single cell RNA sequencing analysis", "cat": "q-bio.GN"},
    {"term": "CRISPR gene editing guide RNA", "cat": "q-bio.GN"},
    {"term": "protein folding energy landscape", "cat": "q-bio.BM"},
    {"term": "metabolic network flux analysis", "cat": "q-bio.MN"},
    {"term": "phylogenetic inference molecular clock", "cat": "q-bio.PE"},
    {"term": "population genetics selection drift", "cat": "q-bio.PE"},
    {"term": "epigenetics chromatin modification", "cat": "q-bio.GN"},
    {"term": "synthetic biology genetic circuit", "cat": "q-bio.MN"},
    {"term": "immune system adaptive immunity", "cat": "q-bio.CB"},
    {"term": "microbiome metagenomics diversity", "cat": "q-bio.PE"},
    {"term": "developmental biology morphogenesis", "cat": "q-bio.CB"},
    {"term": "ecology food web species interaction", "cat": "q-bio.PE"},
    {"term": "systems biology pathway modeling", "cat": "q-bio.MN"},
    {"term": "bioinformatics sequence alignment", "cat": "q-bio.GN"},
    {"term": "structural biology cryo-EM", "cat": "q-bio.BM"},
    {"term": "evolutionary game theory fitness", "cat": "q-bio.PE"},
    {"term": "drug discovery molecular docking", "cat": "q-bio.BM"},
    # ── Computer Science (20) ────────────────────────────────────────────
    {"term": "distributed consensus Raft Paxos", "cat": "cs.DC"},
    {"term": "database query optimization index", "cat": "cs.DB"},
    {"term": "programming language type system", "cat": "cs.PL"},
    {"term": "compiler optimization LLVM", "cat": "cs.PL"},
    {"term": "operating system kernel scheduling", "cat": "cs.OS"},
    {"term": "parallel computing GPU acceleration", "cat": "cs.DC"},
    {"term": "formal methods verification model checking", "cat": "cs.LO"},
    {"term": "approximation algorithm complexity", "cat": "cs.DS"},
    {"term": "streaming algorithm data sketch", "cat": "cs.DS"},
    {"term": "differential privacy mechanism", "cat": "cs.CR"},
    {"term": "information retrieval search ranking", "cat": "cs.IR"},
    {"term": "software engineering testing verification", "cat": "cs.SE"},
    {"term": "computer architecture memory hierarchy", "cat": "cs.AR"},
    {"term": "network protocol routing optimization", "cat": "cs.NI"},
    {"term": "human-computer interaction interface", "cat": "cs.HC"},
    {"term": "computational geometry algorithm", "cat": "cs.CG"},
    {"term": "automata theory formal language", "cat": "cs.FL"},
    {"term": "game theory algorithmic mechanism", "cat": "cs.GT"},
    {"term": "natural language processing semantic", "cat": "cs.CL"},
    {"term": "computer graphics rendering real-time", "cat": "cs.GR"},
    # ── Economics & game theory (10) ──────────────────────────────────────
    {"term": "mechanism design auction incentive", "cat": "econ.TH"},
    {"term": "behavioral economics bounded rationality", "cat": "econ.TH"},
    {"term": "market microstructure order book", "cat": "q-fin.TR"},
    {"term": "network economics platform market", "cat": "econ.TH"},
    {"term": "cooperative game theory coalition", "cat": "econ.TH"},
    {"term": "stochastic game Markov equilibrium", "cat": "econ.TH"},
    {"term": "matching market stable allocation", "cat": "econ.TH"},
    {"term": "social choice voting theory", "cat": "econ.TH"},
    {"term": "contract theory moral hazard", "cat": "econ.TH"},
    {"term": "financial network systemic risk", "cat": "q-fin.RM"},
]

# ── Domain mapping: seeder domain → KG domain ────────────────────────────────
_DOMAIN_TO_KG: Dict[str, str] = {
    'quantum_physics': 'quantum_physics',
    'ai_machine_learning': 'ai_ml',
    'mathematics': 'mathematics',
    'philosophy_of_mind': 'philosophy',
    'neuroscience': 'neuroscience',
    'physics_general': 'physics',
    'cryptography': 'cryptography',
    'blockchain_fundamentals': 'blockchain',
    'complexity_science': 'philosophy',
    'information_theory': 'mathematics',
    'computer_science': 'computer_science',
    'biology_evolution': 'biology',
    'economics_game_theory': 'economics',
    'philosophy_general': 'philosophy',
    'cognitive_science': 'neuroscience',
    'engineering_systems': 'engineering',
    # New domains from expanded topic list
    'chemistry': 'physics',
    'astronomy_cosmology': 'physics',
    'linguistics': 'philosophy',
    'medicine_health': 'biology',
}

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 50 Master Prompts — organised by domain
# Each entry: {"domain": str, "prompt": str}
# Easy to add / remove / edit — just modify this list.
# ---------------------------------------------------------------------------
MASTER_PROMPTS: List[Dict[str, str]] = [
    # ── Science & Physics (10) ─────────────────────────────────────────────
    {
        "domain": "quantum_physics",
        "prompt": (
            "Explain a fundamental concept in quantum mechanics such as "
            "superposition, entanglement, or decoherence.  Include its "
            "mathematical formulation and a real-world application."
        ),
    },
    {
        "domain": "physics_general",
        "prompt": (
            "Describe an important topic in modern physics — for example "
            "supersymmetry (SUSY), particle physics, or general relativity. "
            "What predictions does it make and how are they tested?"
        ),
    },
    {
        "domain": "quantum_chemistry",
        "prompt": (
            "Explain how the Variational Quantum Eigensolver (VQE) is used "
            "in quantum chemistry for molecular orbital calculations, drug "
            "discovery, or materials design.  Include the ansatz concept."
        ),
    },
    {
        "domain": "materials_science",
        "prompt": (
            "Describe a breakthrough in materials science such as high-"
            "temperature superconductors, topological insulators, or quantum "
            "materials.  Explain the underlying physics."
        ),
    },
    {
        "domain": "cosmology",
        "prompt": (
            "Discuss a major topic in cosmology — dark energy, black hole "
            "thermodynamics, or multiverse theories.  What observational "
            "evidence supports or challenges the theory?"
        ),
    },
    {
        "domain": "thermodynamics",
        "prompt": (
            "Explain the laws of thermodynamics and their implications for "
            "entropy, energy conservation, and heat engines.  Include "
            "connections to information theory."
        ),
    },
    {
        "domain": "optics_waves",
        "prompt": (
            "Describe wave-particle duality and its experimental verification. "
            "How do phenomena like interference, diffraction, and laser "
            "operation demonstrate quantum behaviour?"
        ),
    },
    {
        "domain": "nuclear_physics",
        "prompt": (
            "Explain nuclear fission and fusion, the binding energy curve, "
            "and radioactive decay processes.  What are the prospects for "
            "controlled fusion energy?"
        ),
    },
    {
        "domain": "electromagnetism",
        "prompt": (
            "Describe Maxwell's equations and the unification of electricity "
            "and magnetism.  How does the electromagnetic spectrum underpin "
            "modern technology?"
        ),
    },
    {
        "domain": "string_theory",
        "prompt": (
            "Outline the key ideas of string theory and M-theory — extra "
            "dimensions, branes, and quantum gravity.  What are the main "
            "challenges and open questions?"
        ),
    },
    # ── Mathematics (8) ────────────────────────────────────────────────────
    {
        "domain": "number_theory",
        "prompt": (
            "Discuss an important concept in number theory — prime numbers, "
            "the golden ratio, or Fibonacci sequences.  Explain connections "
            "to cryptography or nature."
        ),
    },
    {
        "domain": "topology",
        "prompt": (
            "Explain a key idea in topology such as manifolds, knot theory, "
            "or topological invariants.  How are these used in physics or "
            "data analysis?"
        ),
    },
    {
        "domain": "algebra",
        "prompt": (
            "Describe the concept of symmetry in mathematics via groups, "
            "rings, and fields.  How does group theory apply to particle "
            "physics and crystallography?"
        ),
    },
    {
        "domain": "analysis",
        "prompt": (
            "Explain a foundational concept in mathematical analysis — "
            "limits, measure theory, or functional analysis.  Include an "
            "application in physics or engineering."
        ),
    },
    {
        "domain": "combinatorics",
        "prompt": (
            "Describe an important topic in combinatorics or graph theory — "
            "Euler paths, network flows, or Ramsey theory.  How are these "
            "applied to real-world optimization?"
        ),
    },
    {
        "domain": "probability_statistics",
        "prompt": (
            "Explain Bayesian inference and how it differs from frequentist "
            "statistics.  Include an example involving probability "
            "distributions and decision-making."
        ),
    },
    {
        "domain": "geometry",
        "prompt": (
            "Discuss non-Euclidean geometry, fractal geometry, or projective "
            "geometry.  How do these extend our understanding of space and "
            "shape?"
        ),
    },
    {
        "domain": "logic_foundations",
        "prompt": (
            "Explain Goedel's incompleteness theorems and their implications "
            "for formal systems, set theory, and the limits of mathematical "
            "provability."
        ),
    },
    # ── Computer Science & AI (8) ──────────────────────────────────────────
    {
        "domain": "cryptography",
        "prompt": (
            "Describe post-quantum cryptography — lattice-based schemes, "
            "zero-knowledge proofs, or hash-based signatures.  Why are they "
            "needed and how do they work?"
        ),
    },
    {
        "domain": "distributed_systems",
        "prompt": (
            "Explain consensus algorithms in distributed systems — Paxos, "
            "Raft, or BFT variants.  How does the CAP theorem constrain "
            "system design?"
        ),
    },
    {
        "domain": "computational_complexity",
        "prompt": (
            "Discuss the P vs NP problem, computational reductions, and "
            "hardness results.  What are the practical implications for "
            "cryptography and optimization?"
        ),
    },
    {
        "domain": "ai_machine_learning",
        "prompt": (
            "Explain a key concept in AI — transformer architectures, "
            "reinforcement learning, or knowledge graphs.  How has it "
            "advanced the state of the art?"
        ),
    },
    {
        "domain": "programming_languages",
        "prompt": (
            "Describe important ideas in programming language theory — type "
            "systems, compilers, or functional vs imperative paradigms.  "
            "How do they affect software reliability?"
        ),
    },
    {
        "domain": "software_architecture",
        "prompt": (
            "Explain design patterns, microservices, or event-driven "
            "architecture.  How do these approaches help scale complex "
            "software systems?"
        ),
    },
    {
        "domain": "algorithms",
        "prompt": (
            "Describe an important algorithm family — graph algorithms, "
            "dynamic programming, or sorting algorithms.  Include time "
            "complexity analysis and practical use cases."
        ),
    },
    {
        "domain": "databases",
        "prompt": (
            "Explain database internals — B-trees, LSM trees, MVCC, or "
            "distributed database architectures.  How do they achieve "
            "consistency and performance?"
        ),
    },
    # ── Blockchain & Crypto (6) ────────────────────────────────────────────
    {
        "domain": "blockchain_fundamentals",
        "prompt": (
            "Explain blockchain fundamentals — the UTXO model, Merkle trees, "
            "and consensus mechanisms.  How do they ensure trustless security?"
        ),
    },
    {
        "domain": "smart_contracts",
        "prompt": (
            "Describe smart contract development in Solidity — formal "
            "verification, common vulnerabilities, and security best "
            "practices."
        ),
    },
    {
        "domain": "defi",
        "prompt": (
            "Explain DeFi concepts — automated market makers, lending "
            "protocols, and yield farming.  What are the risks and "
            "innovations?"
        ),
    },
    {
        "domain": "layer2",
        "prompt": (
            "Describe Layer 2 scaling solutions — rollups (optimistic and "
            "ZK), state channels, and plasma.  How do they inherit L1 "
            "security?"
        ),
    },
    {
        "domain": "tokenomics",
        "prompt": (
            "Explain tokenomics design — emission curves, staking incentives, "
            "governance tokens, and vesting schedules.  What makes a "
            "sustainable token model?"
        ),
    },
    {
        "domain": "cross_chain",
        "prompt": (
            "Describe cross-chain interoperability — bridges, atomic swaps, "
            "and relay chains.  What are the security trade-offs?"
        ),
    },
    # ── Philosophy & Consciousness (6) ─────────────────────────────────────
    {
        "domain": "philosophy_of_mind",
        "prompt": (
            "Discuss Integrated Information Theory (IIT), the hard problem "
            "of consciousness, and the nature of qualia.  Can consciousness "
            "be measured or computed?"
        ),
    },
    {
        "domain": "ethics_ai_safety",
        "prompt": (
            "Explain AI alignment, value loading, and constitutional AI.  "
            "What structural approaches can ensure safe artificial general "
            "intelligence?"
        ),
    },
    {
        "domain": "epistemology",
        "prompt": (
            "Describe theories of knowledge — justified true belief, "
            "scientific method, and falsifiability.  How do these apply to "
            "machine reasoning?"
        ),
    },
    {
        "domain": "kabbalah_sacred_geometry",
        "prompt": (
            "Explain the Kabbalistic Tree of Life and the 10 Sephirot.  How "
            "do the golden ratio and sacred geometry appear in nature and "
            "mathematics?"
        ),
    },
    {
        "domain": "eastern_philosophy",
        "prompt": (
            "Discuss consciousness in Buddhist, Taoist, and Vedantic "
            "philosophy.  How do these traditions conceptualize awareness, "
            "self, and interconnection?"
        ),
    },
    {
        "domain": "philosophy_of_science",
        "prompt": (
            "Explain paradigm shifts, scientific revolutions, and the concept "
            "of emergence.  How do new theories replace old ones?"
        ),
    },
    # ── Biology & Nature (5) ───────────────────────────────────────────────
    {
        "domain": "neuroscience",
        "prompt": (
            "Describe neural networks in the brain, synaptic plasticity, "
            "cerebrospinal fluid circulation, and memory formation.  How "
            "does biological computation inspire AI?"
        ),
    },
    {
        "domain": "evolutionary_biology",
        "prompt": (
            "Explain natural selection, the phylogenetic Tree of Life, and "
            "speciation mechanisms.  How does evolution produce complexity?"
        ),
    },
    {
        "domain": "ecology",
        "prompt": (
            "Describe ecosystem dynamics, trophic networks, and "
            "sustainability.  How do feedback loops maintain ecological "
            "balance?"
        ),
    },
    {
        "domain": "genetics",
        "prompt": (
            "Explain DNA structure, gene expression, epigenetics, and "
            "CRISPR.  How do genetic mechanisms encode and transmit "
            "information?"
        ),
    },
    {
        "domain": "complexity_science",
        "prompt": (
            "Discuss emergence, self-organisation, and chaos theory.  How "
            "do complex systems produce behaviour that cannot be predicted "
            "from individual components?"
        ),
    },
    # ── Information & Communication (4) ────────────────────────────────────
    {
        "domain": "information_theory",
        "prompt": (
            "Explain Shannon entropy, channel capacity, and data compression. "
            "How does information theory connect to thermodynamics and "
            "quantum mechanics?"
        ),
    },
    {
        "domain": "network_science",
        "prompt": (
            "Describe small-world networks, gossip protocols, and Byzantine "
            "fault tolerance.  How are these applied in peer-to-peer "
            "systems?"
        ),
    },
    {
        "domain": "signal_processing",
        "prompt": (
            "Explain Fourier transforms, wavelets, and noise filtering.  "
            "How are these used in communications, imaging, and data "
            "analysis?"
        ),
    },
    {
        "domain": "cybernetics",
        "prompt": (
            "Describe feedback loops, control systems, and homeostasis.  "
            "How does cybernetics bridge biology, engineering, and AI?"
        ),
    },
    # ── Economics & Society (3) ─────────────────────────────────────────────
    {
        "domain": "economics",
        "prompt": (
            "Explain monetary theory, game theory, and mechanism design.  "
            "How do incentive structures shape economic behaviour and "
            "market outcomes?"
        ),
    },
    {
        "domain": "energy_sustainability",
        "prompt": (
            "Describe renewable energy technologies, the physics of energy "
            "conversion, and the path to sustainable energy systems."
        ),
    },
    {
        "domain": "history_of_science",
        "prompt": (
            "Discuss major paradigm shifts in the history of science — "
            "from Copernicus to quantum mechanics.  What patterns emerge "
            "in how discoveries transform understanding?"
        ),
    },
]


class KnowledgeSeeder:
    """Background knowledge seeder that queries LLMs with master prompts.

    Rate-limit safe with per-hour cap, per-call cooldown, 429 detection,
    and adapter fallback.  All parameters are configurable via Config.
    """

    def __init__(self, llm_manager: object, db_manager: object) -> None:
        """
        Args:
            llm_manager: LLMAdapterManager instance.
            db_manager: DatabaseManager for block height queries.
        """
        self.llm_manager = llm_manager
        self.db = db_manager

        # Round-robin index into MASTER_PROMPTS
        self._prompt_index: int = 0
        self._prompt_lock: threading.Lock = threading.Lock()

        # Rate limiting state (shared across all workers)
        self._calls_this_hour: int = 0
        self._hour_window_start: float = time.time()
        self._last_call_time: float = 0.0
        self._backoff_until: float = 0.0
        self._rate_lock: threading.Lock = threading.Lock()

        # Per-worker height tracking so workers don't block on same interval
        self._worker_last_heights: dict = {}  # worker_id -> last_seed_height

        # History for monitoring
        self._history: List[Dict] = []
        self._total_nodes_created: int = 0
        self._total_tokens_used: int = 0

        # Knowledge graph reference (set externally for domain-weighted selection)
        self._kg: Optional[object] = None

        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_seed_height: int = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # LLM workers (Ollama) — share hourly rate limit
    # Reduced to 1 for CPU-only Ollama — prevents chat timeouts
    _NUM_WORKERS: int = 1
    # Internet workers (Grokipedia + ArXiv) — no Ollama, separate rate limit
    # 200 workers: optimal balance between throughput and API responsiveness.
    # 500 workers caused GIL starvation — API became unresponsive.
    # 200 workers = ~100K nodes/hour without starving FastAPI.
    _NUM_INTERNET_WORKERS: int = 200
    # Minimum seconds between fetches per worker
    _INTERNET_COOLDOWN: float = 2.0

    def start(self) -> None:
        """Start background seeder daemon threads (5 LLM + 5 internet workers)."""
        if self._thread and self._thread.is_alive():
            logger.warning("Knowledge seeder already running")
            return
        self._stop_event.clear()

        # Internet worker rate limiting (separate from LLM)
        self._internet_last_call: float = 0.0
        self._internet_lock: threading.Lock = threading.Lock()
        self._internet_nodes_created: int = 0

        # Launch LLM seeder workers
        self._worker_threads: List[threading.Thread] = []
        for i in range(self._NUM_WORKERS):
            t = threading.Thread(
                target=self._run_worker, args=(i,),
                name=f"knowledge-seeder-{i}", daemon=True,
            )
            t.start()
            self._worker_threads.append(t)

        # Launch internet mining workers (Wikipedia + ArXiv — no Ollama needed)
        self._internet_threads: List[threading.Thread] = []
        for i in range(self._NUM_INTERNET_WORKERS):
            t = threading.Thread(
                target=self._run_internet_worker, args=(i,),
                name=f"kg-internet-{i}", daemon=True,
            )
            t.start()
            self._internet_threads.append(t)

        # Keep _thread pointing at first worker for backwards-compat
        self._thread = self._worker_threads[0]
        logger.info(
            f"Knowledge seeder started ({self._NUM_WORKERS} LLM workers + "
            f"{self._NUM_INTERNET_WORKERS} internet workers, "
            f"rate_limit={Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR}/hr, "
            f"cooldown={Config.LLM_SEEDER_COOLDOWN_SECONDS}s)"
        )

    def stop(self) -> None:
        """Stop all background seeder and internet threads."""
        self._stop_event.set()
        for t in getattr(self, '_worker_threads', []):
            t.join(timeout=5)
        for t in getattr(self, '_internet_threads', []):
            t.join(timeout=5)
        self._worker_threads = []
        self._internet_threads = []
        self._thread = None
        logger.info("Knowledge seeder stopped")

    def seed_once(self, domain: Optional[str] = None) -> Optional[Dict]:
        """Seed a single prompt (manual / testing).

        Args:
            domain: If given, seeds a prompt from that domain.
                    Otherwise uses the next prompt in round-robin order.

        Returns:
            Dict with seed result, or None if rate-limited / failed.
        """
        prompt_entry = self._pick_prompt(domain)
        if not prompt_entry:
            return None
        return self._execute_seed(prompt_entry)

    def get_stats(self) -> Dict:
        """Get seeder statistics for monitoring."""
        workers = getattr(self, '_worker_threads', [])
        inet_workers = getattr(self, '_internet_threads', [])
        return {
            "running": any(t.is_alive() for t in workers) if workers else (
                self._thread is not None and self._thread.is_alive()
            ),
            "num_llm_workers": len(workers),
            "num_internet_workers": len(inet_workers),
            "internet_workers_alive": sum(1 for t in inet_workers if t.is_alive()),
            "prompt_index": self._prompt_index,
            "total_prompts": len(MASTER_PROMPTS),
            "calls_this_hour": self._calls_this_hour,
            "rate_limit_per_hour": Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR,
            "total_nodes_created": self._total_nodes_created,
            "internet_nodes_created": getattr(self, '_internet_nodes_created', 0),
            "total_tokens_used": self._total_tokens_used,
            "seeds_completed": len(self._history),
            "last_seed_height": self._last_seed_height,
            "recent_history": self._history[-10:],
        }

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main background loop — polls every 3s, seeds on interval."""
        self._run_worker(0)

    def _run_worker(self, worker_id: int) -> None:
        """Worker loop — each worker independently queries a domain offset."""
        # Stagger worker starts so they hit different prompt indices
        if worker_id > 0:
            self._stop_event.wait(timeout=worker_id * 2.0)
        while not self._stop_event.is_set():
            try:
                self._maybe_seed_worker(worker_id)
            except Exception as e:
                logger.error(f"Seeder worker-{worker_id} error: {e}", exc_info=True)
            self._stop_event.wait(timeout=3)

    def _maybe_seed(self) -> None:
        """Check if it's time to seed and do so if rate limits allow."""
        try:
            current_height = self.db.get_current_height()
        except Exception:
            return  # DB not ready

        # Only seed every N blocks
        interval = Config.LLM_SEEDER_INTERVAL_BLOCKS
        if interval <= 0:
            return
        if self._last_seed_height >= 0 and (current_height - self._last_seed_height) < interval:
            return

        # Rate limit: hourly cap
        now = time.time()
        if now - self._hour_window_start >= 3600:
            self._calls_this_hour = 0
            self._hour_window_start = now

        if self._calls_this_hour >= Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR:
            return

        # Rate limit: per-call cooldown
        if now - self._last_call_time < Config.LLM_SEEDER_COOLDOWN_SECONDS:
            return

        # Backoff after 429 / error
        if now < self._backoff_until:
            return

        prompt_entry = self._pick_prompt()
        if not prompt_entry:
            return

        result = self._execute_seed(prompt_entry, current_height)
        if result:
            self._last_seed_height = current_height

    def _maybe_seed_worker(self, worker_id: int) -> None:
        """Thread-safe seed check for parallel workers.

        Each worker tracks its own last-seed height so they don't all
        wait for the same interval and can seed in parallel.
        """
        try:
            current_height = self.db.get_current_height()
        except Exception:
            return

        interval = Config.LLM_SEEDER_INTERVAL_BLOCKS
        if interval <= 0:
            return

        last_h = self._worker_last_heights.get(worker_id, -1)
        if last_h >= 0 and (current_height - last_h) < interval:
            return

        with self._rate_lock:
            now = time.time()
            if now - self._hour_window_start >= 3600:
                self._calls_this_hour = 0
                self._hour_window_start = now
            if self._calls_this_hour >= Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR:
                return
            if now - self._last_call_time < Config.LLM_SEEDER_COOLDOWN_SECONDS:
                return
            if now < self._backoff_until:
                return
            # Reserve the slot before releasing lock so workers don't double-call
            self._last_call_time = now
            self._calls_this_hour += 1

        prompt_entry = self._pick_prompt()
        if not prompt_entry:
            return

        result = self._execute_seed_no_ratelimit(prompt_entry, current_height)
        if result:
            self._worker_last_heights[worker_id] = current_height

    # ------------------------------------------------------------------
    # Core seeding logic
    # ------------------------------------------------------------------

    def _pick_prompt(self, domain: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Pick the next prompt to seed.

        If no domain is specified and a knowledge graph is available,
        weights prompt selection toward under-represented domains.
        Otherwise falls back to round-robin.
        """
        if domain:
            matches = [p for p in MASTER_PROMPTS if p["domain"] == domain]
            return random.choice(matches) if matches else None

        if not MASTER_PROMPTS:
            return None

        # Try domain-weighted selection if KG is available
        if self._kg:
            try:
                domain_stats = self._kg.get_domain_stats()
                if domain_stats:
                    return self._pick_weighted_prompt(domain_stats)
            except Exception as e:
                logger.debug("Could not get domain stats for prompt selection: %s", e)

        # Fallback: round-robin (thread-safe)
        lock = getattr(self, '_prompt_lock', None)
        if lock is not None:
            with lock:
                prompt = MASTER_PROMPTS[self._prompt_index % len(MASTER_PROMPTS)]
                self._prompt_index = (self._prompt_index + 1) % len(MASTER_PROMPTS)
        else:
            idx = getattr(self, '_prompt_index', 0)
            prompt = MASTER_PROMPTS[idx % len(MASTER_PROMPTS)]
        return prompt

    def _pick_weighted_prompt(self, domain_stats: Dict) -> Optional[Dict[str, str]]:
        """Pick a prompt weighted toward under-represented domains.

        Priority formula: 1.0 / (1.0 + domain_node_count / 100.0)
        Domains with <100 nodes get 10x priority over 1000+ node domains.
        """
        # Compute weights for each prompt's domain
        weights: List[float] = []
        for p in MASTER_PROMPTS:
            d = p["domain"]
            count = domain_stats.get(d, {}).get('count', 0)
            weight = 1.0 / (1.0 + count / 100.0)
            weights.append(weight)

        total = sum(weights)
        if total <= 0:
            return MASTER_PROMPTS[0]

        # Weighted random selection
        r = random.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return MASTER_PROMPTS[i]
        return MASTER_PROMPTS[-1]

    def _execute_seed(self, prompt_entry: Dict[str, str],
                      block_height: int = 0) -> Optional[Dict]:
        """Execute a single seed: query LLM, distill into KG (also handles rate-limit tracking)."""
        domain = prompt_entry["domain"]
        prompt = prompt_entry["prompt"]

        # Build the system prompt with Aether context
        system_prompt = (
            "You are a knowledge source for the Aether Tree AI. "
            "Give exactly 25-35 key facts, each as a separate short sentence. "
            "Every sentence must be a standalone factual assertion. No elaboration. "
            "Facts must be precise, unique, and information-dense. "
            "Cover different sub-topics within the domain for maximum diversity."
        )

        self._last_call_time = time.time()
        try:
            response = self.llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                distill=True,
                block_height=block_height,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                self._backoff_until = time.time() + 60
                logger.warning(f"Seeder rate-limited, backing off 60s: {e}")
            else:
                logger.warning(f"Seeder LLM call failed: {e}")
            return None

        if not response or response.metadata.get("error"):
            error_msg = str(response.metadata.get("error", "")) if response else ""
            if "429" in error_msg or "rate" in error_msg.lower():
                self._backoff_until = time.time() + 60
                logger.warning(f"Seeder rate-limited via response, backing off 60s")
            return None

        self._calls_this_hour += 1
        return self._record_seed_result(domain, response, block_height)

    def _execute_seed_no_ratelimit(self, prompt_entry: Dict[str, str],
                                   block_height: int = 0) -> Optional[Dict]:
        """Execute a seed without updating rate-limit counters (worker already did)."""
        domain = prompt_entry["domain"]
        prompt = prompt_entry["prompt"]

        system_prompt = (
            "You are a knowledge source for the Aether Tree AI. "
            "Give exactly 25-35 key facts, each as a separate short sentence. "
            "Every sentence must be a standalone factual assertion. No elaboration. "
            "Facts must be precise, unique, and information-dense. "
            "Cover different sub-topics within the domain for maximum diversity."
        )

        try:
            response = self.llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                distill=True,
                block_height=block_height,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                with self._rate_lock:
                    self._backoff_until = time.time() + 60
                logger.warning(f"Seeder worker rate-limited, backing off 60s: {e}")
            else:
                logger.warning(f"Seeder worker LLM call failed: {e}")
            return None

        if not response or response.metadata.get("error"):
            error_msg = str(response.metadata.get("error", "")) if response else ""
            if "429" in error_msg or "rate" in error_msg.lower():
                with self._rate_lock:
                    self._backoff_until = time.time() + 60
                logger.warning(f"Seeder worker rate-limited via response, backing off 60s")
            return None

        return self._record_seed_result(domain, response, block_height)

    def _record_seed_result(self, domain: str, response: object,
                            block_height: int) -> Dict:
        """Record a successful seed result and return the record dict."""
        self._total_tokens_used += response.tokens_used

        # Count distilled nodes (distiller already ran inside generate())
        distilled = self.llm_manager._distiller._distilled_count
        nodes_before = self._total_nodes_created
        self._total_nodes_created = distilled

        record = {
            "domain": domain,
            "block_height": block_height,
            "tokens_used": response.tokens_used,
            "adapter": response.adapter_type,
            "model": response.model,
            "nodes_created": distilled - nodes_before,
            "timestamp": time.time(),
        }
        self._history.append(record)

        # Cap history length
        if len(self._history) > 200:
            self._history = self._history[-100:]

        logger.info(
            f"Seeder: {domain} -> {response.adapter_type}:{response.model} "
            f"({response.tokens_used} tokens, "
            f"{record['nodes_created']} nodes)"
        )
        return record

    # ------------------------------------------------------------------
    # Internet Mining Workers — Wikipedia + ArXiv (no Ollama needed)
    # ------------------------------------------------------------------

    def _run_internet_worker(self, worker_id: int) -> None:
        """Mine knowledge from Wikipedia/ArXiv and inject directly into KG.

        Unlike LLM workers, these bypass Ollama entirely:
        - Fetch factual text from public APIs
        - Parse into sentences and inject as observation/inference nodes
        - Respect a separate, gentler rate limit (8s cooldown)
        """
        # Stagger worker starts so they don't all hit APIs simultaneously
        # 0.05s per worker = 25s for all 500 workers to be active
        if worker_id > 0:
            self._stop_event.wait(timeout=worker_id * 0.05)

        # Rotate between all three sources for maximum throughput & diversity
        # Grokipedia = rich AI-generated articles, ArXiv = research papers,
        # Wikipedia = encyclopedic summaries (fast API, no rate limits)
        sources = ['grokipedia', 'arxiv', 'wikipedia', 'arxiv']
        source_idx = worker_id % len(sources)
        last_call: float = 0.0

        while not self._stop_event.is_set():
            try:
                now = time.time()
                if now - last_call >= self._INTERNET_COOLDOWN:
                    last_call = now
                    source = sources[source_idx % len(sources)]
                    source_idx += 1

                    if source == 'grokipedia':
                        created = self._mine_grokipedia(worker_id)
                    elif source == 'arxiv':
                        created = self._mine_arxiv(worker_id)
                    else:
                        created = self._mine_wikipedia(worker_id)

                    if created > 0:
                        with self._internet_lock:
                            self._internet_nodes_created = getattr(
                                self, '_internet_nodes_created', 0
                            ) + created
            except Exception as e:
                logger.debug(f"Internet worker-{worker_id} error: {e}")
                # Adaptive backoff: if errors happen, slow down this worker
                self._stop_event.wait(timeout=min(30.0, 2.0 * (1 + getattr(self, f'_w{worker_id}_errs', 0))))
                err_key = f'_w{worker_id}_errs'
                setattr(self, err_key, min(getattr(self, err_key, 0) + 1, 10))
                continue

            # Reset error count on success
            setattr(self, f'_w{worker_id}_errs', 0)
            self._stop_event.wait(timeout=1.0)

    def _mine_wikipedia(self, worker_id: int) -> int:
        """Fetch a Wikipedia article and inject sentences as KG nodes."""
        kg = self._kg
        if kg is None:
            return 0

        # Pick a random topic from a random domain
        domain = random.choice(list(_WIKI_TOPICS_BY_DOMAIN.keys()))
        topics = _WIKI_TOPICS_BY_DOMAIN.get(domain, [])
        if not topics:
            return 0
        topic = random.choice(topics)

        try:
            url = (
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(topic.replace(' ', '_'))
            )
            req = urllib.request.Request(
                url, headers={'User-Agent': 'QBC-Aether/1.0 (knowledge-mining)'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.debug(f"Wikipedia fetch failed ({topic}): {e}")
            return 0

        extract = data.get('extract', '')
        title   = data.get('title', topic)
        if not extract or len(extract) < 50:
            return 0

        # Map Wikipedia domain to KG domain
        kg_domain = _DOMAIN_TO_KG.get(domain, 'general')

        # Split into sentences and inject as knowledge nodes
        sentences = self._split_sentences(extract)
        created = 0
        prev_node_id = None

        try:
            current_height = self.db.get_current_height()
        except Exception:
            current_height = 0

        for sent in sentences:
            if len(sent) < 40:
                continue
            try:
                node = kg.add_node(
                    node_type='observation',
                    content={
                        'text': sent,
                        'source': f'wikipedia:{title}',
                        'domain': kg_domain,
                        'grounding': 'internet',
                    },
                    confidence=0.82,
                    source_block=current_height,
                )
                if node:
                    node.grounding_source = 'wikipedia'
                    created += 1
                    # Chain consecutive sentences with 'supports' edges
                    if prev_node_id is not None:
                        try:
                            kg.add_edge(
                                from_node_id=prev_node_id,
                                to_node_id=node.node_id,
                                edge_type='supports',
                                weight=0.7,
                            )
                        except Exception:
                            pass
                    prev_node_id = node.node_id
            except Exception as e:
                logger.debug(f"Wikipedia node inject error: {e}")

        if created > 0:
            logger.info(
                f"Internet worker-{worker_id}: Wikipedia '{title}' "
                f"→ {created} nodes ({kg_domain})"
            )
        return created

    def _mine_grokipedia(self, worker_id: int) -> int:
        """Fetch a Grokipedia article and inject sentences as KG nodes.

        Grokipedia (grokipedia.com) is xAI's AI-generated encyclopedia with
        rich, fact-checked articles. We extract clean text from the HTML,
        split into sentences, and inject as high-confidence observation nodes.
        """
        kg = self._kg
        if kg is None:
            return 0

        # Pick a random topic from a random domain
        domain = random.choice(list(_WIKI_TOPICS_BY_DOMAIN.keys()))
        topics = _WIKI_TOPICS_BY_DOMAIN.get(domain, [])
        if not topics:
            return 0
        topic = random.choice(topics)

        try:
            slug = topic.replace(' ', '_')
            url = f"https://grokipedia.com/page/{urllib.parse.quote(slug)}"
            req = urllib.request.Request(
                url, headers={'User-Agent': 'QBC-Aether/1.0 (knowledge-mining)'}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            logger.debug(f"Grokipedia fetch failed ({topic}): {e}")
            return 0

        if len(html) < 500:
            return 0

        # Extract clean text: strip script/style, then HTML tags
        import re as _re
        html = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
        html = _re.sub(r'<style[^>]*>.*?</style>', '', html, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', ' ', html)
        text = _re.sub(r'\s+', ' ', text).strip()

        # Find the article content (starts after the title, skip nav/menu)
        # Look for the topic name or first heading as anchor
        anchor_idx = text.find(topic)
        if anchor_idx < 0:
            # Try without parenthetical disambiguation
            short_topic = topic.split('(')[0].strip()
            anchor_idx = text.find(short_topic)
        if anchor_idx >= 0:
            text = text[anchor_idx:]
        elif len(text) > 2000:
            # Skip first 1000 chars (nav/menu) if we can't find anchor
            text = text[1000:]

        # Limit to first 8000 chars (article body, avoid references/footer)
        text = text[:8000]

        if len(text) < 200:
            return 0

        # Map domain to KG domain
        kg_domain = _DOMAIN_TO_KG.get(domain, 'general')

        # Split into sentences and inject as knowledge nodes
        sentences = self._split_sentences(text)
        created = 0
        prev_node_id = None

        try:
            current_height = self.db.get_current_height()
        except Exception:
            current_height = 0

        for sent in sentences:
            if len(sent) < 40 or len(sent) > 500:
                continue
            # Skip sentences that are mostly non-alpha (JS remnants, CSS)
            alpha_ratio = sum(1 for c in sent if c.isalpha()) / max(len(sent), 1)
            if alpha_ratio < 0.6:
                continue
            try:
                node = kg.add_node(
                    node_type='observation',
                    content={
                        'text': sent,
                        'source': f'grokipedia:{topic}',
                        'domain': kg_domain,
                        'grounding': 'internet',
                    },
                    confidence=0.85,
                    source_block=current_height,
                )
                if node:
                    node.grounding_source = 'grokipedia'
                    created += 1
                    # Chain consecutive sentences with 'supports' edges
                    if prev_node_id is not None:
                        try:
                            kg.add_edge(
                                from_node_id=prev_node_id,
                                to_node_id=node.node_id,
                                edge_type='supports',
                                weight=0.7,
                            )
                        except Exception:
                            pass
                    prev_node_id = node.node_id
            except Exception as e:
                logger.debug(f"Grokipedia node inject error: {e}")

        if created > 0:
            logger.info(
                f"Internet worker-{worker_id}: Grokipedia '{topic}' "
                f"→ {created} nodes ({kg_domain})"
            )
        return created

    def _mine_arxiv(self, worker_id: int) -> int:
        """Fetch recent ArXiv paper titles/abstracts and inject as KG nodes."""
        kg = self._kg
        if kg is None:
            return 0

        query_entry = random.choice(_ARXIV_QUERIES)
        term = query_entry['term']
        cat  = query_entry['cat']

        try:
            params = urllib.parse.urlencode({
                'search_query': f'all:{term} AND cat:{cat}',
                'start': str(random.randint(0, 200)),
                'max_results': '20',
                'sortBy': 'lastUpdatedDate',
                'sortOrder': 'descending',
            })
            url = f"https://export.arxiv.org/api/query?{params}"
            req = urllib.request.Request(
                url, headers={'User-Agent': 'QBC-Aether/1.0 (knowledge-mining)'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_text = resp.read().decode('utf-8')
        except Exception as e:
            logger.debug(f"ArXiv fetch failed ({term}): {e}")
            return 0

        # Extract titles and summaries from Atom XML (no xml lib needed)
        entries = xml_text.split('<entry>')
        created = 0

        try:
            current_height = self.db.get_current_height()
        except Exception:
            current_height = 0

        for entry in entries[1:]:  # skip feed header
            title_start = entry.find('<title>') + 7
            title_end   = entry.find('</title>')
            summary_start = entry.find('<summary>') + 9
            summary_end   = entry.find('</summary>')

            if title_start < 7 or title_end < 0:
                continue
            title   = entry[title_start:title_end].strip().replace('\n', ' ')
            summary = ''
            if summary_start >= 9 and summary_end >= 0:
                summary = entry[summary_start:summary_end].strip().replace('\n', ' ')

            # Map ArXiv category to KG domain
            cat_to_domain = {
                'quant-ph': 'quantum_physics',
                'cs.AI': 'ai_ml', 'cs.LG': 'ai_ml', 'cs.CL': 'ai_ml',
                'cs.CV': 'ai_ml', 'cs.NE': 'ai_ml', 'cs.RO': 'ai_ml',
                'cs.CR': 'cryptography', 'cs.DC': 'computer_science',
                'cs.DS': 'computer_science', 'cs.PL': 'computer_science',
                'q-bio.NC': 'biology', 'q-bio.GN': 'biology',
                'stat.ML': 'ai_ml', 'stat.TH': 'mathematics',
                'math.AT': 'mathematics', 'math.AG': 'mathematics',
                'math.CO': 'mathematics', 'math.PR': 'mathematics',
                'math.OC': 'mathematics', 'math.NA': 'mathematics',
                'hep-th': 'physics', 'hep-ph': 'physics',
                'cond-mat': 'physics', 'gr-qc': 'physics',
                'astro-ph': 'physics', 'nlin.CD': 'philosophy',
                'econ.TH': 'economics', 'econ.GN': 'economics',
                'physics.comp-ph': 'physics',
            }
            kg_domain = cat_to_domain.get(cat, 'general')

            # Inject title as inference node
            if title and len(title) >= 20:
                try:
                    node = kg.add_node(
                        node_type='inference',
                        content={
                            'text': f"Research: {title}",
                            'source': f'arxiv:{cat}',
                            'domain': kg_domain,
                            'grounding': 'internet',
                        },
                        confidence=0.75,
                        source_block=current_height,
                    )
                    if node:
                        node.grounding_source = 'arxiv'
                        created += 1
                except Exception:
                    pass

            # Inject summary sentences
            if summary and len(summary) >= 60:
                for sent in self._split_sentences(summary)[:4]:
                    if len(sent) < 40:
                        continue
                    try:
                        node = kg.add_node(
                            node_type='observation',
                            content={
                                'text': sent,
                                'source': f'arxiv:{cat}',
                                'domain': kg_domain,
                                'grounding': 'internet',
                            },
                            confidence=0.72,
                            source_block=current_height,
                        )
                        if node:
                            node.grounding_source = 'arxiv'
                            created += 1
                    except Exception:
                        pass

        if created > 0:
            logger.info(
                f"Internet worker-{worker_id}: ArXiv '{term}' "
                f"→ {created} nodes"
            )
        return created

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Simple sentence splitter on '.', '!', '?' boundaries."""
        import re
        # Split on sentence-ending punctuation followed by space or end
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        # Also split very long run-ons at semicolons
        result = []
        for part in parts:
            if len(part) > 300:
                for sub in part.split(';'):
                    sub = sub.strip()
                    if sub:
                        result.append(sub)
            else:
                if part.strip():
                    result.append(part.strip())
        return result
