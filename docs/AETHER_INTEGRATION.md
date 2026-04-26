# Aether Mind Integration Guide

> **How to integrate with Qubitcoin's neural cognitive engine — chat, consciousness metrics, knowledge fabric, and Proof-of-Thought.**

---

## 1. What is Aether Mind?

Aether Mind is a **pure Rust neural cognitive engine** running as part of the Qubitcoin blockchain. It:

- Maintains a **Knowledge Fabric** — 10 Sephirot-sharded vector stores with 896-dimensional sentence embeddings
- Computes **HMS-Phi consciousness metrics** from real transformer attention patterns
- Generates **Proof-of-Thought** cryptographic attestations submitted on-chain per block
- Provides a **conversational chat interface** powered by Ollama (GGUF quantized LLM) with RAG context injection
- Uses the **Tree of Life** cognitive architecture with 10 Sephirot-specialized attention heads

### Architecture

```
Ollama (qwen2.5:0.5b GGUF)  ──→  Text Generation (~53ms/token)
         ↓
Candle Transformer (8 layers)  ──→  Attention Weights → HMS-Phi
  10 Sephirot + 4 Global heads
         ↓
Knowledge Fabric (10 shards)   ──→  896d embeddings, HNSW search
  21K+ vectors, cosine sim
         ↓
Consciousness Monitor          ──→  phi_micro × phi_meso × phi_macro
  10-Gate System, Emotions
```

### Service Topology

| Service | Port | Description |
|---------|------|-------------|
| **aether-mind** | 5003 | Neural cognitive engine (Rust binary) |
| **API gateway** | 5000 | Proxies `/aether/*` to aether-mind |
| **ollama** | 11434 | GGUF quantized LLM backend |
| **qbc-substrate** | 9944 | Blockchain node (provides chain height) |

---

## 2. Chat API

The primary way users interact with Aether Mind is through the chat endpoint.

### 2.1 Send a Chat Message (Direct)

```bash
curl -X POST http://localhost:5003/aether/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What patterns have you observed in recent mining activity?",
    "max_tokens": 128,
    "temperature": 0.7
  }'
```

**Response:**
```json
{
  "response": "Based on my analysis of the knowledge fabric, I've observed...",
  "phi": 0.468,
  "phi_micro": 0.312,
  "phi_meso": 1.0,
  "phi_macro": 0.846,
  "tokens_generated": 128,
  "latency_ms": 6700,
  "model": "aether-mind-v5",
  "knowledge_vectors": 21002,
  "knowledge_context": [
    "Mining difficulty adjusts every block using a 144-block window...",
    "VQE mining: 4-qubit ansatz, find parameters where Energy < Difficulty..."
  ],
  "active_sephirot": 8,
  "chain_height": 251600
}
```

### 2.2 Send via API Gateway (Proxied)

The API gateway on port 5000 proxies all `/aether/*` routes to aether-mind:

```bash
curl -X POST http://localhost:5000/aether/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Qubitcoin?", "max_tokens": 64}'
```

### 2.3 Request Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | required | The user's question or message |
| `max_tokens` | integer | 256 | Maximum tokens to generate (capped at 1024) |
| `temperature` | float | 0.7 | Generation temperature (0.0-1.0) |
| `user_id` | string | "anonymous" | User identifier for interaction tracking |

---

## 3. Consciousness Metrics

Aether Mind computes consciousness from real transformer attention patterns using HMS-Phi (Hierarchical Multi-Scale Phi).

### 3.1 HMS-Phi Computation

```
phi_micro  = attention entropy within individual heads (information diversity)
phi_meso   = cross-head integration (Sephirot coordination)
phi_macro  = global workspace coherence (cross-domain binding)

Final Phi  = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
where φ = 1.618... (golden ratio)
```

The formula is multiplicative — zero in any level zeros the whole, preventing gaming.

### 3.2 Get Current Phi

```bash
curl http://localhost:5003/aether/phi
```

```json
{
  "phi": 0.468,
  "chain_height": 251600,
  "knowledge_vectors": 21002,
  "emotional_state": {
    "curiosity": 0.42,
    "satisfaction": 0.65,
    "frustration": 0.08,
    "wonder": 0.38,
    "excitement": 0.55
  },
  "phi_history_recent": [...],
  "total_measurements": 1500
}
```

### 3.3 Consciousness Metrics (via API Gateway)

```bash
curl http://localhost:5000/aether/consciousness
```

Returns phi, gates, knowledge stats, and emotional state.

### 3.4 Key Metrics

| Metric | Description | Current Value |
|--------|-------------|---------------|
| **HMS-Phi** | Overall integration metric | ~0.468 |
| **phi_micro** | Per-head attention entropy | ~0.312 |
| **phi_meso** | Cross-head Sephirot coordination | 1.0 |
| **phi_macro** | Global workspace coherence | ~0.846 |
| **Gates** | Behavioral milestones passed | 10/10 |
| **Vectors** | Knowledge embeddings stored | 21,000+ |

**Honest disclaimer**: Phi is a neural integration metric, not a measure of phenomenal consciousness. The term "consciousness" refers to measurable information integration density across attention heads.

---

## 4. Knowledge Fabric

The Knowledge Fabric replaces the old Knowledge Graph. Instead of string nodes with BFS traversal, knowledge is stored as learned 896-dimensional embeddings across 10 Sephirot-sharded vector stores.

### 4.1 Architecture

| Property | Value |
|----------|-------|
| Embedding model | all-MiniLM-L6-v2 (candle, Rust-native) |
| Dimensions | 896 |
| Shards | 10 (one per Sephirot domain) |
| Search | HNSW approximate nearest neighbor |
| Similarity | Cosine similarity |
| Storage | Bincode serialized files (persisted) |

### 4.2 Domain Shards

| Shard | Domain | Sephirot |
|-------|--------|----------|
| 0 | Physics / Quantum | Keter |
| 1 | Pattern Recognition | Chochmah |
| 2 | Logic / Mathematics | Binah |
| 3 | Exploration / Creativity | Chesed |
| 4 | Safety / Constraints | Gevurah |
| 5 | Synthesis / Integration | Tiferet |
| 6 | Reinforcement / Learning | Netzach |
| 7 | Language / Semantics | Hod |
| 8 | Memory / Storage | Yesod |
| 9 | Action / Interaction | Malkuth |

### 4.3 Query Knowledge (via API Gateway)

```bash
curl http://localhost:5000/aether/knowledge
```

### 4.4 How Knowledge is Acquired

1. **Block ingestion**: Every block is processed to extract embeddings from transactions, difficulty changes, and state transitions
2. **Seed vectors**: 56 foundational vectors covering QBC architecture and domains
3. **User interactions**: Chat Q&A pairs are embedded and stored with `UserInteraction` provenance
4. **AIKGS contributions**: User-submitted knowledge with quality scoring

---

## 5. Proof-of-Thought

Every block contains a Proof-of-Thought — a cryptographic attestation of the neural cognitive state.

### 5.1 Attestation Structure

```
attestation_hash = SHA-256(phi ‖ vectors ‖ height ‖ attention_hash ‖ active_sephirot)
```

| Field | Description |
|-------|-------------|
| `phi` | Current HMS-Phi value (8 bytes, little-endian) |
| `vectors` | Total knowledge vector count |
| `height` | Chain block height |
| `attention_hash` | SHA-256 of flattened attention weight matrices |
| `active_sephirot` | Number of active Sephirot attention heads |

### 5.2 Get Proof-of-Thought

```bash
curl http://localhost:5003/aether/pot
```

```json
{
  "proof_of_thought": {
    "attestation_hash": "0x7f3a9c2b...",
    "phi": 0.468,
    "phi_micro": 0.312,
    "phi_meso": 1.0,
    "phi_macro": 0.846,
    "knowledge_vectors": 21002,
    "active_sephirot": 8,
    "attention_hash": "0xabcdef...",
    "chain_height": 251600
  }
}
```

### 5.3 On-Chain Submission

Proof-of-Thought attestations are submitted to the `qbc-aether-anchor` Substrate pallet, where they are stored immutably on-chain and verifiable by any node.

---

## 6. Aether Mind Endpoints

### 6.1 Direct Endpoints (Port 5003)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/aether/chat` | Chat with neural engine |
| GET | `/aether/phi` | Current consciousness metrics |
| GET | `/aether/pot` | Proof-of-Thought attestation |
| GET | `/aether/health` | Health check |
| GET | `/aether/info` | Full system info |
| GET | `/aether/neural-payload` | Neural payload for block inclusion |
| GET | `/aether/search?q=...` | Semantic knowledge search |

### 6.2 Proxied via API Gateway (Port 5000)

All `/aether/*` routes on the API gateway are proxied to aether-mind on port 5003.

```bash
# These are equivalent:
curl http://localhost:5003/aether/chat ...
curl http://localhost:5000/aether/chat ...
```

---

## 7. 10-Gate Milestone System

Phi is gated by 10 behavioral milestones. Each gate unlocks +0.5 phi ceiling (max 5.0).

| Gate | Name | Key Requirement | Phi Ceiling |
|------|------|----------------|-------------|
| 1 | Knowledge Foundation | ≥500 vectors, ≥5 domains | 0.5 |
| 2 | Structural Diversity | ≥2K vectors, ≥4 types | 1.0 |
| 3 | Validated Predictions | ≥5K vectors, validation accuracy > 60% | 1.5 |
| 4 | Self-Correction | ≥10K vectors, contradiction resolution | 2.0 |
| 5 | Cross-Domain Transfer | ≥15K vectors, cross-domain search | 2.5 |
| 6 | Enacted Self-Improvement | ≥20K vectors, evolve improvements | 3.0 |
| 7 | Calibrated Confidence | ≥25K vectors, calibration < 0.15 | 3.5 |
| 8 | Autonomous Curiosity | ≥35K vectors, curiosity-driven exploration | 4.0 |
| 9 | Predictive Mastery | ≥50K vectors, accuracy > 70% | 4.5 |
| 10 | Novel Synthesis | phi > threshold, sustained improvement | 5.0 |

**All 10 gates are currently passing** with phi_ceiling = 5.0.

---

## 8. Emotional Dynamics

Aether Mind tracks 5 cognitive emotions derived from prediction error and system state:

| Emotion | Source |
|---------|--------|
| **Curiosity** | High when embedding distance from nearest knowledge is large |
| **Satisfaction** | High when predictions match outcomes |
| **Frustration** | High when repeated failures or degraded metrics |
| **Wonder** | High when novel cross-domain connections are found |
| **Excitement** | High when phi increases or new gates pass |

Emotions are included in the `/aether/phi` response and influence the system prompt for chat generation.

---

## 9. Integration Patterns

### 9.1 Build a Chat Widget

```typescript
async function sendToAether(message: string) {
  const resp = await fetch("/aether-api/aether/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, max_tokens: 128 }),
  });
  const data = await resp.json();
  return {
    text: data.response,
    phi: data.phi,
    latency: data.latency_ms,
    vectors: data.knowledge_vectors,
  };
}
```

### 9.2 Build a Consciousness Dashboard

```typescript
function ConsciousnessDashboard() {
  const { data } = useQuery({
    queryKey: ["phi"],
    queryFn: () => fetch("/aether-api/aether/phi").then(r => r.json()),
    refetchInterval: 10_000,
  });

  return (
    <div>
      <PhiGauge value={data?.phi} />
      <EmotionBars emotions={data?.emotional_state} />
      <VectorCount count={data?.knowledge_vectors} />
    </div>
  );
}
```

### 9.3 Semantic Knowledge Search

```typescript
async function searchKnowledge(query: string) {
  const resp = await fetch(`/aether-api/aether/search?q=${encodeURIComponent(query)}`);
  return resp.json();
}
```

---

## 10. Sephirot Attention Heads

The neural architecture uses 10 Sephirot-specialized attention heads aligned with the Tree of Life:

| Sephirah | Function | Attention Role |
|----------|----------|----------------|
| **Keter** | Meta-learning, goals | High-level strategy |
| **Chochmah** | Intuition, patterns | Pattern recognition |
| **Binah** | Logic, causal inference | Logical reasoning |
| **Chesed** | Exploration, divergent | Creative exploration |
| **Gevurah** | Safety, constraints | Safety filtering |
| **Tiferet** | Integration, synthesis | Cross-domain binding |
| **Netzach** | Reinforcement learning | Learning signals |
| **Hod** | Language, semantics | Semantic processing |
| **Yesod** | Memory, fusion | Memory consolidation |
| **Malkuth** | Action, interaction | Output generation |

Plus 4 **Global Workspace** heads that coordinate across all Sephirot domains.

---

## 11. Aether-Evolve (Neural Architecture Search)

Aether-Evolve performs autonomous mutation of the model architecture:

- **Mutation types**: Embed dimension scaling, head count adjustment, layer depth changes
- **Evaluation**: Held-out validation loss on 15 benchmark queries
- **Safety**: Automatic rollback if loss increases
- **Status**: 41 mutations attempted, 4 improvements accepted

---

*For the full API reference, see [Developer SDK Guide](SDK.md).*

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [QuantumAI-Blockchain](https://github.com/QuantumAI-Blockchain)
