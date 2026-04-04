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
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

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

        # Rate limiting state
        self._calls_this_hour: int = 0
        self._hour_window_start: float = time.time()
        self._last_call_time: float = 0.0
        self._backoff_until: float = 0.0

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

    def start(self) -> None:
        """Start the background seeder daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Knowledge seeder already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="knowledge-seeder", daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Knowledge seeder started "
            f"(interval={Config.LLM_SEEDER_INTERVAL_BLOCKS} blocks, "
            f"rate_limit={Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR}/hr, "
            f"cooldown={Config.LLM_SEEDER_COOLDOWN_SECONDS}s)"
        )

    def stop(self) -> None:
        """Stop the background seeder."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
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
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "prompt_index": self._prompt_index,
            "total_prompts": len(MASTER_PROMPTS),
            "calls_this_hour": self._calls_this_hour,
            "rate_limit_per_hour": Config.LLM_SEEDER_RATE_LIMIT_PER_HOUR,
            "total_nodes_created": self._total_nodes_created,
            "total_tokens_used": self._total_tokens_used,
            "seeds_completed": len(self._history),
            "last_seed_height": self._last_seed_height,
            "recent_history": self._history[-10:],
        }

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main background loop — polls every 10s, seeds on interval."""
        while not self._stop_event.is_set():
            try:
                self._maybe_seed()
            except Exception as e:
                logger.error(f"Knowledge seeder error: {e}", exc_info=True)
            self._stop_event.wait(timeout=10)

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

        # Fallback: round-robin
        prompt = MASTER_PROMPTS[self._prompt_index % len(MASTER_PROMPTS)]
        self._prompt_index = (self._prompt_index + 1) % len(MASTER_PROMPTS)
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
        """Execute a single seed: query LLM, distill into KG."""
        domain = prompt_entry["domain"]
        prompt = prompt_entry["prompt"]

        # Build the system prompt with Aether context
        system_prompt = (
            "You are a knowledge source for the Aether Tree AGI. "
            "Be VERY BRIEF — 3-5 key facts only, each as a separate short sentence. "
            "Every sentence must be a standalone factual assertion. No elaboration."
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
            # Check for rate limit in error metadata
            error_msg = str(response.metadata.get("error", "")) if response else ""
            if "429" in error_msg or "rate" in error_msg.lower():
                self._backoff_until = time.time() + 60
                logger.warning(f"Seeder rate-limited via response, backing off 60s")
            return None

        self._calls_this_hour += 1
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
