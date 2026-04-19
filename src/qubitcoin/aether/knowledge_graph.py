"""
Knowledge Graph - KeterNode System
Manages the decentralized knowledge graph that forms the foundation of the Aether Tree.
Each node (KeterNode) represents a piece of verified knowledge; edges represent relationships.
"""
import asyncio
import hashlib
import json
import math
import os
import queue
import threading
import time
from collections import OrderedDict, deque
from collections.abc import MutableMapping
from dataclasses import dataclass, field, asdict
from typing import Deque, Dict, Iterator, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Edge bound — adjacency indices (_adj_out/_adj_in) provide O(1) lookup;
# the master edge list is a secondary record bounded to prevent OOM.
MAX_EDGES = 1_000_000
# Maximum edges per node in adjacency index — prevents hub nodes from
# accumulating unbounded adjacency lists.
MAX_ADJ_PER_NODE = 500

# Rust acceleration
_RUST_AVAILABLE = False
try:
    from .rust_bridge import RUST_AVAILABLE, RustKnowledgeGraph, RustKeterNode
    _RUST_AVAILABLE = RUST_AVAILABLE and RustKnowledgeGraph is not None
except ImportError:
    pass


@dataclass
class KeterNode:
    """
    A knowledge node in the Aether Tree.
    Named after Keter (Crown) in Kabbalistic Tree of Life — the highest sephira.
    """
    node_id: int = 0
    node_type: str = 'assertion'  # assertion, observation, inference, axiom, prediction, meta_observation
    content_hash: str = ''
    content: dict = field(default_factory=dict)
    confidence: float = 0.5  # [0.0, 1.0]
    source_block: int = 0
    timestamp: float = 0.0
    domain: str = ''  # Auto-assigned domain (quantum_physics, mathematics, etc.)
    last_referenced_block: int = 0  # Last block where this node was used in reasoning
    reference_count: int = 0  # How many times this node has been used in reasoning
    grounding_source: str = ''  # '', 'block_oracle', 'prediction_verified', 'qusd_oracle'
    # In-memory graph links
    edges_out: List[int] = field(default_factory=list)
    edges_in: List[int] = field(default_factory=list)

    def effective_confidence(self, current_block: int = 0) -> float:
        """Return confidence adjusted for exponential time-decay.

        Uses exponential decay with configurable half-life instead of linear,
        providing more realistic knowledge freshness modeling.
        Axioms never decay.  Floor is configurable (default 0.3) so old
        knowledge never fully vanishes.
        """
        if self.node_type == 'axiom' or current_block <= 0:
            return self.confidence
        from ..config import Config
        halflife = Config.CONFIDENCE_DECAY_HALFLIFE
        floor = Config.CONFIDENCE_DECAY_FLOOR
        ref_block = self.last_referenced_block or self.source_block
        age = max(0, current_block - ref_block)
        # Exponential decay: decay_factor = 2^(-age/halflife)
        if halflife > 0:
            decay = math.pow(2.0, -age / halflife)
        else:
            decay = 1.0
        decay = max(floor, decay)
        return self.confidence * decay

    def calculate_hash(self) -> str:
        data = json.dumps({
            'type': self.node_type,
            'content': self.content,
            'source_block': self.source_block,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop('edges_out', None)
        d.pop('edges_in', None)
        return d


@dataclass
class KeterEdge:
    """Directed edge between two KeterNodes"""
    from_node_id: int
    to_node_id: int
    edge_type: str = 'supports'  # supports, contradicts, derives, requires, refines, causes, abstracts, analogous_to
    weight: float = 1.0
    timestamp: float = 0.0


# Domain keyword mapping for auto-classification
DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
    'quantum_physics': {'qubit', 'quantum', 'superposition', 'entanglement', 'decoherence',
                        'hamiltonian', 'vqe', 'qiskit', 'photon', 'wave', 'particle',
                        'wavefunction', 'eigenstate', 'eigenvalue', 'hilbert', 'pauli',
                        'fermion', 'boson', 'spin', 'coherence', 'ansatz', 'hadamard',
                        'bloch', 'measurement', 'observable', 'density_matrix'},
    'mathematics': {'theorem', 'proof', 'algebra', 'topology', 'geometry', 'calculus',
                    'prime', 'fibonacci', 'equation', 'integral', 'matrix', 'vector',
                    'polynomial', 'logarithm', 'derivative', 'differential', 'manifold',
                    'eigenspace', 'determinant', 'convergence', 'isomorphism', 'phi',
                    'golden_ratio', 'fractal', 'modular', 'arithmetic'},
    'computer_science': {'algorithm', 'compiler', 'database', 'hash', 'binary',
                         'complexity', 'turing', 'sorting', 'graph_theory', 'recursion',
                         'concurrency', 'thread', 'mutex', 'cache', 'latency',
                         'throughput', 'api', 'protocol', 'serialization', 'bandwidth'},
    'blockchain': {'block', 'transaction', 'consensus', 'mining', 'utxo', 'merkle',
                   'ledger', 'token', 'smart_contract', 'defi', 'bridge', 'staking',
                   'difficulty', 'reward', 'halving', 'fee', 'node', 'peer', 'chain',
                   'supply', 'coinbase', 'nonce', 'hash_rate', 'proof', 'validator',
                   'wallet', 'address', 'mempool', 'orphan', 'fork', 'finality',
                   'gas', 'yield', 'liquidity', 'tvl', 'apy', 'amm', 'dex', 'vault',
                   'collateral', 'governance', 'dao', 'proposal', 'vote', 'treasury',
                   'block_height', 'block_hash', 'prev_hash', 'tx', 'txid',
                   'confirmations', 'blocktime', 'epoch', 'era', 'emission',
                   'miner', 'hashrate', 'propagation', 'reorg', 'sidechain',
                   'rollup', 'layer2', 'l2', 'swap', 'pool', 'lp', 'stake'},
    'cryptography': {'encryption', 'signature', 'dilithium', 'lattice', 'zero_knowledge',
                     'zkp', 'aes', 'rsa', 'cipher', 'post_quantum',
                     'hmac', 'sha256', 'sha3', 'keccak', 'kyber', 'kem',
                     'nist', 'keypair', 'public_key', 'private_key', 'signing',
                     'verification', 'digest', 'commitment', 'pedersen', 'bulletproof',
                     'stealth', 'zk_snark', 'zk_stark', 'poseidon', 'groth16'},
    'philosophy': {'consciousness', 'qualia', 'epistemology', 'ethics', 'ontology',
                   'kabbalah', 'sephirot', 'phenomenology', 'mind', 'metaphysics',
                   'keter', 'chochmah', 'binah', 'chesed', 'gevurah', 'tiferet',
                   'netzach', 'hod', 'yesod', 'malkuth', 'sephira', 'aether',
                   'cognition', 'awareness', 'reasoning', 'thought', 'philosophy'},
    'biology': {'neuron', 'dna', 'gene', 'evolution', 'cell', 'protein',
                'ecology', 'organism', 'neural', 'brain', 'synapse',
                'genome', 'mutation', 'phenotype', 'genotype', 'mitosis'},
    'physics': {'relativity', 'gravity', 'thermodynamics', 'entropy', 'energy',
                'electromagnetism', 'nuclear', 'optics', 'cosmology', 'dark_matter',
                'higgs', 'boson', 'susy', 'supersymmetry', 'field', 'force',
                'momentum', 'velocity', 'acceleration', 'mass', 'potential',
                'kinetic', 'photon', 'spectrum', 'planck'},
    'economics': {'market', 'inflation', 'monetary', 'gdp', 'trade',
                  'supply_demand', 'fiscal', 'currency', 'game_theory',
                  'price', 'exchange', 'rate', 'peg', 'stablecoin', 'qusd',
                  'reserve', 'arbitrage', 'oracle', 'volatility', 'hedge',
                  'portfolio', 'risk', 'return', 'profit', 'loss'},
    'ai_ml': {'transformer', 'neural_network', 'reinforcement', 'gradient',
              'backpropagation', 'llm', 'attention', 'embedding', 'training', 'inference',
              'classification', 'regression', 'clustering', 'overfitting',
              'dropout', 'batch_norm', 'convolution', 'gpt', 'bert', 'diffusion',
              'generative', 'discriminative', 'autoencoder', 'gan', 'rl'},
    'technology': {'software', 'hardware', 'server', 'cloud', 'docker', 'container',
                   'kubernetes', 'microservice', 'deployment', 'devops', 'ci_cd',
                   'linux', 'network', 'firewall', 'load_balancer', 'proxy',
                   'http', 'tcp', 'websocket', 'grpc', 'rest', 'json', 'yaml',
                   'git', 'version_control', 'monitoring', 'logging', 'metrics'},
}

# Bigram patterns for more accurate classification
DOMAIN_BIGRAMS: Dict[str, Set[str]] = {
    'blockchain': {'smart contract', 'block height', 'block hash', 'hash rate',
                   'block reward', 'gas fee', 'gas limit', 'chain id',
                   'block time', 'total supply', 'max supply', 'genesis block',
                   'merkle root', 'difficulty target', 'block observation',
                   'contract activity', 'mining pool', 'transaction fee',
                   'liquidity pool', 'yield farming', 'flash loan',
                   'price oracle', 'token swap', 'layer 2'},
    'quantum_physics': {'quantum state', 'quantum gate', 'quantum circuit',
                        'ground state', 'energy level', 'quantum computing',
                        'quantum observation', 'bell state', 'quantum error'},
    'cryptography': {'public key', 'private key', 'digital signature',
                     'zero knowledge', 'post quantum', 'key exchange',
                     'hash function', 'range proof', 'stealth address'},
    'ai_ml': {'neural network', 'deep learning', 'machine learning',
              'natural language', 'computer vision', 'reinforcement learning',
              'attention mechanism', 'loss function', 'gradient descent'},
    'economics': {'supply demand', 'game theory', 'monetary policy',
                  'price discovery', 'market cap', 'exchange rate'},
    'philosophy': {'tree of life', 'proof of thought', 'knowledge graph',
                   'consciousness metric', 'cognitive field'},
    'physics': {'dark matter', 'higgs field', 'dark energy',
                'general relativity', 'special relativity'},
}

# Content type keys that auto-classify to a domain
CONTENT_TYPE_DOMAIN_MAP: Dict[str, str] = {
    'block_observation': 'blockchain',
    'quantum_observation': 'quantum_physics',
    'contract_activity': 'blockchain',
    'transaction_observation': 'blockchain',
    'mining_observation': 'blockchain',
    'consensus_observation': 'blockchain',
    'network_observation': 'blockchain',
    'economic_observation': 'economics',
    'price_observation': 'economics',
    'stablecoin_observation': 'economics',
    'aether_observation': 'philosophy',
    'consciousness_observation': 'philosophy',
    'reasoning_observation': 'philosophy',
    'knowledge_observation': 'philosophy',
}

# Substring patterns that indicate a domain when found anywhere in text
DOMAIN_SUBSTRINGS: Dict[str, List[str]] = {
    'blockchain': ['blockchain', 'block_hash', 'prev_hash', 'block_height',
                   'coinbase', 'mempool', 'utxo', 'merkle', 'hashrate',
                   'finality', 'sidechain', 'rollup'],
    'quantum_physics': ['quantum', 'qubit', 'superposition', 'entangle',
                        'hamiltonian', 'eigenstate', 'wavefunction'],
    'cryptography': ['dilithium', 'encrypt', 'decrypt', 'cipher', 'signature',
                     'keypair', 'zkp', 'bulletproof', 'pedersen', 'poseidon'],
    'ai_ml': ['neural_net', 'backprop', 'gradient', 'transformer',
              'autoencoder', 'embedding'],
    'philosophy': ['sephir', 'kabbala', 'consciousness', 'cogniti'],
}


def classify_domain(content: dict) -> str:
    """Classify a knowledge node's domain from its content.

    Uses multi-strategy classification:
    1. Content type key auto-classification
    2. Bigram matching for multi-word terms
    3. Substring matching for compound words
    4. Single keyword matching
    Returns the best-matching domain or 'general' if no match at all.
    """
    # Strategy 0: Content type auto-classification
    content_type = content.get('type', '')
    if isinstance(content_type, str) and content_type in CONTENT_TYPE_DOMAIN_MAP:
        return CONTENT_TYPE_DOMAIN_MAP[content_type]

    text = ' '.join(str(v) for v in content.values()).lower()
    # Normalize separators for keyword matching but keep original for bigrams
    text_normalized = text.replace('-', '_').replace('.', ' ')
    words = set(text_normalized.split())

    scores: Dict[str, float] = {}

    # Strategy 1: Bigram matching (weighted 2x per match)
    for domain, bigrams in DOMAIN_BIGRAMS.items():
        for bigram in bigrams:
            if bigram in text:
                scores[domain] = scores.get(domain, 0) + 2.0

    # Strategy 2: Substring matching for compound words
    for domain, substrings in DOMAIN_SUBSTRINGS.items():
        for substr in substrings:
            if substr in text_normalized:
                scores[domain] = scores.get(domain, 0) + 1.5

    # Strategy 3: Single keyword matching (skip very short words to reduce false positives)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        matched = len(words & keywords)
        if matched > 0:
            # Penalize domains that only match on very common/ambiguous words
            # to avoid false positives like 'energy' matching physics for blockchain metrics
            ambiguous_words = {'energy', 'field', 'node', 'block', 'proof', 'rate',
                               'hash', 'risk', 'return', 'loss', 'pool', 'vote'}
            strong_matches = len((words & keywords) - ambiguous_words)
            weak_matches = matched - strong_matches
            scores[domain] = scores.get(domain, 0) + strong_matches + weak_matches * 0.3

    if not scores:
        return 'general'

    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain


class BoundedNodeCache(MutableMapping):
    """LRU-bounded cache for KeterNodes.

    Drop-in replacement for ``Dict[int, KeterNode]``.  Implements the full
    ``MutableMapping`` interface so every existing ``self.nodes[nid]``,
    ``self.nodes.get(nid)``, ``len(self.nodes)``, ``for n in self.nodes.values()``
    etc. works unchanged.

    When the cache exceeds *max_size*, the least-recently-used entries are
    evicted.  Eviction only removes the in-memory reference — the node still
    lives in CockroachDB and can be re-fetched on cache miss.
    """

    def __init__(self, max_size: int = 100_000) -> None:
        self._data: OrderedDict[int, 'KeterNode'] = OrderedDict()
        self._max_size = max_size
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    # --- MutableMapping required methods ---

    def __getitem__(self, key: int) -> 'KeterNode':
        try:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        except KeyError:
            self.misses += 1
            raise

    def __setitem__(self, key: int, value: 'KeterNode') -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        self._evict()

    def __delitem__(self, key: int) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[int]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    # --- Performance-critical overrides (avoid MutableMapping defaults) ---

    def get(self, key: int, default=None):
        try:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        except KeyError:
            self.misses += 1
            return default

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def pop(self, key: int, *args):
        return self._data.pop(key, *args)

    # --- Eviction ---

    def _evict(self) -> None:
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)
            self.evictions += 1

    # --- Stats ---

    def cache_stats(self) -> dict:
        total = self.hits + self.misses
        return {
            'size': len(self._data),
            'max_size': self._max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(self.hits / max(total, 1), 4),
            'evictions': self.evictions,
        }


class KnowledgeGraph:
    """
    In-memory knowledge graph backed by database persistence.
    Supports CRUD operations, graph traversal, and root hash computation.
    Includes a TF-IDF index for semantic search.
    """

    def __init__(self, db_manager):
        self.db = db_manager
        self._lock = threading.RLock()
        self.nodes: BoundedNodeCache = BoundedNodeCache(max_size=100_000)
        self.edges: Deque[KeterEdge] = deque(maxlen=MAX_EDGES)
        # O(1) edge adjacency index — avoids O(n) scans of self.edges
        self._adj_out: Dict[int, List[KeterEdge]] = {}  # node_id -> outgoing edges
        self._adj_in: Dict[int, List[KeterEdge]] = {}   # node_id -> incoming edges
        # O(1) domain index — avoids O(n) scans for domain-filtered queries
        self._domain_index: Dict[str, Set[int]] = {}  # domain -> set of node_ids
        self._next_id = 1
        # Merkle root cache — avoids O(n) recomputation per call
        self._merkle_dirty: bool = True
        self._merkle_cache: str = ''
        # TF-IDF semantic search index
        from .kg_index import TFIDFIndex
        self.search_index = TFIDFIndex()
        # Dense embedding vector index (semantic similarity)
        from .vector_index import VectorIndex
        self.vector_index = VectorIndex()

        # Distributed graph shard client (fire-and-forget replication).
        # Nodes/edges are replicated to the shard service for trillion-node scale.
        self._shard_client = None
        self._shard_loop = None
        try:
            shard_addr = os.environ.get('GRAPH_SHARD_ADDR', '')
            if shard_addr:
                from .shard_client import GraphShardClient
                self._shard_client = GraphShardClient(shard_addr)
                self._shard_loop = asyncio.new_event_loop()
                _t = threading.Thread(
                    target=self._shard_loop.run_forever,
                    name="kg-shard-loop", daemon=True,
                )
                _t.start()
                asyncio.run_coroutine_threadsafe(
                    self._shard_client.connect(), self._shard_loop
                )
                logger.info("KnowledgeGraph: shard replication to %s ACTIVE", shard_addr)
        except Exception as exc:
            logger.info("KnowledgeGraph: shard client not initialized: %s", exc)

        # Rust shadow graph for compute-heavy operations (Merkle root,
        # search, stats, phi computation). Bulk-loaded after DB load,
        # then kept in sync via add_node/add_edge.
        self._rust_kg = None
        if _RUST_AVAILABLE and RustKnowledgeGraph is not None:
            try:
                self._rust_kg = RustKnowledgeGraph()
                logger.info("KnowledgeGraph: Rust shadow graph ACTIVE")
            except Exception as exc:
                logger.warning("KnowledgeGraph: Rust shadow init failed: %s", exc)

        # Async write queue — node/edge DB persistence is non-blocking.
        # In-memory state is always consistent; DB is written asynchronously.
        self._write_queue: queue.Queue = queue.Queue(maxsize=50000)
        self._writer_stop = threading.Event()
        self._writer_thread = threading.Thread(
            target=self._async_writer, name="kg-db-writer", daemon=True
        )
        self._writer_thread.start()

        self._load_from_db()
        self._sync_rust_kg()

    def _load_from_db(self):
        """Load knowledge graph from database into memory.

        If the DB query fails mid-iteration (e.g. connection drop),
        partial data already loaded into self.nodes / self.edges is
        retained so the graph starts with whatever was successfully read.
        """
        nodes_loaded = 0
        edges_loaded = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                rows = session.execute(
                    text("""SELECT id, node_type, content_hash, content, confidence,
                                   source_block, domain, grounding_source,
                                   reference_count, last_referenced_block
                            FROM knowledge_nodes ORDER BY id""")
                )
                try:
                    for r in rows:
                        node = KeterNode(
                            node_id=r[0],
                            node_type=r[1],
                            content_hash=r[2],
                            content=json.loads(r[3]) if isinstance(r[3], str) else (r[3] or {}),
                            confidence=float(r[4] or 0.5),
                            source_block=r[5] or 0,
                            domain=r[6] or '',
                            grounding_source=r[7] or '',
                            reference_count=r[8] or 0,
                            last_referenced_block=r[9] or 0,
                        )
                        self.nodes[node.node_id] = node
                        self._next_id = max(self._next_id, node.node_id + 1)
                        # Maintain domain index during load
                        if node.domain:
                            self._domain_index.setdefault(node.domain, set()).add(node.node_id)
                        nodes_loaded += 1
                except Exception as e:
                    logger.warning(
                        f"Knowledge graph node iteration failed after {nodes_loaded} nodes: {e}; "
                        f"continuing with partial data"
                    )

                edge_rows = session.execute(
                    text("SELECT from_node_id, to_node_id, edge_type, weight FROM knowledge_edges ORDER BY id")
                )
                try:
                    for r in edge_rows:
                        edge = KeterEdge(
                            from_node_id=r[0], to_node_id=r[1],
                            edge_type=r[2], weight=float(r[3] or 1.0)
                        )
                        self.edges.append(edge)
                        self._adj_out.setdefault(r[0], []).append(edge)
                        self._adj_in.setdefault(r[1], []).append(edge)
                        if r[0] in self.nodes:
                            self.nodes[r[0]].edges_out.append(r[1])
                        if r[1] in self.nodes:
                            self.nodes[r[1]].edges_in.append(r[0])
                        edges_loaded += 1
                except Exception as e:
                    logger.warning(
                        f"Knowledge graph edge iteration failed after {edges_loaded} edges: {e}; "
                        f"continuing with partial data"
                    )

            # Build TF-IDF index, auto-classify domains and grounding for loaded nodes
            unclassified = 0
            grounded_count = 0
            _total = len(self.nodes)
            _progress_interval = max(1, _total // 10)  # log every 10%
            for _idx, (nid, node) in enumerate(self.nodes.items()):
                self.search_index.add_node(nid, node.content)
                if not node.domain:
                    node.domain = classify_domain(node.content)
                    unclassified += 1
                # Retroactively classify grounding_source for DB-loaded nodes
                if not node.grounding_source:
                    content = node.content if isinstance(node.content, dict) else {}
                    content_type = content.get('type', '')
                    has_block_ref = bool(content.get('block_height') or content.get('height'))
                    if node.node_type == 'observation' and has_block_ref:
                        node.grounding_source = 'block_oracle'
                        grounded_count += 1
                    elif node.node_type == 'axiom' and node.source_block == 0:
                        node.grounding_source = 'genesis_seed'
                        grounded_count += 1
                    elif content_type in ('quantum_observation', 'contract_activity',
                                         'temporal_pattern', 'difficulty_trend',
                                         'network_growth_inference', 'transaction_pattern',
                                         'activity_inference'):
                        node.grounding_source = 'block_oracle'
                        grounded_count += 1
                    elif content_type == 'prediction_confirmed':
                        node.grounding_source = 'prediction_verified'
                        grounded_count += 1
                    elif content.get('source', '').startswith('llm:'):
                        node.grounding_source = 'llm_distilled'
                        grounded_count += 1
                if (_idx + 1) % _progress_interval == 0:
                    logger.info(f"KG load progress: {_idx + 1}/{_total} nodes indexed ({(_idx + 1) * 100 // _total}%%)")

            # Skip bulk vector embedding at startup — too slow for 100K+ nodes.
            # Vectors are built incrementally as new nodes are added via _async_writer.
            if _total <= 10000:
                batch = {nid: node.content for nid, node in self.nodes.items()}
                embedded = self.vector_index.add_nodes_batch(batch)
                if embedded:
                    logger.info(f"Vector index: embedded {embedded} nodes")
            else:
                logger.info(f"Skipping bulk vector embedding for {_total} nodes (vectors built incrementally)")

            domain_counts = {}
            for node in self.nodes.values():
                d = node.domain or 'general'
                domain_counts[d] = domain_counts.get(d, 0) + 1

            # Pre-warm the TF-IDF index so first search doesn't stall 5-10s
            if hasattr(self.search_index, '_refresh_idf'):
                t_idf = time.time()
                self.search_index._refresh_idf()
                logger.info("TF-IDF IDF cache pre-warmed in %.1fms",
                            (time.time() - t_idf) * 1000)

            logger.info(f"Knowledge graph loaded: {len(self.nodes)} nodes, {len(self.edges)} edges, "
                         f"{self.search_index.get_stats()['unique_terms']} indexed terms, "
                         f"{len(domain_counts)} domains, {grounded_count} retroactively grounded"
                         + (f" ({unclassified} auto-classified)" if unclassified else ''))

            # Auto-compact routine block_observation bloat on startup.
            # On a 185K+ block chain, ~691K of ~695K nodes are routine empty
            # block observations that add zero knowledge value. Remove them.
            block_obs_count = sum(
                1 for n in self.nodes.values()
                if isinstance(n.content, dict) and n.content.get('type') == 'block_observation'
                and n.content.get('tx_count', 0) <= 1
                and not n.content.get('milestone')
                and not n.content.get('difficulty_shift')
                and not n.content.get('has_thought_proof')
            )
            if block_obs_count > 1000:
                logger.info(
                    "Auto-compacting %d routine block_observation nodes on startup...",
                    block_obs_count,
                )
                compacted = self.compact_block_observations()
                if compacted > 0:
                    # Refresh search index after mass removal
                    if hasattr(self.search_index, '_refresh_idf'):
                        self.search_index._idf_dirty = True
                        self.search_index._refresh_idf()

            # Persist domain + grounding classifications back to DB in background
            if unclassified > 0 or grounded_count > 0:
                self._start_background_metadata_persist(unclassified + grounded_count)

        except Exception as e:
            logger.warning(
                f"Knowledge graph DB load failed ({nodes_loaded} nodes, {edges_loaded} edges recovered): {e}"
            )

    def _start_background_metadata_persist(self, estimated_count: int) -> None:
        """Persist in-memory domain/grounding classifications back to DB."""
        import threading

        def _persist_worker() -> None:
            BATCH = 500
            updated = 0
            try:
                items = [
                    (n.node_id, n.domain, n.grounding_source)
                    for n in self.nodes.values()
                    if n.domain or n.grounding_source
                ]
                if not self._db_manager:
                    return
                for i in range(0, len(items), BATCH):
                    if self._writer_stop.is_set():
                        break
                    batch = items[i:i + BATCH]
                    try:
                        with self._db_manager.get_session() as session:
                            for node_id, domain, grounding in batch:
                                session.execute(
                                    "UPDATE knowledge_nodes SET domain = :d, grounding_source = :g "
                                    "WHERE node_id = :id AND (domain IS NULL OR domain = '' "
                                    "OR grounding_source IS NULL OR grounding_source = '')",
                                    {'d': domain or '', 'g': grounding or '', 'id': node_id}
                                )
                            session.commit()
                            updated += len(batch)
                    except Exception as e:
                        logger.debug("Metadata persist batch error: %s", e)
                    time.sleep(0.2)
                logger.info("Background metadata persist: %d nodes updated", updated)
            except Exception as e:
                logger.debug("Metadata persist worker error: %s", e)

        t = threading.Thread(target=_persist_worker, name="kg-metadata-persist", daemon=True)
        t.start()
        logger.info("Starting background metadata persist for ~%d nodes", estimated_count)

    def _start_background_vector_rebuild(self) -> None:
        """Start a low-priority background thread to embed existing nodes.

        Processes nodes in small batches with sleep between batches to avoid
        saturating CPU. Embeds ~500 nodes/sec on CPU-only (sentence-transformers).
        """
        import threading

        def _rebuild_worker():
            BATCH = 200
            SLEEP = 0.5  # seconds between batches — keep CPU available for mining
            total = 0
            try:
                node_items = list(self.nodes.items())
                for i in range(0, len(node_items), BATCH):
                    if self._writer_stop.is_set():
                        break
                    batch = {nid: node.content for nid, node in node_items[i:i + BATCH]}
                    try:
                        embedded = self.vector_index.add_nodes_batch(batch)
                        if embedded:
                            total += embedded
                    except Exception as e:
                        logger.debug(f"Background vector batch failed: {e}")
                    if i > 0 and i % (BATCH * 50) == 0:
                        logger.info(f"Background vector rebuild: {total} / {len(node_items)} embedded")
                    time.sleep(SLEEP)
                logger.info(f"Background vector rebuild complete: {total} nodes embedded")
                # Build the HNSW index now that all embeddings are loaded
                try:
                    hnsw = self.vector_index._ensure_py_hnsw()
                    if hnsw:
                        logger.info("Background vector rebuild: HNSW index built (%d vectors)", total)
                except Exception as e2:
                    logger.debug(f"HNSW build after vector rebuild failed: {e2}")
            except Exception as e:
                logger.warning(f"Background vector rebuild failed: {e}")

        t = threading.Thread(target=_rebuild_worker, daemon=True, name='kg-vector-rebuild')
        t.start()

    def _sync_rust_kg(self) -> None:
        """Bulk-load Python graph state into the Rust shadow graph.

        Called once after _load_from_db(). Subsequent mutations are synced
        incrementally in add_node() and add_edge().
        """
        if self._rust_kg is None:
            return
        try:
            nodes_snapshot = list(self.nodes.values())
            if not nodes_snapshot:
                return
            # Build Rust KeterNode list via add_node calls
            for node in nodes_snapshot:
                content = node.content if isinstance(node.content, dict) else {}
                # Convert all values to strings for Rust
                str_content = {str(k): str(v) for k, v in content.items()}
                self._rust_kg.add_node(
                    node.node_type, str_content, node.confidence,
                    node.source_block, node.domain or "",
                )
            # Bulk-load edges
            for edge in self.edges:
                self._rust_kg.add_edge(
                    edge.from_node_id, edge.to_node_id,
                    edge.edge_type, edge.weight,
                )
            logger.info(
                "Rust shadow KG synced: %d nodes, %d edges",
                self._rust_kg.node_count(), self._rust_kg.edge_count(),
            )
        except Exception as exc:
            logger.warning("Rust KG sync failed: %s — disabling shadow graph", exc)
            self._rust_kg = None

    def _async_writer(self) -> None:
        """Background thread: drain write queue and batch-commit to DB."""
        from sqlalchemy import text
        BATCH_SIZE = 200
        FLUSH_INTERVAL = 0.25  # seconds

        while not self._writer_stop.is_set():
            batch = []
            deadline = time.monotonic() + FLUSH_INTERVAL
            # Collect items until batch full or timeout
            while len(batch) < BATCH_SIZE:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    item = self._write_queue.get(timeout=min(remaining, FLUSH_INTERVAL))
                    batch.append(item)
                except queue.Empty:
                    break

            if not batch:
                continue

            # Separate DB items from vector items
            db_items = [i for i in batch if i[0] in ('node', 'edge')]
            vec_items = [i for i in batch if i[0] == 'vec']

            # Write DB batch in a single transaction
            if db_items:
                try:
                    with self.db.get_session() as session:
                        for item in db_items:
                            if item[0] == 'node':
                                _, node_id, ntype, chash, content_json, conf, sb, dom, gs, rc, lrb = item
                                session.execute(
                                    text("""
                                        INSERT INTO knowledge_nodes
                                            (id, node_type, content_hash, content, confidence,
                                             source_block, domain, grounding_source,
                                             reference_count, last_referenced_block)
                                        VALUES (:id, :ntype, :chash, CAST(:content AS jsonb), :conf,
                                                :sb, :dom, :gs, :rc, :lrb)
                                        ON CONFLICT (id) DO NOTHING
                                    """),
                                    {'id': node_id, 'ntype': ntype, 'chash': chash,
                                     'content': content_json, 'conf': conf, 'sb': sb,
                                     'dom': dom, 'gs': gs, 'rc': rc, 'lrb': lrb}
                                )
                            elif item[0] == 'edge':
                                _, fid, tid, etype, w = item
                                session.execute(
                                    text("""
                                        INSERT INTO knowledge_edges (from_node_id, to_node_id, edge_type, weight)
                                        VALUES (:fid, :tid, :etype, :w)
                                        ON CONFLICT (from_node_id, to_node_id, edge_type) DO UPDATE SET weight = :w
                                    """),
                                    {'fid': fid, 'tid': tid, 'etype': etype, 'w': w}
                                )
                        session.commit()
                except Exception as e:
                    logger.error(f"Async KG writer DB batch failed ({len(db_items)} items): {e}")

            # Vector embeddings DISABLED in background writer to prevent GIL starvation.
            # The _async_writer's synchronous Ollama HTTP calls (requests.post) hold the
            # GIL during response parsing, blocking the asyncio event loop and making the
            # API unresponsive. Embeddings are computed on-demand when needed for search.
            # Vec items are silently dropped — they can be regenerated later.
            embed_updates: List[Tuple[int, List[float]]] = []
            if vec_items:
                logger.debug(f"Skipped {len(vec_items)} vector embeddings (background writer disabled)")

            # Batch-write embeddings to CockroachDB (column is VECTOR(896))
            DB_EMBED_DIM = 896
            if embed_updates:
                try:
                    with self.db.get_session() as session:
                        for nid, vec in embed_updates:
                            # Resize to match DB column dimension
                            if len(vec) < DB_EMBED_DIM:
                                vec = vec + [0.0] * (DB_EMBED_DIM - len(vec))
                            elif len(vec) > DB_EMBED_DIM:
                                vec = vec[:DB_EMBED_DIM]
                            vec_str = '[' + ','.join(f'{v:.6f}' for v in vec) + ']'
                            session.execute(
                                text("""UPDATE knowledge_nodes
                                        SET embedding = :vec
                                        WHERE id = :nid"""),
                                {'nid': nid, 'vec': vec_str}
                            )
                        session.commit()
                except Exception as e:
                    logger.debug(f"Embedding DB persist failed: {e}")

                # Replicate embeddings to distributed shard service (HNSW vector index)
                self._shard_replicate_embeddings(embed_updates)

        # Drain remaining items on shutdown
        remaining_items = []
        while not self._write_queue.empty():
            try:
                remaining_items.append(self._write_queue.get_nowait())
            except queue.Empty:
                break
        if remaining_items:
            db_rem = [i for i in remaining_items if i[0] in ('node', 'edge')]
            if db_rem:
                try:
                    with self.db.get_session() as session:
                        for item in db_rem:
                            if item[0] == 'node':
                                _, node_id, ntype, chash, content_json, conf, sb, dom, gs, rc, lrb = item
                                session.execute(
                                    text("""
                                        INSERT INTO knowledge_nodes
                                            (id, node_type, content_hash, content, confidence,
                                             source_block, domain, grounding_source,
                                             reference_count, last_referenced_block)
                                        VALUES (:id, :ntype, :chash, CAST(:content AS jsonb), :conf,
                                                :sb, :dom, :gs, :rc, :lrb)
                                        ON CONFLICT (id) DO NOTHING
                                    """),
                                    {'id': node_id, 'ntype': ntype, 'chash': chash,
                                     'content': content_json, 'conf': conf, 'sb': sb,
                                     'dom': dom, 'gs': gs, 'rc': rc, 'lrb': lrb}
                                )
                            elif item[0] == 'edge':
                                _, fid, tid, etype, w = item
                                session.execute(
                                    text("""
                                        INSERT INTO knowledge_edges (from_node_id, to_node_id, edge_type, weight)
                                        VALUES (:fid, :tid, :etype, :w)
                                        ON CONFLICT (from_node_id, to_node_id, edge_type) DO UPDATE SET weight = :w
                                    """),
                                    {'fid': fid, 'tid': tid, 'etype': etype, 'w': w}
                                )
                        session.commit()
                except Exception as e:
                    logger.error(f"Async KG writer shutdown flush failed: {e}")

    def add_node(self, node_type: str, content: dict, confidence: float,
                 source_block: int, domain: str = '') -> KeterNode:
        """Add a new knowledge node"""
        with self._lock:
            node = KeterNode(
                node_id=self._next_id,
                node_type=node_type,
                content=content,
                confidence=max(0.0, min(1.0, confidence)),
                source_block=source_block,
                timestamp=time.time(),
                domain=domain or classify_domain(content),
                last_referenced_block=source_block,
            )
            node.content_hash = node.calculate_hash()
            self._next_id += 1
            self.nodes[node.node_id] = node
            self._merkle_dirty = True
            # Maintain domain index
            if node.domain:
                self._domain_index.setdefault(node.domain, set()).add(node.node_id)

        # Update TF-IDF index synchronously (fast — no model inference)
        self.search_index.add_node(node.node_id, content)

        # Sync to Rust shadow graph (non-blocking, fire-and-forget)
        if getattr(self, '_rust_kg', None) is not None:
            try:
                str_content = {str(k): str(v) for k, v in content.items()} if isinstance(content, dict) else {}
                self._rust_kg.add_node(
                    node.node_type, str_content, node.confidence,
                    source_block, node.domain or "",
                )
            except Exception:
                pass  # Rust shadow is best-effort

        # Vector embedding is async — enqueued alongside DB write to avoid
        # blocking on sentence-transformer model.encode() per node.
        # Persist asynchronously via write queue (non-blocking).
        # Guard with hasattr: tests may instantiate KnowledgeGraph via __new__
        # without calling __init__, so _write_queue may not exist.
        if hasattr(self, '_write_queue'):
            try:
                self._write_queue.put_nowait((
                    'node', node.node_id, node.node_type, node.content_hash,
                    json.dumps(node.content), node.confidence, source_block,
                    node.domain, node.grounding_source, node.reference_count,
                    node.last_referenced_block,
                ))
                # Queue vector embedding update (the sentence-transformer model call)
                self._write_queue.put_nowait(('vec', node.node_id, content))
            except queue.Full:
                logger.warning("KG write queue full — dropping node persist for id=%d", node.node_id)

        # Replicate to distributed shard service (fire-and-forget)
        self._shard_replicate_node(node, content)

        return node

    def add_edge(self, from_id: int, to_id: int, edge_type: str = 'supports',
                 weight: float = 1.0) -> Optional[KeterEdge]:
        """Add a directed edge between two nodes"""
        with self._lock:
            if from_id not in self.nodes or to_id not in self.nodes:
                logger.warning(f"Cannot add edge: node {from_id} or {to_id} not found")
                return None

            edge = KeterEdge(
                from_node_id=from_id, to_node_id=to_id,
                edge_type=edge_type, weight=weight,
                timestamp=time.time()
            )
            self.edges.append(edge)
            out_list = self._adj_out.setdefault(from_id, [])
            out_list.append(edge)
            if len(out_list) > MAX_ADJ_PER_NODE:
                # Evict oldest edges from this node's adjacency list
                self._adj_out[from_id] = out_list[-MAX_ADJ_PER_NODE:]
            in_list = self._adj_in.setdefault(to_id, [])
            in_list.append(edge)
            if len(in_list) > MAX_ADJ_PER_NODE:
                self._adj_in[to_id] = in_list[-MAX_ADJ_PER_NODE:]
            self._merkle_dirty = True
            self.nodes[from_id].edges_out.append(to_id)
            self.nodes[to_id].edges_in.append(from_id)

        # Sync to Rust shadow graph
        if getattr(self, '_rust_kg', None) is not None:
            try:
                self._rust_kg.add_edge(from_id, to_id, edge_type, weight)
            except Exception:
                pass

        # Persist asynchronously via write queue (non-blocking)
        if hasattr(self, '_write_queue'):
            try:
                self._write_queue.put_nowait(('edge', from_id, to_id, edge_type, weight))
            except queue.Full:
                logger.warning("KG write queue full — dropping edge persist %d→%d", from_id, to_id)

        # Replicate to distributed shard service (fire-and-forget)
        self._shard_replicate_edge(from_id, to_id, edge_type, weight)

        return edge

    def _shard_replicate_node(self, node: 'KeterNode', content: dict) -> None:
        """Fire-and-forget replication of a node to the shard service."""
        client = getattr(self, '_shard_client', None)
        loop = getattr(self, '_shard_loop', None)
        if client is None or loop is None or not client.connected:
            return
        try:
            str_content = {str(k): str(v) for k, v in content.items()} if isinstance(content, dict) else {}
            asyncio.run_coroutine_threadsafe(
                client.put_node(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    content=str_content,
                    confidence=node.confidence,
                    source_block=node.source_block,
                    domain=node.domain or 'general',
                    grounding_source=node.grounding_source or '',
                ),
                loop,
            )
        except Exception:
            pass  # Best-effort replication

    def _shard_replicate_edge(self, from_id: int, to_id: int, edge_type: str, weight: float) -> None:
        """Fire-and-forget replication of an edge to the shard service."""
        client = getattr(self, '_shard_client', None)
        loop = getattr(self, '_shard_loop', None)
        if client is None or loop is None or not client.connected:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                client.put_edge(from_id, to_id, edge_type, weight),
                loop,
            )
        except Exception:
            pass  # Best-effort replication

    def _shard_replicate_embeddings(self, embed_updates: list) -> None:
        """Fire-and-forget replication of embeddings to shard service.

        Called by the async writer after computing embeddings. Updates the
        shard service nodes with their embedding vectors so the Rust HNSW
        vector index is populated.
        """
        client = getattr(self, '_shard_client', None)
        loop = getattr(self, '_shard_loop', None)
        if client is None or loop is None or not client.connected:
            return
        if not embed_updates:
            return

        for node_id, embedding in embed_updates:
            try:
                node = self.nodes.get(node_id)
                if node is None:
                    continue
                content = node.content if isinstance(node.content, dict) else {}
                str_content = {str(k): str(v) for k, v in content.items()}
                asyncio.run_coroutine_threadsafe(
                    client.put_node(
                        node_id=node.node_id,
                        node_type=node.node_type,
                        content=str_content,
                        confidence=node.confidence,
                        source_block=node.source_block,
                        domain=node.domain or 'general',
                        grounding_source=node.grounding_source or '',
                        embedding=embedding,
                    ),
                    loop,
                )
            except Exception:
                pass  # Best-effort replication

    def sync_all_to_shards(self) -> dict:
        """Bulk-load ALL in-memory nodes and edges to the shard service.

        Returns stats dict with nodes_synced, edges_synced, duration_s.
        Runs synchronously — may take 30-120s for 100K+ nodes.
        """
        client = getattr(self, '_shard_client', None)
        loop = getattr(self, '_shard_loop', None)
        if client is None or loop is None or not client.connected:
            return {"error": "shard client not connected"}

        import time as _time
        t0 = _time.time()
        BATCH = 500

        # Collect all nodes
        with self._lock:
            all_nodes = list(self.nodes.values())
            all_edges = list(self.edges)

        logger.info("sync_all_to_shards: %d nodes, %d edges", len(all_nodes), len(all_edges))

        # Bulk-load nodes in batches (with embeddings from vector_index)
        nodes_synced = 0
        embed_count = 0
        for i in range(0, len(all_nodes), BATCH):
            batch = all_nodes[i:i + BATCH]
            records = []
            for n in batch:
                content = n.content if isinstance(n.content, dict) else {}
                # Include embedding if available in vector_index
                embedding = None
                if hasattr(self, 'vector_index') and self.vector_index:
                    embedding = self.vector_index.get_vector(n.node_id)
                if embedding:
                    embed_count += 1
                records.append({
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "content": {str(k): str(v) for k, v in content.items()},
                    "confidence": n.confidence,
                    "source_block": n.source_block,
                    "domain": n.domain or "general",
                    "grounding_source": n.grounding_source or "",
                    "embedding": embedding,
                })

            future = asyncio.run_coroutine_threadsafe(
                client.bulk_put_nodes(records), loop
            )
            try:
                result = future.result(timeout=60.0)
                if result:
                    nodes_synced += result.get("nodes_written", 0)
            except Exception as exc:
                logger.warning("sync_all_to_shards batch %d failed: %s", i, exc)

            if (i // BATCH) % 20 == 0:
                logger.info("sync_all_to_shards: %d/%d nodes", nodes_synced, len(all_nodes))

        # Bulk-load edges in batches
        edges_synced = 0
        EDGE_BATCH = 2000
        for i in range(0, len(all_edges), EDGE_BATCH):
            batch = all_edges[i:i + EDGE_BATCH]
            records = [
                {
                    "from_node_id": e.from_node_id,
                    "to_node_id": e.to_node_id,
                    "edge_type": e.edge_type,
                    "weight": e.weight,
                }
                for e in batch
            ]
            future = asyncio.run_coroutine_threadsafe(
                client.bulk_put_edges(records), loop
            )
            try:
                result = future.result(timeout=120.0)
                if result:
                    edges_synced += result.get("edges_written", 0)
            except Exception as exc:
                logger.warning("sync_all_to_shards edge batch %d failed: %s", i, exc)

            if (i // EDGE_BATCH) % 20 == 0:
                logger.info("sync_all_to_shards: %d/%d edges", edges_synced, len(all_edges))

        elapsed = _time.time() - t0
        stats = {
            "nodes_synced": nodes_synced,
            "edges_synced": edges_synced,
            "embeddings_synced": embed_count,
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "duration_s": round(elapsed, 1),
        }
        logger.info("sync_all_to_shards complete: %s", stats)
        return stats

    def get_node(self, node_id: int) -> Optional[KeterNode]:
        """Return a KeterNode by its ID, or None if not found.

        Checks the in-memory LRU cache first; on miss, fetches from
        CockroachDB and populates the cache.
        """
        with self._lock:
            cached = self.nodes.get(node_id)
            if cached is not None:
                return cached
        # Cache miss — try DB
        return self._db_get_node(node_id)

    def _db_get_node(self, node_id: int) -> Optional[KeterNode]:
        """Fetch a single node from CockroachDB by ID and populate cache."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                row = session.execute(
                    text("""SELECT id, node_type, content_hash, content, confidence,
                                   source_block, domain, grounding_source,
                                   reference_count, last_referenced_block
                            FROM knowledge_nodes WHERE id = :nid"""),
                    {'nid': node_id}
                ).fetchone()
            if row is None:
                return None
            node = self._row_to_node(row)
            with self._lock:
                self.nodes[node.node_id] = node
            return node
        except Exception:
            return None

    def get_nodes_by_domain(self, domain: str, limit: int = 200) -> List[KeterNode]:
        """Return nodes for a given domain using O(1) domain index.

        Args:
            domain: Domain string to filter by.
            limit: Maximum nodes to return.

        Returns:
            List of KeterNode instances in the domain.
        """
        node_ids = self._domain_index.get(domain, set())
        result: List[KeterNode] = []
        for nid in node_ids:
            if len(result) >= limit:
                break
            node = self.nodes.get(nid)
            if node is not None:
                result.append(node)
        return result

    def get_domains(self) -> List[str]:
        """Return list of all domains with at least one node."""
        return [d for d, ids in self._domain_index.items() if ids]

    def get_neighbors(self, node_id: int, direction: str = 'out') -> List[KeterNode]:
        """Get neighboring nodes"""
        with self._lock:
            node = self.nodes.get(node_id)
            if not node:
                return []
            ids = node.edges_out if direction == 'out' else node.edges_in
            return [self.nodes[nid] for nid in ids if nid in self.nodes]

    def get_subgraph(self, root_id: int, depth: int = 3) -> Dict[int, KeterNode]:
        """BFS to get subgraph up to given depth"""
        with self._lock:
            visited: Dict[int, KeterNode] = {}
            queue = deque([(root_id, 0)])

            while queue:
                nid, d = queue.popleft()
                if nid in visited or d > depth:
                    continue
                node = self.nodes.get(nid)
                if not node:
                    continue
                visited[nid] = node
                for neighbor_id in node.edges_out + node.edges_in:
                    if neighbor_id not in visited:
                        queue.append((neighbor_id, d + 1))

            return visited

    def find_paths(self, from_id: int, to_id: int, max_depth: int = 5) -> List[List[int]]:
        """Find all paths between two nodes up to max_depth"""
        paths = []

        def _dfs(current: int, target: int, path: List[int], visited: Set[int]):
            if len(path) > max_depth:
                return
            if current == target:
                paths.append(list(path))
                return
            node = self.nodes.get(current)
            if not node:
                return
            for nid in node.edges_out:
                if nid not in visited:
                    visited.add(nid)
                    path.append(nid)
                    _dfs(nid, target, path, visited)
                    path.pop()
                    visited.remove(nid)

        _dfs(from_id, to_id, [from_id], {from_id})
        return paths

    def propagate_confidence(self, node_id: int, iterations: int = 3,
                             damping: float = 0.5, epsilon: float = 0.001):
        """
        Propagate confidence scores through the graph with convergence guarantee.

        Uses damping factor to prevent oscillation and early stopping when
        max delta falls below epsilon.

        Args:
            node_id: Starting node for propagation (currently propagates
                globally — the parameter is accepted for API compatibility).
            iterations: Maximum iterations.
            damping: Damping factor in (0, 1] to prevent oscillation.
            epsilon: Convergence threshold — stop when max delta < epsilon.
        """
        with self._lock:
            for iteration in range(iterations):
                updates = {}
                max_delta = 0.0
                for nid, node in list(self.nodes.items()):
                    if not node.edges_in:
                        continue
                    support_sum = 0.0
                    contradict_sum = 0.0
                    count = 0
                    for edge in self._adj_in.get(nid, []):
                        parent = self.nodes.get(edge.from_node_id)
                        if not parent:
                            continue
                        if edge.edge_type in ('supports', 'derives'):
                            support_sum += parent.confidence * edge.weight
                            count += 1
                        elif edge.edge_type == 'contradicts':
                            contradict_sum += parent.confidence * edge.weight
                            count += 1

                    if count > 0:
                        # Weighted update with damping to prevent oscillation
                        raw_delta = (support_sum - contradict_sum) / count * 0.1
                        damped_delta = raw_delta * damping
                        new_conf = max(0.0, min(1.0, node.confidence + damped_delta))
                        delta = abs(new_conf - node.confidence)
                        if delta > max_delta:
                            max_delta = delta
                        updates[nid] = new_conf

                for nid, conf in updates.items():
                    self.nodes[nid].confidence = conf

                # Early stopping on convergence
                if max_delta < epsilon:
                    break

    def compute_knowledge_root(self) -> str:
        """
        Compute Merkle root hash of the entire knowledge graph.
        Used in Proof-of-Thought for chain binding.
        Cached — only recomputes when graph is mutated.

        Takes a snapshot under the lock, then computes the Merkle tree
        outside the lock so add_node() is never blocked.
        """
        # Rust acceleration for Merkle root computation
        if getattr(self, '_rust_kg', None) is not None and self._merkle_dirty:
            try:
                root = self._rust_kg.compute_knowledge_root()
                if root:
                    with self._lock:
                        self._merkle_cache = root
                        self._merkle_dirty = False
                    return root
            except Exception as exc:
                logger.debug("Rust compute_knowledge_root failed: %s", exc)

        with self._lock:
            if not self.nodes:
                return hashlib.sha256(b'empty_knowledge').hexdigest()
            if not self._merkle_dirty and self._merkle_cache:
                return self._merkle_cache
            # Snapshot: only the data needed for hashing (brief, O(n) alloc)
            snapshot = [
                (nid, self.nodes[nid].content_hash, self.nodes[nid].confidence)
                for nid in sorted(self.nodes.keys())
            ]

        # Merkle computation outside the lock — add_node() can proceed freely
        leaves = [
            hashlib.sha256(
                f"{nid}:{ch}:{conf:.6f}".encode()
            ).hexdigest()
            for nid, ch, conf in snapshot
        ]

        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = hashlib.sha256(
                    (leaves[i] + leaves[i + 1]).encode()
                ).hexdigest()
                new_leaves.append(combined)
            leaves = new_leaves

        root = leaves[0]
        with self._lock:
            self._merkle_cache = root
            self._merkle_dirty = False
        return root

    def gc_adjacency(self) -> int:
        """Garbage-collect adjacency indices for nodes no longer in the graph.

        Over time, node eviction from BoundedNodeCache and deque auto-discard
        can leave orphaned entries in _adj_out / _adj_in.  This method removes
        them, preventing unbounded memory growth in the adjacency dicts.

        Returns:
            Number of orphaned adjacency keys removed.
        """
        removed = 0
        with self._lock:
            live_ids = set(self.nodes.keys())
            for adj in (self._adj_out, self._adj_in):
                orphan_keys = [k for k in adj if k not in live_ids]
                for k in orphan_keys:
                    del adj[k]
                    removed += 1
        if removed:
            logger.info("gc_adjacency: removed %d orphaned adjacency entries", removed)
        return removed

    def prune_low_confidence(self, threshold: float = 0.1, protect_types: Optional[Set[str]] = None) -> int:
        """
        Remove nodes with confidence below threshold from memory AND database.

        Nodes of protected types (e.g. 'axiom') are never pruned.
        Edges referencing pruned nodes are also removed.

        Args:
            threshold: Minimum confidence to keep a node
            protect_types: Node types that are never pruned

        Returns:
            Number of nodes removed
        """
        protect = protect_types or {'axiom'}
        to_remove = [
            nid for nid, node in self.nodes.items()
            if node.confidence < threshold and node.node_type not in protect
        ]

        if not to_remove:
            return 0

        # Remove from in-memory graph — single-pass over edges using a set
        remove_set = set(to_remove)
        with self._lock:
            self.edges = deque(
                (e for e in self.edges
                 if e.from_node_id not in remove_set and e.to_node_id not in remove_set),
                maxlen=MAX_EDGES,
            )
            # Clean adjacency indices and node cross-references in one pass.
            # Uses adj index to update only affected neighbors: O(degree) per node
            # instead of the old O(N) scan of all nodes per removed node.
            for nid in remove_set:
                for edge in self._adj_out.get(nid, []):
                    adj_list = self._adj_in.get(edge.to_node_id, [])
                    self._adj_in[edge.to_node_id] = [e for e in adj_list if e.from_node_id != nid]
                    # Also clean the neighbor's edges_in list
                    neighbor = self.nodes.get(edge.to_node_id)
                    if neighbor and nid in neighbor.edges_in:
                        neighbor.edges_in.remove(nid)
                for edge in self._adj_in.get(nid, []):
                    adj_list = self._adj_out.get(edge.from_node_id, [])
                    self._adj_out[edge.from_node_id] = [e for e in adj_list if e.to_node_id != nid]
                    # Also clean the neighbor's edges_out list
                    neighbor = self.nodes.get(edge.from_node_id)
                    if neighbor and nid in neighbor.edges_out:
                        neighbor.edges_out.remove(nid)
                self._adj_out.pop(nid, None)
                self._adj_in.pop(nid, None)
                del self.nodes[nid]
            self._merkle_dirty = True

        # Cascade prune to search and vector indices
        for nid in remove_set:
            if hasattr(self, 'search_index') and self.search_index is not None:
                try:
                    self.search_index.remove_node(nid)
                except Exception:
                    pass
            if hasattr(self, 'vector_index') and self.vector_index is not None:
                try:
                    self.vector_index.remove_node(nid)
                except Exception:
                    pass

        # Delete from database
        db_deleted_nodes = 0
        db_deleted_edges = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                # Delete edges first (referential integrity)
                result = session.execute(
                    text("""
                        DELETE FROM knowledge_edges
                        WHERE from_node_id = ANY(:ids) OR to_node_id = ANY(:ids)
                    """),
                    {"ids": to_remove}
                )
                db_deleted_edges = result.rowcount

                # Delete nodes
                result = session.execute(
                    text("DELETE FROM knowledge_nodes WHERE id = ANY(:ids)"),
                    {"ids": to_remove}
                )
                db_deleted_nodes = result.rowcount

                session.commit()
        except Exception as e:
            logger.error(f"Failed to delete pruned nodes from DB: {e}")

        # Also GC any adjacency entries orphaned by BoundedNodeCache eviction
        self.gc_adjacency()

        logger.info(
            f"Pruned {len(to_remove)} low-confidence nodes (threshold={threshold}), "
            f"DB: {db_deleted_nodes} nodes + {db_deleted_edges} edges deleted"
        )
        return len(to_remove)

    def persist_confidence_updates(self) -> int:
        """
        Write changed confidence, domain, grounding, and reference data back to DB.

        Called periodically (e.g. every 100 blocks) to ensure that
        in-memory state changes from reasoning/propagation survive restarts.

        Uses a single batch UPDATE via UNNEST for massive speedup over
        per-row updates (1 round-trip instead of N).

        Returns:
            Number of rows updated.
        """
        if not self.nodes:
            return 0

        try:
            from sqlalchemy import text
            # Collect all node metadata
            ids = []
            confs = []
            domains = []
            groundings = []
            ref_counts = []
            last_refs = []
            for nid, node in self.nodes.items():
                ids.append(nid)
                confs.append(round(node.confidence, 8))
                domains.append(node.domain or '')
                groundings.append(node.grounding_source or '')
                ref_counts.append(node.reference_count)
                last_refs.append(node.last_referenced_block)

            if not ids:
                return 0

            # Batch update using UNNEST — single SQL round-trip
            BATCH_SIZE = 5000
            updated = 0
            with self.db.get_session() as session:
                for i in range(0, len(ids), BATCH_SIZE):
                    bi = ids[i:i + BATCH_SIZE]
                    bc = confs[i:i + BATCH_SIZE]
                    bd = domains[i:i + BATCH_SIZE]
                    bg = groundings[i:i + BATCH_SIZE]
                    br = ref_counts[i:i + BATCH_SIZE]
                    bl = last_refs[i:i + BATCH_SIZE]
                    result = session.execute(
                        text("""
                            UPDATE knowledge_nodes AS kn
                            SET confidence = batch.conf,
                                domain = batch.dom,
                                grounding_source = batch.gs,
                                reference_count = batch.rc,
                                last_referenced_block = batch.lrb
                            FROM (SELECT UNNEST(:ids) AS id,
                                         UNNEST(:confs) AS conf,
                                         UNNEST(:doms) AS dom,
                                         UNNEST(:gss) AS gs,
                                         UNNEST(:rcs) AS rc,
                                         UNNEST(:lrbs) AS lrb) AS batch
                            WHERE kn.id = batch.id
                              AND (kn.confidence != batch.conf
                                   OR kn.domain != batch.dom
                                   OR kn.grounding_source != batch.gs
                                   OR kn.reference_count != batch.rc
                                   OR kn.last_referenced_block != batch.lrb)
                        """),
                        {'ids': bi, 'confs': bc, 'doms': bd,
                         'gss': bg, 'rcs': br, 'lrbs': bl}
                    )
                    updated += result.rowcount
                session.commit()

            if updated > 0:
                logger.info(f"Persisted metadata updates for {updated} nodes (batch)")
            return updated
        except Exception as e:
            logger.error(f"Failed to persist metadata updates: {e}")
            return 0

    def search(self, query: str, top_k: int = 10) -> List[Tuple[KeterNode, float]]:
        """
        Semantic search blending TF-IDF keyword match + dense vector similarity.

        Uses in-memory TF-IDF + vector index for speed, with DB text search
        as supplemental source for broader coverage of 700K+ nodes.

        Args:
            query: Natural language search query
            top_k: Maximum results to return

        Returns:
            List of (KeterNode, similarity_score) tuples, best match first.
        """
        import time as _time
        _t0 = _time.monotonic()

        # TF-IDF results (keyword match)
        tfidf_results = self.search_index.query(query, top_k=top_k * 2)
        _t1 = _time.monotonic()

        # Vector results (semantic similarity)
        vector_results = self.vector_index.query(query, top_k=top_k * 2)
        _t2 = _time.monotonic()

        # Blend scores: 0.4 * tfidf + 0.6 * vector (semantic weighs more)
        scores: Dict[int, float] = {}
        for nid, score in tfidf_results:
            scores[nid] = scores.get(nid, 0.0) + 0.4 * score
        for nid, score in vector_results:
            scores[nid] = scores.get(nid, 0.0) + 0.6 * score

        # DB text search as supplemental source (catches nodes not in memory/index)
        try:
            db_results = self._db_text_search(query, limit=top_k * 2)
            for nid, score in db_results:
                # Lower weight for DB results to not overwhelm in-memory matches
                scores[nid] = scores.get(nid, 0.0) + 0.3 * score
        except Exception:
            pass  # DB search is best-effort supplemental
        _t3 = _time.monotonic()

        if (_t3 - _t0) > 2.0:
            logger.warning(
                "KG search slow: tfidf=%.1fs vec=%.1fs db=%.1fs total=%.1fs q=%s",
                _t1 - _t0, _t2 - _t1, _t3 - _t2, _t3 - _t0, query[:60],
            )

        # Sort by blended score, return top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            (self.nodes.get(nid, self._row_to_node_safe(nid)), score)
            for nid, score in ranked
            if nid in self.nodes or self._node_exists_in_db(nid)
        ]

    def _db_text_search(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        """Search knowledge_nodes using search_text column with LIKE.

        Uses idx_kn_search_text index. Returns (node_id, relevance_score) tuples.
        """
        from sqlalchemy import text
        # Split query into keywords, search with ILIKE for each
        keywords = [w.strip().lower() for w in query.split() if len(w.strip()) >= 3]
        if not keywords:
            return []

        # Build WHERE clause: search_text ILIKE '%keyword%' for each keyword
        # Use the first 3 keywords to keep the query fast
        conditions = []
        params: dict = {'lim': limit}
        for i, kw in enumerate(keywords[:3]):
            conditions.append(f"search_text ILIKE :kw{i}")
            params[f'kw{i}'] = f'%{kw}%'

        where = ' AND '.join(conditions)
        with self.db.get_session() as session:
            # Set 3s timeout to prevent ILIKE full-scan from blocking GWT processors
            session.execute(text("SET statement_timeout = '3s'"))
            try:
                rows = session.execute(
                    text(f"""SELECT id, confidence
                             FROM knowledge_nodes
                             WHERE {where}
                             ORDER BY confidence DESC
                             LIMIT :lim"""),
                    params
                ).fetchall()
            finally:
                session.execute(text("SET statement_timeout = '0'"))
        # Normalize confidence as relevance score
        return [(r[0], float(r[1] or 0.5)) for r in rows]

    def _row_to_node_safe(self, node_id: int) -> Optional[KeterNode]:
        """Fetch a single node from DB by ID. Returns None on failure."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                r = session.execute(
                    text("""SELECT id, node_type, content_hash, content, confidence,
                                   source_block, domain, grounding_source,
                                   reference_count, last_referenced_block
                            FROM knowledge_nodes WHERE id = :nid"""),
                    {'nid': node_id}
                ).fetchone()
            if r:
                node = self._row_to_node(r)
                # Cache it for future lookups
                self.nodes[node.node_id] = node
                return node
        except Exception:
            pass
        return None

    def _node_exists_in_db(self, node_id: int) -> bool:
        """Quick check if a node exists in DB (for search result validation)."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                r = session.execute(
                    text("SELECT 1 FROM knowledge_nodes WHERE id = :nid"),
                    {'nid': node_id}
                ).fetchone()
            return r is not None
        except Exception:
            return False

    def vector_search(self, query: str, top_k: int = 10) -> List[Tuple[KeterNode, float]]:
        """Semantic vector search using pgvector HNSW index in CockroachDB.

        Encodes the query with the same sentence-transformer model used for
        node embeddings, then uses the L2 distance operator (<->) to find
        nearest neighbors via the HNSW index.

        Falls back to in-memory vector_index if CRDB search fails.
        """
        from .vector_index import _compute_embedding
        try:
            query_vec = _compute_embedding(query)
        except Exception:
            return self.search(query, top_k)  # fallback to blended search

        try:
            return self._db_vector_search(query_vec, top_k)
        except Exception as e:
            logger.debug("pgvector search fallback to in-memory: %s", e)
            # Fall back to in-memory vector index
            results = self.vector_index.query(query, top_k=top_k)
            return [
                (self.nodes[nid], score)
                for nid, score in results
                if nid in self.nodes
            ]

    def _db_vector_search(self, query_vec: list, top_k: int) -> List[Tuple[KeterNode, float]]:
        """pgvector HNSW search using L2 distance operator."""
        try:
            from sqlalchemy import text
            vec_str = '[' + ','.join(f'{v:.6f}' for v in query_vec) + ']'
            with self.db.get_session() as session:
                rows = session.execute(
                    text("""SELECT id, node_type, content_hash, content, confidence,
                                   source_block, domain, grounding_source,
                                   reference_count, last_referenced_block,
                                   embedding <-> :qvec::vector AS distance
                            FROM knowledge_nodes
                            WHERE embedding IS NOT NULL
                            ORDER BY embedding <-> :qvec::vector
                            LIMIT :lim"""),
                    {'qvec': vec_str, 'lim': top_k}
                ).fetchall()
            result = []
            for r in rows:
                cached = self.nodes.get(r[0])
                if cached:
                    node = cached
                else:
                    node = self._row_to_node(r)
                # Convert L2 distance to similarity score (1 / (1 + distance))
                distance = float(r[10]) if r[10] is not None else 1.0
                similarity = 1.0 / (1.0 + distance)
                result.append((node, similarity))
            return result
        except Exception as e:
            logger.debug(f"pgvector search unavailable (CockroachDB lacks <-> operator): {e}")
            return []

    def find_by_type(self, node_type: str, limit: int = 100) -> List[KeterNode]:
        """Find nodes by type, sorted by confidence descending.

        Uses CockroachDB indexed query (idx_kn_type_source_block) instead of
        O(n) Python dict scan.  Falls back to in-memory scan if DB unavailable.
        """
        try:
            return self._db_find_by_type(node_type, limit)
        except Exception as e:
            logger.debug("DB find_by_type fallback to memory: %s", e)
        with self._lock:
            matching = [
                n for n in self.nodes.values()
                if n.node_type == node_type
            ]
        matching.sort(key=lambda n: n.confidence, reverse=True)
        return matching[:limit]

    def _db_find_by_type(self, node_type: str, limit: int) -> List[KeterNode]:
        """DB-backed find_by_type using idx_kn_type_source_block index."""
        from sqlalchemy import text
        with self.db.get_session() as session:
            rows = session.execute(
                text("""SELECT id, node_type, content_hash, content, confidence,
                               source_block, domain, grounding_source,
                               reference_count, last_referenced_block
                        FROM knowledge_nodes
                        WHERE node_type = :ntype
                        ORDER BY confidence DESC
                        LIMIT :lim"""),
                {'ntype': node_type, 'lim': limit}
            ).fetchall()
        result = []
        for r in rows:
            # Check cache first, populate from DB if missing
            cached = self.nodes.get(r[0])
            if cached:
                result.append(cached)
            else:
                result.append(self._row_to_node(r))
        return result

    def find_by_content(self, key: str, value: str, limit: int = 50) -> List[KeterNode]:
        """Find nodes whose content dict contains a matching key-value.

        Uses CockroachDB JSONB inverted index (idx_kn_content_gin) instead of
        O(n) Python dict scan.  Falls back to in-memory scan if DB unavailable.
        """
        try:
            return self._db_find_by_content(key, value, limit)
        except Exception as e:
            logger.debug("DB find_by_content fallback to memory: %s", e)
        with self._lock:
            matching = [
                n for n in self.nodes.values()
                if str(n.content.get(key, '')) == str(value)
            ]
        matching.sort(key=lambda n: n.source_block, reverse=True)
        return matching[:limit]

    def _db_find_by_content(self, key: str, value: str, limit: int) -> List[KeterNode]:
        """DB-backed find_by_content using JSONB containment operator (@>)."""
        from sqlalchemy import text
        # CockroachDB @> containment operator uses GIN index
        filter_json = json.dumps({key: value})
        with self.db.get_session() as session:
            rows = session.execute(
                text("""SELECT id, node_type, content_hash, content, confidence,
                               source_block, domain, grounding_source,
                               reference_count, last_referenced_block
                        FROM knowledge_nodes
                        WHERE content @> :filter::jsonb
                        ORDER BY source_block DESC
                        LIMIT :lim"""),
                {'filter': filter_json, 'lim': limit}
            ).fetchall()
        result = []
        for r in rows:
            cached = self.nodes.get(r[0])
            if cached:
                result.append(cached)
            else:
                result.append(self._row_to_node(r))
        return result

    def find_recent(self, count: int = 20) -> List[KeterNode]:
        """Get the most recently added nodes by source block.

        Uses CockroachDB indexed query (idx_kn_source_block_desc) instead of
        O(n) Python sort.  Falls back to in-memory scan if DB unavailable.
        """
        try:
            return self._db_find_recent(count)
        except Exception as e:
            logger.debug("DB find_recent fallback to memory: %s", e)
        with self._lock:
            nodes = sorted(
                self.nodes.values(),
                key=lambda n: n.source_block,
                reverse=True,
            )
        return nodes[:count]

    def _db_find_recent(self, count: int) -> List[KeterNode]:
        """DB-backed find_recent using idx_kn_source_block_desc index."""
        from sqlalchemy import text
        with self.db.get_session() as session:
            rows = session.execute(
                text("""SELECT id, node_type, content_hash, content, confidence,
                               source_block, domain, grounding_source,
                               reference_count, last_referenced_block
                        FROM knowledge_nodes
                        ORDER BY source_block DESC
                        LIMIT :lim"""),
                {'lim': count}
            ).fetchall()
        result = []
        for r in rows:
            cached = self.nodes.get(r[0])
            if cached:
                result.append(cached)
            else:
                result.append(self._row_to_node(r))
        return result

    @staticmethod
    def _row_to_node(r) -> KeterNode:
        """Convert a DB row tuple to a KeterNode."""
        return KeterNode(
            node_id=r[0],
            node_type=r[1],
            content_hash=r[2],
            content=json.loads(r[3]) if isinstance(r[3], str) else (r[3] or {}),
            confidence=float(r[4] or 0.5),
            source_block=r[5] or 0,
            domain=r[6] or '',
            grounding_source=r[7] or '',
            reference_count=r[8] or 0,
            last_referenced_block=r[9] or 0,
        )

    def get_edge_types_for_node(self, node_id: int) -> Dict[str, List[int]]:
        """Get all edges grouped by type for a specific node. O(degree) via adjacency index."""
        result: Dict[str, List[int]] = {}
        for edge in self._adj_out.get(node_id, []):
            result.setdefault(f"out_{edge.edge_type}", []).append(edge.to_node_id)
        for edge in self._adj_in.get(node_id, []):
            result.setdefault(f"in_{edge.edge_type}", []).append(edge.from_node_id)
        return result

    def get_edges_from(self, node_id: int) -> List[KeterEdge]:
        """Get all outgoing edges from a node. O(1) lookup."""
        with self._lock:
            return list(self._adj_out.get(node_id, []))

    def get_edges_to(self, node_id: int) -> List[KeterEdge]:
        """Get all incoming edges to a node. O(1) lookup."""
        with self._lock:
            return list(self._adj_in.get(node_id, []))

    def export_json_ld(self, limit: int = 0) -> dict:
        """Export the knowledge graph in JSON-LD format.

        Args:
            limit: Maximum number of nodes to export (0 = all).

        Returns:
            JSON-LD document with @context, @graph nodes, and edges.
        """
        context = {
            "@vocab": "https://qbc.network/ontology#",
            "qbc": "https://qbc.network/ontology#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "node_type": "qbc:nodeType",
            "confidence": {"@id": "qbc:confidence", "@type": "xsd:float"},
            "source_block": {"@id": "qbc:sourceBlock", "@type": "xsd:integer"},
            "content_hash": "qbc:contentHash",
            "supports": "qbc:supports",
            "contradicts": "qbc:contradicts",
            "derives": "qbc:derives",
            "requires": "qbc:requires",
            "refines": "qbc:refines",
        }

        nodes_list = sorted(self.nodes.values(), key=lambda n: n.node_id)
        if limit > 0:
            nodes_list = nodes_list[:limit]
        exported_ids = {n.node_id for n in nodes_list}

        graph = []
        for node in nodes_list:
            entry: dict = {
                "@id": f"qbc:node/{node.node_id}",
                "@type": "qbc:KeterNode",
                "node_type": node.node_type,
                "confidence": round(node.confidence, 6),
                "source_block": node.source_block,
                "content_hash": node.content_hash,
            }
            if node.content:
                entry["qbc:content"] = node.content
            graph.append(entry)

        # Add edges that connect exported nodes
        for edge in self.edges:
            if edge.from_node_id in exported_ids and edge.to_node_id in exported_ids:
                graph.append({
                    "@id": f"qbc:edge/{edge.from_node_id}-{edge.to_node_id}",
                    "@type": "qbc:KeterEdge",
                    "qbc:from": {"@id": f"qbc:node/{edge.from_node_id}"},
                    "qbc:to": {"@id": f"qbc:node/{edge.to_node_id}"},
                    "qbc:edgeType": edge.edge_type,
                    "qbc:weight": round(edge.weight, 6),
                })

        return {
            "@context": context,
            "@graph": graph,
            "qbc:stats": {
                "exported_nodes": len(nodes_list),
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
            },
        }

    def touch_node(self, node_id: int, current_block: int) -> None:
        """Update a node's last_referenced_block and increment reference count.

        Called when a node is used in reasoning or referenced in a query.
        Resets the decay clock and builds evidence for the node.
        """
        node = self.nodes.get(node_id)
        if node:
            node.last_referenced_block = current_block
            node.reference_count += 1

    def boost_referenced_nodes(self, min_references: int = 5, boost_per_ref: float = 0.01,
                               max_boost: float = 0.15) -> int:
        """Boost confidence of frequently-referenced nodes.

        Nodes that have been used in reasoning multiple times get a small
        confidence increase, creating natural selection pressure: useful
        knowledge rises, unused knowledge fades (via decay).

        Args:
            min_references: Minimum references before boost applies.
            boost_per_ref: Confidence increase per log(references).
            max_boost: Maximum total boost per call.

        Returns:
            Number of nodes boosted.
        """
        boosted = 0
        for node in self.nodes.values():
            if node.reference_count >= min_references:
                boost = min(max_boost, boost_per_ref * math.log(node.reference_count))
                new_conf = min(1.0, node.confidence + boost)
                if new_conf > node.confidence:
                    node.confidence = new_conf
                    boosted += 1
        if boosted:
            logger.info(f"Boosted confidence for {boosted} frequently-referenced nodes")
        return boosted

    def get_domain_stats(self) -> Dict[str, dict]:
        """Get node counts and average confidence per domain.

        Uses CockroachDB GROUP BY with idx_kn_domain_confidence index.
        Falls back to in-memory scan if DB unavailable.
        """
        try:
            return self._db_get_domain_stats()
        except Exception as e:
            logger.debug("DB get_domain_stats fallback to memory: %s", e)
        domains: Dict[str, dict] = {}
        for node in self.nodes.values():
            d = node.domain or 'general'
            if d not in domains:
                domains[d] = {'count': 0, 'total_confidence': 0.0}
            domains[d]['count'] += 1
            domains[d]['total_confidence'] += node.confidence

        result: Dict[str, dict] = {}
        for d, info in sorted(domains.items(), key=lambda x: x[1]['count'], reverse=True):
            result[d] = {
                'count': info['count'],
                'avg_confidence': round(info['total_confidence'] / info['count'], 4) if info['count'] else 0.0,
            }
        return result

    def _db_get_domain_stats(self) -> Dict[str, dict]:
        """DB-backed domain stats using GROUP BY."""
        from sqlalchemy import text
        with self.db.get_session() as session:
            rows = session.execute(
                text("""SELECT COALESCE(NULLIF(domain, ''), 'general') AS dom,
                               COUNT(*) AS cnt,
                               ROUND(AVG(confidence)::numeric, 4) AS avg_conf
                        FROM knowledge_nodes
                        GROUP BY dom
                        ORDER BY cnt DESC""")
            ).fetchall()
        return {
            r[0]: {'count': r[1], 'avg_confidence': float(r[2] or 0.0)}
            for r in rows
        }

    def reclassify_domains(self) -> int:
        """Reclassify domains for all nodes that have no domain set or are 'general'.

        Uses the improved multi-strategy classifier to re-evaluate nodes
        that were previously unclassified or defaulted to 'general'.

        Returns:
            Number of nodes reclassified.
        """
        count = 0
        for node in self.nodes.values():
            if not node.domain or node.domain == 'general':
                new_domain = classify_domain(node.content)
                if new_domain != node.domain:
                    node.domain = new_domain
                    count += 1
        if count:
            logger.info(f"Reclassified domains for {count} nodes")
        return count

    def detect_contradictions(self, new_node_id: int, max_checks: int = 20) -> int:
        """Scan for potential contradictions between a new node and existing ones.

        Checks for numeric value conflicts and opposing assertions
        in nodes of the same domain.

        Args:
            new_node_id: The newly-added node to check.
            max_checks: Max existing nodes to compare against.

        Returns:
            Number of contradiction edges created.
        """
        new_node = self.nodes.get(new_node_id)
        if not new_node or new_node.node_type not in ('assertion', 'inference'):
            return 0

        new_text = str(new_node.content.get('text', '')).lower()
        if not new_text:
            return 0

        created = 0
        # Find nodes in the same domain to compare
        candidates = [
            n for n in self.nodes.values()
            if n.node_id != new_node_id
            and n.node_type in ('assertion', 'inference')
            and (n.domain == new_node.domain or not new_node.domain)
            and n.content.get('text')
        ]
        # Sort by most recent first
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        candidates = candidates[:max_checks]

        for existing in candidates:
            existing_text = str(existing.content.get('text', '')).lower()
            if not existing_text:
                continue

            # Check for numeric value conflicts
            import re
            new_numbers = set(re.findall(r'\b\d+\.?\d*\b', new_text))
            existing_numbers = set(re.findall(r'\b\d+\.?\d*\b', existing_text))

            # Same subject (high word overlap) but different numbers
            new_words = set(new_text.split())
            existing_words = set(existing_text.split())
            overlap = len(new_words & existing_words)
            total = len(new_words | existing_words)
            word_similarity = overlap / total if total > 0 else 0

            if (word_similarity > 0.4
                    and new_numbers and existing_numbers
                    and new_numbers != existing_numbers
                    and len(new_numbers & existing_numbers) == 0):
                # Likely contradiction: same subject, different numeric values
                edge = self.add_edge(
                    new_node_id, existing.node_id, 'contradicts', weight=0.7
                )
                if edge:
                    created += 1
                if created >= 3:
                    break

        if created:
            logger.info(
                f"Detected {created} potential contradictions for node {new_node_id}"
            )
        return created

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 2: Auto-Pruning Trigger
    # ────────────────────────────────────────────────────────────────────────

    def auto_prune_if_needed(self, max_nodes: int = 200000) -> int:
        """Auto-prune when graph exceeds max_nodes.

        Uses adaptive threshold based on confidence distribution: prunes
        the lowest-confidence nodes until the graph is back under the limit.
        The threshold is set at the percentile that would remove enough nodes.

        Args:
            max_nodes: Maximum allowed node count before pruning triggers.

        Returns:
            Number of nodes pruned (0 if no pruning needed).
        """
        if len(self.nodes) <= max_nodes:
            return 0

        excess = len(self.nodes) - max_nodes
        # Calculate adaptive threshold from confidence distribution
        confidences = sorted(n.confidence for n in self.nodes.values())
        # Find the confidence value at the percentile that removes enough nodes
        # Add 10% buffer to prune a bit more than the minimum
        prune_count = min(len(confidences) - 1, int(excess * 1.1))
        threshold = confidences[prune_count]
        # Ensure minimum threshold
        threshold = max(threshold, 0.05)

        logger.info(
            f"Auto-prune triggered: {len(self.nodes)} nodes > {max_nodes} limit, "
            f"adaptive threshold={threshold:.4f}, targeting ~{prune_count} nodes"
        )
        return self.prune_low_confidence(threshold=threshold)

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 5: Orphan Node Detection
    # ────────────────────────────────────────────────────────────────────────

    def find_orphan_nodes(self) -> List[int]:
        """Find nodes with no edges (neither incoming nor outgoing).

        These are disconnected knowledge nodes that contribute nothing
        to the graph structure. They should either be connected to
        related nodes or pruned.

        Returns:
            List of orphan node IDs.
        """
        orphans = []
        for nid, node in self.nodes.items():
            has_out = bool(self._adj_out.get(nid))
            has_in = bool(self._adj_in.get(nid))
            if not has_out and not has_in:
                orphans.append(nid)
        return orphans

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 6: Duplicate Content Detection
    # ────────────────────────────────────────────────────────────────────────

    def find_and_merge_duplicates(self, similarity_threshold: float = 0.92) -> int:
        """Find near-duplicate nodes and merge them.

        Detects duplicates via:
        1. Exact content_hash matches (definite duplicates)
        2. High cosine similarity from vector index (near-duplicates)

        Keeps the higher-confidence node and redirects all edges from the
        duplicate to the survivor. The duplicate is then removed.

        Args:
            similarity_threshold: Minimum cosine similarity to consider as duplicate.

        Returns:
            Number of nodes merged (removed).
        """
        merged = 0
        # Phase 1: Exact content hash duplicates
        hash_groups: Dict[str, List[int]] = {}
        for nid, node in self.nodes.items():
            if node.content_hash:
                hash_groups.setdefault(node.content_hash, []).append(nid)

        to_remove: Set[int] = set()
        redirect_map: Dict[int, int] = {}  # duplicate_id -> survivor_id

        for chash, nids in hash_groups.items():
            if len(nids) < 2:
                continue
            # Sort by confidence descending — first is the survivor
            nids.sort(key=lambda n: self.nodes[n].confidence, reverse=True)
            survivor = nids[0]
            for dup in nids[1:]:
                if dup not in to_remove:
                    to_remove.add(dup)
                    redirect_map[dup] = survivor

        # Phase 2: Vector similarity duplicates (only if vector index has content)
        if hasattr(self.vector_index, 'find_similar_nodes'):
            checked: Set[Tuple[int, int]] = set()
            sample_ids = list(self.nodes.keys())
            # Limit checks for performance — sample up to 1000 nodes
            if len(sample_ids) > 1000:
                import random
                sample_ids = random.sample(sample_ids, 1000)

            for nid in sample_ids:
                if nid in to_remove:
                    continue
                try:
                    similar = self.vector_index.find_similar_nodes(nid, top_k=5)
                    for sim_id, sim_score in similar:
                        if sim_id == nid or sim_id in to_remove:
                            continue
                        pair = (min(nid, sim_id), max(nid, sim_id))
                        if pair in checked:
                            continue
                        checked.add(pair)
                        if sim_score >= similarity_threshold:
                            # Keep higher confidence
                            if self.nodes[nid].confidence >= self.nodes.get(sim_id, KeterNode()).confidence:
                                to_remove.add(sim_id)
                                redirect_map[sim_id] = nid
                            else:
                                to_remove.add(nid)
                                redirect_map[nid] = sim_id
                                break  # nid is being removed, stop checking its neighbors
                except Exception:
                    continue

        if not to_remove:
            return 0

        # Redirect edges from duplicates to survivors
        with self._lock:
            for dup_id, survivor_id in redirect_map.items():
                # Redirect outgoing edges
                for edge in list(self._adj_out.get(dup_id, [])):
                    if edge.to_node_id != survivor_id and edge.to_node_id not in to_remove:
                        self.add_edge(survivor_id, edge.to_node_id, edge.edge_type, edge.weight)
                # Redirect incoming edges
                for edge in list(self._adj_in.get(dup_id, [])):
                    if edge.from_node_id != survivor_id and edge.from_node_id not in to_remove:
                        self.add_edge(edge.from_node_id, survivor_id, edge.edge_type, edge.weight)

            # Remove duplicate nodes
            self.edges = [
                e for e in self.edges
                if e.from_node_id not in to_remove and e.to_node_id not in to_remove
            ]
            for dup_id in to_remove:
                self._adj_out.pop(dup_id, None)
                self._adj_in.pop(dup_id, None)
                if dup_id in self.nodes:
                    del self.nodes[dup_id]
                if hasattr(self, 'search_index') and self.search_index:
                    try:
                        self.search_index.remove_node(dup_id)
                    except Exception:
                        pass
                if hasattr(self, 'vector_index') and self.vector_index:
                    try:
                        self.vector_index.remove_node(dup_id)
                    except Exception:
                        pass
                merged += 1
            self._merkle_dirty = True

        # Delete from database
        if to_remove:
            try:
                from sqlalchemy import text as sa_text
                with self.db.get_session() as session:
                    remove_list = list(to_remove)
                    session.execute(
                        sa_text("DELETE FROM knowledge_edges WHERE from_node_id = ANY(:ids) OR to_node_id = ANY(:ids)"),
                        {"ids": remove_list}
                    )
                    session.execute(
                        sa_text("DELETE FROM knowledge_nodes WHERE id = ANY(:ids)"),
                        {"ids": remove_list}
                    )
                    session.commit()
            except Exception as e:
                logger.error(f"Failed to delete merged duplicates from DB: {e}")

        logger.info(f"Merged {merged} duplicate nodes")
        return merged

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 9: Knowledge Quality Score
    # ────────────────────────────────────────────────────────────────────────

    def compute_node_quality(self, node_id: int) -> float:
        """Compute a composite quality score for a knowledge node.

        The score is a weighted combination of:
        - Confidence (30%): Base reliability measure
        - Edge count (20%): Connectivity indicates importance
        - Reference count (15%): Usage in reasoning
        - Grounding status (15%): Verified knowledge is higher quality
        - Recency (10%): Recent nodes are more relevant
        - Domain specificity (10%): Non-'general' domain gets bonus

        Args:
            node_id: The node to score.

        Returns:
            Quality score in [0.0, 1.0], or 0.0 if node not found.
        """
        node = self.nodes.get(node_id)
        if not node:
            return 0.0

        # Confidence component (0-1)
        conf_score = node.confidence

        # Edge count component — normalized with diminishing returns
        total_edges = len(self._adj_out.get(node_id, [])) + len(self._adj_in.get(node_id, []))
        edge_score = min(1.0, math.log1p(total_edges) / math.log1p(20))

        # Reference count component — log scale
        ref_score = min(1.0, math.log1p(node.reference_count) / math.log1p(50))

        # Grounding component — binary with partial credit
        grounding_score = 1.0 if node.grounding_source else 0.0

        # Recency component — based on source_block relative to newest
        max_block = max((n.source_block for n in self.nodes.values()), default=0)
        if max_block > 0:
            recency_score = min(1.0, node.source_block / max_block)
        else:
            recency_score = 0.5

        # Domain specificity — non-general gets bonus
        domain_score = 0.0 if (not node.domain or node.domain == 'general') else 1.0

        quality = (
            0.30 * conf_score
            + 0.20 * edge_score
            + 0.15 * ref_score
            + 0.15 * grounding_score
            + 0.10 * recency_score
            + 0.10 * domain_score
        )
        return round(min(1.0, max(0.0, quality)), 4)

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 10: Graph Health Metrics
    # ────────────────────────────────────────────────────────────────────────

    def get_health_metrics(self) -> dict:
        """Compute comprehensive health metrics for the knowledge graph.

        Returns a dict with:
        - orphan_ratio: Fraction of nodes with no edges
        - avg_edge_count: Mean edges per node (in + out)
        - domain_diversity: Shannon entropy of domain distribution
        - grounding_ratio: Fraction of grounded nodes
        - duplicate_ratio: Estimated fraction of duplicate content hashes
        - confidence_distribution: Quartiles (min, q25, median, q75, max)
        """
        total = len(self.nodes)
        if total == 0:
            return {
                'orphan_ratio': 0.0,
                'avg_edge_count': 0.0,
                'domain_diversity': 0.0,
                'grounding_ratio': 0.0,
                'duplicate_ratio': 0.0,
                'confidence_distribution': {'min': 0, 'q25': 0, 'median': 0, 'q75': 0, 'max': 0},
            }

        # Orphan ratio
        orphan_count = 0
        total_edge_count = 0
        grounded_count = 0
        domain_counts: Dict[str, int] = {}
        hash_counts: Dict[str, int] = {}
        confidences: List[float] = []

        for nid, node in self.nodes.items():
            edges = len(self._adj_out.get(nid, [])) + len(self._adj_in.get(nid, []))
            if edges == 0:
                orphan_count += 1
            total_edge_count += edges

            if node.grounding_source:
                grounded_count += 1

            d = node.domain or 'general'
            domain_counts[d] = domain_counts.get(d, 0) + 1

            if node.content_hash:
                hash_counts[node.content_hash] = hash_counts.get(node.content_hash, 0) + 1

            confidences.append(node.confidence)

        # Shannon entropy for domain diversity
        entropy = 0.0
        for count in domain_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Duplicate ratio
        duplicate_nodes = sum(c - 1 for c in hash_counts.values() if c > 1)

        # Confidence quartiles
        confidences.sort()
        n = len(confidences)

        def percentile(data: List[float], pct: float) -> float:
            idx = int(pct * (len(data) - 1))
            return round(data[idx], 4)

        return {
            'orphan_ratio': round(orphan_count / total, 4),
            'avg_edge_count': round(total_edge_count / total, 2),
            'domain_diversity': round(entropy, 4),
            'grounding_ratio': round(grounded_count / total, 4),
            'duplicate_ratio': round(duplicate_nodes / total, 4) if total > 0 else 0.0,
            'confidence_distribution': {
                'min': round(confidences[0], 4),
                'q25': percentile(confidences, 0.25),
                'median': percentile(confidences, 0.50),
                'q75': percentile(confidences, 0.75),
                'max': round(confidences[-1], 4),
            },
        }

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 11: Smart Node Aging
    # ────────────────────────────────────────────────────────────────────────

    def age_stale_nodes(self, current_block: int, max_age_blocks: int = 50000) -> int:
        """Reduce confidence of old, unreferenced nodes.

        Applies aggressive aging to nodes that:
        - Have not been referenced recently
        - Are not axioms or grounded
        - Have low reference counts

        This creates natural selection pressure: actively-used knowledge
        persists while stale, unused knowledge fades.

        Args:
            current_block: Current blockchain block height.
            max_age_blocks: Age threshold for aggressive decay.

        Returns:
            Number of nodes aged.
        """
        aged = 0
        for node in self.nodes.values():
            if node.node_type == 'axiom':
                continue
            if node.grounding_source:
                continue

            ref_block = node.last_referenced_block or node.source_block
            age = current_block - ref_block
            if age <= max_age_blocks:
                continue

            # More aggressive decay for unreferenced nodes
            # Nodes with more references decay slower
            ref_factor = max(0.1, 1.0 / (1.0 + math.log1p(node.reference_count)))
            excess_age = age - max_age_blocks
            decay = min(0.05, 0.001 * ref_factor * (excess_age / max_age_blocks))
            new_conf = max(0.01, node.confidence - decay)
            if new_conf < node.confidence:
                node.confidence = new_conf
                aged += 1

        if aged:
            logger.info(f"Aged {aged} stale nodes (current_block={current_block}, max_age={max_age_blocks})")
        return aged

    # ────────────────────────────────────────────────────────────────────────
    # Improvement 12: Edge Weight Normalization
    # ────────────────────────────────────────────────────────────────────────

    def normalize_edge_weights(self) -> int:
        """Normalize outgoing edge weights per node to sum to 1.0.

        Prevents weight inflation from repeated edge additions.
        Only normalizes nodes with total outgoing weight > 1.0.

        Returns:
            Number of nodes whose edges were normalized.
        """
        normalized = 0
        for nid in list(self._adj_out.keys()):
            edges = self._adj_out.get(nid, [])
            if not edges:
                continue
            total_weight = sum(abs(e.weight) for e in edges)
            if total_weight <= 1.0 or total_weight == 0:
                continue
            for edge in edges:
                edge.weight = edge.weight / total_weight
            normalized += 1

        if normalized:
            self._merkle_dirty = True
            logger.info(f"Normalized edge weights for {normalized} nodes")
        return normalized

    @property
    def rust_kg(self):
        """Access the Rust shadow KnowledgeGraph for compute delegation (e.g. PhiCalculator)."""
        return getattr(self, '_rust_kg', None)

    def get_stats(self) -> dict:
        """Get knowledge graph statistics.

        Caches the result for 30 seconds to avoid re-iterating 100K+ nodes
        on every API call. Cache is also invalidated when nodes/edges change.
        """
        import time as _time
        now = _time.monotonic()
        cache = getattr(self, '_stats_cache', None)
        cache_time = getattr(self, '_stats_cache_time', 0.0)
        cache_size = getattr(self, '_stats_cache_size', -1)
        current_size = len(self.nodes)

        # Return cached if <30s old and node count unchanged
        if cache is not None and (now - cache_time) < 30.0 and cache_size == current_size:
            return cache

        # Rust-accelerated stats when available
        if getattr(self, '_rust_kg', None) is not None:
            try:
                result = self._rust_kg.get_stats()
                self._stats_cache = result
                self._stats_cache_time = now
                self._stats_cache_size = current_size
                return result
            except Exception:
                pass

        # Snapshot to avoid RuntimeError from concurrent LRU mutations
        try:
            nodes_snapshot = list(self.nodes.values())
        except RuntimeError:
            nodes_snapshot = []

        type_counts: dict = {}
        domain_counts: dict = {}
        total_conf = 0.0
        for node in nodes_snapshot:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
            d = node.domain or 'general'
            domain_counts[d] = domain_counts.get(d, 0) + 1
            total_conf += node.confidence

        edge_type_counts: dict = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        avg_confidence = total_conf / len(nodes_snapshot) if nodes_snapshot else 0.0

        # Use cached merkle root (don't recompute on stats call)
        kr = getattr(self, '_merkle_cache', None)
        if not kr:
            kr = '0' * 16

        result = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': type_counts,
            'edge_types': edge_type_counts,
            'avg_confidence': round(avg_confidence, 4),
            'domains': domain_counts,
            'knowledge_root': kr[:16] + '...',
        }

        self._stats_cache = result
        self._stats_cache_time = now
        self._stats_cache_size = current_size
        return result

    # ────────────────────────────────────────────────────────────────────────
    # Improvements 51-65: Advanced Knowledge Graph Operations
    # ────────────────────────────────────────────────────────────────────────

    MAX_NODES: int = 2_000_000  # OOM protection cap (raised post-compaction)

    def prune_stale_nodes(self, max_age_blocks: int = 50000,
                          min_confidence: float = 0.2,
                          current_block: int = 0) -> int:
        """Remove old low-confidence nodes, but NEVER prune axioms.

        Targets nodes older than max_age_blocks with confidence below
        min_confidence. Axioms and grounded nodes are always protected.

        Args:
            max_age_blocks: Age threshold in blocks.
            min_confidence: Confidence threshold for pruning.
            current_block: Current block height for age calculation.

        Returns:
            Number of nodes pruned.
        """
        if current_block <= 0:
            # Estimate from highest source_block
            current_block = max((n.source_block for n in self.nodes.values()), default=0)
        if current_block <= 0:
            return 0

        to_prune: List[int] = []
        for nid, node in self.nodes.items():
            # Never prune axioms or grounded nodes
            if node.node_type == 'axiom' or node.grounding_source:
                continue
            ref_block = node.last_referenced_block or node.source_block
            age = current_block - ref_block
            if age >= max_age_blocks and node.confidence < min_confidence:
                to_prune.append(nid)

        if not to_prune:
            return 0

        pruned = self.prune_low_confidence(
            threshold=min_confidence + 0.001,
            protect_types={'axiom'}
        )
        logger.info(
            f"Stale node pruning: removed {pruned} nodes "
            f"(age>{max_age_blocks}, confidence<{min_confidence})"
        )
        return pruned

    def compute_node_importance(self, node_id: int) -> float:
        """Compute importance score based on edge count, references, confidence, and age.

        Args:
            node_id: Node to evaluate.

        Returns:
            Importance score in [0, 1], or 0.0 if node not found.
        """
        node = self.nodes.get(node_id)
        if not node:
            return 0.0

        # Edge connectivity (in + out)
        edge_count = len(self._adj_out.get(node_id, [])) + len(self._adj_in.get(node_id, []))
        edge_score = min(1.0, math.log1p(edge_count) / math.log1p(30))

        # Reference count (log scale)
        ref_score = min(1.0, math.log1p(node.reference_count) / math.log1p(100))

        # Confidence
        conf_score = node.confidence

        # Age bonus: newer nodes get slight boost
        max_block = max((n.source_block for n in self.nodes.values()), default=1)
        age_score = node.source_block / max_block if max_block > 0 else 0.5

        # Axioms are always important
        type_bonus = 0.2 if node.node_type == 'axiom' else 0.0

        importance = (
            0.25 * edge_score
            + 0.25 * ref_score
            + 0.25 * conf_score
            + 0.15 * age_score
            + 0.10 * (1.0 if node.grounding_source else 0.0)
            + type_bonus
        )
        return round(min(1.0, max(0.0, importance)), 4)

    def deduplicate_nodes(self, similarity_threshold: float = 0.95) -> int:
        """Merge near-duplicate nodes using vector similarity.

        Delegates to find_and_merge_duplicates with the given threshold.
        Axiom nodes are never removed.

        Args:
            similarity_threshold: Cosine similarity threshold.

        Returns:
            Number of duplicate nodes merged.
        """
        return self.find_and_merge_duplicates(similarity_threshold=similarity_threshold)

    def get_statistics(self) -> dict:
        """Return comprehensive graph statistics suitable for chat/dashboard exposure.

        Includes node/edge counts, type distributions, domain breakdown,
        confidence stats, edge type distribution, freshness info, and health indicators.

        Returns:
            Comprehensive statistics dict.
        """
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)

        # Node type distribution
        node_type_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        confidence_sum = 0.0
        grounded = 0
        orphan_count = 0
        oldest_block = float('inf')
        newest_block = 0

        for nid, node in self.nodes.items():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
            d = node.domain or 'general'
            domain_counts[d] = domain_counts.get(d, 0) + 1
            confidence_sum += node.confidence
            if node.grounding_source:
                grounded += 1
            if not self._adj_out.get(nid) and not self._adj_in.get(nid):
                orphan_count += 1
            if node.source_block < oldest_block:
                oldest_block = node.source_block
            if node.source_block > newest_block:
                newest_block = node.source_block

        # Edge type distribution
        edge_type_counts: Dict[str, int] = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        avg_confidence = confidence_sum / total_nodes if total_nodes > 0 else 0.0

        return {
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'node_types': node_type_counts,
            'edge_types': edge_type_counts,
            'domains': domain_counts,
            'domain_count': len(domain_counts),
            'avg_confidence': round(avg_confidence, 4),
            'grounded_nodes': grounded,
            'grounding_ratio': round(grounded / total_nodes, 4) if total_nodes > 0 else 0.0,
            'orphan_nodes': orphan_count,
            'orphan_ratio': round(orphan_count / total_nodes, 4) if total_nodes > 0 else 0.0,
            'oldest_block': oldest_block if oldest_block != float('inf') else 0,
            'newest_block': newest_block,
            'block_span': newest_block - (oldest_block if oldest_block != float('inf') else 0),
            'knowledge_root': self.compute_knowledge_root()[:16] + '...',
            'vector_index_size': len(self.vector_index.embeddings) if self.vector_index else 0,
            'search_index_terms': self.search_index.get_stats().get('unique_terms', 0) if self.search_index else 0,
        }

    def get_freshest_nodes(self, domain: str = '', limit: int = 20) -> List[KeterNode]:
        """Get the most recently created nodes, optionally filtered by domain.

        Args:
            domain: Filter by domain (empty string = all domains).
            limit: Maximum number of nodes to return.

        Returns:
            List of KeterNodes sorted by source_block descending.
        """
        with self._lock:
            if domain:
                candidates = [n for n in self.nodes.values() if n.domain == domain]
            else:
                candidates = list(self.nodes.values())
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        return candidates[:limit]

    def summarize_domain(self, domain: str) -> str:
        """Produce a natural language summary of knowledge in a domain.

        Args:
            domain: Domain name to summarize.

        Returns:
            Human-readable summary string.
        """
        nodes = [n for n in self.nodes.values() if n.domain == domain]
        if not nodes:
            return f"No knowledge found in domain '{domain}'."

        total = len(nodes)
        avg_conf = sum(n.confidence for n in nodes) / total
        type_counts: Dict[str, int] = {}
        for n in nodes:
            type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1
        grounded = sum(1 for n in nodes if n.grounding_source)
        newest = max(n.source_block for n in nodes)
        oldest = min(n.source_block for n in nodes)

        types_str = ', '.join(f"{count} {t}s" for t, count in
                              sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5])

        summary = (
            f"Domain '{domain}' contains {total} knowledge nodes "
            f"(avg confidence: {avg_conf:.2f}). "
            f"Composition: {types_str}. "
            f"{grounded} nodes are grounded in verified data. "
            f"Knowledge spans blocks {oldest} to {newest}."
        )
        return summary

    def find_cross_domain_connections(self, min_weight: float = 0.3) -> List[Dict]:
        """Discover connections between different domains.

        Finds edges where the source and target nodes belong to different
        domains, which indicates cross-domain knowledge transfer.

        Args:
            min_weight: Minimum edge weight to include.

        Returns:
            List of dicts with source_domain, target_domain, edge_type,
            count, and example node IDs.
        """
        connections: Dict[Tuple[str, str, str], Dict] = {}

        for edge in self.edges:
            if edge.weight < min_weight:
                continue
            from_node = self.nodes.get(edge.from_node_id)
            to_node = self.nodes.get(edge.to_node_id)
            if not from_node or not to_node:
                continue
            d1 = from_node.domain or 'general'
            d2 = to_node.domain or 'general'
            if d1 == d2:
                continue

            key = (d1, d2, edge.edge_type)
            if key not in connections:
                connections[key] = {
                    'source_domain': d1,
                    'target_domain': d2,
                    'edge_type': edge.edge_type,
                    'count': 0,
                    'examples': [],
                }
            connections[key]['count'] += 1
            if len(connections[key]['examples']) < 3:
                connections[key]['examples'].append(
                    (edge.from_node_id, edge.to_node_id)
                )

        result = sorted(connections.values(), key=lambda x: x['count'], reverse=True)
        return result[:50]

    def get_knowledge_by_topic(self, topic_words: List[str], limit: int = 20) -> List[KeterNode]:
        """Retrieve nodes matching topic words using semantic + keyword search.

        Combines vector search (semantic) with keyword filtering for
        better topic-based retrieval.

        Args:
            topic_words: List of topic keywords.
            limit: Maximum results.

        Returns:
            List of matching KeterNodes ranked by relevance.
        """
        query = ' '.join(topic_words)
        # Use the blended search (TF-IDF + vector)
        results = self.search(query, top_k=limit)
        return [node for node, _score in results]

    def enforce_max_nodes(self) -> int:
        """Cap in-memory nodes to MAX_NODES to prevent OOM.

        If nodes exceed MAX_NODES, prune the oldest lowest-confidence
        non-axiom nodes until under the limit.

        Returns:
            Number of nodes pruned.
        """
        if len(self.nodes) <= self.MAX_NODES:
            return 0

        excess = len(self.nodes) - self.MAX_NODES
        # Score nodes: lower score = higher pruning priority
        scored: List[Tuple[float, int]] = []
        for nid, node in self.nodes.items():
            if node.node_type == 'axiom' or node.grounding_source:
                continue
            # Score based on confidence + recency + references
            max_block = max((n.source_block for n in self.nodes.values()), default=1)
            recency = node.source_block / max_block if max_block > 0 else 0
            score = node.confidence * 0.5 + recency * 0.3 + min(1.0, node.reference_count / 10) * 0.2
            scored.append((score, nid))

        scored.sort(key=lambda x: x[0])
        to_remove = [nid for _, nid in scored[:int(excess * 1.1)]]

        if not to_remove:
            return 0

        remove_set = set(to_remove)
        # Remove from graph
        with self._lock:
            self.edges = deque(
                (e for e in self.edges
                 if e.from_node_id not in remove_set and e.to_node_id not in remove_set),
                maxlen=MAX_EDGES,
            )
            for nid in remove_set:
                for edge in self._adj_out.get(nid, []):
                    adj_list = self._adj_in.get(edge.to_node_id, [])
                    self._adj_in[edge.to_node_id] = [e for e in adj_list if e.from_node_id != nid]
                    neighbor = self.nodes.get(edge.to_node_id)
                    if neighbor and nid in neighbor.edges_in:
                        neighbor.edges_in.remove(nid)
                for edge in self._adj_in.get(nid, []):
                    adj_list = self._adj_out.get(edge.from_node_id, [])
                    self._adj_out[edge.from_node_id] = [e for e in adj_list if e.to_node_id != nid]
                    neighbor = self.nodes.get(edge.from_node_id)
                    if neighbor and nid in neighbor.edges_out:
                        neighbor.edges_out.remove(nid)
                self._adj_out.pop(nid, None)
                self._adj_in.pop(nid, None)
                del self.nodes[nid]
                if hasattr(self, 'search_index') and self.search_index:
                    try:
                        self.search_index.remove_node(nid)
                    except Exception:
                        pass
                if hasattr(self, 'vector_index') and self.vector_index:
                    try:
                        self.vector_index.remove_node(nid)
                    except Exception:
                        pass
            self._merkle_dirty = True

        logger.warning(
            f"OOM protection: pruned {len(remove_set)} nodes "
            f"(limit={self.MAX_NODES}, was {len(self.nodes) + len(remove_set)})"
        )
        return len(remove_set)

    def get_grounding_stats(self) -> dict:
        """Get statistics on grounded vs ungrounded knowledge nodes.

        Returns:
            Dict with total_nodes, grounded_nodes, grounding_ratio,
            and by_source breakdown.
        """
        total = len(self.nodes)
        by_source: Dict[str, int] = {}
        grounded = 0
        for node in self.nodes.values():
            if node.grounding_source:
                grounded += 1
                by_source[node.grounding_source] = by_source.get(node.grounding_source, 0) + 1

        return {
            'total_nodes': total,
            'grounded_nodes': grounded,
            'grounding_ratio': round(grounded / total, 4) if total > 0 else 0.0,
            'by_source': by_source,
        }

    def compact_block_observations(self, keep_milestones: bool = True,
                                    keep_difficulty_shifts: bool = True,
                                    keep_every_nth: int = 1000) -> int:
        """Remove routine block_observation nodes that add no knowledge value.

        Keeps milestone blocks, difficulty shifts, blocks with transactions,
        and every Nth block for chain continuity. Removes everything else.

        This is the primary tool for eliminating node bloat. On a chain at
        block 185K+ with 695K nodes, ~691K are routine block_observations.

        Args:
            keep_milestones: Keep blocks marked as milestones.
            keep_difficulty_shifts: Keep blocks with difficulty_shift=True.
            keep_every_nth: Keep every Nth block for continuity (0 = keep none).

        Returns:
            Number of nodes removed.
        """
        to_remove: List[int] = []
        for nid, node in self.nodes.items():
            content = node.content
            if not isinstance(content, dict):
                continue
            if content.get('type') != 'block_observation':
                continue
            # Never remove axioms or grounded nodes
            if node.node_type == 'axiom' or node.grounding_source:
                continue

            height = content.get('height', 0)
            # Keep conditions
            if keep_milestones and content.get('milestone'):
                continue
            if keep_difficulty_shifts and content.get('difficulty_shift'):
                continue
            if content.get('tx_count', 0) > 1:  # Has real transactions
                continue
            if content.get('has_thought_proof'):
                continue
            if keep_every_nth > 0 and height % keep_every_nth == 0:
                continue
            # This is a routine empty block observation — remove it
            to_remove.append(nid)

        if not to_remove:
            logger.info("Compaction: no routine block_observations to remove")
            return 0

        logger.info(
            "Compacting %d routine block_observation nodes (keeping milestones=%s, "
            "difficulty_shifts=%s, every_%d)",
            len(to_remove), keep_milestones, keep_difficulty_shifts, keep_every_nth,
        )

        # Use existing prune infrastructure for safe removal
        remove_set = set(to_remove)
        with self._lock:
            self.edges = deque(
                (e for e in self.edges
                 if e.from_node_id not in remove_set and e.to_node_id not in remove_set),
                maxlen=MAX_EDGES,
            )
            for nid in remove_set:
                for edge in self._adj_out.get(nid, []):
                    adj_list = self._adj_in.get(edge.to_node_id, [])
                    self._adj_in[edge.to_node_id] = [e for e in adj_list if e.from_node_id != nid]
                    neighbor = self.nodes.get(edge.to_node_id)
                    if neighbor and nid in neighbor.edges_in:
                        neighbor.edges_in.remove(nid)
                for edge in self._adj_in.get(nid, []):
                    adj_list = self._adj_out.get(edge.from_node_id, [])
                    self._adj_out[edge.from_node_id] = [e for e in adj_list if e.to_node_id != nid]
                    neighbor = self.nodes.get(edge.from_node_id)
                    if neighbor and nid in neighbor.edges_out:
                        neighbor.edges_out.remove(nid)
                self._adj_out.pop(nid, None)
                self._adj_in.pop(nid, None)
                del self.nodes[nid]
            self._merkle_dirty = True

        # Cascade to search and vector indices
        for nid in remove_set:
            if hasattr(self, 'search_index') and self.search_index is not None:
                try:
                    self.search_index.remove_node(nid)
                except Exception:
                    pass
            if hasattr(self, 'vector_index') and self.vector_index is not None:
                try:
                    self.vector_index.remove_node(nid)
                except Exception:
                    pass

        # Delete from database
        if hasattr(self, 'db_manager') and self.db_manager:
            try:
                from ..database.manager import DatabaseManager
                if isinstance(self.db_manager, DatabaseManager):
                    with self.db_manager.get_session() as session:
                        from ..database.models import KnowledgeNode, KnowledgeEdge
                        batch_size = 500
                        remove_list = list(remove_set)
                        for i in range(0, len(remove_list), batch_size):
                            batch = remove_list[i:i + batch_size]
                            session.query(KnowledgeEdge).filter(
                                (KnowledgeEdge.from_node_id.in_(batch))
                                | (KnowledgeEdge.to_node_id.in_(batch))
                            ).delete(synchronize_session=False)
                            session.query(KnowledgeNode).filter(
                                KnowledgeNode.node_id.in_(batch)
                            ).delete(synchronize_session=False)
                        session.commit()
                    logger.info("Compaction: deleted %d nodes from database", len(remove_set))
            except Exception as e:
                logger.warning("Compaction DB cleanup failed: %s", e)

        logger.info(
            "Compaction complete: removed %d nodes, %d remaining",
            len(remove_set), len(self.nodes),
        )
        return len(remove_set)

# --- Rust acceleration shim ---
# aether_core Rust acceleration: data classes (KeterNode/KeterEdge) stay Python
# because the DB-backed KnowledgeGraph serializes them with Python attributes.
# PhiCalculator stays Python too (Rust API mismatch). The Rust crate provides
# standalone KG/Phi for future use but isn't drop-in compatible yet.
try:
    import aether_core as _aether_core  # noqa: F401
    logger.info("KnowledgeGraph: aether_core available, using Python KG (DB-backed)")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python KnowledgeGraph")


# ────────────────────────────────────────────────────────────────────────
# Differential Privacy Wrapper (L5)
# ────────────────────────────────────────────────────────────────────────

import random as _random


class DPKnowledgeGraphQuery:
    """Differential-privacy wrapper for knowledge graph queries.

    Adds calibrated Laplace noise to aggregate numeric results (counts,
    scores) so that the presence or absence of any single knowledge node
    cannot be inferred from the query output.

    Args:
        knowledge_graph: The underlying KnowledgeGraph instance.
        epsilon: Privacy budget (lower = more private, higher = more accurate).
                 Default 1.0 is a reasonable balance.
    """

    def __init__(self, knowledge_graph: "KnowledgeGraph", epsilon: float = 1.0):
        self.kg = knowledge_graph
        self.epsilon = max(epsilon, 0.01)  # floor to prevent division by zero

    def _laplace_noise(self, sensitivity: float) -> float:
        """Sample Laplace noise scaled to sensitivity / epsilon."""
        scale = sensitivity / self.epsilon
        return _random.gauss(0, 0) + (_random.expovariate(1.0 / scale) - _random.expovariate(1.0 / scale))

    def node_count(self) -> int:
        """Return noisy node count (sensitivity = 1)."""
        return max(0, int(len(self.kg.nodes) + self._laplace_noise(1.0)))

    def edge_count(self) -> int:
        """Return noisy edge count (sensitivity = 1)."""
        return max(0, int(len(self.kg.edges) + self._laplace_noise(1.0)))

    def type_distribution(self) -> Dict[str, int]:
        """Return noisy distribution of node types (sensitivity = 1 per type)."""
        counts: Dict[str, int] = {}
        for node in self.kg.nodes.values():
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return {
            ntype: max(0, int(count + self._laplace_noise(1.0)))
            for ntype, count in counts.items()
        }

    def avg_confidence(self) -> float:
        """Return noisy average confidence (sensitivity ≈ 1/n)."""
        nodes = list(self.kg.nodes.values())
        if not nodes:
            return 0.0
        avg = sum(n.confidence for n in nodes) / len(nodes)
        sensitivity = 1.0 / max(len(nodes), 1)
        return max(0.0, min(1.0, avg + self._laplace_noise(sensitivity)))

    def search(self, query: str, top_k: int = 10) -> List[Tuple["KeterNode", float]]:
        """Run search with noisy scores (sensitivity = 1.0 for similarity)."""
        results = self.kg.search(query, top_k=top_k)
        noisy_results = []
        for node, score in results:
            noisy_score = max(0.0, score + self._laplace_noise(0.1))
            noisy_results.append((node, noisy_score))
        noisy_results.sort(key=lambda x: x[1], reverse=True)
        return noisy_results
