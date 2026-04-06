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

# ── Wikipedia topics per knowledge domain ─────────────────────────────────────
# Used by internet workers to mine grounded factual knowledge without LLM.
_WIKI_TOPICS_BY_DOMAIN: Dict[str, List[str]] = {
    "quantum_physics": [
        "Quantum entanglement", "Superposition principle", "Wave function",
        "Quantum decoherence", "Bell's theorem", "Quantum tunnelling",
        "Schrödinger equation", "Quantum field theory", "Planck constant",
        "Heisenberg uncertainty principle",
    ],
    "ai_machine_learning": [
        "Transformer (deep learning)", "Reinforcement learning",
        "Neural network", "Large language model", "Backpropagation",
        "Attention mechanism", "Convolutional neural network",
        "Generative adversarial network", "Knowledge graph",
        "Artificial general intelligence",
    ],
    "mathematics": [
        "Gödel's incompleteness theorems", "Riemann hypothesis",
        "Topology", "Category theory", "Information theory",
        "Fourier analysis", "Prime number", "Golden ratio",
        "Graph theory", "Bayesian inference",
    ],
    "philosophy_of_mind": [
        "Consciousness", "Integrated information theory",
        "Hard problem of consciousness", "Qualia",
        "Functionalism (philosophy of mind)", "Emergentism",
        "Global workspace theory", "Embodied cognition",
        "Theory of mind", "Philosophical zombie",
    ],
    "neuroscience": [
        "Neuroplasticity", "Default mode network", "Long-term potentiation",
        "Cerebrospinal fluid", "Hippocampus", "Prefrontal cortex",
        "Synaptic pruning", "Mirror neuron", "Neurogenesis",
        "Brain–computer interface",
    ],
    "physics_general": [
        "Standard Model", "General relativity", "Quantum chromodynamics",
        "Dark matter", "Dark energy", "String theory",
        "Supersymmetry", "Higgs boson", "Black hole", "Entropy",
    ],
    "cryptography": [
        "Elliptic-curve cryptography", "Zero-knowledge proof",
        "Lattice-based cryptography", "Hash function",
        "Public-key cryptography", "Merkle tree", "Byzantine fault tolerance",
        "Post-quantum cryptography", "Homomorphic encryption", "Dilithium (cryptography)",
    ],
    "blockchain_fundamentals": [
        "Blockchain", "Bitcoin", "Ethereum", "Smart contract",
        "Proof of work", "Decentralized finance",
        "Unspent transaction output", "Consensus mechanism",
        "Cross-chain interoperability", "Layer 2 blockchain solution",
    ],
    "complexity_science": [
        "Emergence", "Complex system", "Self-organization",
        "Chaos theory", "Cellular automaton", "Phase transition",
        "Attractor", "Feedback", "Scale-free network", "Swarm intelligence",
    ],
    "information_theory": [
        "Shannon entropy", "Channel capacity", "Kolmogorov complexity",
        "Data compression", "Mutual information", "Entropy (information theory)",
        "Error correction code", "Algorithmic information theory",
        "Minimum description length", "Coding theory",
    ],
}

# ArXiv search terms by domain (maps to ArXiv category codes)
_ARXIV_QUERIES: List[Dict[str, str]] = [
    {"term": "quantum computing entanglement", "cat": "quant-ph"},
    {"term": "large language model reasoning", "cat": "cs.AI"},
    {"term": "integrated information theory consciousness", "cat": "q-bio.NC"},
    {"term": "knowledge graph embedding", "cat": "cs.LG"},
    {"term": "blockchain consensus scalability", "cat": "cs.CR"},
    {"term": "neural network interpretability", "cat": "cs.LG"},
    {"term": "causal inference discovery", "cat": "stat.ML"},
    {"term": "topological data analysis", "cat": "math.AT"},
    {"term": "quantum error correction", "cat": "quant-ph"},
    {"term": "reinforcement learning planning", "cat": "cs.AI"},
]

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
    # Internet workers (Wikipedia + ArXiv) — no Ollama, separate rate limit
    _NUM_INTERNET_WORKERS: int = 5
    # Minimum seconds between Wikipedia fetches per worker (be respectful)
    _INTERNET_COOLDOWN: float = 8.0

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
            "You are a knowledge source for the Aether Tree AGI. "
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
            "You are a knowledge source for the Aether Tree AGI. "
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
        if worker_id > 0:
            self._stop_event.wait(timeout=worker_id * 2.5)

        # Alternate between Wikipedia and ArXiv (per-worker, independent cooldown)
        sources = ['wikipedia', 'arxiv']
        source_idx = worker_id % len(sources)
        last_call: float = 0.0

        while not self._stop_event.is_set():
            try:
                now = time.time()
                if now - last_call >= self._INTERNET_COOLDOWN:
                    last_call = now
                    source = sources[source_idx % len(sources)]
                    source_idx += 1

                    if source == 'wikipedia':
                        created = self._mine_wikipedia(worker_id)
                    else:
                        created = self._mine_arxiv(worker_id)

                    if created > 0:
                        with self._internet_lock:
                            self._internet_nodes_created = getattr(
                                self, '_internet_nodes_created', 0
                            ) + created
            except Exception as e:
                logger.debug(f"Internet worker-{worker_id} error: {e}")

            self._stop_event.wait(timeout=4.0)

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
        domain_map = {
            'quantum_physics': 'quantum_physics',
            'ai_machine_learning': 'ai_ml',
            'mathematics': 'mathematics',
            'philosophy_of_mind': 'philosophy',
            'neuroscience': 'biology',
            'physics_general': 'quantum_physics',
            'cryptography': 'cryptography',
            'blockchain_fundamentals': 'blockchain',
            'complexity_science': 'philosophy',
            'information_theory': 'mathematics',
        }
        kg_domain = domain_map.get(domain, 'general')

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
                'start': '0',
                'max_results': '5',
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
                'cs.AI': 'ai_ml',
                'cs.LG': 'ai_ml',
                'cs.CR': 'cryptography',
                'q-bio.NC': 'biology',
                'stat.ML': 'ai_ml',
                'math.AT': 'mathematics',
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
