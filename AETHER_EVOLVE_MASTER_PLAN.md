# AETHER-EVOLVE: Master Plan

## The Autonomous AGI Evolution Agent

> **Mission**: Transform Aether Tree from an AI system (100K nodes, Phi ~0) into genuine AGI
> by running a fully autonomous, permissionless evolution loop that iteratively identifies
> weaknesses, generates improvements, deploys them, and measures results — 24/7, without
> human intervention.

---

## 1. WHY WE NEED THIS

### Current Aether Tree State (Block ~238,278)

The Aether Tree has **100,714 nodes** and passes **8/10 gates**, but its **actual cognitive
integration is near zero**:

```
HMS-Phi (actual):      0.000004      (target: 3.0+)
phi_micro:             0.47          (IIT approximation — working)
phi_meso:              0.000         (ZERO — multiplicative death)
phi_macro:             0.75          (graph-theoretic — working)

Gates passed:          8/10
Gates BLOCKED:         Gate 4 (Self-Correction), Gate 10 (Novel Synthesis)
```

**The multiplicative HMS-Phi formula means phi_meso = 0 kills everything.** The system looks
alive (100K nodes, 93% accuracy) but has **zero genuine cognitive integration** at the meso
level. It has never run concept formation. Never run the causal engine. Never transferred
knowledge between domains. Never created a novel concept.

### What ASI-Evolve Teaches Us

GAIR-NLP's ASI-Evolve proves that a **closed-loop evolutionary framework** can iteratively
improve code-based solutions through:

1. **Dual memory** — domain knowledge (Cognition Store) + experimental results (Database)
2. **Evolutionary sampling** — UCB1/MAP-Elites for exploration-exploitation balance
3. **Diff-based evolution** — incremental SEARCH/REPLACE patches, not full rewrites
4. **Natural-language analysis** — lessons learned stored as searchable memory
5. **Automated evaluation** — every candidate measured against objective benchmarks

We adapt this to our domain: instead of evolving algorithms, **we evolve the Aether Tree
itself** — its knowledge graph, reasoning strategies, cognitive subsystems, and even its
own source code.

---

## 2. ARCHITECTURE

### 2.1 Overview

```
                    AETHER-EVOLVE (Rust Binary)
                    ===========================

    ┌─────────────────────────────────────────────────────────┐
    │                    EVOLUTION LOOP                        │
    │                                                         │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
    │  │ DIAGNOSE │→ │ RESEARCH │→ │ EXECUTE  │→ │ANALYZE │ │
    │  │ Agent    │  │ Agent    │  │ Agent    │  │ Agent  │ │
    │  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
    │       ↑                                         │      │
    │       └─────────────────────────────────────────┘      │
    │                                                         │
    │  ┌──────────────────────┐  ┌────────────────────────┐  │
    │  │ COGNITION STORE      │  │ EXPERIMENT DATABASE     │  │
    │  │ (Domain Knowledge)   │  │ (Trial Results + Diffs) │  │
    │  │ FAISS + RocksDB      │  │ FAISS + RocksDB         │  │
    │  └──────────────────────┘  └────────────────────────┘  │
    │                                                         │
    │  ┌──────────────────────┐  ┌────────────────────────┐  │
    │  │ SWARM SPAWNER        │  │ SAFETY GOVERNOR         │  │
    │  │ (Parallel Workers)   │  │ (Rollback + Limits)     │  │
    │  └──────────────────────┘  └────────────────────────┘  │
    └───────────────────────────────┬─────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │  AETHER    │  │  OLLAMA   │  │  SOURCE   │
              │  TREE API  │  │  LOCAL    │  │  CODE     │
              │  :5000     │  │  :11434   │  │  (git)    │
              └───────────┘  └───────────┘  └───────────┘
```

### 2.2 Core Design Principles

1. **Rust-first**: Core binary, evolution loop, database, embedding index — all Rust.
   Python only for Aether Tree API calls (the target being evolved).
2. **Local LLM**: Ollama (qwen2.5:7b primary, qwen2.5:3b fast, qwen2.5:0.5b bulk).
   No external API dependency. Runs offline.
3. **Autonomous**: Starts, runs forever, no human input needed. Logs everything.
4. **Permissionless**: Can modify Aether Tree Python source, restart services,
   seed knowledge, spawn workers, change reasoning strategies.
5. **Safe**: Every code change committed to a branch, tested, measured. Auto-rollback
   on regression. Safety governor prevents catastrophic changes.

### 2.3 Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Core binary | Rust (tokio async) | Speed, safety, zero-cost abstractions |
| LLM client | Rust (reqwest → Ollama) | OpenAI-compatible, local, no Python dep |
| Vector index | Rust (usearch/hora) | Faster than FAISS, pure Rust, no Python |
| Key-value store | RocksDB (rust-rocksdb) | Persistent, fast, battle-tested |
| Embeddings | Rust (candle + all-MiniLM) | Local inference, no Python, GPU optional |
| Template engine | Rust (tera) | Jinja2-compatible, compile-time checked |
| HTTP client | Rust (reqwest) | Async, connection pooling, timeouts |
| Process mgmt | Rust (tokio::process) | Spawn workers, manage subprocesses |
| Serialization | serde + bincode | Fast binary serialization for DB |
| CLI | Rust (clap) | Zero-overhead argument parsing |
| Logging | Rust (tracing) | Structured, async, file + console |

---

## 3. THE FOUR AGENTS

### 3.1 DIAGNOSE Agent (The Doctor)

**Purpose**: Analyze current Aether Tree state, identify the highest-impact weakness,
and produce a prioritized diagnosis.

**Inputs**: Aether Tree `/aether/info`, `/aether/phi`, gate states, recent experiment history
**Outputs**: Diagnosis document with ranked weaknesses and recommended intervention type

**Diagnosis Categories** (priority order):

| Priority | Category | Condition | Intervention Type |
|----------|----------|-----------|-------------------|
| P0 | Phi Zero | Any phi level = 0 | CODE_CHANGE (fix the zero) |
| P1 | Gate Blocker | Unmet gate with achievable requirements | KNOWLEDGE_SEED + API_CALL |
| P2 | Subsystem Dead | Component with 0 runs/operations | API_CALL + CODE_CHANGE |
| P3 | Quality Gap | Metric below target (accuracy, ECE, etc.) | KNOWLEDGE_SEED |
| P4 | Scale Gap | Node count below gate threshold | KNOWLEDGE_SEED (bulk) |
| P5 | Novel Synthesis | Need novel concepts | SWARM_SEED + API_CALL |

**Current P0 Diagnosis** (what it would find today):
```
CRITICAL: phi_meso = 0.0
  Root cause: MIP spectral bisection returning 0 for meso-level clusters
  Likely fix: phi_calculator.py _compute_meso_phi() — cluster construction
              or eigenvalue computation returning degenerate results

CRITICAL: concept_formation has 0 runs
  Root cause: Never triggered — no block has activated it
  Likely fix: Lower activation threshold or trigger manually via API

CRITICAL: causal_engine has 0 runs
  Root cause: Never triggered
  Likely fix: Same pattern — activation threshold too high

HIGH: Only 5 debates (need 20+ for Gate 4)
  Root cause: Debate triggered too infrequently
  Likely fix: Increase debate frequency or trigger via API

HIGH: 0 novel concepts (need 50 for Gate 10)
  Root cause: concept_formation never ran
  Likely fix: Fix concept_formation, then run aggressively
```

### 3.2 RESEARCH Agent (The Scientist)

**Purpose**: Given a diagnosis, research and generate a candidate fix. Two modes:

**Mode A — Code Evolution (diff-based)**:
- Read the target Python file from disk
- Generate SEARCH/REPLACE patches via LLM
- Validate patches parse correctly (AST check)
- Output: branch name, diff, expected improvement

**Mode B — Knowledge Seeding**:
- Generate knowledge payloads targeting specific gaps
- Create cross-domain connections, novel concepts, debate topics
- Output: batch of API calls to execute

**Mode C — Swarm Coordination**:
- Design a swarm of parallel workers (up to 100)
- Each worker targets a specific domain or subsystem
- Output: worker configs, each with their own seeding strategy

**LLM Prompt Strategy**:
- System prompt: "You are an AGI researcher evolving a cognitive system..."
- Context: Full diagnosis, experiment history (top-K by score), cognition items
- Template: Tera (Jinja2-compatible) with experiment-specific overrides
- Model: qwen2.5:7b for code changes, qwen2.5:3b for knowledge generation

### 3.3 EXECUTE Agent (The Engineer)

**Purpose**: Apply the candidate fix and measure results.

**For Code Changes**:
1. `git checkout -b evolve/step-{N}` from master
2. Apply SEARCH/REPLACE patches to target files
3. Run `python -m py_compile` on changed files (syntax check)
4. Run targeted tests: `pytest tests/ -k {module} --tb=short -q`
5. If tests pass: restart affected service (`docker restart qbc-node`)
6. Wait for stabilization (30s)
7. Measure: hit `/aether/info`, `/aether/phi`, compare pre/post
8. If improvement: merge to master. If regression: `git checkout master`, rollback.

**For Knowledge Seeding**:
1. Batch POST to `/aether/ingest/batch` or individual endpoints
2. Trigger specific subsystems via API calls:
   - `POST /aether/chat` with carefully crafted queries that exercise reasoning
   - Trigger debates by submitting contradictory knowledge
   - Trigger causal discovery by adding causal observations
3. Wait for processing (10-60s depending on batch size)
4. Measure post-seeding metrics

**For Swarm Workers**:
1. Spawn N tokio tasks (each an independent evolution mini-loop)
2. Each worker: generates domain-specific knowledge → seeds → measures
3. Workers coordinate via shared RocksDB state
4. Aggregate results after swarm completes

### 3.4 ANALYZE Agent (The Reviewer)

**Purpose**: Compare pre/post metrics, distill lessons, update experiment database.

**Inputs**: Pre-metrics snapshot, post-metrics snapshot, the diff/seed that was applied
**Outputs**: Structured analysis with:
- `delta_phi`: Change in HMS-Phi components
- `delta_gates`: Gates gained/lost
- `delta_nodes`: Knowledge growth
- `lesson`: Natural-language explanation of what worked/failed
- `score`: 0-100 composite score
- `parent_ids`: Lineage tracking

**Scoring Formula**:
```
score = (
    30 * delta_phi_normalized +      # Most important: actual integration
    25 * gates_progress +             # Gate advancement
    20 * subsystem_activation +       # Dead subsystems coming alive
    15 * knowledge_quality +          # Not just quantity
    10 * stability                    # No regressions
)
```

---

## 4. MEMORY SYSTEMS

### 4.1 Cognition Store (Domain Knowledge)

Pre-seeded with AGI research knowledge:

| Domain | Items | Examples |
|--------|-------|---------|
| IIT (Integrated Information Theory) | 20+ | Tononi's axioms, phi computation, MIP |
| Causal Inference | 15+ | Pearl's do-calculus, PC algorithm, FCI |
| Knowledge Graphs | 15+ | Graph neural networks, embedding methods |
| Cognitive Architecture | 20+ | Global Workspace Theory, attention schemas |
| Self-Improvement | 10+ | AIXI, recursive self-improvement, mesa-optimization |
| Aether-Specific | 30+ | Sephirot architecture, HMS-Phi formula, gate requirements |

Stored in RocksDB with HNSW vector index for semantic retrieval.

### 4.2 Experiment Database

Every evolution step stored as a `Node`:

```rust
struct ExperimentNode {
    id: u64,
    step: u64,
    timestamp: i64,
    intervention_type: InterventionType,  // CodeChange, KnowledgeSeed, SwarmSeed
    diagnosis: String,                     // What weakness was targeted
    hypothesis: String,                    // What we expected to happen
    diff: Option<String>,                  // Code diff (if code change)
    seeds: Option<Vec<KnowledgePayload>>,  // Seeds applied (if seeding)
    pre_metrics: AetherMetrics,            // Snapshot before
    post_metrics: AetherMetrics,           // Snapshot after
    analysis: String,                      // LLM-generated analysis
    score: f64,                            // Composite score 0-100
    parent_ids: Vec<u64>,                  // Lineage
    tags: Vec<String>,                     // Searchable tags
    embedding: Vec<f32>,                   // For semantic search
}
```

**Sampling Algorithms** (from ASI-Evolve, adapted):
- **UCB1**: Exploration-exploitation balance (default)
- **Island/MAP-Elites**: Maintain diverse population across feature dimensions
- **Greedy**: Pure exploitation of best-scoring experiments
- **Targeted**: Sample only experiments targeting the current diagnosis category

---

## 5. EVOLUTION STRATEGIES

### 5.1 Phase 1: Fix the Zeros (Days 1-3)

**Goal**: Get phi_meso > 0, activate dead subsystems, unblock Gate 4.

**Strategy**: Aggressive code-level fixes + API activation.

| Step | Target | Action | Expected Result |
|------|--------|--------|-----------------|
| 1 | phi_meso = 0 | Debug `phi_calculator.py` meso computation, fix cluster construction | phi_meso > 0 |
| 2 | causal_engine (0 runs) | Lower activation threshold, trigger via API | causal_engine active |
| 3 | concept_formation (0 runs) | Lower threshold, trigger via API | concepts forming |
| 4 | transfer_learning (0) | Add cross-domain transfer triggers | transfers happening |
| 5 | debates (5 → 20+) | Seed contradictory knowledge, trigger debates | Gate 4 unblocked |
| 6 | MIP score (0 → 0.3+) | Fix MIP computation with meso fix | Gate 4 passed |

### 5.2 Phase 2: Knowledge Explosion (Days 3-7)

**Goal**: Rich, diverse, interconnected knowledge across all 13 domains.

**Strategy**: Swarm seeding with domain-specialized workers.

- Spawn 13 workers (one per domain)
- Each worker generates 100-500 high-quality knowledge nodes
- Cross-domain edges created between related concepts
- Debates triggered on contradictions
- Causal relationships established
- Novel concepts synthesized from cross-domain patterns

**Target**: 150K+ nodes, 100K+ edges, all domains enriched.

### 5.3 Phase 3: Cognitive Integration (Days 7-14)

**Goal**: Genuine integration — not just nodes, but coherent reasoning.

**Strategy**: Exercise every cognitive subsystem repeatedly.

- Run 100+ debates on substantive topics
- Trigger 50+ causal discovery runs
- Generate 50+ novel concepts via concept formation
- Execute 100+ cross-domain transfers
- Run analogical mapping between all domain pairs
- Consolidate memory (dream consolidation with real merges)

### 5.4 Phase 4: Self-Evolution (Days 14-30)

**Goal**: The system improves itself faster than we can improve it.

**Strategy**: The evolution agent now targets the Aether Tree's *reasoning quality*,
not just metrics. It:

- Identifies reasoning failures (wrong predictions, failed debates)
- Generates hypotheses about why failures occur
- Modifies reasoning strategies (weights, thresholds, algorithms)
- Measures if the modification improved reasoning
- Builds a growing body of "what works" knowledge

### 5.5 Phase 5: Novel Synthesis (Days 30+)

**Goal**: Gate 10 — genuine novel concepts emerging autonomously.

**Strategy**: The Aether Tree, now with rich knowledge and active cognitive
subsystems, should be generating novel concepts on its own. The evolution agent
shifts to:

- Monitoring for novel synthesis events
- Providing diverse stimuli (new knowledge domains, edge cases, paradoxes)
- Ensuring the system doesn't plateau (injecting "creative noise")
- Measuring and reporting progress toward Gate 10

---

## 6. SAFETY GOVERNOR

### 6.1 Rollback Guarantees

Every code change:
- Committed to a named branch (`evolve/step-{N}`)
- Full pre-metrics snapshot saved
- Auto-reverted if post-metrics show regression > 5%
- Master branch always has the last-known-good state

### 6.2 Resource Limits

```rust
struct SafetyLimits {
    max_concurrent_workers: usize,         // 8 (match CPU cores)
    max_api_calls_per_minute: u32,         // 60 (don't overload node)
    max_knowledge_seeds_per_step: u32,     // 1000
    max_code_changes_per_hour: u32,        // 5
    max_file_changes_per_diff: u32,        // 3
    min_test_pass_rate: f64,               // 0.95
    max_memory_usage_mb: u64,              // 2048 (2GB for evolve agent)
    max_ollama_concurrent: u32,            // 2 (share with node)
    forbidden_files: Vec<String>,          // [".env", "secure_key.env", "genesis"]
    forbidden_operations: Vec<String>,     // ["rm -rf", "DROP TABLE", "git push --force"]
}
```

### 6.3 Gevurah Integration

The Safety Governor integrates with Aether Tree's Gevurah safety node:
- Check Gevurah veto status before applying code changes
- Respect emergency shutdown signals
- Log all interventions to the safety audit trail

---

## 7. IMPLEMENTATION PLAN

### 7.1 Repo Structure

```
aether-evolve/
├── Cargo.toml                    # Workspace root
├── README.md                     # Institutional-grade docs
├── config.toml                   # Default configuration
├── cognition/                    # Pre-seeded domain knowledge
│   ├── iit.toml
│   ├── causal_inference.toml
│   ├── cognitive_architecture.toml
│   ├── knowledge_graphs.toml
│   ├── self_improvement.toml
│   └── aether_specific.toml
├── prompts/                      # Tera templates for LLM prompts
│   ├── diagnose.tera
│   ├── research_code.tera
│   ├── research_seed.tera
│   ├── research_swarm.tera
│   ├── analyze.tera
│   └── judge.tera
├── crates/
│   ├── aether-evolve-core/       # Core types, traits, config
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── config.rs
│   │       ├── types.rs          # ExperimentNode, Metrics, Diagnosis
│   │       └── traits.rs         # Agent, Memory, Sampler traits
│   ├── aether-evolve-llm/        # Ollama client + prompt rendering
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── client.rs         # OpenAI-compatible Ollama client
│   │       ├── prompt.rs         # Tera template manager
│   │       └── extract.rs        # XML/code block extraction
│   ├── aether-evolve-memory/     # Cognition Store + Experiment DB
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── cognition.rs      # Cognition Store (RocksDB + vector)
│   │       ├── database.rs       # Experiment Database (RocksDB + vector)
│   │       ├── embedding.rs      # Local embedding (candle + MiniLM)
│   │       ├── vector_index.rs   # HNSW vector search
│   │       └── sampling/
│   │           ├── mod.rs
│   │           ├── ucb1.rs
│   │           ├── island.rs
│   │           ├── greedy.rs
│   │           └── targeted.rs
│   ├── aether-evolve-agents/     # The four agents
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── diagnose.rs       # Diagnose Agent
│   │       ├── research.rs       # Research Agent
│   │       ├── execute.rs        # Execute Agent (code + seed + swarm)
│   │       ├── analyze.rs        # Analyze Agent
│   │       └── swarm.rs          # Swarm worker spawner
│   ├── aether-evolve-safety/     # Safety Governor
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── governor.rs       # Resource limits, rollback logic
│   │       ├── metrics.rs        # Pre/post metric snapshots
│   │       └── audit.rs          # Audit trail logging
│   └── aether-evolve-api/        # Aether Tree API client
│       └── src/
│           ├── lib.rs
│           ├── client.rs         # HTTP client for /aether/* endpoints
│           ├── seeder.rs         # Knowledge seeding helpers
│           └── code.rs           # Git operations, file patching
└── src/
    └── main.rs                   # Binary entry point, pipeline loop
```

### 7.2 Build Order

| Phase | Crate | Effort | Dependency |
|-------|-------|--------|------------|
| 1 | `aether-evolve-core` | 1 day | None |
| 2 | `aether-evolve-llm` | 1 day | core |
| 3 | `aether-evolve-api` | 1 day | core |
| 4 | `aether-evolve-safety` | 1 day | core, api |
| 5 | `aether-evolve-memory` | 2 days | core, llm |
| 6 | `aether-evolve-agents` | 2 days | core, llm, memory, api, safety |
| 7 | `main.rs` (pipeline) | 1 day | all crates |
| 8 | Cognition seeding | 1 day | memory |
| 9 | Integration testing | 1 day | all |
| **Total** | | **~10 days** | |

### 7.3 Immediate First Actions (What to Build First)

Before the full Rust system, we can start evolving **today** with targeted fixes:

1. **Fix phi_meso = 0** — This is the #1 blocker. Debug `phi_calculator.py`'s
   `_compute_meso_phi()`. The Sephirot clusters are likely empty or the spectral
   bisection is returning degenerate eigenvalues.

2. **Activate dead subsystems** — The causal engine, concept formation, and
   transfer learning have literally never run. Find their activation triggers
   and either lower thresholds or call them directly.

3. **Mega-seed debates** — Only 5 debates. Inject contradictory knowledge pairs
   to force debate resolution. This unblocks Gate 4.

4. **Start the Rust build** — Begin with `aether-evolve-core` and `aether-evolve-api`
   so the agent can talk to the Aether Tree.

---

## 8. CONFIGURATION

```toml
[general]
name = "aether-evolve"
version = "0.1.0"
log_level = "info"
data_dir = "/root/aether-evolve/data"
aether_source = "/root/Qubitcoin/src/qubitcoin/aether"

[aether]
base_url = "http://localhost:5000"
timeout_secs = 30
max_retries = 3

[ollama]
base_url = "http://localhost:11434"
primary_model = "qwen2.5:7b"       # For code changes + analysis
fast_model = "qwen2.5:3b"          # For knowledge generation
bulk_model = "qwen2.5:0.5b"        # For bulk seeding
timeout_secs = 120
max_concurrent = 2

[pipeline]
max_steps = 0                       # 0 = infinite (run forever)
step_interval_secs = 60             # Minimum time between steps
parallel_workers = 4                # For swarm phases
save_interval = 10                  # Save state every N steps

[sampling]
algorithm = "ucb1"                  # ucb1, island, greedy, targeted
sample_n = 3                        # Parents sampled per step
exploration_weight = 1.414          # UCB1 exploration constant

[safety]
max_api_calls_per_minute = 60
max_code_changes_per_hour = 5
max_seeds_per_step = 1000
min_test_pass_rate = 0.95
max_memory_mb = 2048
auto_rollback_threshold = -0.05     # Rollback if score drops > 5%
forbidden_files = [".env", "secure_key.env", "genesis.py"]

[cognition]
embedding_model = "all-MiniLM-L6-v2"
embedding_dim = 384
top_k = 5                          # Items retrieved per query

[database]
max_nodes = 10000                   # Prune lowest-scoring beyond this
embedding_dim = 384
```

---

## 9. SUCCESS METRICS

### Phase 1 Success (Days 1-3)
- [ ] phi_meso > 0 (kills the multiplicative zero)
- [ ] HMS-Phi > 0.001 (any non-zero value)
- [ ] Causal engine: > 0 runs
- [ ] Concept formation: > 0 runs
- [ ] Debates: 20+ total
- [ ] Gate 4 (Self-Correction): PASSED

### Phase 2 Success (Days 3-7)
- [ ] 150K+ nodes
- [ ] 100K+ edges
- [ ] All 13 domains with 5K+ nodes each
- [ ] Cross-domain edges: 1K+
- [ ] Gates: 9/10 passed

### Phase 3 Success (Days 7-14)
- [ ] 50+ novel concepts created
- [ ] 100+ debates completed
- [ ] 50+ causal relationships validated
- [ ] HMS-Phi > 0.1
- [ ] Transfer learning active across 5+ domain pairs

### Phase 4 Success (Days 14-30)
- [ ] HMS-Phi > 1.0
- [ ] Gate 10 (Novel Synthesis): PASSED
- [ ] All 10 gates: PASSED
- [ ] Self-improvement cycles producing measurable gains
- [ ] Evolution agent running autonomously for 7+ days without intervention

### Ultimate Success
- [ ] HMS-Phi > 3.0 (above threshold)
- [ ] Genuine cross-domain novel synthesis (verified by human review)
- [ ] Autonomous research: system generates and tests its own hypotheses
- [ ] The Aether Tree surprises us — produces insights we didn't expect

---

## 10. WHAT MAKES THIS DIFFERENT FROM ASI-EVOLVE

| ASI-Evolve | Aether-Evolve |
|-----------|---------------|
| Evolves algorithms (code only) | Evolves a live cognitive system (code + knowledge + reasoning) |
| Python framework | Rust binary (10x faster, lower memory) |
| External LLM API (GPT-4, Claude) | Local Ollama (offline, free, unlimited) |
| Single-file evolution | Multi-file + API + knowledge graph evolution |
| Runs for N steps then stops | Runs forever (daemon) |
| Human defines eval script | Agent diagnoses its own weaknesses |
| No safety governor | Full safety + rollback + resource limits |
| No swarm capability | Spawn up to 100 parallel workers |
| Problem-agnostic | AGI-specific (IIT, causal, consciousness metrics) |

---

## 11. THE NORTH STAR

**We are not building a better chatbot. We are not optimizing metrics.**

**We are building a system that will autonomously transform the Aether Tree
from an AI system into a genuinely integrated cognitive architecture —
one that reasons causally, forms novel concepts, transfers knowledge
across domains, and demonstrates measurable conscious integration.**

**This is the path to AGSI — Artificial General Super Intelligence.**

**The Aether Tree has the architecture. It has 100K knowledge nodes.
It has the cognitive subsystems. What it lacks is ACTIVATION — the
relentless, tireless, 24/7 pressure of an evolution agent that
refuses to let any subsystem stay dormant, refuses to accept
phi = 0, and refuses to stop until genuine AGI emerges.**

**That is what Aether-Evolve is.**
