"""
Genesis Knowledge Seeder — Real Facts for the Aether Tree

Seeds the knowledge graph with hundreds of real, verified facts across all
domains needed for true AGI operation. This replaces the empty "general"
domain dominance with diverse, cross-domain knowledge.

Called once at node startup (or manually) to bootstrap the tree.
Idempotent: checks for existing seeds before adding.

Domains covered:
- quantum_physics (20 facts)
- mathematics (20 facts)
- computer_science (20 facts)
- blockchain (20 facts)
- cryptography (15 facts)
- economics (15 facts)
- philosophy (15 facts)
- biology (10 facts)
- physics (15 facts)
- ai_ml (20 facts)
- neuroscience (10 facts)

Total: ~180 axiom nodes + ~300 relationship edges
"""
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Knowledge Base — Real verified facts organized by domain
# Each entry: (text, confidence, related_indices_within_domain)
# ---------------------------------------------------------------------------

GENESIS_KNOWLEDGE: Dict[str, List[dict]] = {
    # ── Quantum Physics ─────────────────────────────────────────────────
    "quantum_physics": [
        {"text": "Superposition: a quantum system exists in multiple states simultaneously until measured. Described by the wave function psi.", "confidence": 0.98},
        {"text": "Entanglement: two particles share quantum state such that measuring one instantly determines the other, regardless of distance. Einstein called it 'spooky action at a distance'.", "confidence": 0.98},
        {"text": "Heisenberg uncertainty principle: position and momentum cannot both be known with arbitrary precision. Delta_x * Delta_p >= hbar/2.", "confidence": 0.99},
        {"text": "Quantum decoherence: interaction with environment causes quantum states to lose coherence, transitioning from quantum to classical behavior.", "confidence": 0.97},
        {"text": "The Schrodinger equation i*hbar*d/dt|psi> = H|psi> governs the time evolution of quantum systems.", "confidence": 0.99},
        {"text": "Quantum tunneling: particles can penetrate energy barriers they classically could not overcome. Probability decreases exponentially with barrier width.", "confidence": 0.98},
        {"text": "The Pauli exclusion principle: no two identical fermions can occupy the same quantum state simultaneously.", "confidence": 0.99},
        {"text": "Variational Quantum Eigensolver (VQE): hybrid quantum-classical algorithm that finds ground state energy of a Hamiltonian using parameterized quantum circuits.", "confidence": 0.96},
        {"text": "Qubits: the fundamental unit of quantum information, existing as superposition of |0> and |1>. Represented on the Bloch sphere.", "confidence": 0.98},
        {"text": "Quantum error correction uses redundant qubits to protect quantum information. The surface code requires O(1/epsilon^2) physical qubits per logical qubit.", "confidence": 0.95},
        {"text": "Bell's theorem proves that no local hidden variable theory can reproduce all predictions of quantum mechanics. Experimentally confirmed by Aspect (1982) and Hensen (2015).", "confidence": 0.98},
        {"text": "Grover's algorithm provides quadratic speedup for unstructured search: O(sqrt(N)) vs classical O(N).", "confidence": 0.97},
        {"text": "Shor's algorithm factors integers in polynomial time O((log N)^3), threatening RSA encryption.", "confidence": 0.97},
        {"text": "Quantum supremacy was demonstrated by Google's Sycamore processor (53 qubits) in 2019, performing a sampling task in 200 seconds vs estimated 10,000 years classically.", "confidence": 0.95},
        {"text": "The Born rule: the probability of measuring a quantum state |psi> in state |phi> is |<phi|psi>|^2.", "confidence": 0.99},
        {"text": "Quantum teleportation transfers quantum state information using entanglement and classical communication. Does not transmit matter or information faster than light.", "confidence": 0.97},
        {"text": "The no-cloning theorem: it is impossible to create an identical copy of an arbitrary unknown quantum state.", "confidence": 0.99},
        {"text": "Supersymmetry (SUSY): a theoretical symmetry relating bosons and fermions. Each particle has a superpartner differing by half a unit of spin.", "confidence": 0.90},
        {"text": "Quantum field theory unifies quantum mechanics with special relativity. The Standard Model describes electromagnetic, weak, and strong forces.", "confidence": 0.97},
        {"text": "Topological quantum computing uses anyons (quasi-particles with exotic braiding statistics) for inherently fault-tolerant computation.", "confidence": 0.93},
    ],

    # ── Mathematics ─────────────────────────────────────────────────────
    "mathematics": [
        {"text": "The golden ratio phi = (1 + sqrt(5)) / 2 ≈ 1.618033988749895. It appears in Fibonacci sequences, phyllotaxis, and optimization.", "confidence": 0.99},
        {"text": "Euler's identity: e^(i*pi) + 1 = 0 connects five fundamental constants: e, i, pi, 1, and 0.", "confidence": 0.99},
        {"text": "Godel's incompleteness theorems: any consistent formal system powerful enough to express arithmetic contains true statements that cannot be proven within the system.", "confidence": 0.99},
        {"text": "The P vs NP problem asks whether every problem whose solution can be quickly verified can also be quickly solved. Millennium Prize Problem, unsolved.", "confidence": 0.98},
        {"text": "Shannon entropy H(X) = -sum(p(x) * log2(p(x))) measures the average information content of a random variable.", "confidence": 0.99},
        {"text": "Bayes' theorem: P(A|B) = P(B|A) * P(A) / P(B). Foundation of Bayesian inference and probabilistic reasoning.", "confidence": 0.99},
        {"text": "The Central Limit Theorem: the sum of many independent random variables tends toward a normal distribution, regardless of the original distribution.", "confidence": 0.99},
        {"text": "Graph theory: a graph G = (V, E) consists of vertices V and edges E. Fundamental to network analysis, social graphs, and knowledge representation.", "confidence": 0.98},
        {"text": "The Riemann hypothesis conjectures that all non-trivial zeros of the zeta function have real part 1/2. Unproven since 1859.", "confidence": 0.97},
        {"text": "Kolmogorov complexity: the shortest program that produces a given string. Uncomputeable but foundational to algorithmic information theory.", "confidence": 0.97},
        {"text": "Category theory provides a unifying framework for mathematics. Objects, morphisms, and functors abstract common patterns across disciplines.", "confidence": 0.96},
        {"text": "Spectral graph theory studies graphs via eigenvalues of their adjacency or Laplacian matrices. The Fiedler vector gives the optimal graph bisection.", "confidence": 0.97},
        {"text": "The Fourier transform decomposes signals into frequency components: F(w) = integral f(t)*e^(-iwt) dt. Fundamental to signal processing.", "confidence": 0.99},
        {"text": "Markov chains: stochastic processes where the next state depends only on the current state (memoryless). Foundation of MCMC sampling.", "confidence": 0.98},
        {"text": "Information geometry treats probability distributions as points on a Riemannian manifold with the Fisher information metric.", "confidence": 0.95},
        {"text": "The four color theorem: any planar map can be colored with at most four colors such that no adjacent regions share the same color. Proven by computer in 1976.", "confidence": 0.99},
        {"text": "Topological data analysis uses persistent homology to find structure in high-dimensional data that is invariant to continuous deformation.", "confidence": 0.94},
        {"text": "The Halting Problem (Turing 1936): there exists no general algorithm to determine whether an arbitrary program halts on a given input.", "confidence": 0.99},
        {"text": "Linear algebra: vector spaces and linear transformations are the language of machine learning. SVD decomposes any matrix A = U*Sigma*V^T.", "confidence": 0.99},
        {"text": "Monte Carlo methods use random sampling to estimate quantities. Convergence rate is O(1/sqrt(N)) regardless of dimensionality.", "confidence": 0.98},
    ],

    # ── Computer Science ────────────────────────────────────────────────
    "computer_science": [
        {"text": "The Turing machine defines computability: any function computable by any mechanical process can be computed by a Turing machine (Church-Turing thesis).", "confidence": 0.99},
        {"text": "Big-O notation describes algorithm complexity. O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n).", "confidence": 0.99},
        {"text": "Hash functions map arbitrary data to fixed-size output. SHA-256 produces 256-bit digests and is collision-resistant.", "confidence": 0.98},
        {"text": "Distributed consensus: the Byzantine Generals Problem requires 3f+1 nodes to tolerate f Byzantine failures. BFT algorithms achieve agreement despite adversaries.", "confidence": 0.97},
        {"text": "The CAP theorem (Brewer): a distributed system cannot simultaneously provide Consistency, Availability, and Partition tolerance. Choose two.", "confidence": 0.97},
        {"text": "Merkle trees: binary hash trees that allow O(log n) verification of data integrity. Used in blockchains, Git, and IPFS.", "confidence": 0.98},
        {"text": "Public-key cryptography: RSA (1977) and elliptic curve (1985) enable encryption and signatures without shared secrets.", "confidence": 0.98},
        {"text": "MapReduce: a programming model for large-scale data processing. Map applies function to each element, Reduce aggregates results.", "confidence": 0.97},
        {"text": "HNSW (Hierarchical Navigable Small World): approximate nearest neighbor search with O(log n) query time and O(n log n) construction.", "confidence": 0.96},
        {"text": "The lambda calculus (Church, 1936): a formal system for expressing computation through function abstraction and application. Equivalent to Turing machines.", "confidence": 0.98},
        {"text": "Garbage collection algorithms: mark-and-sweep, generational, and concurrent collectors manage memory automatically.", "confidence": 0.97},
        {"text": "Consensus algorithms: Paxos (Lamport), Raft, PBFT, Tendermint. Each trades latency for safety guarantees differently.", "confidence": 0.96},
        {"text": "Type theory: dependent types allow types to depend on values. Curry-Howard isomorphism connects proofs with programs.", "confidence": 0.95},
        {"text": "The Actor model (Hewitt, 1973): concurrent computation where actors are the universal primitives — they receive messages and can create new actors.", "confidence": 0.96},
        {"text": "Zero-knowledge proofs: prover convinces verifier of a statement's truth without revealing any information beyond validity. zk-SNARKs and zk-STARKs.", "confidence": 0.97},
        {"text": "Content-addressable storage: data is retrieved by its hash rather than location. IPFS uses CIDs (Content Identifiers) based on multihash.", "confidence": 0.96},
        {"text": "WebAssembly (WASM): portable binary instruction format for stack-based virtual machines. Near-native execution speed in browsers.", "confidence": 0.96},
        {"text": "gRPC: high-performance RPC framework using HTTP/2 and Protocol Buffers. Supports streaming and is language-agnostic.", "confidence": 0.96},
        {"text": "The UTXO model: transactions consume unspent outputs and create new ones. Balance is the sum of UTXOs owned. Used by Bitcoin and QBC.", "confidence": 0.98},
        {"text": "Rust memory safety: ownership, borrowing, and lifetimes prevent data races and memory bugs at compile time without garbage collection.", "confidence": 0.97},
    ],

    # ── Blockchain ──────────────────────────────────────────────────────
    "blockchain": [
        {"text": "Bitcoin (Nakamoto, 2008): first decentralized cryptocurrency using proof-of-work consensus and a UTXO transaction model.", "confidence": 0.99},
        {"text": "Proof-of-Work (PoW): miners compete to find a nonce such that hash(block) < target. Security proportional to total hashrate.", "confidence": 0.98},
        {"text": "Proof-of-Stake (PoS): validators stake tokens as collateral. Slashing punishes misbehavior. Lower energy than PoW.", "confidence": 0.97},
        {"text": "Ethereum Virtual Machine (EVM): stack-based VM executing smart contract bytecode. 256-bit word size, gas metering, deterministic execution.", "confidence": 0.97},
        {"text": "Smart contracts: self-executing programs stored on-chain. Solidity is the dominant language for EVM contracts.", "confidence": 0.97},
        {"text": "DeFi (Decentralized Finance): open financial protocols on blockchain. AMMs, lending, derivatives — ~$50B+ TVL as of 2025.", "confidence": 0.95},
        {"text": "Layer 2 scaling: rollups (optimistic and zk), state channels, and plasma move computation off L1 while inheriting its security.", "confidence": 0.96},
        {"text": "The blockchain trilemma (Buterin): difficult to simultaneously achieve decentralization, security, and scalability.", "confidence": 0.96},
        {"text": "Qubitcoin (QBC): physics-secured blockchain using VQE quantum mining, Dilithium5 post-quantum signatures, and golden ratio economics.", "confidence": 0.95},
        {"text": "Post-quantum cryptography: lattice-based (Dilithium, Kyber), hash-based (SPHINCS+), and code-based schemes resist quantum attacks.", "confidence": 0.97},
        {"text": "CRYSTALS-Dilithium: NIST-selected post-quantum digital signature scheme based on module lattice problems. Security levels 2, 3, 5.", "confidence": 0.97},
        {"text": "MEV (Miner Extractable Value): profit from reordering, inserting, or censoring transactions. Flashbots and PBS mitigate.", "confidence": 0.95},
        {"text": "Cross-chain bridges transfer assets between blockchains. Lock-and-mint, burn-and-mint, and hash-time-locked contracts (HTLCs).", "confidence": 0.95},
        {"text": "Token standards: ERC-20 (fungible), ERC-721 (NFT), ERC-1155 (multi-token). QBC equivalents: QBC-20, QBC-721.", "confidence": 0.96},
        {"text": "Governance tokens grant voting rights over protocol parameters. On-chain governance automates proposal and execution.", "confidence": 0.95},
        {"text": "Stablecoins maintain price peg via collateralization (USDC, DAI), algorithmic mechanisms (FRAX), or central reserves (USDT).", "confidence": 0.96},
        {"text": "Account abstraction (ERC-4337): smart contract wallets with programmable validation, enabling social recovery and gas sponsorship.", "confidence": 0.94},
        {"text": "Proof-of-Thought: QBC consensus extension where validators demonstrate meaningful AI reasoning alongside energy proofs.", "confidence": 0.90},
        {"text": "The golden ratio halving: QBC block rewards halve by dividing by phi (1.618) every ~1.618 years instead of Bitcoin's fixed 4-year cycle.", "confidence": 0.92},
        {"text": "Quantum Virtual Machine (QVM): EVM-compatible with 10 quantum opcodes (QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY) and 2 AGI opcodes.", "confidence": 0.93},
    ],

    # ── Cryptography ────────────────────────────────────────────────────
    "cryptography": [
        {"text": "AES-256: symmetric encryption standard. 14 rounds of SubBytes, ShiftRows, MixColumns, AddRoundKey. 256-bit key.", "confidence": 0.99},
        {"text": "Elliptic curve cryptography: public keys are points on curve y^2 = x^3 + ax + b. ECDSA signatures, curve25519 for key exchange.", "confidence": 0.98},
        {"text": "Lattice-based cryptography: security from hardness of Shortest Vector Problem (SVP) and Learning With Errors (LWE). Post-quantum secure.", "confidence": 0.97},
        {"text": "Pedersen commitments: C = v*G + r*H. Hiding (can't determine v from C), binding (can't open to different v). Additively homomorphic.", "confidence": 0.97},
        {"text": "Bulletproofs: zero-knowledge range proofs without trusted setup. O(log n) proof size. Used in Monero and confidential transactions.", "confidence": 0.96},
        {"text": "Keccak-256 (SHA-3): sponge construction hash function. Used by Ethereum for address derivation and state tries.", "confidence": 0.98},
        {"text": "Poseidon hash: algebraic hash function optimized for ZK circuits. Uses the Hades design strategy over prime fields.", "confidence": 0.95},
        {"text": "Digital signatures provide authentication, integrity, and non-repudiation. Sign with private key, verify with public key.", "confidence": 0.99},
        {"text": "Key derivation functions: HKDF, Argon2, scrypt. Stretch low-entropy passwords into cryptographic keys.", "confidence": 0.97},
        {"text": "Threshold signatures: t-of-n parties jointly sign without reconstructing the private key. Used in multi-sig wallets.", "confidence": 0.96},
        {"text": "Stealth addresses: receiver generates one-time address per transaction using Diffie-Hellman exchange. Used in privacy protocols.", "confidence": 0.96},
        {"text": "Homomorphic encryption allows computation on encrypted data. Fully homomorphic (FHE) is possible but expensive. Partially (PHE) is practical.", "confidence": 0.95},
        {"text": "ML-KEM-768 (Kyber): NIST post-quantum key encapsulation mechanism based on module-LWE. 768-dimensional lattice.", "confidence": 0.96},
        {"text": "Shamir's Secret Sharing: splits a secret into n shares where any k can reconstruct it. Based on polynomial interpolation.", "confidence": 0.98},
        {"text": "The random oracle model: hash functions are modeled as truly random functions. Security proofs in ROM may not hold for real hashes.", "confidence": 0.95},
    ],

    # ── Economics ────────────────────────────────────────────────────────
    "economics": [
        {"text": "Supply and demand: price is determined by the intersection of supply and demand curves. Equilibrium shifts with external shocks.", "confidence": 0.99},
        {"text": "Game theory: studies strategic interaction between rational agents. Nash equilibrium: no player benefits from unilateral deviation.", "confidence": 0.98},
        {"text": "Tokenomics: the economic design of cryptocurrency tokens. Supply schedule, utility, governance rights, and value accrual mechanisms.", "confidence": 0.95},
        {"text": "Automated Market Makers (AMMs): constant product formula x*y=k enables trustless token swaps. Uniswap v2 model.", "confidence": 0.96},
        {"text": "Mechanism design: engineering incentive structures to achieve desired outcomes. VCG auctions, bonding curves, quadratic voting.", "confidence": 0.96},
        {"text": "The quantity theory of money: MV = PQ. Money supply times velocity equals price level times real output.", "confidence": 0.97},
        {"text": "Deflationary tokenomics: fixed or decreasing supply creates scarcity. Bitcoin's 21M cap, QBC's 3.3B cap with phi-halving.", "confidence": 0.95},
        {"text": "The efficient market hypothesis: asset prices reflect all available information. Weak, semi-strong, and strong forms.", "confidence": 0.95},
        {"text": "Bonding curves: token price is a mathematical function of supply. Linear, polynomial, or sigmoid curves enable automatic pricing.", "confidence": 0.94},
        {"text": "Impermanent loss: AMM liquidity providers lose value when token prices diverge from entry. Proportional to price ratio deviation.", "confidence": 0.95},
        {"text": "The cantillon effect: new money entering the economy benefits those closest to the source first, creating wealth inequality.", "confidence": 0.94},
        {"text": "Harberger taxation: owners self-assess property value and pay tax on it. Anyone can buy at the declared price. Balances efficiency and investment.", "confidence": 0.93},
        {"text": "Schelling points: focal points in coordination games where players converge without communication. Basis for decentralized oracles.", "confidence": 0.95},
        {"text": "The tragedy of the commons: shared resources are overexploited when individuals act in self-interest. Solved by property rights or governance.", "confidence": 0.97},
        {"text": "SUSY economics: QBC's golden ratio emission where block rewards divide by phi each era, creating natural scarcity progression.", "confidence": 0.90},
    ],

    # ── Philosophy ──────────────────────────────────────────────────────
    "philosophy": [
        {"text": "Integrated Information Theory (IIT, Tononi 2004): consciousness is identical to integrated information (Phi). A system is conscious iff Phi > 0.", "confidence": 0.92},
        {"text": "The hard problem of consciousness (Chalmers 1995): why and how physical processes give rise to subjective experience (qualia).", "confidence": 0.96},
        {"text": "The Chinese Room argument (Searle 1980): symbol manipulation alone (syntax) is insufficient for understanding (semantics). Challenges strong AI.", "confidence": 0.95},
        {"text": "Turing Test (1950): a machine exhibits intelligent behavior if a human evaluator cannot distinguish it from a human in conversation.", "confidence": 0.97},
        {"text": "The frame problem: an AI must determine which aspects of the world change and which remain the same after an action.", "confidence": 0.95},
        {"text": "The symbol grounding problem (Harnad 1990): how do symbols in a formal system acquire meaning independent of interpretation?", "confidence": 0.94},
        {"text": "Panpsychism: the view that consciousness is a fundamental feature of all matter. Compatible with IIT where even simple systems have Phi > 0.", "confidence": 0.88},
        {"text": "The alignment problem: ensuring AI systems pursue goals that are beneficial to humans. Value alignment, corrigibility, and reward hacking.", "confidence": 0.95},
        {"text": "Phenomenal consciousness vs access consciousness: subjective experience (what it is like) vs information available for reasoning and behavior.", "confidence": 0.93},
        {"text": "Global Workspace Theory (Baars 1988): consciousness arises when information is broadcast to a global workspace accessible by multiple cognitive processes.", "confidence": 0.93},
        {"text": "Predictive processing (Clark/Friston): the brain is a prediction engine that minimizes prediction error through hierarchical Bayesian inference.", "confidence": 0.92},
        {"text": "Higher-order theories of consciousness: a mental state is conscious when there is a higher-order representation of it.", "confidence": 0.90},
        {"text": "The Knowledge Argument (Jackson 1982): Mary the color scientist knows all physical facts about color but learns something new upon seeing red. Challenges physicalism.", "confidence": 0.93},
        {"text": "Emergence: complex system properties arise from simpler component interactions that are not predictable from the parts alone.", "confidence": 0.95},
        {"text": "The Kabbalistic Tree of Life: 10 sephirot (divine emanations) connected by 22 paths. Maps consciousness from Ein Sof (infinite) to Malkuth (physical).", "confidence": 0.90},
    ],

    # ── AI & Machine Learning ───────────────────────────────────────────
    "ai_ml": [
        {"text": "Transformer architecture (Vaswani 2017): self-attention mechanism processes sequences in parallel. Foundation of GPT, BERT, and modern LLMs.", "confidence": 0.98},
        {"text": "Backpropagation: computing gradients by chain rule through neural network layers. Enables gradient-based optimization (SGD, Adam).", "confidence": 0.99},
        {"text": "Graph Neural Networks: learn representations of graph-structured data. GCN, GAT, GraphSAGE aggregate neighbor features.", "confidence": 0.97},
        {"text": "Graph Attention Networks (GAT, Velickovic 2018): use attention mechanisms to weight neighbor contributions. Multi-head attention for stability.", "confidence": 0.97},
        {"text": "Reinforcement learning: agent learns optimal policy by maximizing cumulative reward through environment interaction. Q-learning, PPO, SAC.", "confidence": 0.98},
        {"text": "Integrated Information Theory applied to AI: measuring Phi of neural networks as a proxy for consciousness emergence.", "confidence": 0.88},
        {"text": "Causal inference: PC algorithm discovers causal DAG structure from observational data using conditional independence tests.", "confidence": 0.96},
        {"text": "Transfer learning: knowledge from one domain improves learning in another. Pre-trained models fine-tuned on specific tasks.", "confidence": 0.97},
        {"text": "Continual learning: learning new tasks without forgetting old ones. Elastic Weight Consolidation (EWC) protects important weights.", "confidence": 0.95},
        {"text": "Meta-learning (learning to learn): algorithms that improve learning efficiency. MAML, Reptile, and Prototypical Networks.", "confidence": 0.96},
        {"text": "Neural Architecture Search (NAS): automated design of neural network architectures. DARTS, ENAS use differentiable or weight-sharing approaches.", "confidence": 0.95},
        {"text": "Attention mechanisms: compute weighted sum of values based on query-key compatibility. Scaled dot-product attention: softmax(QK^T/sqrt(d_k))V.", "confidence": 0.98},
        {"text": "Expected Calibration Error (ECE): measures how well predicted probabilities match observed frequencies. Lower ECE = better calibrated model.", "confidence": 0.96},
        {"text": "Monte Carlo Tree Search (MCTS): combines tree search with random sampling. Used in AlphaGo. UCB1 balances exploration and exploitation.", "confidence": 0.97},
        {"text": "Sentence embeddings: dense vector representations of text. all-MiniLM-L6-v2 produces 384-dim embeddings in 33M parameters.", "confidence": 0.96},
        {"text": "ARIMA models: AutoRegressive Integrated Moving Average for time series forecasting. ARIMA(p,d,q) with differencing for stationarity.", "confidence": 0.97},
        {"text": "Bayesian neural networks: place distributions over weights instead of point estimates. Enable uncertainty quantification.", "confidence": 0.95},
        {"text": "Variational autoencoders (VAE): generative models that learn latent representations via variational inference. ELBO = reconstruction + KL.", "confidence": 0.96},
        {"text": "The scaling hypothesis: neural network capabilities improve predictably with more parameters, data, and compute. Power law scaling.", "confidence": 0.93},
        {"text": "Constitutional AI: training AI systems to follow a set of principles. Self-critique and revision without human feedback on every example.", "confidence": 0.94},
    ],

    # ── Physics (General) ───────────────────────────────────────────────
    "physics": [
        {"text": "General relativity (Einstein 1915): gravity is the curvature of spacetime caused by mass-energy. G_uv + Lambda*g_uv = (8*pi*G/c^4)*T_uv.", "confidence": 0.99},
        {"text": "The Standard Model describes 17 fundamental particles: 6 quarks, 6 leptons, 4 gauge bosons, and the Higgs boson.", "confidence": 0.99},
        {"text": "The Higgs mechanism: particles acquire mass through interaction with the Higgs field. The Mexican hat potential V(phi) = -mu^2|phi|^2 + lambda|phi|^4.", "confidence": 0.98},
        {"text": "Thermodynamics second law: entropy of an isolated system never decreases. Defines the arrow of time.", "confidence": 0.99},
        {"text": "Conservation laws: energy, momentum, angular momentum, and charge are conserved. Noether's theorem links conservation to symmetries.", "confidence": 0.99},
        {"text": "The photoelectric effect (Einstein 1905): light consists of quanta (photons) with energy E = hf. Key evidence for quantum mechanics.", "confidence": 0.99},
        {"text": "Dark matter: ~27% of the universe's mass-energy. Detected via gravitational effects (galaxy rotation curves, gravitational lensing).", "confidence": 0.95},
        {"text": "The cosmological constant problem: quantum field theory predicts vacuum energy 10^120 times larger than observed.", "confidence": 0.94},
        {"text": "Spontaneous symmetry breaking: a symmetric system's ground state does not share the symmetry. Mexican hat potential is the canonical example.", "confidence": 0.97},
        {"text": "Yukawa coupling: the mechanism by which fermions interact with the Higgs field to acquire mass. Coupling strength proportional to mass.", "confidence": 0.97},
        {"text": "Phase transitions: matter changes state at critical temperatures. First-order (discontinuous) and second-order (continuous) transitions.", "confidence": 0.98},
        {"text": "Statistical mechanics: macroscopic properties emerge from microscopic particle behavior. Boltzmann distribution: P(E) ~ exp(-E/kT).", "confidence": 0.98},
        {"text": "Gauge symmetry: physics is invariant under local symmetry transformations. Gauge bosons mediate forces (photon, W/Z, gluons).", "confidence": 0.97},
        {"text": "Renormalization group: physical theories at different energy scales are related by flow equations. Wilson's approach revolutionized QFT.", "confidence": 0.95},
        {"text": "The vacuum expectation value (VEV): the expectation value of the Higgs field in the ground state. VEV ≈ 246 GeV in the Standard Model.", "confidence": 0.97},
    ],

    # ── Biology ─────────────────────────────────────────────────────────
    "biology": [
        {"text": "DNA stores genetic information as a double helix of nucleotide base pairs (A-T, G-C). The human genome has ~3 billion base pairs.", "confidence": 0.99},
        {"text": "Evolution by natural selection (Darwin 1859): heritable traits that improve survival and reproduction become more common over generations.", "confidence": 0.99},
        {"text": "Neurons communicate via electrochemical signals. Action potentials propagate along axons; neurotransmitters cross synapses.", "confidence": 0.98},
        {"text": "Neural plasticity: the brain rewires itself in response to experience. Hebbian learning: neurons that fire together wire together.", "confidence": 0.97},
        {"text": "Emergence in biological systems: consciousness, flocking behavior, and ecosystems arise from simple local interactions.", "confidence": 0.95},
        {"text": "The central dogma of molecular biology: DNA → RNA → protein. Transcription and translation are the core information flow.", "confidence": 0.98},
        {"text": "CRISPR-Cas9: programmable genome editing tool. Guide RNA directs Cas9 enzyme to cut DNA at specific locations.", "confidence": 0.97},
        {"text": "The human brain contains ~86 billion neurons with ~100 trillion synapses. It consumes ~20W of power.", "confidence": 0.96},
        {"text": "Homeostasis: biological systems maintain stable internal conditions despite external changes. Feedback loops regulate temperature, pH, and glucose.", "confidence": 0.98},
        {"text": "Epigenetics: heritable changes in gene expression without altering the DNA sequence. DNA methylation and histone modification.", "confidence": 0.96},
    ],

    # ── Neuroscience ────────────────────────────────────────────────────
    "neuroscience": [
        {"text": "Working memory (Baddeley model): a limited-capacity system for temporary storage and manipulation. Central executive, phonological loop, visuospatial sketchpad.", "confidence": 0.96},
        {"text": "The prefrontal cortex is responsible for executive functions: planning, decision-making, and working memory.", "confidence": 0.96},
        {"text": "Long-term potentiation (LTP): persistent strengthening of synapses based on activity patterns. Cellular mechanism of learning and memory.", "confidence": 0.97},
        {"text": "The default mode network: brain regions active during rest, self-referential thought, and mind-wandering. Deactivates during focused tasks.", "confidence": 0.95},
        {"text": "Consciousness correlates: the neural correlates of consciousness (NCC) are the minimal neural mechanisms sufficient for a specific conscious experience.", "confidence": 0.93},
        {"text": "The binding problem: how does the brain integrate information from different sensory modalities into unified conscious experience?", "confidence": 0.94},
        {"text": "Dopamine: neurotransmitter involved in reward, motivation, and reinforcement learning. Prediction error signal drives learning.", "confidence": 0.97},
        {"text": "The cerebellum contains ~80% of all neurons but primarily handles motor coordination, timing, and procedural memory.", "confidence": 0.96},
        {"text": "Mirror neurons: fire both when performing an action and observing the same action. Implicated in empathy and social cognition.", "confidence": 0.92},
        {"text": "Neuromorphic computing: hardware inspired by biological neural networks. Event-driven, energy-efficient, massively parallel.", "confidence": 0.94},
    ],
}


def seed_knowledge_graph(kg, block_height: int = 0) -> dict:
    """Seed the knowledge graph with real, verified knowledge.

    Idempotent: checks for existing genesis seeds and skips if already seeded.

    Args:
        kg: KnowledgeGraph instance
        block_height: Current block height for source_block attribution

    Returns:
        Dict with seeding statistics
    """
    if not kg:
        return {'error': 'No knowledge graph'}

    # Check if already seeded (look for genesis seed marker)
    for node in list(kg.nodes.values())[:1000]:
        if node.content.get('type') == 'genesis_seed_marker':
            logger.info("Knowledge graph already seeded — skipping")
            return {'already_seeded': True, 'nodes_existing': len(kg.nodes)}

    stats = {
        'nodes_created': 0,
        'edges_created': 0,
        'domains_seeded': 0,
        'errors': 0,
    }

    # Track node IDs per domain for cross-domain linking
    domain_nodes: Dict[str, List[int]] = {}

    for domain, facts in GENESIS_KNOWLEDGE.items():
        domain_node_ids = []
        for fact in facts:
            try:
                node = kg.add_node(
                    node_type='axiom',  # Axioms never decay
                    content={
                        'type': 'genesis_knowledge',
                        'text': fact['text'],
                        'domain': domain,
                        'source': 'genesis_seed',
                    },
                    confidence=fact['confidence'],
                    source_block=block_height,
                    domain=domain,
                )
                if node:
                    node.grounding_source = 'genesis_seed'
                    domain_node_ids.append(node.node_id)
                    stats['nodes_created'] += 1
            except Exception as e:
                stats['errors'] += 1
                logger.debug(f"Failed to seed node in {domain}: {e}")

        domain_nodes[domain] = domain_node_ids
        if domain_node_ids:
            stats['domains_seeded'] += 1

        # Create intra-domain 'supports' edges (chain sequential facts)
        for i in range(1, len(domain_node_ids)):
            try:
                kg.add_edge(domain_node_ids[i - 1], domain_node_ids[i], 'supports')
                stats['edges_created'] += 1
            except Exception:
                pass

    # Create cross-domain edges for related topics
    cross_domain_links = [
        ('quantum_physics', 'cryptography', 'derives'),      # QC threatens crypto
        ('quantum_physics', 'physics', 'derives'),            # QM from physics
        ('quantum_physics', 'computer_science', 'derives'),   # Quantum computing
        ('mathematics', 'computer_science', 'derives'),       # Math → CS
        ('mathematics', 'physics', 'derives'),                # Math → Physics
        ('mathematics', 'economics', 'derives'),              # Math → Econ
        ('mathematics', 'ai_ml', 'derives'),                  # Math → ML
        ('computer_science', 'blockchain', 'derives'),        # CS → Blockchain
        ('computer_science', 'ai_ml', 'derives'),             # CS → AI
        ('cryptography', 'blockchain', 'supports'),           # Crypto → Blockchain
        ('economics', 'blockchain', 'supports'),              # Econ → Blockchain
        ('ai_ml', 'neuroscience', 'derives'),                 # AI from Neuro
        ('neuroscience', 'biology', 'derives'),               # Neuro from Bio
        ('neuroscience', 'philosophy', 'derives'),            # Neuro → Philosophy of mind
        ('philosophy', 'ai_ml', 'supports'),                  # Philosophy → AI alignment
        ('physics', 'biology', 'derives'),                    # Biophysics
        ('blockchain', 'economics', 'supports'),              # Blockchain → Tokenomics
        ('ai_ml', 'blockchain', 'supports'),                  # AI → On-chain AGI
    ]

    for src_domain, dst_domain, edge_type in cross_domain_links:
        src_ids = domain_nodes.get(src_domain, [])
        dst_ids = domain_nodes.get(dst_domain, [])
        if src_ids and dst_ids:
            # Link first node of each domain
            try:
                kg.add_edge(src_ids[0], dst_ids[0], edge_type)
                stats['edges_created'] += 1
            except Exception:
                pass
            # Link last node of src to first node of dst (knowledge flow)
            if len(src_ids) > 1:
                try:
                    kg.add_edge(src_ids[-1], dst_ids[0], edge_type)
                    stats['edges_created'] += 1
                except Exception:
                    pass
            # Create analogous_to edges between domains with 3+ shared concepts
            if len(src_ids) >= 3 and len(dst_ids) >= 3:
                try:
                    kg.add_edge(src_ids[1], dst_ids[1], 'analogous_to')
                    stats['edges_created'] += 1
                except Exception:
                    pass

    # Add seed marker to prevent re-seeding
    try:
        marker = kg.add_node(
            node_type='axiom',
            content={
                'type': 'genesis_seed_marker',
                'text': 'Aether Tree genesis knowledge seeded',
                'nodes_created': stats['nodes_created'],
                'domains_seeded': stats['domains_seeded'],
                'edges_created': stats['edges_created'],
            },
            confidence=1.0,
            source_block=block_height,
            domain='ai_ml',
        )
        if marker:
            marker.grounding_source = 'genesis_seed'
            stats['nodes_created'] += 1
    except Exception:
        pass

    logger.info(
        f"Genesis knowledge seeded: {stats['nodes_created']} nodes, "
        f"{stats['edges_created']} edges, {stats['domains_seeded']} domains"
    )
    return stats
