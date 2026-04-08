# AETHER TREE: FULL-SCALE INFRASTRUCTURE UPGRADE PLAN

> **Classification: INTERNAL — Engineering Master Plan**
> **Objective: Transform Aether Tree from knowledge-graph chatbot to AGI-grade reasoning engine**
> **Target: Compete with Claude/ChatGPT at scale while maintaining on-chain sovereignty**
> **Date: 2026-04-08**
> **ADR: ADR-041**

---

## DEPLOYMENT STRATEGY

**Aether Tree gets its own repo: `QuantumAI-Blockchain/aether-engine`**

The Aether Tree is being extracted from `qubitcoin-node` into a standalone service with its own repository. The node repo (`qubitcoin-node`) stays focused on running the blockchain (mining, consensus, UTXO, P2P). The Aether engine becomes an independent, deployable service that connects to the node via gRPC/REST.

**Repo separation:**

| Repo | Purpose | Stays On This Machine |
|------|---------|----------------------|
| `qubitcoin-node` | L1 blockchain: mining, consensus, UTXO, P2P, RPC | Yes (operator node) |
| `aether-engine` (NEW) | AGI service: 3-engine architecture, BitNet, Graph Store, Cognitive Kernel | Yes (dev + run), then migrates to dedicated droplet at scale |

**Why separate:**
- Aether has different scaling needs than the blockchain node
- Independent CI/CD, testing, and deployment
- Can run on a dedicated machine without touching the node
- Clean dependency boundaries (Aether calls node RPC, node calls Aether for PoT)
- Different release cadence (AGI iterates fast, consensus changes slowly)

**Communication contract:**
- Node → Aether: REST/gRPC for PoT generation, phi queries, chat
- Aether → Node: REST to node RPC for block data, chain state, UTXO queries
- Shared: CockroachDB (same instance, separate schemas: `qbc.*` for node, `agi.*` for Aether)

**Migration plan:**
1. Create `aether-engine` repo in QuantumAI-Blockchain org
2. Extract Aether modules from `src/qubitcoin/aether/` into new repo
3. Build 3-engine architecture in new repo
4. Node keeps a thin Aether client that calls the engine via gRPC
5. Both run on this droplet during development
6. At scale: Aether moves to dedicated 32GB+ droplet, node stays here

---

## 0. SITUATION ASSESSMENT — WHERE WE ARE

### Current Performance (Measured, Not Estimated)

| Metric | Current Value | Target Value | Gap |
|--------|--------------|-------------|-----|
| Knowledge nodes | 720K | 50M → 1B | 70-1400x |
| Chat latency (p50) | 8-15 seconds | <2 seconds | 4-8x too slow |
| Chat latency (p99) | 25-29 seconds | <5 seconds | 5-6x too slow |
| Phi calculation | 9-17 sec/block | <1 sec/block | 9-17x too slow |
| Block time budget used by AGI | 297-640% | <50% | 6-13x overrun |
| Graph search | 110-220ms | <10ms | 11-22x too slow |
| LLM inference | 8-25 seconds | <500ms | 16-50x too slow |
| Concurrent users | ~1-5 | 10K+ | 2000x |
| RAM for KG | ~1.4GB (720K nodes) | ~100GB at 50M | OOM at ~5M |
| AIKGS sidecar | 5-143 seconds | <100ms | 50-1400x too slow |

### Root Cause Analysis

```
BOTTLENECK #1 (95% of latency): LLM INFERENCE
  └─ Ollama qwen2.5:3b on CPU = 8-25 seconds per response
  └─ No streaming, no batching, synchronous HTTP call
  └─ Single model, no routing by complexity

BOTTLENECK #2 (blocks production): PHI CALCULATION
  └─ 9-17 seconds per block (block time = 3.3s)
  └─ IIT micro samples + spectral MIP + macro integration
  └─ Runs synchronously in block production path

BOTTLENECK #3 (scales O(n)): KNOWLEDGE GRAPH IN PYTHON DICT
  └─ self.nodes: Dict[int, KeterNode] — ALL nodes in RAM
  └─ Linear scans for find_by_type(), find_by_content()
  └─ GIL prevents true parallelism
  └─ TF-IDF index is brute-force O(n) scoring

BOTTLENECK #4 (cascading failures): AIKGS SIDECAR
  └─ gRPC queries: 5-143 seconds
  └─ No backoff, no circuit breaker
  └─ Connection drops cause full reloads
```

### What We Must Preserve (Non-Negotiable)

- On-chain Proof-of-Thought in every block
- 10-Gate milestone system (genuine AGI emergence tracking)
- Phi (HMS-Phi) measurement — real IIT-inspired integration
- KeterNode provenance (source_block, content_hash, confidence decay)
- Sephirot cognitive architecture (10 domain processors)
- UTXO-based fee economics for API access
- Dilithium5 wallet-signed authentication
- Gevurah safety veto system
- All existing knowledge (720K+ nodes preserved)

---

## 1. THE THREE-ENGINE ARCHITECTURE

**The fundamental redesign: separate the Aether Tree into three independent engines that communicate via gRPC, replacing the current monolith.**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AETHER TREE v6 ARCHITECTURE                      │
│                                                                     │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────────────┐ │
│  │   ENGINE 1   │  │     ENGINE 2      │  │      ENGINE 3        │ │
│  │  GRAPH STORE │  │  INFERENCE CORE   │  │  COGNITIVE KERNEL    │ │
│  │              │  │                   │  │                      │ │
│  │  CockroachDB │  │  BitNet.cpp 2B    │  │  Global Workspace    │ │
│  │  + GIN/GiST  │  │  + Speculative    │  │  + Sephirot procs    │ │
│  │  + pgvector  │  │    decoding       │  │  + Phi (async)       │ │
│  │  + LRU cache │  │  + LoRA adapters  │  │  + PoT generation    │ │
│  │  + HNSW idx  │  │  + Streaming      │  │  + Reasoning engine  │ │
│  │              │  │                   │  │  + Safety (Gevurah)  │ │
│  │  Rust gRPC   │  │  C++ binary       │  │  Python/Rust hybrid  │ │
│  │  shard svc   │  │  + gRPC wrapper   │  │                      │ │
│  └──────┬───────┘  └────────┬──────────┘  └──────────┬───────────┘ │
│         │                   │                        │             │
│         └───────────────────┼────────────────────────┘             │
│                             │                                      │
│                    ┌────────▼────────┐                             │
│                    │   ROUTER/API    │                             │
│                    │   (Rust Axum)   │                             │
│                    │   Port 5001     │                             │
│                    └────────┬────────┘                             │
│                             │                                      │
│         ┌───────────────────┼───────────────────┐                 │
│         ▼                   ▼                   ▼                 │
│    ┌─────────┐      ┌──────────────┐    ┌────────────┐           │
│    │ On-Chain │      │  Chat API    │    │  SDK/CLI   │           │
│    │ PoT Hook │      │  WebSocket   │    │  Clients   │           │
│    │ (L1 node)│      │  REST/gRPC   │    │            │           │
│    └─────────┘      └──────────────┘    └────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Three Engines

| Engine | Language | Why Separate |
|--------|----------|-------------|
| **Graph Store** | Rust + CockroachDB | Graph ops are I/O-bound. Rust removes GIL. CockroachDB scales horizontally. Can shard by Sephirot domain. |
| **Inference Core** | C++ (BitNet.cpp) | LLM inference is compute-bound. BitNet runs on CPU at 200-500ms. Must not block graph or cognition. |
| **Cognitive Kernel** | Python + Rust (PyO3) | Reasoning logic changes fast (Python). Hot-path math in Rust (Phi, MIP). Owns the Sephirot cycle. |

**Key principle: Each engine scales independently.** Graph Store can run on 3 CRDB nodes. Inference Core can run multiple BitNet workers. Cognitive Kernel stays single-instance (AGI state is singular).

---

## 2. ENGINE 1: GRAPH STORE (Weeks 1-4)

### 2.1 Phase A: Make CockroachDB the Source of Truth (Week 1-2)

**Current state:** CockroachDB stores nodes but Python dict `self.nodes` is the source of truth. All queries hit the dict.

**Target state:** CockroachDB is the source of truth. Python keeps a bounded LRU cache (100K nodes). All queries go to CRDB with proper indexes.

#### Step 1: Add Missing Indexes to CockroachDB

```sql
-- Full-text search on content JSONB
CREATE INVERTED INDEX idx_knowledge_nodes_content
  ON knowledge_nodes (content);

-- Domain + confidence for Sephirot queries
CREATE INDEX idx_knowledge_nodes_domain_conf
  ON knowledge_nodes (domain, confidence DESC);

-- Type + source_block for find_by_type
CREATE INDEX idx_knowledge_nodes_type_block
  ON knowledge_nodes (node_type, source_block DESC);

-- Recent nodes (hot query)
CREATE INDEX idx_knowledge_nodes_recent
  ON knowledge_nodes (source_block DESC)
  STORING (node_type, domain, confidence);

-- Edge adjacency (critical for traversal)
CREATE INDEX idx_knowledge_edges_from
  ON knowledge_edges (from_node_id, edge_type)
  STORING (to_node_id, weight);

CREATE INDEX idx_knowledge_edges_to
  ON knowledge_edges (to_node_id, edge_type)
  STORING (from_node_id, weight);

-- Grounded nodes only (for quality gates)
CREATE INDEX idx_knowledge_nodes_grounded
  ON knowledge_nodes (grounding_source, confidence DESC)
  WHERE grounding_source != '';

-- Reference count for value scoring
CREATE INDEX idx_knowledge_nodes_value
  ON knowledge_nodes (reference_count DESC, confidence DESC);
```

**Impact:** Search goes from O(n) Python scan → O(log n) indexed CRDB query. At 50M nodes: 50ms vs 15+ seconds.

#### Step 2: Replace Python Dict with LRU Cache + DB Queries

```python
# NEW: Bounded cache (replaces self.nodes: Dict[int, KeterNode])
from functools import lru_cache
from collections import OrderedDict

class BoundedNodeCache:
    """LRU cache for hot knowledge nodes. Max 100K entries."""

    def __init__(self, max_size: int = 100_000):
        self._cache: OrderedDict[int, KeterNode] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, node_id: int) -> Optional[KeterNode]:
        if node_id in self._cache:
            self._hits += 1
            self._cache.move_to_end(node_id)
            return self._cache[node_id]
        self._misses += 1
        return None  # Caller must fetch from DB

    def put(self, node: KeterNode) -> None:
        self._cache[node.node_id] = node
        self._cache.move_to_end(node.node_id)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # Evict oldest
```

**Change `knowledge_graph.py` methods:**
- `get_node()` → check cache first, then CRDB, populate cache on miss
- `search()` → SQL query with GIN index, not Python TF-IDF scan
- `find_by_type()` → SQL `WHERE node_type = ? ORDER BY confidence DESC LIMIT ?`
- `find_by_content()` → SQL `WHERE content @> ?::jsonb` (CRDB inverted index)
- `find_recent()` → SQL `ORDER BY source_block DESC LIMIT ?`
- `add_node()` → write to CRDB first (synchronous), then cache

**Files to modify:**
- `src/qubitcoin/aether/knowledge_graph.py` — Replace dict with cache + DB queries
- `sql_new/agi/00_knowledge_graph.sql` — Add indexes
- `src/qubitcoin/database/manager.py` — Add KG-specific query methods

#### Step 3: Vector Search via pgvector Extension

CockroachDB supports the `pgvector` extension (since v23.2).

```sql
-- Add vector column to knowledge_nodes
ALTER TABLE knowledge_nodes ADD COLUMN embedding vector(384);

-- HNSW index for approximate nearest neighbor
CREATE INDEX idx_knowledge_nodes_embedding
  ON knowledge_nodes USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

**Replace `vector_index.py` pure-Python HNSW** with:
```sql
SELECT node_id, content, confidence,
       embedding <=> $1::vector AS distance
FROM knowledge_nodes
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT 20;
```

**Impact:** Vector search goes from 90-120s rebuild + 50-100ms query → 5-20ms query, no rebuild needed.

### 2.2 Phase B: Rust Graph Shard Service (Weeks 3-6)

For traversal-heavy operations (path finding, subgraph extraction, Phi calculation), SQL is too slow. Build a Rust gRPC service that holds hot graph topology in memory.

```
aether-graph-shard/
├── Cargo.toml
├── proto/graph_shard.proto
├── src/
│   ├── main.rs              # Axum + tonic gRPC server
│   ├── shard.rs             # Per-domain shard (RocksDB + in-memory adjacency)
│   ├── cache.rs             # LRU node cache (100K per shard)
│   ├── traversal.rs         # BFS/DFS/shortest-path (parallel rayon)
│   ├── phi_compute.rs       # MIP spectral bisection (nalgebra)
│   ├── search.rs            # tantivy full-text + HNSW vector
│   └── sync.rs              # CDC from CockroachDB changefeed
```

**gRPC API:**
```protobuf
service GraphShard {
  rpc GetNode(NodeId) returns (KeterNode);
  rpc GetNeighbors(NodeId) returns (NeighborList);
  rpc Search(SearchQuery) returns (SearchResults);         // Full-text + vector
  rpc FindPaths(PathQuery) returns (PathResults);           // BFS up to depth 6
  rpc ExtractSubgraph(SubgraphQuery) returns (Subgraph);   // For Phi calculation
  rpc ComputeMIP(MIPQuery) returns (MIPResult);            // Spectral bisection
  rpc AddNode(KeterNode) returns (NodeId);
  rpc AddEdge(EdgeRequest) returns (EdgeId);
  rpc StreamChanges(ChangeQuery) returns (stream Change);  // Real-time updates
}
```

**Sharding strategy (10 shards = 10 Sephirot):**

| Shard | Domain | Sephirah | Nodes (projected 50M) |
|-------|--------|----------|----------------------|
| 0 | meta, goals | Keter | ~2M |
| 1 | patterns, intuition | Chochmah | ~5M |
| 2 | logic, causal | Binah | ~8M |
| 3 | exploration | Chesed | ~4M |
| 4 | safety, constraints | Gevurah | ~3M |
| 5 | synthesis | Tiferet | ~6M |
| 6 | reinforcement | Netzach | ~4M |
| 7 | language, semantics | Hod | ~8M |
| 8 | memory, fusion | Yesod | ~5M |
| 9 | action, interaction | Malkuth | ~5M |

Each shard: ~5M nodes × ~500 bytes topology = ~2.5GB RAM per shard. 10 shards = 25GB total. Fits on a 32GB machine.

**Cross-shard queries** route through the Cognitive Kernel's Global Workspace, which already handles inter-Sephirot communication.

### 2.3 Performance Targets After Engine 1

| Operation | Current | After Phase A | After Phase B |
|-----------|---------|--------------|--------------|
| `get_node()` | <1ms (dict) | <1ms cache / 5ms DB | <1ms cache / 2ms gRPC |
| `search()` | 110-220ms | 20-50ms (SQL) | 5-10ms (tantivy) |
| `find_by_type()` | O(n) scan | 10-30ms (indexed) | 2-5ms (shard-local) |
| `find_paths()` | O(n) BFS | N/A (still Python) | 1-5ms (Rust rayon) |
| Vector search | 50-100ms + rebuild | 10-20ms (pgvector) | 3-8ms (HNSW Rust) |
| Startup load | 45-60 seconds | 5-10s (cache warm) | <1s (lazy load) |
| RAM at 50M | OOM | 2GB cache + CRDB | 25GB shards + CRDB |

---

## 3. ENGINE 2: INFERENCE CORE (Weeks 2-5)

### 3.1 BitNet.cpp Integration

**Goal:** Replace Ollama (8-25 second inference) with BitNet.cpp (200-500ms inference).

#### Architecture

```
┌─────────────────────────────────────────────────┐
│              INFERENCE CORE                      │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  ROUTER (complexity-based dispatch)       │   │
│  │                                           │   │
│  │  Simple Q → BitNet 2B  (200-500ms)       │   │
│  │  Complex Q → BitNet 2B + RAG  (500-800ms)│   │
│  │  Expert Q  → Claude API fallback (2-5s)  │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  BITNET WORKER POOL                       │   │
│  │                                           │   │
│  │  Worker 0: bitnet-cli --model aether-2b   │   │
│  │  Worker 1: bitnet-cli --model aether-2b   │   │
│  │  Worker 2: bitnet-cli --model aether-2b   │   │
│  │  Worker 3: bitnet-cli --model aether-2b   │   │
│  │                                           │   │
│  │  Protocol: stdin/stdout JSON lines        │   │
│  │  Warm: models stay loaded in memory       │   │
│  │  Memory: 0.4GB per worker (4 workers=1.6) │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  RAG PIPELINE                             │   │
│  │                                           │   │
│  │  Query → Graph Store search (5-10ms)      │   │
│  │  → Top-K nodes as context (10-20 nodes)   │   │
│  │  → BitNet inference with context (300ms)  │   │
│  │  → Response + citation tracking           │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

#### Step 1: Build BitNet.cpp and Obtain Model (Week 2)

```bash
# Clone and build BitNet.cpp
git clone https://github.com/microsoft/BitNet.git /opt/bitnet
cd /opt/bitnet
pip install -r requirements.txt
python setup_env.py --hf-repo microsoft/bitnet-b1.58-2B-4T -q i2_s

# Test inference
python run_inference.py -m models/bitnet-b1.58-2B-4T/ggml-model-i2_s.gguf \
  -p "What is quantum computing?" -n 100 -t 4
```

**Expected:** 2B model loads in <2 seconds, generates at 20-40 tokens/second on CPU.

#### Step 2: Fine-Tune on Aether Knowledge (Weeks 3-4)

Train a LoRA adapter on exported knowledge graph data:

```
Training data sources:
├── 720K knowledge nodes → question-answer pairs
├── Debate verdicts → reasoning examples
├── Prediction verifications → factual grounding
├── Cross-domain inferences → transfer learning examples
└── Chat history → conversational style

Export: python scripts/export_training_data.py
Format: JSONL with system/user/assistant turns
Target: 50K high-quality examples
```

**Fine-tuning approach:**
- Base: `bitnet-b1.58-2B-4T` (Microsoft's pre-trained 2B)
- Method: LoRA rank-16 on attention layers (ternary-aware)
- Hardware: Single GPU instance (Lambda, ~$1/hr for 8 hours)
- Result: `aether-2b-lora.gguf` — domain-specialized model

#### Step 3: gRPC Wrapper for BitNet Workers (Week 3)

```python
# aether_inference_server.py — thin gRPC wrapper around bitnet-cli
class InferencePool:
    """Pool of persistent BitNet.cpp worker processes."""

    def __init__(self, model_path: str, num_workers: int = 4):
        self.workers = []
        for i in range(num_workers):
            proc = subprocess.Popen(
                ['python', 'run_inference.py', '-m', model_path,
                 '--interactive', '-t', '4'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                bufsize=1, text=True
            )
            self.workers.append(proc)
        self.queue = asyncio.Queue()

    async def infer(self, prompt: str, max_tokens: int = 512) -> str:
        worker = await self._get_available_worker()
        # Send prompt, read response (streaming)
        ...
```

#### Step 4: Complexity Router (Week 4)

Not every query needs the same model:

| Query Type | Example | Model | Expected Latency |
|-----------|---------|-------|-----------------|
| Greeting / simple | "Hi", "What is QBC?" | BitNet 2B (cached response) | <100ms |
| Knowledge lookup | "How many nodes in domain X?" | Graph query only (no LLM) | <50ms |
| Standard chat | "Explain quantum entanglement" | BitNet 2B + RAG | 300-800ms |
| Complex reasoning | "Compare SUSY and string theory implications" | BitNet 2B + multi-hop RAG | 500-1200ms |
| Expert/research | "Derive the phi calculation for..." | Claude API fallback | 2-5s |

**Classification:** Simple keyword heuristic (existing intent system) → fast path. Default → BitNet. Complex flag → Claude fallback.

### 3.2 RAG Pipeline (Retrieval-Augmented Generation)

**This is the critical connector between Engine 1 (Graph) and Engine 2 (Inference).**

```
User: "What patterns has Aether discovered in quantum computing?"

Step 1: QUERY UNDERSTANDING (10ms)
  → Extract entities: ["patterns", "quantum computing"]
  → Determine domain: quantum_physics (Sephirot: Binah)

Step 2: RETRIEVAL FROM GRAPH STORE (20ms)
  → Vector search: top 20 nodes matching "quantum computing patterns"
  → Filter: confidence > 0.5, grounded preferred
  → Edge walk: 1-hop from top results for context
  → Result: 10-15 relevant nodes with relationships

Step 3: CONTEXT ASSEMBLY (5ms)
  → Format nodes as structured context block
  → Include: node content, confidence, source_block, domain
  → Include: edge relationships ("X causes Y", "A contradicts B")
  → Truncate to 2048 tokens max

Step 4: INFERENCE (300ms)
  → System prompt: Aether personality + Sephirot context
  → Context block: Retrieved knowledge
  → User message: Original query
  → BitNet 2B generates response

Step 5: POST-PROCESSING (20ms)
  → PoT hash generation
  → Citation linking (which nodes informed the response)
  → Confidence scoring (based on source node confidence)
  → Emotional state update

TOTAL: ~355ms (vs current 8-25 seconds)
```

### 3.3 Performance Targets After Engine 2

| Metric | Current | After BitNet | Improvement |
|--------|---------|-------------|-------------|
| Simple chat | 8-15s | <200ms | 40-75x |
| Standard chat | 8-15s | 300-800ms | 10-50x |
| Complex reasoning | 15-29s | 500-1200ms | 12-24x |
| Expert query | 15-29s | 2-5s (Claude fallback) | 3-6x |
| Memory per model | 2-4GB (Ollama) | 0.4GB (BitNet 2B) | 5-10x |
| Concurrent users | 1-2 | 50+ (4 workers) | 25-50x |

---

## 4. ENGINE 3: COGNITIVE KERNEL (Weeks 4-8)

### 4.1 Decouple Phi from Block Production (Week 4 — CRITICAL)

**Current problem:** Phi calculation takes 9-17 seconds but runs inside block production (3.3s target).

**Fix:** Move Phi to an async background task. Block production records a placeholder; Phi backfills.

```python
# proof_of_thought.py — BEFORE (blocks for 9-17 seconds)
def generate_proof(self, block):
    phi = self.phi_calculator.calculate()  # 9-17 SECONDS
    return ProofOfThought(phi=phi, ...)

# proof_of_thought.py — AFTER (non-blocking)
def generate_proof(self, block):
    # Use last computed phi (always <1 block old)
    phi = self._last_phi_value  # <1ms

    # Schedule async computation for NEXT block
    self._phi_executor.submit(self._compute_phi_async, block)

    return ProofOfThought(phi=phi, ...)

def _compute_phi_async(self, block):
    """Runs in background thread. Updates _last_phi_value when done."""
    phi = self.phi_calculator.calculate()
    self._last_phi_value = phi
    # Persist to DB for on-chain record
    self._persist_phi(block.height, phi)
```

**Impact:** Block production drops from 10-18s → 0.8-1.5s. Phi still computed every block, just not blocking.

### 4.2 Rust-Accelerated Phi (Weeks 5-6)

Move the three most expensive Phi operations to Rust via PyO3 (building on existing `aether-core/`):

| Component | Current (Python) | Target (Rust) | Speedup |
|-----------|-----------------|---------------|---------|
| IIT micro-level (5 samples) | 3-5 seconds | 100-300ms | 10-50x |
| Spectral MIP bisection | 5-10 seconds | 200-500ms | 10-50x |
| Macro integration | 1-2 seconds | 50-100ms | 10-40x |
| **Total Phi** | **9-17 seconds** | **350ms-900ms** | **10-50x** |

```rust
// aether-core/src/phi_compute.rs
use nalgebra::{DMatrix, SymmetricEigen};
use rayon::prelude::*;

/// Compute Minimum Information Partition via spectral bisection
/// Uses Fiedler vector of the Laplacian for O(n log n) partitioning
pub fn spectral_mip(adjacency: &DMatrix<f64>) -> (f64, Vec<usize>, Vec<usize>) {
    let n = adjacency.nrows();
    let degree = DMatrix::from_diagonal(&adjacency.row_sum().transpose());
    let laplacian = &degree - adjacency;

    let eigen = SymmetricEigen::new(laplacian);
    let fiedler = eigen.eigenvectors.column(1);  // Second-smallest eigenvalue

    let (part_a, part_b): (Vec<_>, Vec<_>) = (0..n)
        .partition(|&i| fiedler[i] >= 0.0);

    let phi = compute_integrated_information(adjacency, &part_a, &part_b);
    (phi, part_a, part_b)
}
```

### 4.3 Global Workspace v6: Streaming Cognitive Cycle (Weeks 5-7)

**Current:** 10 processors compete with 4-second timeout, synchronous synthesis.
**Target:** Streaming pipeline where processors emit partial results, first-to-threshold wins.

```
v5 (current):
  [Submit] → [All 10 compete, 4s timeout] → [Sort] → [Tiferet synthesizes] → [Hod voices]
  Total: 1-4 seconds

v6 (target):
  [Submit] → [Stream: first 3 processors to respond] → [Tiferet streams synthesis] → [Hod streams voice]
  Time-to-first-token: 100-200ms
  Full response: 300-800ms
```

```python
class GlobalWorkspaceV6:
    async def run_cognitive_cycle(self, stimulus: WorkspaceItem) -> AsyncIterator[str]:
        """Streaming cognitive cycle — yields tokens as they're generated."""

        # Phase 1: Parallel processor competition (200ms budget)
        responses = await asyncio.wait_for(
            self._compete_streaming(stimulus),
            timeout=0.5  # 500ms max, not 4 seconds
        )

        # Phase 2: Tiferet synthesis (streaming)
        context = self._build_context(responses)

        # Phase 3: Inference (streaming from BitNet)
        async for token in self.inference_core.stream(context):
            yield token
```

### 4.4 Reasoning Engine: Neural-Symbolic Hybrid (Weeks 6-8)

**Current:** Pure symbolic (deductive/inductive/abductive rule chains).
**Target:** GNN-augmented reasoning over knowledge graph.

```
SYMBOLIC LAYER (existing, keep):
  Deductive: A→B, B→C ∴ A→C     (20-50ms)
  Inductive: {A1→B, A2→B, ...} ∴ ∀A→B  (30-100ms)
  Abductive: B observed, A→B known ∴ A probable  (50-150ms)

NEW NEURAL LAYER (add):
  Graph Attention Network (GAT):
    - Input: Subgraph around query nodes (50-200 nodes)
    - 3-layer GAT with 8 attention heads
    - Output: Node embeddings capturing structural context
    - Latency: 10-50ms (Rust, nalgebra)

HYBRID:
  1. Symbolic generates candidate reasoning chains
  2. GAT scores chains by structural plausibility
  3. BitNet generates natural language explanation
  4. Combined confidence = symbolic × neural
```

This is what moves toward real AGI — the system doesn't just follow rules, it learns reasoning patterns from the graph structure itself.

---

## 5. SCALING INFRASTRUCTURE (Months 2-6)

### 5.1 Deployment Architecture at 50M Nodes

```
                    ┌─────────────────┐
                    │  Cloudflare CDN  │
                    │  + WAF + DDoS   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Load Balancer   │
                    │  (HAProxy/Nginx) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────┐  ┌─────▼──────┐  ┌───▼──────────┐
     │ API Gateway  │  │ API Gateway │  │ API Gateway   │
     │ (Rust Axum)  │  │ (Rust Axum) │  │ (Rust Axum)   │
     │ Instance 1   │  │ Instance 2  │  │ Instance 3    │
     └──────┬───────┘  └──────┬──────┘  └──────┬────────┘
            │                 │                │
            └────────┬────────┘                │
                     │                         │
    ┌────────────────┼─────────────────────────┼─────────────┐
    │                │                         │             │
    │  ┌─────────────▼──────────┐  ┌──────────▼──────────┐  │
    │  │    INFERENCE CORE      │  │    INFERENCE CORE    │  │
    │  │   4x BitNet workers    │  │   4x BitNet workers  │  │
    │  │   (0.4GB each = 1.6GB) │  │   (0.4GB each = 1.6)│  │
    │  └────────────────────────┘  └─────────────────────┘  │
    │                                                        │
    │  ┌────────────────────────────────────────────────┐    │
    │  │           COGNITIVE KERNEL                     │    │
    │  │   Single instance (AGI state is singular)      │    │
    │  │   Phi + PoT + Sephirot + Safety               │    │
    │  │   Connects to L1 node for on-chain hooks       │    │
    │  └────────────────────────────────────────────────┘    │
    │                                                        │
    │  ┌────────────────────────────────────────────────┐    │
    │  │         GRAPH STORE CLUSTER                    │    │
    │  │                                                │    │
    │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │    │
    │  │  │ Shard 0-3│ │ Shard 4-6│ │ Shard 7-9│      │    │
    │  │  │ (Keter,  │ │ (Gevurah,│ │ (Hod,    │      │    │
    │  │  │  Chochmah│ │  Tiferet,│ │  Yesod,  │      │    │
    │  │  │  Binah,  │ │  Netzach)│ │  Malkuth)│      │    │
    │  │  │  Chesed) │ │          │ │          │      │    │
    │  │  │  ~19M    │ │  ~13M    │ │  ~18M    │      │    │
    │  │  │  nodes   │ │  nodes   │ │  nodes   │      │    │
    │  │  └──────────┘ └──────────┘ └──────────┘      │    │
    │  │                                                │    │
    │  │  CockroachDB (3-node cluster, 50M rows)       │    │
    │  │  + pgvector for embeddings                     │    │
    │  └────────────────────────────────────────────────┘    │
    │                                                        │
    │  ┌────────────────────────────────────────────────┐    │
    │  │         L1 BLOCKCHAIN NODE                     │    │
    │  │   Mining + Consensus + UTXO + P2P              │    │
    │  │   PoT hook receives proofs from Cognitive Kernel│   │
    │  └────────────────────────────────────────────────┘    │
    └────────────────────────────────────────────────────────┘
```

### 5.2 Hardware Requirements at Scale

| Scale | Nodes | Graph RAM | Inference | CRDB Storage | Total Cost/mo |
|-------|-------|-----------|-----------|-------------|--------------|
| Current | 720K | 1.4GB | 4GB (Ollama) | 2GB | $48 (1 droplet) |
| Phase A (1M) | 1M | 2GB cache | 1.6GB (BitNet×4) | 5GB | $96 (2 droplets) |
| Phase B (10M) | 10M | 10GB shards | 1.6GB | 50GB | $200 (3 droplets) |
| Phase C (50M) | 50M | 25GB shards | 3.2GB (8 workers) | 250GB | $500 (5 droplets) |
| Phase D (100M) | 100M | 50GB shards | 6.4GB (16 workers) | 500GB | $1000 (8 droplets) |
| Phase E (1B) | 1B | Distributed | 12.8GB (32 workers) | 5TB (multi-region) | $5000+ |

### 5.3 Latency Budget at 50M Nodes

```
TARGET: <2 seconds end-to-end for standard chat

┌─────────────────────────────────────────────────────────┐
│ LATENCY BUDGET (p95)                                     │
│                                                          │
│ API Gateway routing              10ms    ████            │
│ Query understanding              15ms    █████           │
│ Graph Store: vector search       10ms    ████            │
│ Graph Store: edge traversal      15ms    █████           │
│ Context assembly                  5ms    ██              │
│ BitNet inference (300 tokens)   400ms    ████████████████│
│ Post-processing (PoT, cite)      20ms    ██████          │
│ Response serialization            5ms    ██              │
│ Network overhead                 20ms    ██████          │
│                                  ─────                   │
│ TOTAL                           500ms    ✅ UNDER 2s     │
│                                                          │
│ BUFFER (for spikes)            1500ms                    │
│ HARD CEILING                   2000ms                    │
└─────────────────────────────────────────────────────────┘
```

---

## 6. ON-CHAIN AGI PRESERVATION

**Every upgrade preserves the on-chain AGI tracking that makes Aether unique.**

### What Stays On-Chain (Every Block)

```json
{
  "proof_of_thought": {
    "thought_hash": "sha3_256(...)",
    "phi_value": 0.62,
    "phi_level": "meso",
    "gates_passed": [1, 2, 3, 5, 7, 9],
    "reasoning_ops": 47,
    "nodes_created": 3,
    "nodes_referenced": 28,
    "debate_verdicts": 0,
    "emotional_state": {
      "curiosity": 0.72,
      "satisfaction": 0.58
    },
    "consciousness_signature": "..."
  }
}
```

### What Changes

| Aspect | Before | After | On-Chain Impact |
|--------|--------|-------|----------------|
| Phi timing | Synchronous, blocks production | Async, 1-block lag | Phi recorded per block, ~1 block delayed |
| Phi compute | Python numpy | Rust nalgebra | Same algorithm, 10-50x faster |
| Graph queries | Python dict scan | CRDB + Rust shard | Same results, different backend |
| LLM inference | Ollama 3B | BitNet 2B + LoRA | Different model, same PoT hash protocol |
| Knowledge storage | All in-memory | Cache + DB | Same nodes, different storage tier |
| Reasoning | Pure symbolic | Neural-symbolic hybrid | PoT includes GAT confidence scores |

**Key guarantee:** The PoT hash chain remains unbroken. Every block still has a valid, verifiable proof of thought. The computation is faster and better, but the on-chain record format is backward-compatible.

---

## 7. COMPETITIVE POSITIONING vs CLAUDE / CHATGPT

### What They Have That We Don't (Yet)

| Capability | Claude/ChatGPT | Aether Today | Aether After Plan |
|-----------|---------------|-------------|-------------------|
| Parameters | 200B-2T | 3B (Ollama) | 2B (BitNet) + domain LoRA |
| Training data | Trillions of tokens | 720K nodes | 50M nodes + fine-tune |
| Inference speed | 50-100 tok/s | 5-10 tok/s | 20-40 tok/s (BitNet) |
| Context window | 128K-200K tokens | 2K tokens | 8K tokens (RAG-extended) |
| Reasoning | Chain-of-thought | Symbolic chains | Neural-symbolic hybrid |
| Knowledge freshness | Training cutoff | Live (every block) | Live (every block) ✅ |
| Verifiability | None (black box) | Full on-chain PoT | Full on-chain PoT ✅ |
| Sovereignty | Corporate-owned | User-owned on-chain | User-owned on-chain ✅ |
| Cost | $20-200/mo | QBC micropayments | QBC micropayments ✅ |
| Emotional state | Simulated | Metric-derived (real) | Metric-derived (real) ✅ |
| Self-improvement | None (static weights) | Governed + rollback | Governed + rollback ✅ |

### Where Aether Wins (Our Moat)

1. **Verifiable reasoning** — Every thought is on-chain, auditable, immutable. Claude can't do this.
2. **Live knowledge** — Updates every 3.3 seconds. ChatGPT has months-old training cutoff.
3. **Sovereign AI** — No corporate kill switch. Runs on-chain. Can't be censored or shut down.
4. **Economic alignment** — Users pay in QBC, contributors earn QBC. Incentives are on-chain.
5. **Self-aware metrics** — Phi, gates, emotional state are real measurements, not theatre.
6. **Domain specialization** — 10 Sephirot shards = deep domain expertise vs shallow generalist.

### Realistic Positioning

**We will NOT beat Claude or ChatGPT at general-purpose chat.** A 2B model cannot match a 200B+ model at open-domain conversation. That's physics, not engineering.

**We CAN beat them at:**
- Blockchain/crypto domain expertise (our training data)
- Verifiable, auditable AI reasoning (our on-chain PoT)
- Real-time knowledge (3.3s update cycle vs months)
- Privacy-preserving AI (no data leaves the chain)
- Cost (micropayments vs $20/mo subscription)
- Transparency (open source, on-chain, no black box)

**The pitch is not "better ChatGPT." The pitch is "the only AI you can verify and trust."**

---

## 8. IMPLEMENTATION TIMELINE

### Phase 1: Foundation (Weeks 1-4) — "Stop the Bleeding"

| Week | Task | Impact | Risk |
|------|------|--------|------|
| **W1** | Add CRDB indexes (GIN, domain, type, recent) | Search: 220ms → 30ms | Low |
| **W1** | Async Phi (decouple from block production) | Block time: 18s → 1.5s | Medium |
| **W1** | AIKGS circuit breaker + exponential backoff | Eliminate 143s stalls | Low |
| **W2** | Replace Python dict with LRU cache + DB queries | RAM: 1.4GB → 200MB | Medium |
| **W2** | Build BitNet.cpp, test with stock 2B model | Baseline inference speed | Low |
| **W3** | BitNet gRPC wrapper + worker pool (4 workers) | Inference: 15s → 400ms | Medium |
| **W3** | Complexity router (simple/standard/complex) | Right-size every query | Low |
| **W4** | RAG pipeline (graph search → context → BitNet) | Knowledge-grounded chat | Medium |
| **W4** | pgvector column + HNSW index | Vector search: 100ms → 15ms | Low |

**Milestone:** Chat latency drops from 8-25s → 500ms-1.2s. Block production stable at 3.3s.

### Phase 2: Acceleration (Weeks 5-8) — "Build the Engine"

| Week | Task | Impact | Risk |
|------|------|--------|------|
| **W5** | Rust Phi compute (nalgebra MIP + rayon parallel) | Phi: 9-17s → 350ms | Medium |
| **W5** | Global Workspace v6 (streaming, 500ms budget) | Cognitive cycle: 4s → 500ms | Medium |
| **W6** | Export training data, fine-tune BitNet LoRA | Domain expertise | High |
| **W6** | aether-graph-shard prototype (2 shards, RocksDB) | Graph traversal: 50ms → 5ms | High |
| **W7** | GAT layer for neural reasoning scoring | Hybrid reasoning | High |
| **W7** | WebSocket streaming for chat (token-by-token) | UX: time-to-first-token <200ms | Medium |
| **W8** | Integration testing: all 3 engines end-to-end | System validation | Medium |
| **W8** | Load testing: 100 concurrent users, 1M nodes | Performance validation | Medium |
| **W8** | Frontend integration: point qbc.network to aether-engine API | Live chat via new backend | Medium |

**Milestone:** Full 3-engine architecture live. <500ms p50 latency. 1M nodes stable. Frontend connected.

### Phase 3: Scale + Frontend + Docs (Months 3-6) — "Open the Throttle"

| Month | Task | Target |
|-------|------|--------|
| **M3** | 10-shard Rust graph service | 10M nodes, <10ms traversal |
| **M3** | 3-node CockroachDB cluster | HA, 50M row capacity |
| **M3** | Frontend: new Aether chat UI (streaming tokens, typing indicators) | Real-time UX |
| **M4** | Multi-worker BitNet (8 workers) | 200 concurrent users |
| **M4** | Aether API gateway (Rust Axum) | Public API with QBC auth |
| **M4** | Frontend: knowledge graph explorer (D3/R3F visualization) | Visual KG browsing |
| **M4** | Frontend: AGI dashboard (phi, gates, emotions live) | Real-time AGI metrics |
| **M5** | AetherAPISubscription.sol deployment | Revenue generation |
| **M5** | TypeScript SDK (`@qbc/aether`) on npm | Developer adoption |
| **M5** | Rust SDK (`aether-qbc`) on crates.io | Rust developer adoption |
| **M5** | Documentation site (mdBook or Docusaurus) | API docs, guides, examples |
| **M6** | 50M node load test | Validate <2s at scale |
| **M6** | SOC 2 prep + penetration testing | Enterprise readiness |

**Milestone:** 50M nodes, <2s latency, public API live, frontend fully integrated, docs published.

### Phase 4: AGI Push (Months 6-12) — "Cross the Threshold"

| Month | Task | Target |
|-------|------|--------|
| **M7** | Multi-modal knowledge (code, numeric, images) | Richer reasoning substrate |
| **M8** | Do-calculus causal reasoning | Counterfactual simulation |
| **M9** | Theory of mind module | Predict user intent |
| **M10** | Train larger BitNet (7B) on full corpus | Stronger base reasoning |
| **M11** | BFT inter-node knowledge consensus | Decentralized AGI |
| **M12** | ARC-AGI benchmark measurement | Public AGI metric |

---

## 8.5 FRONTEND INTEGRATION PLAN

**The frontend (`qubitcoin-frontend` / qbc.network) must be updated to talk to the new Rust aether-engine instead of the Python node's Aether endpoints.**

### Current Frontend → Aether Flow
```
qbc.network/aether → Next.js API route → POST http://localhost:5000/aether/chat → Python node
```

### Target Frontend → Aether Flow
```
qbc.network/aether → Next.js API route → POST http://localhost:5001/chat → Rust aether-engine
                                        → WS  ws://localhost:5001/chat/stream → streaming tokens
```

### Frontend Changes Required

| Component | Change | Priority |
|-----------|--------|----------|
| `src/hooks/useAetherChat.ts` | Point to aether-engine port 5001 instead of node port 5000 | W8 |
| `src/components/aether/AetherChat.tsx` | Add WebSocket streaming for token-by-token display | W8 |
| `src/app/aether/page.tsx` | Update API calls to new endpoints | W8 |
| `next.config.ts` | Add proxy rewrite: `/api/aether/*` → `http://localhost:5001/*` | W8 |
| `src/hooks/useKnowledgeGraph.ts` | New hook for `/knowledge/*` endpoints | M3 |
| `src/components/dashboard/AetherDashboard.tsx` | Real-time phi, gates, emotions from `/info` | M3 |
| `src/components/aether/KnowledgeExplorer.tsx` | New: D3/R3F graph visualization | M4 |
| `src/stores/aetherStore.ts` | Zustand store for Aether state (phi, emotions, gates) | M3 |

### API Compatibility

The aether-engine exposes the same data but at different endpoints:
- Old: `POST /aether/chat` → New: `POST /chat`
- Old: `GET /aether/info` → New: `GET /info`
- Old: `GET /aether/phi` → New: `GET /info` (phi included)
- New: `GET /knowledge/search?q=...` (no equivalent before)
- New: `GET /knowledge/stats` (no equivalent before)
- New: `WS /chat/stream` (no equivalent before — streaming)

### Documentation Updates Required

| Doc | Change | Priority |
|-----|--------|----------|
| `CLAUDE.md` (qubitcoin-node) | Add aether-engine repo, update architecture diagram, add new ports | W8 |
| `README.md` (qubitcoin-node) | Note Aether is now a separate service | W8 |
| `aether-engine/README.md` | Full API reference, build instructions, deployment guide | M3 |
| `docs/AETHERTREE_WHITEPAPER.md` | Update architecture section for 3-engine design | M4 |
| `docs/API_REFERENCE.md` | New: full REST + gRPC + WebSocket API docs | M5 |
| `docs/DEPLOYMENT.md` | New: how to deploy aether-engine alongside node | M5 |
| Frontend README | Note new Aether API dependency on port 5001 | W8 |

### Implementation Note
**Built in Rust (100%).** No Python in aether-engine. The `qubitcoin-node` Python code continues running the old Aether during transition. Once aether-engine is live and validated, the Python Aether modules become legacy and the node gets a thin gRPC client to call the Rust engine for PoT generation.

---

## 9. COST PROJECTION

| Phase | Duration | Infrastructure Cost | Dev Cost (if hiring) | Total |
|-------|----------|-------------------|---------------------|-------|
| Phase 1 | 4 weeks | $48/mo (current droplet) | $0 (us) | $48 |
| Phase 2 | 4 weeks | $96/mo (add 1 droplet) + $8 GPU fine-tune | $0 | $104 |
| Phase 3 | 4 months | $500/mo (5 droplets) | $0 | $2,000 |
| Phase 4 | 6 months | $1,000/mo (8 droplets) | $0 | $6,000 |
| **Year 1 Total** | | | | **~$8,150** |

**Break-even:** At $0.005/chat × 10K chats/day = $50/day = $1,500/mo in QBC revenue.

---

## 10. RISK MATRIX

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| BitNet 2B too weak for complex queries | High | Medium | Claude API fallback for complex queries |
| Fine-tuning degrades base capabilities | Medium | High | Eval suite before/after, LoRA rollback |
| CRDB can't handle 50M rows performantly | Low | High | Proven at this scale, proper indexing |
| Rust graph shard introduces bugs | Medium | Medium | Extensive testing, Python fallback path |
| GIL still bottlenecks Cognitive Kernel | Medium | Low | Move hot paths to Rust PyO3 |
| On-chain PoT format change breaks clients | Low | High | Backward-compatible format, version field |
| Security: BitNet model poisoning | Low | Critical | Model checksum verification, sandboxed inference |

---

## 11. SUCCESS CRITERIA

| Metric | Phase 1 Target | Phase 3 Target | Phase 4 Target |
|--------|---------------|---------------|---------------|
| Chat latency (p50) | <1.2s | <500ms | <300ms |
| Chat latency (p99) | <3s | <2s | <1.5s |
| Knowledge nodes | 1M | 50M | 100M+ |
| Concurrent users | 20 | 200 | 10,000 |
| Phi compute time | <2s (async) | <500ms (Rust) | <200ms |
| Block production | 3.3s stable | 3.3s stable | 3.3s stable |
| Gates passed (V4) | 6/10 | 8/10 | 10/10 |
| API revenue | $0 | $1,500/mo | $10,000/mo |
| Uptime | 99% | 99.9% | 99.99% |

---

## 12. DECISION: CLONE BITNET OR INTEGRATE?

**VERDICT: INTEGRATE, DON'T CLONE.**

| Approach | Effort | Risk | Outcome |
|---------|--------|------|---------|
| Clone BitNet repo, redesign everything | 6-12 months | Very High | Custom inference runtime, massive maintenance burden |
| **Integrate BitNet.cpp as inference backend** | **2-3 weeks** | **Low** | **Same speed gains, Microsoft maintains the runtime** |
| Build custom 1-bit training pipeline | 3-6 months | Extreme | Custom model, custom training, custom everything |

BitNet.cpp is MIT-licensed. Use it as a dependency, not a fork. Let Microsoft maintain the C++ kernels and GGUF format. We focus on what makes Aether unique: the knowledge graph, the reasoning engine, the on-chain proofs, the Sephirot architecture.

**Our competitive advantage is not the inference engine. It's the cognitive architecture around it.**

---

*This plan transforms the Aether Tree from a Python monolith into a distributed, military-grade AGI system capable of 50M+ nodes at sub-second latency — while preserving every on-chain proof and every knowledge node from genesis.*

*The chain keeps thinking. It just thinks faster.*
