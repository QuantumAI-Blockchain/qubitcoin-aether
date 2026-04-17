# AI Master TODO — Path to True Emergence

> Generated 2026-04-06 (session 55). Tracks all fixes needed for genuine AI.
> Check boxes as items are completed. Update dates.

---

## CRITICAL (Must Fix)

- [x] **AI-001: Fix EmotionalState .get_state() → .states** (2026-04-06, fa12906)
  - 3 call sites in chat.py called nonexistent method
  - Emotions were always empty

- [x] **AI-002: Long-term memory consolidation** — VERIFIED CORRECT (2026-04-06)
  - Line 1878-1880: already has `block.height % Config.AETHER_LONG_TERM_CONSOLIDATION_INTERVAL == 0` gate
  - Audit agent was wrong — no fix needed

- [x] **AI-003: Intent routing — inference conclusions override dedicated handlers** (2026-04-06, fa12906)
  - Added `_dedicated_intents` set to exclusion lists

- [x] **AI-004: Emotion nouns displayed raw** (2026-04-06, fa12906)
  - Added `_emo_adjective()` helper

---

## HIGH PRIORITY (Needed for Gate Progression)

- [x] **AI-005: Inference node generation — VERIFIED WORKING** (2026-04-06)
  - `_run_autonomous_reasoning()` creates 5-10 inferences per cycle (every 10 blocks)
  - Logs confirmed: "Autonomous reasoning at block 186350: 10 inferences created"
  - Was already working, just not visible in stats

- [x] **AI-005b: Stats reporting broken — used wrong attribute names** (2026-04-06, f1f6272)
  - debate_count: `getattr(dp, 'total_debates')` → `dp.get_stats()['total_debates']`
  - predictions: `te.predictions_validated` → `te._predictions_validated` (underscore)
  - contradictions: added `_contradictions_resolved` counter to AetherEngine
  - curiosity: `_total_discoveries` → `len(exploration_history)`

- [x] **AI-006: Multi-domain KG sparsity** (2026-04-06)
  - Added cross-domain knowledge extraction to `knowledge_extractor.py`
  - Every 50 blocks: physics (VQE energy interpretation), economics (tx volume supply-demand),
    complexity_science (difficulty feedback control), mathematics (hash entropy/information theory)
  - ~3-4 non-blockchain nodes per 50 blocks, auto-classified by domain
  - Seeder already has 50 diverse domain prompts with inverse-frequency weighting

- [x] **AI-007: Debate engine — VERIFIED WORKING** (2026-04-06)
  - Logs show: "Debate 'generalization...': accepted (prop=0.970)" — 5 debates at last trigger
  - Runs every 211 blocks. Counter resets on restart (in-memory).
  - Stats now reported correctly via get_stats()

- [ ] **AI-008: Causal discovery — 0 causal edges**
  - Depends on AI-006 (domain diversity) — NOW BEING SEEDED
  - PC algorithm needs >= 20 nodes per domain with variance
  - Runs every 307 blocks
  - Monitor: cross-domain nodes will accumulate over time, enabling PC algorithm

- [ ] **AI-009: Self-improvement — 0 cycles after restart**
  - Runs every 607 blocks (~33 min). Next trigger: block % 607 == 0
  - SI engine IS initialized (logs confirm). Counter now persisted to DB.
  - Monitor: should show cycles after ~33 min of uptime

- [ ] **AI-010: Curiosity engine — verify goals generating**
  - Runs every 563 blocks
  - Stats exposed in /aether/info via curiosity section
  - System may be working but need to verify via diagnostic logs

---

## MEDIUM PRIORITY (Quality Improvements)

- [x] **AI-011: Prediction validation — VERIFIED WORKING** (2026-04-06)
  - Logs: "Validated 3 predictions at block 186390 (accuracy: 100%)"
  - Stats now show: 12 validated, 100% accuracy
  - Fixed by using correct attribute name `_predictions_validated`

- [ ] **AI-012: Metacognition ECE tracking**
  - ECE needs sufficient evaluation count to be meaningful
  - Gate 7 requires ECE < 0.15 with >= 200 evaluations
  - Natural improvement as blocks accumulate

- [x] **AI-013: Add diagnostic logging for all AI subsystems** (2026-04-06)
  - Added consolidated diagnostic log every 100 blocks in `process_block_knowledge()`
  - Logs: KG nodes, Phi, gates, debates, contradictions, predictions (with accuracy),
    SI cycles, curiosity discoveries, dominant emotion, causal edges, domain count
  - Format: `AI diagnostics at block N: KG=X nodes | Phi=Y | gates=Z/10 | ...`

- [x] **AI-014: Expose AI subsystem stats in /aether/info endpoint** (2026-04-06)
  - Added to `get_stats()`: emotional_state (emotions + dominant), self_improvement
    (cycles, adjustments, rollbacks), prediction_summary (validated, correct, accuracy),
    contradictions_resolved
  - Already had: debate_protocol, causal_engine, curiosity, temporal_engine, etc. (40+ subsystems)

- [x] **AI-019: Counter persistence across restarts** (2026-04-06)
  - Counters (debates_run, contradictions_resolved, predictions_validated/correct)
    now persisted to `system_config` table (category='agi_counters') every 500 blocks
  - Loaded on startup via `_load_persisted_counters()`
  - No more counter reset to 0 on node restart

---

## ARCHITECTURAL (Phase 2+)

- [ ] **AI-015: Distributed KG — LRU hot cache**
  - Top 100K nodes in memory, cold rest in CockroachDB
  - Needed when KG exceeds ~1M nodes

- [ ] **AI-016: BFT inter-node knowledge consensus**
  - 2/3 supermajority for knowledge acceptance
  - Requires multi-node P2P first

- [ ] **AI-017: Do-calculus causal reasoning**
  - Counterfactual simulation via Pearl structural equations
  - Upgrades causal_engine beyond PC algorithm

- [ ] **AI-018: Multi-modal grounding**
  - Code/numeric/time-series alongside text nodes

---

## COMPLETED

| ID | Description | Date | Commit |
|----|-------------|------|--------|
| AI-001 | Fix EmotionalState .get_state() → .states | 2026-04-06 | fa12906 |
| AI-002 | Long-term memory consolidation — verified correct | 2026-04-06 | N/A |
| AI-003 | Intent routing — dedicated handlers protected | 2026-04-06 | fa12906 |
| AI-004 | Emotion noun → adjective conversion | 2026-04-06 | fa12906 |
| AI-005 | Inference generation — verified working (5-10/cycle) | 2026-04-06 | N/A |
| AI-005b | Stats reporting — wrong attribute names fixed | 2026-04-06 | f1f6272 |
| AI-006 | Cross-domain KG extraction (physics/econ/complexity/math) | 2026-04-06 | — |
| AI-007 | Debate engine — verified working | 2026-04-06 | f1f6272 |
| AI-011 | Prediction validation — verified working (12 valid, 100%) | 2026-04-06 | f1f6272 |
| AI-013 | Consolidated diagnostic logging every 100 blocks | 2026-04-06 | — |
| AI-014 | Emotional/SI/prediction stats in /aether/info | 2026-04-06 | — |
| AI-019 | Counter persistence to DB (survive restart) | 2026-04-06 | — |
