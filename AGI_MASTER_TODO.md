# AGI Master TODO — Path to True Emergence

> Generated 2026-04-06 (session 55). Tracks all fixes needed for genuine AGI.
> Check boxes as items are completed. Update dates.

---

## CRITICAL (Must Fix)

- [x] **AGI-001: Fix EmotionalState .get_state() → .states** (2026-04-06, fa12906)
  - 3 call sites in chat.py called nonexistent method
  - Emotions were always empty

- [x] **AGI-002: Long-term memory consolidation** — VERIFIED CORRECT (2026-04-06)
  - Line 1878-1880: already has `block.height % Config.AETHER_LONG_TERM_CONSOLIDATION_INTERVAL == 0` gate
  - Audit agent was wrong — no fix needed

- [x] **AGI-003: Intent routing — inference conclusions override dedicated handlers** (2026-04-06, fa12906)
  - Added `_dedicated_intents` set to exclusion lists

- [x] **AGI-004: Emotion nouns displayed raw** (2026-04-06, fa12906)
  - Added `_emo_adjective()` helper

---

## HIGH PRIORITY (Needed for Gate Progression)

- [x] **AGI-005: Inference node generation — VERIFIED WORKING** (2026-04-06)
  - `_run_autonomous_reasoning()` creates 5-10 inferences per cycle (every 10 blocks)
  - Logs confirmed: "Autonomous reasoning at block 186350: 10 inferences created"
  - Was already working, just not visible in stats

- [x] **AGI-005b: Stats reporting broken — used wrong attribute names** (2026-04-06, f1f6272)
  - debate_count: `getattr(dp, 'total_debates')` → `dp.get_stats()['total_debates']`
  - predictions: `te.predictions_validated` → `te._predictions_validated` (underscore)
  - contradictions: added `_contradictions_resolved` counter to AetherEngine
  - curiosity: `_total_discoveries` → `len(exploration_history)`

- [ ] **AGI-006: Multi-domain KG sparsity**
  - Causal discovery (PC algorithm) needs multi-domain diversity
  - Current KG dominated by blockchain observations
  - Action: Verify agent stack is seeding non-blockchain domains
  - Action: Ensure knowledge_extractor classifies domains correctly

- [x] **AGI-007: Debate engine — VERIFIED WORKING** (2026-04-06)
  - Logs show: "Debate 'generalization...': accepted (prop=0.970)" — 5 debates at last trigger
  - Runs every 211 blocks. Counter resets on restart (in-memory).
  - Stats now reported correctly via get_stats()

- [ ] **AGI-008: Causal discovery — 0 causal edges**
  - Depends on AGI-006 (domain diversity)
  - PC algorithm needs >= 20 nodes per domain with variance
  - Runs every 307 blocks

- [ ] **AGI-009: Self-improvement — 0 cycles after restart**
  - Runs every 607 blocks (~33 min). Next trigger: block % 607 == 0
  - SI engine IS initialized (logs confirm). Counter resets on restart.
  - Monitor: should show cycles after ~33 min of uptime

- [ ] **AGI-010: Curiosity engine — verify goals generating**
  - Runs every 563 blocks
  - Stats may not be exposed in API — check `_curiosity_stats`
  - System may be working but invisible

---

## MEDIUM PRIORITY (Quality Improvements)

- [x] **AGI-011: Prediction validation — VERIFIED WORKING** (2026-04-06)
  - Logs: "Validated 3 predictions at block 186390 (accuracy: 100%)"
  - Stats now show: 12 validated, 100% accuracy
  - Fixed by using correct attribute name `_predictions_validated`

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
| AGI-002 | Long-term memory consolidation — verified correct | 2026-04-06 | N/A |
| AGI-003 | Intent routing — dedicated handlers protected | 2026-04-06 | fa12906 |
| AGI-004 | Emotion noun → adjective conversion | 2026-04-06 | fa12906 |
| AGI-005 | Inference generation — verified working (5-10/cycle) | 2026-04-06 | N/A |
| AGI-005b | Stats reporting — wrong attribute names fixed | 2026-04-06 | f1f6272 |
| AGI-007 | Debate engine — verified working | 2026-04-06 | f1f6272 |
| AGI-011 | Prediction validation — verified working (12 valid, 100%) | 2026-04-06 | f1f6272 |
