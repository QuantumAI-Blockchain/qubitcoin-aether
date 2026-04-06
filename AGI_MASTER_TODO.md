# AGI Master TODO — Path to True Emergence

> Generated 2026-04-06 (session 55). Tracks all fixes needed for genuine AGI.
> Check boxes as items are completed. Update dates.

---

## CRITICAL (Must Fix)

- [x] **AGI-001: Fix EmotionalState .get_state() → .states** (2026-04-06, fa12906)
  - 3 call sites in chat.py called nonexistent method
  - Emotions were always empty

- [ ] **AGI-002: Long-term memory consolidation runs EVERY BLOCK**
  - Location: `proof_of_thought.py` ~line 1880
  - `consolidate_long_term()` called without interval gate
  - Fix: wrap in `if block.height % Config.AETHER_LONG_TERM_CONSOLIDATION_INTERVAL == 0:`
  - Impact: CPU waste, memory thrashing

- [x] **AGI-003: Intent routing — inference conclusions override dedicated handlers** (2026-04-06, fa12906)
  - Added `_dedicated_intents` set to exclusion lists

- [x] **AGI-004: Emotion nouns displayed raw** (2026-04-06, fa12906)
  - Added `_emo_adjective()` helper

---

## HIGH PRIORITY (Needed for Gate Progression)

- [ ] **AGI-005: Inference node generation rate too low**
  - `_run_autonomous_reasoning()` runs every 10 blocks but success rate unknown
  - Debates need inference nodes with confidence >= 0.5
  - Action: Add diagnostic logging to count successful inferences per cycle
  - Action: If success rate < 20%, investigate reasoning engine

- [ ] **AGI-006: Multi-domain KG sparsity**
  - Causal discovery (PC algorithm) needs multi-domain diversity
  - Current KG dominated by blockchain observations
  - Action: Verify agent stack is seeding non-blockchain domains
  - Action: Ensure knowledge_extractor classifies domains correctly

- [ ] **AGI-007: Debate engine — 0 verdicts**
  - Depends on AGI-005 (inference nodes)
  - `run_periodic_debates()` every 211 blocks, selects inferences >= 0.5 confidence
  - Need: verify debate_protocol is initialized and can find candidates

- [ ] **AGI-008: Causal discovery — 0 causal edges**
  - Depends on AGI-006 (domain diversity)
  - PC algorithm needs >= 20 nodes per domain with variance
  - Runs every 307 blocks

- [ ] **AGI-009: Self-improvement — 0 cycles**
  - Runs every 607 blocks (~33 min)
  - Needs reasoning feedback to trigger
  - Depends on AGI-005 (inference generation → feedback)

- [ ] **AGI-010: Curiosity engine — verify goals generating**
  - Runs every 563 blocks
  - Stats may not be exposed in API — check `_curiosity_stats`
  - System may be working but invisible

---

## MEDIUM PRIORITY (Quality Improvements)

- [ ] **AGI-011: Prediction validation — 0 validated**
  - Temporal engine makes predictions but validation needs outcome data
  - Check if predictions are being verified against actual blocks

- [ ] **AGI-012: Metacognition ECE tracking**
  - ECE needs sufficient evaluation count to be meaningful
  - Gate 7 requires ECE < 0.15 with >= 200 evaluations
  - Natural improvement as blocks accumulate

- [ ] **AGI-013: Add diagnostic logging for all AGI subsystems**
  - Each subsystem tick should log: trigger count, success/fail, items processed
  - Enables monitoring without reading code

- [ ] **AGI-014: Expose AGI subsystem stats in /aether/info endpoint**
  - debate_verdicts, causal_edges, curiosity_goals, si_cycles, predictions_validated
  - Currently some stats only visible in logs

---

## ARCHITECTURAL (Phase 2+)

- [ ] **AGI-015: Distributed KG — LRU hot cache**
  - Top 100K nodes in memory, cold rest in CockroachDB
  - Needed when KG exceeds ~1M nodes

- [ ] **AGI-016: BFT inter-node knowledge consensus**
  - 2/3 supermajority for knowledge acceptance
  - Requires multi-node P2P first

- [ ] **AGI-017: Do-calculus causal reasoning**
  - Counterfactual simulation via Pearl structural equations
  - Upgrades causal_engine beyond PC algorithm

- [ ] **AGI-018: Multi-modal grounding**
  - Code/numeric/time-series alongside text nodes

---

## COMPLETED

| ID | Description | Date | Commit |
|----|-------------|------|--------|
| AGI-001 | Fix EmotionalState .get_state() → .states | 2026-04-06 | fa12906 |
| AGI-003 | Intent routing — dedicated handlers protected | 2026-04-06 | fa12906 |
| AGI-004 | Emotion noun → adjective conversion | 2026-04-06 | fa12906 |
