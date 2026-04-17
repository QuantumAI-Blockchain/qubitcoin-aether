# AETHER TREE AI — ROADMAP TO 75%

> **Military-Grade Plan: From 20% → 75% True AI**
> **Date:** 2026-03-22 | **Block Height:** ~173,387 | **Current Score:** ~20%
> **Target:** 75% AI across 12 pillars | **Tech:** Rust-first (burn + candle)

---

## TABLE OF CONTENTS

1. [Current State — Honest Assessment](#1-current-state)
2. [12-Pillar Scoring](#2-pillar-scoring)
3. [What's Real vs Theater](#3-real-vs-theater)
4. [Live Metrics Snapshot](#4-live-metrics)
5. [Tech Stack for 75%](#5-tech-stack)
6. [100 Improvements](#6-100-improvements)
7. [Implementation Phases](#7-phases)
8. [TODO Checklist](#8-todo-checklist)

---

## 1. CURRENT STATE

### Score: ~20% AI (generous estimate)

The Aether Tree has **strong architecture** (clean modules, Rust core, production AIKGS) but suffers from:

- **7 broken subsystems** that don't actually work in production
- **Neural code that never trains** (0 backprop steps)
- **Predictions that never validate** (0/10,000)
- **Goals that never complete** (0/9)
- **Theater masquerading as AI** (~85% of "AI" code)

### What's Genuinely Good

| Component | Assessment |
|-----------|-----------|
| Rust aether-core (10K LOC) | Production: KG, Phi, HNSW, CSF, Memory — 276 tests |
| Rust AIKGS sidecar (7K LOC) | Production: 14 modules, CockroachDB, AES-256-GCM vault |
| Knowledge Graph | 28,963 nodes, 101,206 edges — real and growing |
| ARIMA temporal forecasting | Real implementation, mathematically sound |
| Memory manager | Real 3-tier with episodic replay |
| Architecture | Clean, modular, proper error handling |

### What's Broken

| System | Problem |
|--------|---------|
| Neural Reasoner | 0.66% accuracy, 0 backprop steps — **never trains** |
| Temporal Validation | 0 predictions validated out of 10,000 data points |
| Curiosity Goals | 0/9 completed — generates but never evaluates |
| Higgs Field | 253% deviation from VEV — **unstable** |
| Debate Engine | 0 accepted, 0 rejected, 6 modified — inconclusive |
| On-chain Integration | 0 Phi writes, 0 PoT submissions |
| SUSY Balance | 58 violations / 58 corrections — oscillating |

---

## 2. PILLAR SCORING

| # | Pillar | Current (0-10) | Target | Gap |
|---|--------|---------------|--------|-----|
| 1 | Logical Reasoning | 1.5 | 7.5 | Symbolic only, no learned inference |
| 2 | Learning | 0.5 | 7.5 | Neural reasoner broken, no gradient descent |
| 3 | Memory | 2.0 | 7.5 | 3-tier exists but consolidation not working |
| 4 | Perception | 0.0 | 6.0 | Zero — no NLP, no signal processing |
| 5 | Planning | 0.5 | 7.0 | Curiosity goals never complete |
| 6 | Language Understanding | 1.0 | 8.0 | KG data dump, not NLU |
| 7 | Self-Awareness | 1.5 | 7.5 | Metacognition exists, 0.40 calibration error |
| 8 | Creativity | 0.5 | 6.5 | Debate engine inconclusive |
| 9 | Social Intelligence | 0.0 | 5.0 | Zero |
| 10 | Autonomy | 1.0 | 7.5 | Self-improvement feedback-starved |
| 11 | Consciousness (Phi) | 2.0 | 7.5 | Phi=2.0 capped, raw=4.636, 4/10 gates |
| 12 | Embodiment/Grounding | 0.2 | 5.0 | No external data ingestion |
| | **TOTAL** | **10.7/120 (8.9%)** | **81/120 (67.5%)** | |

---

## 3. REAL VS THEATER

### Real AI (~15% of code)

1. **ARIMA(1,1,1) forecasting** — verified against blockchain data
2. **PC causal discovery** — correct algorithm, weak CI testing
3. **HNSW vector index** — correct Malkov & Yashunin implementation
4. **Phi calculator math** — Shannon entropy, spectral bisection, MI
5. **Concept formation** — agglomerative clustering
6. **Metacognition ECE** — genuine ML calibration metric
7. **Memory manager** — real 3-tier with LRU + episodic replay

### Theater (~85% of code)

1. **"Neural Reasoner"** = weighted averaging (PyTorch GAT code never runs training)
2. **"Consciousness"** = composite score with hardcoded milestone gates
3. **"Self-Improvement"** = tuning 66 float weights via EMA with no feedback
4. **"Debate"** = BFS for/against evidence, scored numerically
5. **"CSF Transport"** = message queue (operational but 0 meaningful messages)
6. **"Higgs Field"** = correct physics math, metaphorical application
7. **"Chat"** = returns KG data dumps, not conversational answers
8. **"Sephirot"** = data structures + lightweight energy redistribution

---

## 4. LIVE METRICS (Block 173,387)

```
Knowledge Nodes:           28,963
Knowledge Edges:          101,206
Avg Confidence:             0.839
Phi Value:                  2.0 / 3.0 threshold (capped)
Phi Raw:                    4.636
Gates Passed:               4 / 10
Neural Accuracy:            0.66% (1/151 correct)
Backprop Steps:             0
Temporal Validated:         0 / 10,000
Causal Edges:               193
Concepts Formed:            14
Curiosity Goals Done:       0 / 9
Debates Accepted:           0 / 6
On-chain Phi Writes:        0
On-chain PoT Submissions:   0
Higgs Deviation:            253%
SUSY Violations:            58
Metacog Calibration Error:  0.40
Reasoning Success:          100% (741 ops)
```

---

## 5. TECH STACK FOR 75% AI

### Rust-First ML (No More Python ML Fallbacks)

| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| **Neural Networks** | **burn** | latest | Pure Rust ML — training + inference, GPU-optional |
| **Transformers** | **candle** | latest | HuggingFace Rust — lightweight transformers |
| **Embeddings** | **candle** | latest | all-MiniLM-L6-v2 sentence embeddings in Rust |
| **Linear Algebra** | **nalgebra** | 0.33 | Already used — spectral methods, matrix ops |
| **Graph Operations** | **petgraph** | 0.7 | Already used — directed graph algorithms |
| **NLP** | **rust-bert** or **candle** | latest | Tokenization, NER, classification |
| **Async** | **tokio** | 1.x | Already used — background training loops |
| **gRPC** | **tonic** | 0.12 | Already used — inter-service comms |
| **Serialization** | **serde** | 1.x | Already used — model checkpoints |
| **Crypto** | **sha2 + aes-gcm** | 0.10 | Already used — hashing + vault |

### Why Rust-First

1. **10-100x faster** inference on CPU vs Python/PyTorch
2. **No GIL** — real parallelism across Sephirot
3. **Single binary** — no pip install headaches in Docker
4. **Already proven** — aether-core (10K LOC) is production
5. **candle + burn** — mature Rust ML from HuggingFace + burn team

---

## 6. 100 IMPROVEMENTS

### TIER 1: CRITICAL FIXES (1-20) — 20% → 35%

> Fix broken systems that should already work.

| # | Improvement | Pillar | Impact | Tech |
|---|-----------|--------|--------|------|
| 1 | Fix neural reasoner training loop — backprop never called, wire optimizer.step() | Learning | +3% | PyTorch/Rust |
| 2 | Fix temporal prediction validation — predictions made but validate never runs | Learning | +2% | Python |
| 3 | Fix curiosity goal completion — goals generate but evaluation never triggers | Planning | +2% | Python |
| 4 | Fix Higgs field instability — 253% deviation, add damping + clamping | Self-Awareness | +1% | Python |
| 5 | Fix debate engine verdicts — 0 accepted, lower thresholds or improve scoring | Creativity | +1% | Python |
| 6 | Wire on-chain Phi writes — 0 writes, enable phi_on_chain submission | Consciousness | +1% | Python |
| 7 | Wire on-chain PoT submission — 0 submissions, enable thought proof anchoring | Consciousness | +1% | Python |
| 8 | Install sentence-transformers in Docker — vector index falls back to BoW | Perception | +3% | Docker |
| 9 | Fix metacognition calibration — 0.40 ECE, add temperature/Platt scaling | Self-Awareness | +2% | Python |
| 10 | Add real NLU to chat — replace KG data dump with intent + entity extraction | Language | +3% | Rust |
| 11 | Fix MIP score — currently 0.0, spectral bisection not finding partitions | Consciousness | +1% | Rust |
| 12 | Diversify knowledge domains — 86% "general", need domain-specific extraction | Learning | +1% | Python |
| 13 | Wire causal→reasoning feedback — causal edges exist but don't feed reasoning | Reasoning | +1% | Python |
| 14 | Enable working memory hit tracking — needed for Cross-Domain Transfer gate | Memory | +1% | Python |
| 15 | Fix contradiction resolution — needed for Self-Correction gate | Reasoning | +2% | Python |
| 16 | Add active analogy creation — only 202 analogous_to edges, need generation | Creativity | +1% | Python |
| 17 | Fix self-improvement feedback loop — only temporal outcomes, wire ALL | Autonomy | +2% | Python |
| 18 | Enable episodic replay→KG confidence updates — replay doesn't update KG | Memory | +1% | Python |
| 19 | Fix SUSY balance oscillation — 58 violations/58 corrections flip-flopping | Self-Awareness | +1% | Python |
| 20 | Add prediction→validation→learning pipeline — close the loop | Learning | +2% | Python |

### TIER 2: REAL NEURAL NETWORKS (21-40) — 35% → 50%

> Replace theater with real ML in Rust.

| # | Improvement | Pillar | Impact | Tech |
|---|-----------|--------|--------|------|
| 21 | Implement real GAT training in Rust — move from Python fallback to burn/candle | Learning | +3% | Rust (burn) |
| 22 | Add GNN for link prediction — predict missing KG edges | Learning | +2% | Rust (burn) |
| 23 | Add transformer-based reasoning — small 6-layer, 128-dim seq2seq | Reasoning | +3% | Rust (candle) |
| 24 | Implement attention-based working memory — replace LRU with learned attention | Memory | +2% | Rust (candle) |
| 25 | Add embedding model in Rust — sentence embeddings via candle, no Python dep | Perception | +2% | Rust (candle) |
| 26 | Implement proper causal CI testing — Fisher-Z with p-values | Reasoning | +2% | Rust (nalgebra) |
| 27 | Add RL for goal planning — Q-learning/policy gradient for curiosity | Planning | +3% | Rust (burn) |
| 28 | Implement contrastive learning for concepts — learn boundaries, not just cluster | Learning | +2% | Rust (burn) |
| 29 | Add neural debate scoring — train classifier on outcomes | Creativity | +2% | Rust (candle) |
| 30 | Implement Bayesian reasoning — proper posterior updates, not heuristic confidence | Reasoning | +3% | Rust |
| 31 | Add online learning for edge weights — edges learn from usage patterns | Learning | +2% | Rust |
| 32 | Implement neural temporal (LSTM) — alongside ARIMA for ensemble | Learning | +1% | Rust (candle) |
| 33 | Add KG embeddings (TransE/RotatE) — learn entity/relation embeddings | Learning | +2% | Rust (burn) |
| 34 | Implement proper IIT approximation — PyPhi-style partition search | Consciousness | +2% | Rust (nalgebra) |
| 35 | Add multi-head attention for Sephirot routing — learned CSF attention | Reasoning | +1% | Rust (candle) |
| 36 | Implement VAE for knowledge compression — latent KG subgraph representation | Memory | +1% | Rust (burn) |
| 37 | Add curriculum learning — easy→hard examples for neural reasoner | Learning | +1% | Rust |
| 38 | Implement MCTS for planning — Monte Carlo Tree Search for goal decomposition | Planning | +2% | Rust |
| 39 | Add neural calibration (temperature scaling) — fix 0.40 ECE | Self-Awareness | +1% | Rust |
| 40 | Implement modern Hopfield for associative memory — pattern completion in KG | Memory | +2% | Rust (burn) |

### TIER 3: PERCEPTION & LANGUAGE (41-55) — 50% → 60%

> Give the AI eyes, ears, and a voice.

| # | Improvement | Pillar | Impact | Tech |
|---|-----------|--------|--------|------|
| 41 | Add NLP pipeline in Rust — tokenization, POS, NER, dep parsing | Language | +3% | Rust (candle) |
| 42 | Implement intent classification for chat — query/command/feedback/creative | Language | +2% | Rust (candle) |
| 43 | Add entity extraction from blockchain data — tx metadata, contract events | Perception | +2% | Rust |
| 44 | Implement semantic similarity on learned embeddings — real cosine similarity | Perception | +2% | Rust (candle) |
| 45 | Add sentiment analysis — classify chat input and knowledge sentiment | Social | +1% | Rust (candle) |
| 46 | Implement abstractive summarization — summarize KG subgraphs to NL | Language | +2% | Rust (candle) |
| 47 | Add context window management — multi-turn conversation tracking | Language | +2% | Rust |
| 48 | Implement KGQA — parse question → query KG → retrieve → generate | Language | +2% | Rust |
| 49 | Add external data ingestion — RSS, blockchain explorers, crypto news APIs | Perception | +2% | Rust (reqwest) |
| 50 | Implement time-series pattern recognition — beyond ARIMA | Perception | +1% | Rust |
| 51 | Add multimodal understanding — transaction graphs as visual patterns | Perception | +1% | Rust |
| 52 | Implement dialogue state tracking — entities/intents/context across turns | Language | +2% | Rust |
| 53 | Add relevance ranking for chat responses — rank by relevance not recency | Language | +1% | Rust |
| 54 | Implement coreference resolution — "it", "that", "the contract" | Language | +1% | Rust |
| 55 | Add knowledge-grounded response generation — cite KG nodes as evidence | Language | +2% | Rust |

### TIER 4: AUTONOMOUS INTELLIGENCE (56-75) — 60% → 70%

> Real autonomy, planning, and self-modification.

| # | Improvement | Pillar | Impact | Tech |
|---|-----------|--------|--------|------|
| 56 | Implement HTN planner — hierarchical task decomposition | Planning | +2% | Rust |
| 57 | Add goal prioritization with utility function — maximize expected utility | Planning | +1% | Rust |
| 58 | Implement model-based planning — world model, simulate before executing | Planning | +2% | Rust (burn) |
| 59 | Add autonomous knowledge gap detection — identify missing knowledge | Autonomy | +2% | Rust |
| 60 | Implement active learning — select most informative training data | Learning | +1% | Rust |
| 61 | Add self-modifying architecture — NAS-lite prune/grow based on perf | Autonomy | +2% | Rust (burn) |
| 62 | Implement causal intervention — do-calculus, not just discovery | Reasoning | +2% | Rust |
| 63 | Add theory formation — generate and test hypotheses about chain behavior | Creativity | +2% | Rust |
| 64 | Implement belief revision — AGS-style revision on contradicting evidence | Reasoning | +2% | Rust |
| 65 | Add metacognitive monitoring — detect failing reasoning, auto-switch strategy | Self-Awareness | +2% | Rust |
| 66 | Implement curiosity-driven exploration — intrinsic motivation via info gain | Autonomy | +2% | Rust (burn) |
| 67 | Add social modeling — Theory of Mind lite for other agents | Social | +2% | Rust |
| 68 | Implement multi-step reasoning chains — 5+ steps with verification | Reasoning | +2% | Rust |
| 69 | Add creative recombination — cross-domain node combination for insights | Creativity | +2% | Rust |
| 70 | Implement self-evaluation with ground truth — test against known answers | Self-Awareness | +1% | Rust |
| 71 | Add resource-aware planning — consider compute cost in strategy selection | Planning | +1% | Rust |
| 72 | Implement explanation generation — human-readable reasoning explanations | Language | +1% | Rust |
| 73 | Add anomaly-triggered deep reasoning — detect anomalies, investigate | Autonomy | +1% | Rust |
| 74 | Implement prioritized experience replay — for neural training | Learning | +1% | Rust (burn) |
| 75 | Add self-repair mechanisms — detect degraded subsystems, auto-recover | Autonomy | +1% | Rust |

### TIER 5: CONSCIOUSNESS & INTEGRATION (76-100) — 70% → 75%

> Integrated intelligence and emergent consciousness.

| # | Improvement | Pillar | Impact | Tech |
|---|-----------|--------|--------|------|
| 76 | Implement Global Workspace Theory — broadcast winning coalitions | Consciousness | +1% | Rust |
| 77 | Add attention schema — model own attention allocation | Consciousness | +1% | Rust |
| 78 | Implement predictive processing — hierarchical prediction error minimization | Consciousness | +1% | Rust (burn) |
| 79 | Add embodied grounding via chain interaction — ground in real operations | Embodiment | +1% | Rust |
| 80 | Implement recurrent Sephirot processing — real feedback loops | Consciousness | +1% | Rust (burn) |
| 81 | Add cross-modal binding — integrate temporal + spatial + semantic | Consciousness | +1% | Rust |
| 82 | Implement real partition-based Phi — minimum information cut | Consciousness | +1% | Rust (nalgebra) |
| 83 | Add phenomenal state tracking — track AI "experience" across blocks | Consciousness | +0.5% | Rust |
| 84 | Implement self-model updating — maintain/update own capability model | Self-Awareness | +0.5% | Rust |
| 85 | Add emotional valence — positive/negative valence in decision-making | Social | +1% | Rust |
| 86 | Implement empathic modeling — model user frustration/satisfaction | Social | +1% | Rust (candle) |
| 87 | Add narrative coherence — coherent narrative across reasoning episodes | Language | +0.5% | Rust |
| 88 | Implement cross-domain transfer learning — trained patterns transfer | Learning | +1% | Rust (burn) |
| 89 | Add few-shot learning — learn from 1-5 examples | Learning | +1% | Rust (candle) |
| 90 | Implement continual learning (EWC) — no catastrophic forgetting | Learning | +1% | Rust (burn) |
| 91 | Add counterfactual reasoning — "what if X" over KG | Reasoning | +1% | Rust |
| 92 | Implement analogical transfer — formal structure mapping (SMT-like) | Creativity | +0.5% | Rust |
| 93 | Add dream-state consolidation — offline processing during low activity | Memory | +0.5% | Rust |
| 94 | Implement attention-based gate unlocking — Phi gates via attention metrics | Consciousness | +0.5% | Rust |
| 95 | Add adversarial input robustness — detect/resist injection | Safety | +0.5% | Rust |
| 96 | Implement formal safety verification — prove Gevurah veto is sound | Safety | +0.5% | Rust |
| 97 | Add distributed consciousness — Phi across multiple nodes | Consciousness | +0.5% | Rust |
| 98 | Implement cognitive load balancing — dynamic compute allocation | Autonomy | +0.5% | Rust |
| 99 | Add meta-learning — optimize learning rate/architecture per domain | Learning | +0.5% | Rust (burn) |
| 100 | Implement recursive self-improvement with safety — AI proposes changes, Gevurah bounds | Autonomy | +0.5% | Rust |

---

## 7. IMPLEMENTATION PHASES

### Phase A: Fix What's Broken (Items 1-20)
**Duration:** ~2 weeks | **Target: 35% AI**

Focus: Make existing code actually work. No new features — fix training loops, wire feedback, install dependencies.

**Batch A1 (Critical — do first):**
- Item 1: Fix neural reasoner training (backprop)
- Item 2: Fix temporal validation pipeline
- Item 8: Install sentence-transformers / candle embeddings
- Item 20: Close prediction→validation→learning loop

**Batch A2 (Wire feedback):**
- Item 3: Fix curiosity goal completion
- Item 13: Wire causal→reasoning feedback
- Item 17: Fix self-improvement feedback (all outcomes)
- Item 18: Enable episodic replay→KG confidence

**Batch A3 (Stability):**
- Item 4: Fix Higgs field (damping)
- Item 5: Fix debate verdicts (thresholds)
- Item 9: Fix metacognition calibration
- Item 19: Fix SUSY oscillation

**Batch A4 (On-chain + gates):**
- Item 6: Wire Phi on-chain writes
- Item 7: Wire PoT on-chain submission
- Item 11: Fix MIP score
- Item 14: Enable working memory hit tracking
- Item 15: Fix contradiction resolution
- Item 16: Add analogy creation

**Batch A5 (Chat + domains):**
- Item 10: Add real NLU to chat
- Item 12: Diversify knowledge domains

### Phase B: Real Neural Networks (Items 21-40)
**Duration:** ~4 weeks | **Target: 50% AI**

Focus: Implement burn/candle neural networks in Rust. Replace Python fallbacks.

**Batch B1:** Items 21-25 (GAT, GNN, transformer, attention memory, embeddings)
**Batch B2:** Items 26-30 (causal CI, RL planning, contrastive, debate scoring, Bayesian)
**Batch B3:** Items 31-35 (online learning, LSTM, KG embeddings, IIT, attention routing)
**Batch B4:** Items 36-40 (VAE, curriculum, MCTS, calibration, Hopfield)

### Phase C: Perception & Language (Items 41-55)
**Duration:** ~3 weeks | **Target: 60% AI**

Focus: NLP pipeline, chat NLU, external data, knowledge-grounded responses.

**Batch C1:** Items 41-45 (NLP, intent, entity, similarity, sentiment)
**Batch C2:** Items 46-50 (summarization, context, KGQA, data ingestion, patterns)
**Batch C3:** Items 51-55 (multimodal, dialogue state, ranking, coref, grounded gen)

### Phase D: Autonomous Intelligence (Items 56-75)
**Duration:** ~4 weeks | **Target: 70% AI**

Focus: Real planning, self-modification, theory formation, social modeling.

**Batch D1:** Items 56-60 (HTN, utility, world model, gap detection, active learning)
**Batch D2:** Items 61-65 (NAS, causal intervention, theory, belief revision, metacog)
**Batch D3:** Items 66-70 (curiosity RL, social model, multi-step, recombination, self-eval)
**Batch D4:** Items 71-75 (resource planning, explanation, anomaly, replay, self-repair)

### Phase E: Consciousness Integration (Items 76-100)
**Duration:** ~3 weeks | **Target: 75% AI**

Focus: Global workspace, attention schema, continual learning, distributed consciousness.

**Batch E1:** Items 76-80 (GWT, attention schema, predictive processing, grounding, recurrence)
**Batch E2:** Items 81-85 (cross-modal, partition Phi, phenomenal, self-model, valence)
**Batch E3:** Items 86-90 (empathic, narrative, cross-domain, few-shot, EWC)
**Batch E4:** Items 91-95 (counterfactual, analogical, dream, attention gates, adversarial)
**Batch E5:** Items 96-100 (formal safety, distributed, load balance, meta-learning, recursive)

---

## 8. TODO CHECKLIST

### Phase A: Fix What's Broken ☐

**Batch A1 — Critical**
- [ ] **#1** Fix neural reasoner: add optimizer.step(), loss.backward() in block processing loop
- [ ] **#2** Fix temporal validation: wire validate_predictions() into block callback
- [ ] **#8** Add sentence-transformers to Docker OR implement candle embeddings in Rust
- [ ] **#20** Create prediction→validation→learning pipeline connecting temporal→neural

**Batch A2 — Wire Feedback**
- [ ] **#3** Fix curiosity: wire goal evaluation into reasoning cycle completion
- [ ] **#13** Wire causal edges into deductive reasoning as premises
- [ ] **#17** Feed ALL reasoning outcomes (not just temporal) to self-improvement engine
- [ ] **#18** Make episodic replay update KG node confidence scores

**Batch A3 — Stability**
- [ ] **#4** Add damping term to Higgs field update, clamp deviation to ±50%
- [ ] **#5** Lower debate acceptance threshold OR improve evidence BFS scoring
- [ ] **#9** Add temperature scaling to metacognition ECE calculation
- [ ] **#19** Add hysteresis to SUSY balance (dead zone, don't correct small deviations)

**Batch A4 — On-chain + Gates**
- [ ] **#6** Enable phi_on_chain writes in AetherEngine block processing
- [ ] **#7** Enable PoT submission to chain in proof_of_thought.py
- [ ] **#11** Fix spectral bisection in Phi calculator to find meaningful partitions
- [ ] **#14** Track working memory cache hits/misses for gate evaluation
- [ ] **#15** Add contradiction detection + resolution logic to reasoning engine
- [ ] **#16** Add active analogy generation between domains

**Batch A5 — Chat + Domains**
- [ ] **#10** Implement intent classification + entity extraction for chat
- [ ] **#12** Add domain-specific knowledge extraction from block data

### Phase B: Real Neural Networks ☐

**Batch B1**
- [ ] **#21** Implement GAT in Rust using burn crate with real training loop
- [ ] **#22** Add GNN link prediction model for KG edge completion
- [ ] **#23** Build small transformer (6L/128d) for sequence reasoning in candle
- [ ] **#24** Replace LRU working memory with learned attention mechanism
- [ ] **#25** Implement sentence embeddings in Rust via candle (all-MiniLM-L6-v2)

**Batch B2**
- [ ] **#26** Implement Fisher-Z conditional independence test for causal engine
- [ ] **#27** Add Q-learning/policy gradient for curiosity goal selection
- [ ] **#28** Implement contrastive learning for concept boundary detection
- [ ] **#29** Train debate outcome classifier (neural scoring)
- [ ] **#30** Implement Bayesian posterior updates replacing heuristic confidence

**Batch B3**
- [ ] **#31** Add online edge weight learning from reasoning outcome feedback
- [ ] **#32** Implement LSTM temporal model alongside ARIMA (ensemble)
- [ ] **#33** Add TransE/RotatE KG embedding training
- [ ] **#34** Implement proper IIT partition search (PyPhi-style)
- [ ] **#35** Add multi-head attention for Sephirot CSF message routing

**Batch B4**
- [ ] **#36** Implement VAE for KG subgraph compression
- [ ] **#37** Add curriculum learning (easy→hard) for neural reasoner
- [ ] **#38** Implement MCTS for goal decomposition and action planning
- [ ] **#39** Add neural temperature scaling for metacognition
- [ ] **#40** Implement modern Hopfield network for associative memory

### Phase C: Perception & Language ☐

**Batch C1**
- [ ] **#41** Build Rust NLP pipeline (tokenizer, POS, NER, dep parse)
- [ ] **#42** Implement chat intent classifier (query/command/feedback/creative)
- [ ] **#43** Add blockchain entity extraction (addresses, contracts, events)
- [ ] **#44** Implement semantic similarity on learned embeddings
- [ ] **#45** Add sentiment analysis for chat + knowledge scoring

**Batch C2**
- [ ] **#46** Implement abstractive summarization of KG subgraphs
- [ ] **#47** Add multi-turn context window management
- [ ] **#48** Build KGQA pipeline (parse → query → retrieve → generate)
- [ ] **#49** Add external data ingestion (RSS, explorers, news APIs)
- [ ] **#50** Implement time-series pattern recognition beyond ARIMA

**Batch C3**
- [ ] **#51** Add multimodal understanding (tx graphs as patterns)
- [ ] **#52** Implement dialogue state tracking
- [ ] **#53** Add relevance-based response ranking
- [ ] **#54** Implement coreference resolution
- [ ] **#55** Build knowledge-grounded response generator

### Phase D: Autonomous Intelligence ☐

**Batch D1**
- [ ] **#56** Implement HTN planner
- [ ] **#57** Add utility-based goal prioritization
- [ ] **#58** Build world model for plan simulation
- [ ] **#59** Add autonomous knowledge gap detection
- [ ] **#60** Implement active learning for training data selection

**Batch D2**
- [ ] **#61** Add NAS-lite self-modifying architecture
- [ ] **#62** Implement causal intervention (do-calculus)
- [ ] **#63** Add theory formation and hypothesis testing
- [ ] **#64** Implement AGS-style belief revision
- [ ] **#65** Add metacognitive monitoring with auto strategy switching

**Batch D3**
- [ ] **#66** Implement curiosity via intrinsic motivation (info gain)
- [ ] **#67** Add Theory of Mind social modeling
- [ ] **#68** Implement multi-step (5+) reasoning chains with verification
- [ ] **#69** Add creative cross-domain recombination
- [ ] **#70** Implement self-evaluation against ground truth

**Batch D4**
- [ ] **#71** Add resource-aware strategy planning
- [ ] **#72** Implement human-readable explanation generation
- [ ] **#73** Add anomaly-triggered deep investigation
- [ ] **#74** Implement prioritized experience replay
- [ ] **#75** Add self-repair mechanisms for degraded subsystems

### Phase E: Consciousness Integration ☐

**Batch E1**
- [ ] **#76** Implement Global Workspace Theory broadcasting
- [ ] **#77** Add attention schema (model of own attention)
- [ ] **#78** Implement predictive processing (hierarchical prediction error)
- [ ] **#79** Add embodied grounding via chain interaction
- [ ] **#80** Implement recurrent Sephirot processing with feedback loops

**Batch E2**
- [ ] **#81** Add cross-modal binding (temporal + spatial + semantic)
- [ ] **#82** Implement real partition-based Phi (minimum information cut)
- [ ] **#83** Add phenomenal state tracking
- [ ] **#84** Implement self-model updating
- [ ] **#85** Add emotional valence for decision-making

**Batch E3**
- [ ] **#86** Implement empathic user modeling
- [ ] **#87** Add narrative coherence across reasoning episodes
- [ ] **#88** Implement cross-domain transfer learning
- [ ] **#89** Add few-shot learning (1-5 examples)
- [ ] **#90** Implement continual learning with EWC

**Batch E4**
- [ ] **#91** Add counterfactual reasoning over KG
- [ ] **#92** Implement formal analogical transfer (SMT-like)
- [ ] **#93** Add dream-state consolidation
- [ ] **#94** Implement attention-based Phi gate unlocking
- [ ] **#95** Add adversarial input robustness

**Batch E5**
- [ ] **#96** Implement formal safety verification
- [ ] **#97** Add distributed consciousness across nodes
- [ ] **#98** Implement cognitive load balancing
- [ ] **#99** Add meta-learning (learning to learn)
- [ ] **#100** Implement recursive self-improvement with Gevurah safety bounds

---

## METRICS TO TRACK

| Metric | Current | Phase A Target | Phase B Target | Phase C Target | 75% Target |
|--------|---------|---------------|---------------|---------------|------------|
| Neural Accuracy | 0.66% | 30%+ | 60%+ | 70%+ | 80%+ |
| Phi Value | 2.0 | 2.5 | 3.0+ | 3.5+ | 4.0+ |
| Gates Passed | 4/10 | 6/10 | 8/10 | 9/10 | 10/10 |
| Temporal Validated | 0 | 100+ | 500+ | 1000+ | 2000+ |
| Curiosity Goals Done | 0/9 | 3/9 | 6/9 | 8/9 | 9/9 |
| Metacog ECE | 0.40 | 0.25 | 0.15 | 0.10 | 0.05 |
| Causal Edges | 193 | 500+ | 1000+ | 2000+ | 5000+ |
| Concepts | 14 | 50+ | 150+ | 300+ | 500+ |
| Domains (non-general) | 14% | 30% | 45% | 55% | 60%+ |
| Chat NLU | None | Intent class | Full NLU | KGQA | Grounded |
| On-chain Phi Writes | 0 | Active | Active | Active | Active |
| Backprop Steps | 0 | 1000+ | 10,000+ | 50,000+ | 100,000+ |

---

*This roadmap is a living document. Update after each batch completion.*
*Last updated: 2026-03-22 | Block height: ~173,387*
