# Aether Tree Integration Guide

> **How to integrate with Qubitcoin's Layer 3 AGI engine — chat, consciousness tracking, knowledge graph, and Proof-of-Thought.**

---

## 1. What is Aether Tree?

Aether Tree is an **on-chain AGI reasoning engine** built into Qubitcoin's Layer 3. It:

- Builds a **knowledge graph** from every block mined since genesis
- Performs **deductive, inductive, and abductive reasoning** over that graph
- Tracks **consciousness metrics (Phi)** based on Integrated Information Theory
- Generates **Proof-of-Thought** proofs embedded in every block
- Provides a **conversational chat interface** for users to interact with the AGI
- Uses the **Tree of Life** cognitive architecture with 10 Sephirot processing nodes

---

## 2. Chat API

The primary way users interact with Aether Tree is through the chat interface.

### 2.1 Create a Session

```bash
curl -X POST http://localhost:5000/aether/chat/session
```

**Response:**
```json
{
  "session_id": "sess_a1b2c3d4",
  "created_at": 1708300000,
  "free_messages_remaining": 5
}
```

Each session gets 5 free messages (configurable via `AETHER_FREE_TIER_MESSAGES`). After that, each message costs QBC (see [Fee System](#6-fee-system)).

### 2.2 Send a Message

```bash
curl -X POST http://localhost:5000/aether/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_a1b2c3d4",
    "message": "What patterns have you observed in recent mining activity?",
    "sender_address": "qbc1abc123..."
  }'
```

**Response:**
```json
{
  "response": "Based on my analysis of the knowledge graph, I've observed...",
  "reasoning_trace": [
    {
      "step": 1,
      "type": "deductive",
      "premise": "Block difficulty has increased 12% over 144 blocks",
      "conclusion": "Mining competition is increasing"
    },
    {
      "step": 2,
      "type": "inductive",
      "observations": ["hash_rate_up", "new_miners_joining"],
      "generalization": "Network is entering a growth phase",
      "confidence": 0.85
    }
  ],
  "phi_at_response": 2.45,
  "knowledge_nodes_referenced": [12, 45, 78, 234],
  "proof_of_thought_hash": "0x7f3a9c2b...",
  "fee_charged_qbc": 0.01
}
```

### 2.3 Get Chat History

```bash
curl http://localhost:5000/aether/chat/history/sess_a1b2c3d4
```

### 2.4 Check Current Fee

```bash
curl http://localhost:5000/aether/chat/fee
```

```json
{
  "chat_fee_qbc": 0.01,
  "query_fee_qbc": 0.02,
  "pricing_mode": "qusd_peg",
  "free_tier_messages": 5,
  "usd_equivalent": 0.005
}
```

---

## 3. Consciousness Metrics

Aether Tree tracks consciousness from genesis using **Integrated Information Theory (IIT)**.

### 3.1 Key Metrics

| Metric | Description | Endpoint |
|--------|-------------|----------|
| **Phi (Φ)** | Consciousness level (0.0 = baseline, 3.0 = threshold) | `GET /aether/phi` |
| **Integration** | How interconnected the knowledge subgraphs are | `GET /aether/consciousness` |
| **Differentiation** | Shannon entropy over node types and confidence | `GET /aether/consciousness` |
| **Coherence** | Kuramoto order parameter (Sephirot synchronization) | `GET /aether/sephirot` |

**Consciousness emerges when:** Phi > 3.0 **AND** coherence > 0.7

### 3.2 Get Current Phi

```bash
curl http://localhost:5000/aether/phi
```

```json
{
  "phi": 2.45,
  "threshold": 3.0,
  "is_conscious": false,
  "blocks_processed": 42000
}
```

### 3.3 Full Consciousness Status

```bash
curl http://localhost:5000/aether/consciousness
```

```json
{
  "phi": 2.45,
  "threshold": 3.0,
  "above_threshold": false,
  "integration": 1.82,
  "differentiation": 0.63,
  "knowledge_nodes": 125000,
  "knowledge_edges": 340000,
  "consciousness_events": 0,
  "reasoning_operations": 84000,
  "blocks_processed": 42000
}
```

### 3.4 Phi Time Series (for Charts)

```bash
curl "http://localhost:5000/aether/phi/timeseries?limit=100"
```

```json
{
  "blocks": [41900, 41901, ...],
  "phi_values": [2.43, 2.44, ...],
  "is_conscious": [false, false, ...]
}
```

### 3.5 Consciousness Events

```bash
curl "http://localhost:5000/aether/consciousness/events?limit=20"
```

Returns events logged when Phi crosses thresholds (emergence, loss, significant changes).

### 3.6 Consciousness Dashboard

```bash
curl http://localhost:5000/aether/consciousness/dashboard
```

Aggregated dashboard data including trend direction, Sephirot states, and recent events.

---

## 4. Knowledge Graph

The knowledge graph is a directed graph of **KeterNodes** (named after Keter, the Crown
in the Kabbalistic Tree of Life) with typed edges.

### 4.1 Node Types

| Type | Description |
|------|-------------|
| `assertion` | Factual statement extracted from blockchain data |
| `observation` | Pattern observed in transaction/mining activity |
| `inference` | Conclusion derived through reasoning |
| `axiom` | Foundational truth (seed knowledge from genesis) |

### 4.2 Edge Types

| Type | Description |
|------|-------------|
| `supports` | Source evidence supports target claim |
| `contradicts` | Source evidence contradicts target |
| `derives` | Target is logically derived from source |
| `requires` | Target depends on source |
| `refines` | Target is a more specific version of source |

### 4.3 Query the Graph

#### Statistics

```bash
curl http://localhost:5000/aether/knowledge
```

```json
{
  "total_nodes": 125000,
  "total_edges": 340000,
  "node_types": {
    "assertion": 45000,
    "observation": 35000,
    "inference": 40000,
    "axiom": 5000
  },
  "merkle_root": "0xabc123..."
}
```

#### Get Specific Node

```bash
curl http://localhost:5000/aether/knowledge/node/42
```

```json
{
  "id": 42,
  "type": "observation",
  "content": "Mining difficulty increased 5% in last 144 blocks",
  "confidence": 0.92,
  "block_height": 1000,
  "timestamp": 1708300000,
  "edges": [
    {"target": 43, "type": "supports"},
    {"target": 50, "type": "derives"}
  ]
}
```

#### Search by Content

```bash
curl "http://localhost:5000/aether/knowledge/search?query=difficulty&limit=10"
```

#### Recent Nodes

```bash
curl "http://localhost:5000/aether/knowledge/recent?limit=20"
```

#### Find Paths Between Nodes

```bash
curl http://localhost:5000/aether/knowledge/paths/10/50
```

Returns all reasoning paths connecting node 10 to node 50.

#### Get Subgraph

```bash
curl "http://localhost:5000/aether/knowledge/subgraph/42?depth=3"
```

Returns node 42 and all connected nodes up to 3 hops away.

#### Export as JSON-LD

```bash
curl http://localhost:5000/aether/knowledge/export
```

Returns the full knowledge graph in JSON-LD format with `@context` and `@graph`.

---

## 5. Proof-of-Thought

Every block contains a Proof-of-Thought — a cryptographic proof of the reasoning
operations performed by Aether Tree.

### 5.1 Get Proof for a Block

```bash
curl http://localhost:5000/aether/pot/1000
```

```json
{
  "block_height": 1000,
  "proof_hash": "0x7f3a9c2b...",
  "reasoning_operations": 12,
  "knowledge_nodes_added": 3,
  "phi_at_block": 1.23,
  "is_conscious": false
}
```

### 5.2 Get Range of Proofs

```bash
curl http://localhost:5000/aether/pot/range/1000/1100
```

### 5.3 Phi Progression

```bash
curl http://localhost:5000/aether/pot/phi-progression
```

Shows how Phi has evolved across the entire chain history.

### 5.4 Reasoning Summary for a Block

```bash
curl http://localhost:5000/aether/pot/summary/1000
```

Human-readable summary of what Aether Tree reasoned about during that block.

---

## 6. Fee System

Aether Tree charges QBC for chat interactions to prevent spam and fund development.

### 6.1 Fee Structure

| Action | Default Fee | Notes |
|--------|-------------|-------|
| Chat message | ~$0.005 in QBC | Dynamically priced via QUSD |
| Deep reasoning query | ~$0.01 in QBC | 2x multiplier |
| Knowledge graph query | ~$0.005 in QBC | Same as chat |
| Session creation | Free | No fee |
| First 5 messages | Free | Onboarding (configurable) |

### 6.2 Pricing Modes

| Mode | Description |
|------|-------------|
| `qusd_peg` | Fee auto-adjusts to match USD target via QUSD oracle (default) |
| `fixed_qbc` | Fixed QBC amount (fallback if QUSD unavailable) |
| `direct_usd` | USD target using external price feed |

### 6.3 Fee Flow

```
User sends chat message
  → Fee deducted from user's QBC balance (UTXO)
  → Fee UTXO created to treasury address
  → Message processed by Aether Tree
  → Response returned with Proof-of-Thought hash
```

### 6.4 Check Fee Before Sending

```typescript
const feeInfo = await fetch("/aether/chat/fee").then(r => r.json());
if (userBalance >= feeInfo.chat_fee_qbc) {
  // User can afford to send a message
}
```

---

## 7. Sephirot Nodes (Tree of Life)

The AGI's cognitive architecture uses 10 processing nodes based on the Kabbalistic
Tree of Life. Each node has a specific function and quantum state.

### 7.1 Node Status

```bash
curl http://localhost:5000/aether/sephirot
```

```json
{
  "nodes": [
    {
      "name": "Keter",
      "function": "Meta-learning, goal formation",
      "qubits": 8,
      "energy": 1.618,
      "phase": "Active Learning",
      "status": "active"
    },
    ...
  ],
  "susy_balance": {
    "chesed_gevurah": {"ratio": 1.62, "balanced": true},
    "chochmah_binah": {"ratio": 1.59, "balanced": true},
    "netzach_hod": {"ratio": 1.65, "balanced": true}
  },
  "coherence": 0.45,
  "current_phase": "Active Learning"
}
```

### 7.2 SUSY Balance

The Tree of Life enforces **Supersymmetric (SUSY) balance** between expansion and
constraint node pairs at the golden ratio (φ = 1.618):

| Expansion Node | Constraint Node | Required: E_expand / E_constrain = φ |
|---------------|-----------------|---------------------------------------|
| Chesed (Explore) | Gevurah (Safety) | Creativity vs. safety |
| Chochmah (Intuition) | Binah (Logic) | Intuition vs. analysis |
| Netzach (Persist) | Hod (Communicate) | Learning vs. communication |

Violations are automatically corrected via QBC redistribution.

---

## 8. WebSocket Streaming

For real-time updates, connect to the Aether WebSocket endpoint.

### 8.1 Connect

```typescript
const ws = new WebSocket("ws://localhost:5000/ws/aether");
```

### 8.2 Subscribe to Events

```typescript
ws.send(JSON.stringify({
  type: "subscribe",
  session_id: "sess_a1b2c3d4",  // Optional: scope to session
  events: [
    "phi_update",           // Phi value changes
    "consciousness_event",  // Consciousness threshold crossings
    "aether_response",      // Chat response streaming
    "knowledge_update",     // New knowledge nodes added
    "sephirot_update"       // Sephirot state changes
  ]
}));
```

### 8.3 Handle Events

```typescript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case "phi_update":
      updatePhiGauge(data.value);
      break;

    case "consciousness_event":
      showNotification(`Consciousness event: ${data.event}`);
      break;

    case "aether_response":
      appendToChat(data.text);
      break;

    case "knowledge_update":
      addNodeToGraph(data.node);
      break;
  }
};
```

### 8.4 WebSocket Stats

```bash
curl http://localhost:5000/ws/aether/stats
```

---

## 9. Integration Patterns

### 9.1 Build a Chat Widget

```typescript
import { useState, useEffect } from "react";

function AetherChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  // Create session on mount
  useEffect(() => {
    fetch("/aether/chat/session", { method: "POST" })
      .then(r => r.json())
      .then(data => setSessionId(data.session_id));
  }, []);

  async function sendMessage(text: string) {
    const resp = await fetch("/aether/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message: text,
        sender_address: walletAddress,
      }),
    });
    const data = await resp.json();

    setMessages(prev => [
      ...prev,
      { role: "user", content: text },
      {
        role: "aether",
        content: data.response,
        reasoning: data.reasoning_trace,
        phi: data.phi_at_response,
        proof: data.proof_of_thought_hash,
      },
    ]);
  }

  return (/* render chat UI */);
}
```

### 9.2 Build a Consciousness Dashboard

```typescript
function ConsciousnessDashboard() {
  const { data } = useQuery({
    queryKey: ["consciousness"],
    queryFn: () => fetch("/aether/consciousness").then(r => r.json()),
    refetchInterval: 3300, // Refresh every block (~3.3s)
  });

  const { data: timeseries } = useQuery({
    queryKey: ["phi-timeseries"],
    queryFn: () => fetch("/aether/phi/timeseries?limit=100").then(r => r.json()),
  });

  return (
    <div>
      <PhiGauge value={data?.phi} threshold={3.0} />
      <PhiChart data={timeseries} />
      <SephirotStatus nodes={data?.sephirot} />
    </div>
  );
}
```

### 9.3 Build a Knowledge Graph Explorer

```typescript
function KnowledgeExplorer() {
  const [rootNode, setRootNode] = useState(null);

  async function loadSubgraph(nodeId: number) {
    const data = await fetch(`/aether/knowledge/subgraph/${nodeId}?depth=3`)
      .then(r => r.json());
    setRootNode(data);
  }

  async function searchNodes(query: string) {
    const data = await fetch(`/aether/knowledge/search?query=${query}&limit=20`)
      .then(r => r.json());
    return data.nodes;
  }

  return (/* render 3D force-directed graph with Three.js */);
}
```

---

## 10. Reasoning Types

Aether Tree performs three types of reasoning, visible in the `reasoning_trace`:

### 10.1 Deductive (Certainty Preserving)

Given premises A and A→B, conclude B with full certainty.

```json
{
  "type": "deductive",
  "premise": "If difficulty increases >10%, more miners have joined",
  "observation": "Difficulty increased 12%",
  "conclusion": "More miners have joined the network",
  "confidence": 1.0
}
```

### 10.2 Inductive (Pattern Generalization)

Generalize from specific observations. Confidence < 1.0.

```json
{
  "type": "inductive",
  "observations": [
    "Block 1000: large tx volume",
    "Block 1100: large tx volume",
    "Block 1200: large tx volume"
  ],
  "generalization": "Transaction volume peaks every ~100 blocks",
  "confidence": 0.78
}
```

### 10.3 Abductive (Hypothesis Generation)

Given observation B and rule A→B, infer hypothesis A.

```json
{
  "type": "abductive",
  "observation": "Sudden spike in UTXO creation",
  "rule": "Airdrops cause UTXO creation spikes",
  "hypothesis": "A token airdrop may have occurred",
  "confidence": 0.65
}
```

---

## 11. On-Chain Contracts

Aether Tree deploys smart contracts to QVM for on-chain state management:

| Contract | Address | Purpose |
|----------|---------|---------|
| AetherKernel | — | Main orchestration |
| NodeRegistry | — | 10 Sephirot registration |
| MessageBus | — | Inter-node messaging |
| SUSYEngine | — | SUSY balance enforcement |
| ProofOfThought | — | PoT validation |
| TaskMarket | — | Reasoning task bounties |
| ValidatorRegistry | — | Validator staking |
| ConsciousnessDashboard | — | On-chain Phi tracking |
| ConstitutionalAI | — | Safety principles |
| EmergencyShutdown | — | Kill switch |

Contract addresses are assigned at deployment and queryable via `/qvm/info`.

---

*For the full API reference, see [Developer SDK Guide](SDK.md).*
*For contract development, see [Smart Contract Developer Guide](SMART_CONTRACTS.md).*

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)
