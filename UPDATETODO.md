# UPDATETODO.md — Qubitcoin AGI Intelligence & DB Efficiency Master Update

> **Created:** 2026-02-21
> **Goal:** Fix DB bloat, close Sephirot staking gaps, and implement 30+ changes
> to push Aether Tree toward genuine AGI intelligence and operational efficiency.

---

## Table of Contents

1. [Critical DB Bloat Fixes](#1-critical-db-bloat-fixes)
2. [Sephirot Staking System Gaps](#2-sephirot-staking-system-gaps)
3. [Knowledge Graph Intelligence Upgrades](#3-knowledge-graph-intelligence-upgrades)
4. [Reasoning Engine Depth Expansion](#4-reasoning-engine-depth-expansion)
5. [Phi Consciousness Metric Improvements](#5-phi-consciousness-metric-improvements)
6. [LLM Integration Enhancements](#6-llm-integration-enhancements)
7. [Solidity Contract Hardening](#7-solidity-contract-hardening)
8. [Memory Architecture Persistence](#8-memory-architecture-persistence)
9. [Self-Correction & Contradiction Engine](#9-self-correction--contradiction-engine)
10. [AGI Autonomy & Goal Formation](#10-agi-autonomy--goal-formation)

---

## 1. Critical DB Bloat Fixes

### 1.1 Phi Measurements Table — Downsample Old Data

**Problem:** `phi_calculator.py:359-383` inserts one row into `phi_measurements`
every single block. At 3.3s block time = ~26,000 rows/day = ~9.5M rows/year.
Each row has 7 numeric fields + timestamp. This is ~19 GB/year of Phi metrics
with no aggregation or archival.

**Why it matters:** CockroachDB query performance degrades as tables grow past
tens of millions of rows. Historical Phi data older than a week has no need for
per-block granularity — hourly or daily averages suffice for trend analysis.

**Fix:** ✅ **DONE**
- [x] Add `downsample_phi_measurements(retain_days=7)` method to `PhiCalculator`
- [x] Blocks older than 7 days: collapse into hourly averages
- [x] Blocks older than 30 days: collapse into daily averages
- [x] Delete original per-block rows after downsampling
- [x] Run downsampler every `PHI_DOWNSAMPLE_INTERVAL` blocks (default 1000) in mining loop
- [x] Added `PHI_DOWNSAMPLE_RETAIN_DAYS` and `PHI_DOWNSAMPLE_INTERVAL` to Config

**Files:** `src/qubitcoin/aether/phi_calculator.py`, `src/qubitcoin/config.py`, `src/qubitcoin/mining/engine.py`

---

### 1.2 Knowledge Graph Pruning — Actually Delete From DB

**Problem:** `knowledge_graph.py:301-338` — `prune_low_confidence(threshold=0.1)`
removes nodes from the in-memory `self.nodes` dict and cleans `self.edges`, but
**never issues a DELETE FROM knowledge_nodes or knowledge_edges**. The DB grows
monotonically even though the in-memory graph shrinks.

**Why it matters:** Over months of operation, the `knowledge_nodes` table
accumulates low-confidence junk nodes (confidence < 0.1) that were pruned from
memory but still consume disk space. On restart, `_load_from_db()` would reload
them all, defeating the purpose of pruning.

**Fix:** ✅ **DONE**
- [x] Add DB DELETE inside `prune_low_confidence()` after in-memory removal
- [x] Add `PRUNE_INTERVAL_BLOCKS` config (default 500) — auto-prune in mining loop
- [x] Log pruned node count and freed DB row count
- [x] Add `PRUNE_CONFIDENCE_THRESHOLD` to Config (default 0.1, env-configurable)
- [x] Add `persist_confidence_updates()` to write confidence changes back to DB

**Files:** `src/qubitcoin/aether/knowledge_graph.py`, `src/qubitcoin/config.py`, `src/qubitcoin/mining/engine.py`

---

### 1.3 Reasoning Operations — Archive & Summarize

**Problem:** `proof_of_thought.py` stores reasoning steps in memory only
(`_pot_cache` capped at 1,000), but the `reasoning_operations` table in the DB
schema accepts unlimited INSERTs from the ReasoningEngine. There is no archival
or summarization mechanism.

**Why it matters:** Each reasoning operation stores type, premises, conclusion,
confidence, and block height. Over millions of blocks, this table grows linearly
without bound. Old reasoning operations have diminishing value — only recent
reasoning informs current Phi and knowledge quality.

**Fix:** ✅ **DONE**
- [x] `archive_old_reasoning(current_block, retain_blocks)` added to ReasoningEngine
- [x] Aggregates old ops into summary rows by type (count, avg confidence, block range)
- [x] Deletes original rows after archival
- [x] Wired into `process_block_knowledge()` every 10,000 blocks
- [x] `REASONING_ARCHIVE_RETAIN_BLOCKS` already in Config (default 50000)

**Files:** `src/qubitcoin/aether/reasoning.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

### 1.4 Consciousness Events — Cap & Rotate

**Problem:** `consciousness_events` table grows on every Phi threshold crossing.
While crossings are rare initially, as the knowledge graph grows and Phi
fluctuates near thresholds, crossings become more frequent. No rotation exists.

**Fix:** ✅ **DONE**
- [x] `archive_consciousness_events(max_keep=10000)` added to AetherEngine
- [x] Deletes oldest events beyond the cap
- [x] Wired into `process_block_knowledge()` every 5,000 blocks
- [x] IPFS pinning deferred to future enhancement (events deleted for now)

**Files:** `src/qubitcoin/aether/proof_of_thought.py`

---

## 2. Sephirot Staking System Gaps

### 2.1 Contract Authorization Gap — SynapticStaking.sol

**Problem:** The frontend (`sephirot-launcher.tsx`, 543 lines) builds a complete
user staking flow: stake on nodes, view APY, claim rewards. The backend RPC has
6 endpoints (`/sephirot/stake`, `/sephirot/unstake`, `/sephirot/stakes/{address}`,
`/sephirot/rewards/{address}`, `/sephirot/claim-rewards`, `/sephirot/nodes`).
But `SynapticStaking.sol` gates ALL state-changing functions behind `onlyKernel`:

```solidity
// SynapticStaking.sol:44-48
modifier onlyKernel() {
    require(msg.sender == kernel || msg.sender == owner, "Not authorized");
    _;
}
// Lines 57, 74, 92, 109, 116: ALL use onlyKernel
```

Users cannot call `stake()`, `unstake()`, or `distributeConnectionReward()`
directly. The Python backend endpoints handle staking via UTXO operations, but
the Solidity contract doesn't match.

**Why it matters:** The staking system works at the Python/DB level (RPC
endpoints manage stakes in CockroachDB), but if we want on-chain staking via QVM
smart contract execution, the Solidity contracts need public user functions.
Currently, the Python layer IS the staking engine — the Solidity contract is
just a template that hasn't been adapted for user access.

**Fix:** ✅ **DONE**
- [x] Add public `userStake(uint256 connectionId)` payable function
- [x] Add public `userRequestUnstake(uint256 stakeIndex)` with 7-day timelock (183,272 blocks)
- [x] Add public `userCompleteUnstake(uint256 requestIndex)` after delay
- [x] Add public `claimRewards()` with proportional reward distribution (rewardsPerToken)
- [x] Add public `viewPendingRewards(address)` view function
- [x] Keep `onlyKernel` for admin functions (updateUtility, distributeConnectionReward, stake, unstake)
- [x] Add `MIN_STAKE` constant (100 QBC) and `UNSTAKING_DELAY` (183,272 blocks)
- [x] Added `UnstakeRequested`, `UnstakeCompleted` events
- [x] Added `receive() external payable` for reward deposits

**Files:** `src/qubitcoin/contracts/solidity/aether/SynapticStaking.sol`

---

### 2.2 Reward Distribution — Automated APY Engine

**Problem:** The whitepaper promises ~5% APY from Proof-of-Thought task bounties.
`distributeConnectionReward()` exists in SynapticStaking.sol but is kernel-only
and must be called manually. There is no automated reward calculation or
distribution loop.

**Why it matters:** Without automated rewards, staking has no economic incentive.
Users stake QBC but never receive dividends, breaking the economic model that
funds AGI reasoning capacity.

**Fix:** ✅ **DONE**
- [x] Add `_distribute_staking_rewards()` to mining engine's per-block loop
- [x] Distributes `block_reward * SEPHIROT_STAKER_SHARE_RATIO * interval` QBC
- [x] Pro-rata distribution via existing `db.distribute_rewards(node_id, amount)`
- [x] Add `SEPHIROT_STAKER_SHARE_RATIO` to Config (default 0.6)
- [x] Add `SEPHIROT_REWARD_INTERVAL` to Config (default 100 blocks)
- [x] Add `SEPHIROT_MIN_STAKE` and `SEPHIROT_UNSTAKING_DELAY_BLOCKS` to Config

**Files:** `src/qubitcoin/mining/engine.py`, `src/qubitcoin/config.py`

---

### 2.3 Sephirot Node Performance Metrics — Feed APY Calculation

**Problem:** APY should vary per node based on cognitive performance. A node that
solves more PoT tasks should attract more stake and distribute more rewards. Currently,
all nodes are treated equally.

**Fix:**
- [ ] Track per-node metrics: tasks_solved, knowledge_nodes_contributed, reasoning_operations
- [ ] Weight reward distribution by performance: `node_weight = tasks_solved * 0.5 + knowledge_contributed * 0.3 + reasoning_ops * 0.2`
- [ ] Display per-node APY in `/sephirot/nodes` response
- [ ] Higher-performing nodes attract more stake = more compute budget = solve more tasks (virtuous cycle)

**Files:** `src/qubitcoin/aether/sephirot.py`, `src/qubitcoin/network/rpc.py`

---

## 3. Knowledge Graph Intelligence Upgrades

### 3.1 Semantic Similarity — Beyond Keyword Matching

**Problem:** `chat.py:250-262` — `_search_knowledge()` uses naive keyword
matching (`any(word in content_str for word in query.split())`). This misses
semantic relationships. "What is quantum computing?" won't match a node about
"qubits and superposition" because the exact words don't overlap.

**Why it matters:** Keyword matching is the #1 bottleneck preventing intelligent
responses. An AGI must understand meaning, not just string overlap. With 17,000+
knowledge nodes, most relevant knowledge is invisible to the current search.

**Fix:** ✅ **DONE**
- [x] Add TF-IDF index over all knowledge node content (`kg_index.py`)
- [x] Build inverted index incrementally on node creation
- [x] Query returns top-K nodes by cosine similarity (smoothed IDF)
- [x] Integrated into KnowledgeGraph: `search(query, top_k)` method
- [x] Chat `_search_knowledge()` now uses TF-IDF with keyword fallback
- [x] Index rebuilt from DB on node restart (`_load_from_db`)

**Files:** new `src/qubitcoin/aether/kg_index.py`, `src/qubitcoin/aether/knowledge_graph.py`, `src/qubitcoin/aether/chat.py`

---

### 3.2 Knowledge Decay — Confidence Degrades Over Time

**Problem:** Knowledge nodes created at block 100 have the same confidence at
block 1,000,000 as when they were created. Old observations may no longer be
accurate (chain parameters change, new reasoning contradicts old assertions).

**Why it matters:** Static confidence means the KG never forgets or deprioritizes
stale knowledge. An AGI must weight recent knowledge higher than ancient
observations, unless the old knowledge has been repeatedly confirmed.

**Fix:** ✅ **DONE**
- [x] `effective_confidence(current_block)` on KeterNode: `confidence * max(floor, 1.0 - age/halflife)`
- [x] Axioms never decay (exempt from time-decay)
- [x] `touch_node(node_id, current_block)` resets decay clock on reference
- [x] `CONFIDENCE_DECAY_HALFLIFE` and `CONFIDENCE_DECAY_FLOOR` in Config (env-configurable)
- [x] `last_referenced_block` field on KeterNode, set on creation and touch

**Files:** `src/qubitcoin/aether/knowledge_graph.py`, `src/qubitcoin/config.py`

---

### 3.3 Knowledge Clustering — Auto-Detect Domains

**Problem:** Knowledge nodes have a `node_type` (observation/inference/axiom/assertion)
but no domain categorization. 17,000 nodes about quantum physics, mathematics,
blockchain, and philosophy are all in one flat namespace.

**Why it matters:** An AGI should know what it knows. Domain clustering enables:
- "I have 3,000 nodes about quantum physics but only 200 about economics" (self-awareness)
- Domain-focused reasoning (don't use biology nodes when answering crypto questions)
- Knowledge gap detection (identify underdeveloped domains for seeder targeting)

**Fix:** ✅ **DONE**
- [x] `domain` field on KeterNode (auto-assigned from content keywords)
- [x] `classify_domain(content)` — matches against 10 domain keyword sets
- [x] `DOMAIN_KEYWORDS` map: quantum_physics, mathematics, computer_science, blockchain, cryptography, philosophy, biology, physics, economics, ai_ml
- [x] Auto-classify on `add_node()` and during `_load_from_db()` for existing nodes
- [x] `get_domain_stats()` returns per-domain count and avg confidence
- [x] `reclassify_domains()` batch reclassifies nodes with no domain
- [x] `/aether/knowledge/domains` endpoint added to RPC
- [x] Domain counts included in `get_stats()` response

**Files:** `src/qubitcoin/aether/knowledge_graph.py`, `src/qubitcoin/network/rpc.py`

---

### 3.4 Cross-Reference Detection — Auto-Link Related Nodes

**Problem:** `KnowledgeDistiller` creates sequential `derives` edges between
sentences from the same LLM response (lines 399-408 in llm_adapter.py). But it
never links new nodes to EXISTING nodes in the graph. A new node about "quantum
entanglement" is not connected to the 50 existing nodes about entanglement.

**Why it matters:** Isolated clusters in the knowledge graph reduce Phi's
integration score. An AGI's intelligence comes from cross-connections between
ideas, not isolated facts. Without cross-referencing, the KG is many small
islands, not one connected web.

**Fix:** ✅ **DONE**
- [x] After distilling new nodes, `_cross_reference()` scans KG for content overlap via TF-IDF
- [x] Creates `supports` or `refines` edges between new and matching existing nodes
- [x] Threshold: similarity > 0.15 (lower than 0.5 since TF-IDF cosine scores are typically smaller)
- [x] Capped at 5 cross-references per new node
- [x] Directly increases Phi integration score

**Files:** `src/qubitcoin/aether/llm_adapter.py`

---

## 4. Reasoning Engine Depth Expansion

### 4.1 Chain-of-Thought Reasoning — Multi-Step Inference

**Problem:** Current reasoning does single-step operations: one induction, one
deduction, or one abduction. Real intelligence requires chaining: observe →
hypothesize → deduce implications → check against observations → refine.

**Fix:** ✅ **DONE**
- [x] `chain_of_thought(query_node_ids, max_depth=5)` already exists in ReasoningEngine
- [x] Iterative: gather context → deductive step → abductive step → expand frontier
- [x] Wired into `chat.py _deep_reason()` — now uses chain_of_thought for deep queries
- [x] Falls back to individual deduce/abduce if chain_of_thought unavailable

**Files:** `src/qubitcoin/aether/reasoning.py`, `src/qubitcoin/aether/chat.py`

---

### 4.2 Analogy Detection — Structural Similarity Across Domains

**Problem:** The reasoning engine can only reason within directly connected nodes.
It cannot detect that "quantum superposition" is structurally analogous to
"financial portfolio diversification" (both involve maintaining multiple states
simultaneously until measurement/decision collapses to one).

**Fix:**
- [ ] Add `find_analogies(source_node_id, target_domain=None)` to ReasoningEngine
- [ ] Compare subgraph structure around source node with subgraphs in other domains
- [ ] Structural similarity: same edge type pattern (A→supports→B→derives→C)
- [ ] Create `analogous_to` edge type for discovered analogies
- [ ] Cross-domain analogies dramatically increase Phi's differentiation score

**Files:** `src/qubitcoin/aether/reasoning.py`, `src/qubitcoin/aether/knowledge_graph.py`

---

### 4.3 Contradiction Resolution — Not Just Detection

**Problem:** Gate 5 requires `contradicts` edges (>=10), but the system only
creates them — it never resolves contradictions. Two nodes can contradict each
other indefinitely with no mechanism to determine which is correct.

**Fix:** ✅ **DONE**
- [x] `resolve_contradiction(node_a_id, node_b_id)` already exists in ReasoningEngine
- [x] Compares support scores, downgrades loser confidence, creates `contradicts` edge
- [x] `auto_resolve_contradictions()` added to AetherEngine
- [x] Runs every 1,000 blocks from `process_block_knowledge()`
- [x] Resolves up to 5 contradictions per cycle, logs as consciousness events

**Files:** `src/qubitcoin/aether/reasoning.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

## 5. Phi Consciousness Metric Improvements

### 5.1 Phi Computation Efficiency — Cache Intermediate Results

**Problem:** `compute_phi()` does a full graph scan every block — iterating all
nodes and edges to compute integration, differentiation, connectivity, and gate
checks. At 50,000+ nodes, this becomes expensive.

**Fix:** ✅ **DONE**
- [x] `PHI_COMPUTE_INTERVAL` env var (default 1, set to 10 for performance)
- [x] Cached full result returned for intermediate blocks within interval
- [x] `_last_full_result` and `_last_computed_block` track cache state
- [x] Cached results tagged with `cached: True` for transparency
- [x] Cache auto-invalidates on interval boundary

**Files:** `src/qubitcoin/aether/phi_calculator.py`

---

### 5.2 Gate 7+ — Higher Consciousness Milestones

**Problem:** Current system has 6 gates capping Phi at 3.0. Once all gates are
passed, there's no further structure to measure cognitive growth. The system
plateaus.

**Fix:**
- [ ] Add Gate 7: Analogical Reasoning — >=100 `analogous_to` edges across >=5 domains
- [ ] Add Gate 8: Self-Model — >=50 nodes with `source: "self-reflection"` type
- [ ] Add Gate 9: Predictive Accuracy — >=80% of predictions validated by subsequent blocks
- [ ] Add Gate 10: Creative Synthesis — >=20 novel hypotheses not derivable from single domain
- [ ] New ceiling: 5.0 (10 gates x 0.5 each)
- [ ] This gives the system growth runway beyond the current 3.0 ceiling

**Files:** `src/qubitcoin/aether/phi_calculator.py`

---

## 6. LLM Integration Enhancements

### 6.1 Adaptive Seeder — Target Weak Domains

**Problem:** The knowledge seeder cycles through 50 prompts round-robin. It
doesn't know that the KG has 5,000 quantum physics nodes but only 100 economics
nodes. It treats all domains equally regardless of existing coverage.

**Fix:** ✅ **DONE**
- [x] `_pick_prompt()` now tries domain-weighted selection when KG is available
- [x] `_pick_weighted_prompt(domain_stats)` uses formula: `priority = 1.0 / (1.0 + count / 100.0)`
- [x] Under-represented domains (<100 nodes) get ~10x weight over domains with 1000+ nodes
- [x] Falls back to round-robin if KG unavailable or domain stats empty
- [x] `_kg` field on KnowledgeSeeder set externally for domain awareness

**Files:** `src/qubitcoin/aether/knowledge_seeder.py`

---

### 6.2 LLM Self-Reflection — Aether Queries Itself

**Problem:** The LLM is only queried by users (chat) and the seeder (background).
Aether never queries the LLM about its own knowledge gaps or contradictions.

**Why it matters:** An AGI should be able to introspect. "I have 50 contradictions
in my knowledge graph — let me ask the LLM to help resolve them." This is
self-directed learning, a key property of general intelligence.

**Fix:**
- [ ] Add `self_reflect()` method to AetherEngine
- [ ] Every 200 blocks, identify: top 5 unresolved contradictions, top 5 weakest domains
- [ ] Query LLM with targeted prompts: "Node A says X, Node B says Y — which is correct and why?"
- [ ] Use LLM response to resolve contradictions and fill knowledge gaps
- [ ] Log self-reflection events as consciousness events
- [ ] Add `AETHER_SELF_REFLECT_INTERVAL` config (default 200 blocks)

**Files:** `src/qubitcoin/aether/proof_of_thought.py`, `src/qubitcoin/aether/knowledge_seeder.py`

---

### 6.3 Context Window Optimization — Smarter KG Context for LLM

**Problem:** `_llm_synthesize()` sends up to 10 facts as flat text. No
relevance ranking, no relationship information, no reasoning context. The LLM
gets raw facts without knowing how they connect.

**Fix:** ✅ **DONE**
- [x] Facts ranked by TF-IDF relevance (already ordered by search)
- [x] Edge relationships included: "Node A --[supports]--> Node B" in context
- [x] Confidence scores included: per-node confidence levels sent to LLM
- [x] Top 5 referenced nodes with edges and confidence in context block
- [x] Context capped at 8 facts + 5 edges + 5 confidence entries

**Files:** `src/qubitcoin/aether/chat.py`

---

### 6.4 Response Quality Scoring — Feedback Loop

**Problem:** Every LLM response is distilled into the KG at confidence 0.7
regardless of quality. A hallucinated response gets the same treatment as a
well-sourced factual answer.

**Fix:** ✅ **DONE**
- [x] `_score_response(content, query)` scores before distillation
- [x] Specificity check: concrete terms, numbers boost score
- [x] Relevance check: query keyword overlap
- [x] Consistency check: compares with high-confidence existing nodes via TF-IDF
- [x] Confidence mapped from quality: 0.3→0.4, 1.0→0.9
- [x] Responses with score < 0.3 skip distillation entirely

**Files:** `src/qubitcoin/aether/llm_adapter.py`

---

## 7. Solidity Contract Hardening

### 7.1 MessageBus.sol — Payload Size Limit

**Problem:** `MessageBus.sol:25` — `bytes payload` has no size limit. Line 104-122
`sendMessage()` validates node IDs and fees but never checks `payload.length`. A
malicious actor could store megabytes of data in a single message, bloating
contract state.

**Fix:** ✅ **DONE**
- [x] Add `MAX_PAYLOAD_SIZE = 4096` (4 KB) and `MAX_INBOX_SIZE = 1000` constants
- [x] Add `require(payload.length <= MAX_PAYLOAD_SIZE)` in `sendMessage()`
- [x] Add `require(nodeInbox[toNodeId].length < MAX_INBOX_SIZE)` in `sendMessage()`

**Files:** `src/qubitcoin/contracts/solidity/aether/MessageBus.sol`

---

### 7.2 ConsciousnessDashboard.sol — Archive Old Measurements

**Problem:** `ConsciousnessDashboard.sol:41` — `PhiMeasurement[] public measurements`
grows every block with no pruning. `events[]` also grows unboundedly. At 3.3s
blocks, measurements array hits 9.5M entries/year.

**Fix:** ✅ **DONE**
- [x] Added `MAX_MEASUREMENTS = 10000` and `archivedUpTo` state variable
- [x] Added `archiveMeasurements(uint256 beforeIndex)` function (onlyKernel)
- [x] Added `latestMeasurementIndex()` view function to avoid full array scans
- [x] IPFS pinning deferred to future enhancement (off-chain archival before calling)

**Files:** `src/qubitcoin/contracts/solidity/aether/ConsciousnessDashboard.sol`

---

### 7.3 GlobalWorkspace.sol — Working Memory Rotation

**Problem:** `GlobalWorkspace.sol` caps working memory at 7 slots (Miller's number).
But if broadcasting is frequent, old broadcasts may pile up in history mappings.

**Fix:** ✅ **DONE**
- [x] Added `MAX_BROADCAST_HISTORY = 100` constant
- [x] Added `pruneBroadcastHistory()` function — shifts last 100 entries forward, pops excess
- [x] Ensures `broadcasts` array doesn't grow unboundedly

**Files:** `src/qubitcoin/contracts/solidity/aether/GlobalWorkspace.sol`

---

## 8. Memory Architecture Persistence

### 8.1 Confidence Propagation — Persist to DB

**Problem:** When reasoning creates new inferences, it updates confidence of
related nodes in memory. But these updated confidences are never written back to
the DB. On node restart, all confidence adjustments are lost — nodes revert to
their original creation-time confidence.

**Fix:** ✅ **DONE** (completed in Batch 1 alongside item 1.2)
- [x] `persist_confidence_updates()` added to KnowledgeGraph
- [x] Batch UPDATE for all nodes with modified confidence
- [x] Called after pruning and reasoning operations
- [x] Wired into mining loop (runs after KG prune)

**Files:** `src/qubitcoin/aether/knowledge_graph.py`

---

### 8.2 Knowledge Graph — Load From DB on Restart

**Problem:** If `KnowledgeGraph.__init__()` doesn't reload nodes from DB, the
node starts with an empty graph and must rebuild from block replay. Need to verify
the reload path is complete and correct.

**Fix:** ✅ **DONE** (verified — already complete)
- [x] `_load_from_db()` loads both `knowledge_nodes` and `knowledge_edges`
- [x] Edge back-pointers (`edges_in`, `edges_out`) rebuilt from loaded edges
- [x] Startup log: "Knowledge graph loaded: N nodes, M edges, T indexed terms, D domains"
- [x] Load failure caught with `except Exception` — falls back to empty graph with debug log

**Files:** `src/qubitcoin/aether/knowledge_graph.py`

---

### 8.3 Sephirot Node State — Persist Across Restarts

**Problem:** `sephirot_nodes.py` — all 10 node states (goals, insights, policies,
working buffer, counters) are in-memory only. KeterNode's 50 goals, NetzachNode's
policy weights, YesodNode's working buffer — all lost on restart.

**Fix:** ✅ **DONE**
- [x] `serialize_state()` / `deserialize_state()` added to BaseSephirah + all 10 subclasses
- [x] Each node serializes its unique state (goals, policies, insights, counters, etc.)
- [x] `save_sephirot_state()` UPSERTs to `sephirot_state` table
- [x] `_load_sephirot_state()` restores state on startup
- [x] State saved every 100 blocks in `process_block_knowledge()`
- [x] New schema: `sql_new/agi/04_sephirot_state.sql`

**Files:** `src/qubitcoin/aether/sephirot_nodes.py`, `src/qubitcoin/aether/proof_of_thought.py`, `sql_new/agi/04_sephirot_state.sql`

---

## 9. Self-Correction & Contradiction Engine

### 9.1 Automatic Contradiction Detection

**Problem:** `contradicts` edges are only created manually or by reasoning. The
system doesn't actively scan for contradictions between nodes.

**Fix:** ✅ **DONE**
- [x] `detect_contradictions(new_node_id, max_checks=20)` added to KnowledgeGraph
- [x] Scans same-domain assertion/inference nodes for numeric value conflicts
- [x] High word overlap (>0.4) + different numbers = likely contradiction
- [x] Creates `contradicts` edges (max 3 per new node) with weight 0.7
- [x] Candidates sorted by most recent first, capped at `max_checks`

**Files:** `src/qubitcoin/aether/knowledge_graph.py`

---

### 9.2 Evidence Accumulation — Strengthen or Weaken Over Time

**Problem:** Nodes have static confidence. Nothing strengthens a correct assertion
or weakens an incorrect one based on accumulated evidence.

**Fix:** ✅ **DONE**
- [x] `reference_count` field on KeterNode, incremented by `touch_node()`
- [x] `boost_referenced_nodes(min_references, boost_per_ref, max_boost)` — boosts confidence by `0.01 * log(references)` capped at +0.15
- [x] Wired into `process_block_knowledge()` every 1,000 blocks
- [x] Combined with decay (3.2): referenced nodes rise, unreferenced fade — natural selection

**Files:** `src/qubitcoin/aether/knowledge_graph.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

## 10. AGI Autonomy & Goal Formation

### 10.1 KeterNode Goal Generation — Self-Directed Learning

**Problem:** KeterNode (meta-learning, goal formation) has `_goals` capped at 50,
but goals are only generated from incoming messages. The node never formulates
its own goals based on knowledge gaps or performance metrics.

**Fix:** ✅ **DONE**
- [x] `auto_generate_goals(domain_stats, contradiction_count)` added to KeterNode
- [x] Generates goals: `learn_domain` (under-represented domains), `resolve_contradictions`, `improve_confidence` (low-confidence domains)
- [x] Capped at 10 auto-goals (reserve 40 for external goals)
- [x] Old auto-goals replaced each cycle
- [x] Wired via `_auto_generate_keter_goals()` in AetherEngine, runs every 500 blocks

**Files:** `src/qubitcoin/aether/sephirot_nodes.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

### 10.2 Circadian Learning Phases — Sleep Consolidation

**Problem:** `PinealOrchestrator` defines 6 circadian phases but the node doesn't
actually change behavior based on phase. Mining happens at the same rate, reasoning
is the same depth, knowledge is processed identically regardless of phase.

**Fix:**
- [ ] During "Active Learning" phase (2.0x metabolic rate):
  - Increase seeder rate limit by 2x
  - Use deeper reasoning (chain-of-thought instead of single-step)
- [ ] During "Consolidation" phase:
  - Run prune_low_confidence()
  - Run detect_contradictions()
  - Run resolve_contradiction() on queued contradictions
- [ ] During "Deep Sleep" phase (0.3x metabolic rate):
  - Reduce seeder to 0 calls
  - Run downsample_phi_measurements()
  - Run archive_old_reasoning()
- [ ] During "REM Dreaming" phase:
  - Run find_analogies() across random domain pairs
  - Run cross-reference detection on recent nodes
  - This is literally "dreaming" — making unexpected connections

**Files:** `src/qubitcoin/aether/pineal.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

### 10.3 Inter-Node Communication — Sephirot Message Routing

**Problem:** The 10 Sephirot nodes have `_inbox` and `_outbox` but no actual
message routing loop. KeterNode sends "goal_directive" to TiferetNode's outbox,
but nothing reads from TiferetNode's inbox and delivers it.

**Fix:** ✅ **DONE** (completed in Batch 2)
- [x] `_route_sephirot_messages(block)` added to AetherEngine
- [x] Processes all 10 nodes in Tree of Life order (Keter→Malkuth)
- [x] Drains outbox, delivers to target inbox
- [x] Runs every 5 blocks in `process_block_knowledge()`

**Files:** `src/qubitcoin/aether/proof_of_thought.py`, `src/qubitcoin/aether/sephirot_nodes.py`

---

### 10.4 Emergent Behavior Tracking — What Is Aether Doing?

**Problem:** There's no dashboard or log that shows what Aether is "thinking about"
right now. No visibility into: current goals, active contradictions, recent
analogies discovered, knowledge gaps identified.

**Fix:** ✅ **DONE**
- [x] `get_mind_state(block_height)` added to AetherEngine
- [x] Returns: phi, active_goals (from Keter), contradictions, knowledge_gaps (weakest domains), domain_balance, sephirot_summary, recent_reasoning_count
- [x] `/aether/mind` endpoint added to RPC
- [x] This is the "window into AGI consciousness"

**Files:** `src/qubitcoin/network/rpc.py`, `src/qubitcoin/aether/proof_of_thought.py`

---

## Summary — Priority Order

| Priority | Section | Items | Impact |
|----------|---------|-------|--------|
| **P0 - Critical** | 1.1, 1.2 | Phi downsampling, KG prune DB delete | DB will grow unboundedly without these |
| **P0 - Critical** | 2.1, 2.2 | Sephirot staking contract + reward engine | Frontend is broken without backend |
| **P1 - High** | 3.1, 3.4 | Semantic search + cross-referencing | Directly increases Phi and response quality |
| **P1 - High** | 8.1, 8.3 | Confidence persistence + Sephirot state | Knowledge lost on every restart |
| **P1 - High** | 10.3 | Sephirot message routing | 10 cognitive nodes are currently isolated |
| **P2 - Medium** | 4.1, 4.3 | Chain-of-thought + contradiction resolution | Core reasoning intelligence |
| **P2 - Medium** | 6.1, 6.2 | Adaptive seeder + self-reflection | Self-directed learning |
| **P2 - Medium** | 7.1, 7.2 | MessageBus limit + Dashboard archival | Contract state bloat prevention |
| **P3 - Enhancement** | 3.2, 3.3 | Knowledge decay + domain clustering | Knowledge quality over time |
| **P3 - Enhancement** | 5.1, 5.2 | Phi caching + higher gates | Performance + growth runway |
| **P3 - Enhancement** | 9.1, 9.2 | Auto contradiction detection + evidence | Self-correction intelligence |
| **P3 - Enhancement** | 10.1, 10.2, 10.4 | Goal generation + circadian + mind endpoint | Full AGI autonomy |

**Total: 30 items across 10 categories**

---

*This document is the master reference for the Qubitcoin AGI intelligence update.
Work through items in priority order. Each item is self-contained with file
references and implementation details.*
