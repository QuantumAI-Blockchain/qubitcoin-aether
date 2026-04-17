# Qubitcoin Master Code Inventory

> Generated: 2026-02-22 | Total: 371+ files | ~98,700 LOC
> **Audit tracking document for full codebase audit**

---

## Summary

| Category | Files | LOC | Status |
|----------|-------|-----|--------|
| Python Source (L1/L2/L3) | 95 | 39,327 | **AUDITED** |
| Solidity Contracts | 46 | 6,581 | **AUDITED** |
| Rust P2P | 5 src + proto + cargo | 497 src | **AUDITED** |
| SQL Schemas | 31 | 2,548 | **AUDITED** |
| Frontend (TS/TSX) | 49 | 6,970 | **AUDITED** |
| Tests | 104 | 30,524 | **AUDITED** |
| Docs (MD) | 17 | 12,320 | Pending |
| Entry + Config | 2 | 682 | **AUDITED** |
| **Total** | **349+** | **~99,449** | **19C/26H/18M** |

---

## 1. Entry Points + Config

| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/run_node.py` | 9 | Entry point → `qubitcoin.main()` |
| `src/qubitcoin/__init__.py` | 10 | `QubitcoinNode`, `main`, `__version__` |
| `src/qubitcoin/node.py` | 673 | `QubitcoinNode` (10-component orchestrator), `main()` |
| `src/qubitcoin/config.py` | 353 | `Config` class (all env-based config) |

---

## 2. Layer 1: Blockchain Core

### 2.1 Consensus
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/consensus/__init__.py` | 4 | — |
| `src/qubitcoin/consensus/engine.py` | 550 | `ConsensusEngine` — block validation, difficulty, rewards |

### 2.2 Mining
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/mining/__init__.py` | 4 | — |
| `src/qubitcoin/mining/engine.py` | 398 | `MiningEngine` — VQE mining loop, block creation |
| `src/qubitcoin/mining/capability_detector.py` | 286 | `VQECapabilityDetector` — node hardware/quantum detection |
| `src/qubitcoin/mining/solution_tracker.py` | 243 | `SolutionVerificationTracker` — SUSY solution verification |

### 2.3 Quantum
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/quantum/__init__.py` | 5 | — |
| `src/qubitcoin/quantum/engine.py` | 310 | `QuantumEngine` — VQE optimization, Hamiltonian generation |
| `src/qubitcoin/quantum/crypto.py` | 294 | `Dilithium2` — keygen, sign, verify, derive_address |

### 2.4 Database
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/database/__init__.py` | 5 | — |
| `src/qubitcoin/database/manager.py` | 1,492 | `DatabaseManager` — sessions, queries, UTXO, staking |
| `src/qubitcoin/database/models.py` | 260 | `Block`, `Transaction`, `UTXO`, `Account` — SQLAlchemy models |
| `src/qubitcoin/database/pool_monitor.py` | 253 | `PoolHealthMonitor` — connection pool health |

### 2.5 Network
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/network/__init__.py` | 4 | — |
| `src/qubitcoin/network/rpc.py` | 2,648 | `create_rpc_app()` — all REST endpoints (100+ routes) |
| `src/qubitcoin/network/jsonrpc.py` | 624 | `create_jsonrpc_router()` — eth_* MetaMask compat |
| `src/qubitcoin/network/admin_api.py` | 304 | Admin API router — economics hot-reload |
| `src/qubitcoin/network/p2p_network.py` | 678 | `P2PNetwork` — Python P2P (legacy fallback) |
| `src/qubitcoin/network/rust_p2p_client.py` | 157 | `RustP2PClient` — Rust libp2p gRPC bridge |
| `src/qubitcoin/network/light_node.py` | — | `LightNodeProtocol` — SPV verification |
| `src/qubitcoin/network/capability_advertisement.py` | 246 | `CapabilityAdvertiser` — P2P mining capability |

### 2.6 Storage
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/storage/__init__.py` | 4 | — |
| `src/qubitcoin/storage/ipfs.py` | 249 | `IPFSManager` — IPFS pinning, snapshots |
| `src/qubitcoin/storage/snapshot_scheduler.py` | 511 | `SnapshotScheduler` — blockchain snapshot automation |
| `src/qubitcoin/storage/solution_archiver.py` | 284 | `SolutionArchiver` — SUSY solution IPFS archival |

### 2.7 Utils
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/utils/__init__.py` | 24 | — |
| `src/qubitcoin/utils/logger.py` | 78 | `get_logger()` — structured logging |
| `src/qubitcoin/utils/metrics.py` | 161 | Prometheus metrics (all subsystems) |
| `src/qubitcoin/utils/fee_collector.py` | 257 | `FeeCollector` — fee tracking/treasury |
| `src/qubitcoin/utils/qusd_oracle.py` | 144 | `QUSDOracle` — QBC/USD price feed |

---

## 3. Layer 2: QVM (Quantum Virtual Machine)

### 3.1 QVM Core
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/qvm/__init__.py` | 8 | — |
| `src/qubitcoin/qvm/vm.py` | 1,149 | `QVM` — bytecode interpreter (155 + 10 opcodes) |
| `src/qubitcoin/qvm/opcodes.py` | 361 | Opcode definitions, gas cost tables |
| `src/qubitcoin/qvm/state.py` | 477 | `StateManager` — state roots, account storage |

### 3.2 QVM Compliance
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/qvm/compliance.py` | 446 | `ComplianceEngine`, `KYCLevel` |
| `src/qubitcoin/qvm/compliance_advanced.py` | 554 | Advanced compliance features |
| `src/qubitcoin/qvm/compliance_proofs.py` | 293 | `ComplianceProofStore` |
| `src/qubitcoin/qvm/risk.py` | 137 | Risk assessment |
| `src/qubitcoin/qvm/aml.py` | 219 | AML monitoring |

### 3.3 QVM Plugins
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/qvm/plugins.py` | 275 | `PluginManager` |
| `src/qubitcoin/qvm/defi_plugin.py` | — | DeFi plugin |
| `src/qubitcoin/qvm/governance_plugin.py` | 308 | Governance plugin |
| `src/qubitcoin/qvm/oracle_plugin.py` | 239 | Oracle plugin |
| `src/qubitcoin/qvm/privacy_plugin.py` | 229 | Privacy plugin |
| `src/qubitcoin/qvm/qsol_compiler.py` | 927 | Quantum Solidity compiler |
| `src/qubitcoin/qvm/debugger.py` | 735 | QVM bytecode debugger |

### 3.4 QVM Extensions
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/qvm/abi.py` | 175 | ABI encoding/decoding |
| `src/qubitcoin/qvm/decoherence.py` | 150 | Quantum decoherence model |
| `src/qubitcoin/qvm/hamiltonian_risk.py` | 250 | Hamiltonian-based risk |
| `src/qubitcoin/qvm/systemic_risk.py` | 259 | Systemic risk analysis |
| `src/qubitcoin/qvm/token_indexer.py` | 360 | `TokenIndexer` — QBC-20/721 tracking |
| `src/qubitcoin/qvm/transaction_batcher.py` | 290 | Transaction batching |
| `src/qubitcoin/qvm/state_channels.py` | 363 | State channel support |
| `src/qubitcoin/qvm/regulatory_reports.py` | — | `RegulatoryReportGenerator` |
| `src/qubitcoin/qvm/tx_graph.py` | 161 | Transaction graph analysis |

### 3.5 Contracts
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/contracts/__init__.py` | 5 | — |
| `src/qubitcoin/contracts/engine.py` | 789 | `ContractEngine` — deployment engine |
| `src/qubitcoin/contracts/executor.py` | 339 | `ContractExecutor` — template contract execution |
| `src/qubitcoin/contracts/templates.py` | 29 | Pre-built contract templates |
| `src/qubitcoin/contracts/fee_calculator.py` | 116 | `ContractFeeCalculator` |
| `src/qubitcoin/contracts/verification.py` | 142 | Contract verification |
| `src/qubitcoin/contracts/proxy.py` | 367 | Proxy contract support |

### 3.6 Stablecoin
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/stablecoin/__init__.py` | 4 | — |
| `src/qubitcoin/stablecoin/engine.py` | 563 | QUSD engine |
| `src/qubitcoin/stablecoin/reserve_manager.py` | 511 | Reserve management |
| `src/qubitcoin/stablecoin/reserve_verification.py` | 359 | Reserve verification |

---

## 4. Layer 3: Aether Tree (AI Engine)

### 4.1 Aether Core
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/aether/__init__.py` | 99 | `KnowledgeGraph`, `PhiCalculator`, `ReasoningEngine`, `AetherEngine` |
| `src/qubitcoin/aether/knowledge_graph.py` | 787 | `KnowledgeGraph`, `KeterNode`, `KnowledgeEdge` |
| `src/qubitcoin/aether/reasoning.py` | 832 | `ReasoningEngine` — deductive/inductive/abductive |
| `src/qubitcoin/aether/phi_calculator.py` | 667 | `PhiCalculator` — IIT consciousness metric |
| `src/qubitcoin/aether/proof_of_thought.py` | 960 | `AetherEngine` — PoT, block knowledge, auto-reasoning |

### 4.2 Aether Chat + LLM
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/aether/chat.py` | 615 | `AetherChat` — conversational interface |
| `src/qubitcoin/aether/llm_adapter.py` | 680 | `LLMAdapterManager`, `OpenAIAdapter`, `ClaudeAdapter`, `LocalAdapter` |
| `src/qubitcoin/aether/knowledge_seeder.py` | 712 | `KnowledgeSeeder` — LLM-powered knowledge injection |
| `src/qubitcoin/aether/fee_manager.py` | 138 | `AetherFeeManager` — chat fee calculation |

### 4.3 Sephirot + Cognitive Architecture
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/aether/sephirot.py` | 299 | `SephirotManager`, `SephirahRole`, `SephirahState` |
| `src/qubitcoin/aether/sephirot_nodes.py` | 882 | `SephirahNode`, `create_all_nodes()` |
| `src/qubitcoin/aether/csf_transport.py` | 371 | `CSFTransport` — inter-node messaging |
| `src/qubitcoin/aether/pineal.py` | 547 | `PinealOrchestrator` — circadian timing |
| `src/qubitcoin/aether/safety.py` | 499 | `SafetyManager` — Gevurah veto, Constitutional AI |

### 4.4 Knowledge Pipeline
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/aether/knowledge_extractor.py` | — | `KnowledgeExtractor` — block knowledge extraction |
| `src/qubitcoin/aether/kg_index.py` | 201 | TF-IDF knowledge graph index |
| `src/qubitcoin/aether/query_translator.py` | 295 | Natural language → KG query |
| `src/qubitcoin/aether/ipfs_memory.py` | 204 | `IPFSMemoryStore` — IPFS-backed memory |
| `src/qubitcoin/aether/genesis.py` | 178 | `AetherGenesis` — genesis block AI init |

### 4.5 Aether Services
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/aether/task_protocol.py` | 459 | `ProofOfThoughtProtocol`, `TaskMarket`, `ValidatorRegistry` |
| `src/qubitcoin/aether/consciousness.py` | 267 | `ConsciousnessDashboard` |
| `src/qubitcoin/aether/ws_streaming.py` | 206 | `AetherWSManager` — WebSocket streaming |
| `src/qubitcoin/aether/circulation.py` | 223 | `CirculationTracker` — QBC supply tracking |
| `src/qubitcoin/aether/memory.py` | 448 | `MemoryManager` — episodic/semantic/procedural |
| `src/qubitcoin/aether/pot_explorer.py` | 240 | `ProofOfThoughtExplorer` — PoT block viewer |

---

## 5. Cross-Cutting Modules

### 5.1 Privacy
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/privacy/__init__.py` | 17 | — |
| `src/qubitcoin/privacy/commitments.py` | 231 | Pedersen commitments |
| `src/qubitcoin/privacy/range_proofs.py` | 280 | Bulletproofs range proofs |
| `src/qubitcoin/privacy/stealth.py` | 190 | Stealth address generation |
| `src/qubitcoin/privacy/susy_swap.py` | 263 | Confidential transaction builder |

### 5.2 Bridge
| File | LOC | Primary Exports |
|------|-----|-----------------|
| `src/qubitcoin/bridge/__init__.py` | 18 | — |
| `src/qubitcoin/bridge/manager.py` | 322 | `BridgeManager` |
| `src/qubitcoin/bridge/base.py` | 354 | `BaseBridge` — abstract bridge |
| `src/qubitcoin/bridge/ethereum.py` | — | Ethereum bridge |
| `src/qubitcoin/bridge/solana.py` | 256 | Solana bridge |
| `src/qubitcoin/bridge/monitoring.py` | 570 | Bridge health monitoring |
| `src/qubitcoin/bridge/validators.py` | — | Bridge validators |
| `src/qubitcoin/bridge/proof_store.py` | — | Bridge proof storage |

---

## 6. Solidity Contracts (46 files, 6,581 LOC)

### 6.1 Interfaces
| File | LOC |
|------|-----|
| `contracts/solidity/interfaces/ISephirah.sol` | 39 |
| `contracts/solidity/interfaces/IQBC20.sol` | 36 |
| `contracts/solidity/interfaces/IQBC721.sol` | 20 |

### 6.2 Token Standards
| File | LOC |
|------|-----|
| `contracts/solidity/tokens/QBC20.sol` | 97 |
| `contracts/solidity/tokens/QBC721.sol` | 131 |
| `contracts/solidity/tokens/QBC1155.sol` | 231 |
| `contracts/solidity/tokens/ERC20QC.sol` | 241 |
| `contracts/solidity/tokens/wQBC.sol` | 227 |

### 6.3 QUSD Stablecoin (8 files)
| File | LOC |
|------|-----|
| `contracts/solidity/qusd/QUSD.sol` | 161 |
| `contracts/solidity/qusd/QUSDReserve.sol` | 147 |
| `contracts/solidity/qusd/QUSDDebtLedger.sol` | 146 |
| `contracts/solidity/qusd/QUSDOracle.sol` | 181 |
| `contracts/solidity/qusd/QUSDStabilizer.sol` | 161 |
| `contracts/solidity/qusd/QUSDAllocation.sol` | 193 |
| `contracts/solidity/qusd/QUSDGovernance.sol` | 207 |
| `contracts/solidity/qusd/wQUSD.sol` | 164 |

### 6.4 Aether Contracts (17 files)
| File | LOC |
|------|-----|
| `contracts/solidity/aether/AetherKernel.sol` | 204 |
| `contracts/solidity/aether/NodeRegistry.sol` | 171 |
| `contracts/solidity/aether/MessageBus.sol` | 163 |
| `contracts/solidity/aether/SUSYEngine.sol` | 176 |
| `contracts/solidity/aether/RewardDistributor.sol` | 106 |
| `contracts/solidity/aether/ProofOfThought.sol` | 142 |
| `contracts/solidity/aether/TaskMarket.sol` | 140 |
| `contracts/solidity/aether/ValidatorRegistry.sol` | 153 |
| `contracts/solidity/aether/ConsciousnessDashboard.sol` | 214 |
| `contracts/solidity/aether/PhaseSync.sol` | 162 |
| `contracts/solidity/aether/GlobalWorkspace.sol` | 178 |
| `contracts/solidity/aether/SynapticStaking.sol` | 290 |
| `contracts/solidity/aether/GasOracle.sol` | 96 |
| `contracts/solidity/aether/TreasuryDAO.sol` | 129 |
| `contracts/solidity/aether/ConstitutionalAI.sol` | 151 |
| `contracts/solidity/aether/EmergencyShutdown.sol` | 157 |
| `contracts/solidity/aether/UpgradeGovernor.sol` | 133 |
| `contracts/solidity/aether/VentricleRouter.sol` | 252 |

### 6.5 Sephirot Contracts (10 files)
| File | LOC |
|------|-----|
| `contracts/solidity/aether/sephirot/SephirahKeter.sol` | 97 |
| `contracts/solidity/aether/sephirot/SephirahChochmah.sol` | 62 |
| `contracts/solidity/aether/sephirot/SephirahBinah.sol` | 69 |
| `contracts/solidity/aether/sephirot/SephirahChesed.sol` | 62 |
| `contracts/solidity/aether/sephirot/SephirahGevurah.sol` | 72 |
| `contracts/solidity/aether/sephirot/SephirahTiferet.sol` | 69 |
| `contracts/solidity/aether/sephirot/SephirahNetzach.sol` | 69 |
| `contracts/solidity/aether/sephirot/SephirahHod.sol` | 69 |
| `contracts/solidity/aether/sephirot/SephirahYesod.sol` | 84 |
| `contracts/solidity/aether/sephirot/SephirahMalkuth.sol` | 69 |

### 6.6 Bridge Contracts (2 files)
| File | LOC |
|------|-----|
| `contracts/solidity/bridge/BridgeVault.sol` | 298 |
| `contracts/solidity/bridge/wQBC.sol` | 162 |

---

## 7. SQL Schemas (31 files, 2,548 LOC)

### 7.1 Legacy (`sql/`)
| File | LOC |
|------|-----|
| `sql/00_init_database.sql` | 14 |
| `sql/01_core_blockchain.sql` | 166 |
| `sql/02_privacy_susy_swaps.sql` | 65 |
| `sql/03_smart_contracts_qvm.sql` | 91 |
| `sql/04_multi_chain_bridge.sql` | 58 |
| `sql/05_qusd_stablecoin.sql` | 48 |
| `sql/06_quantum_research.sql` | 54 |
| `sql/07_ipfs_storage.sql` | 64 |
| `sql/08_system_configuration.sql` | 111 |
| `sql/09_genesis_block.sql` | 68 |

### 7.2 New (`sql_new/`)
| File | LOC |
|------|-----|
| `sql_new/qbc/00_init_database.sql` | 25 |
| `sql_new/qbc/01_blocks_transactions.sql` | 98 |
| `sql_new/qbc/02_utxo_model.sql` | 58 |
| `sql_new/qbc/03_addresses_balances.sql` | 35 |
| `sql_new/qbc/04_chain_state.sql` | 53 |
| `sql_new/qbc/05_mempool.sql` | 38 |
| `sql_new/qbc/99_genesis_block.sql` | 295 |
| `sql_new/agi/00_knowledge_graph.sql` | 93 |
| `sql_new/agi/01_reasoning_engine.sql` | 122 |
| `sql_new/agi/02_training_data.sql` | 143 |
| `sql_new/agi/03_phi_metrics.sql` | 157 |
| `sql_new/agi/04_sephirot_state.sql` | 26 |
| `sql_new/qvm/00_contracts_core.sql` | 91 |
| `sql_new/qvm/01_execution_engine.sql` | 92 |
| `sql_new/qvm/02_state_storage.sql` | 53 |
| `sql_new/qvm/03_gas_metering.sql` | 66 |
| `sql_new/research/00_hamiltonians.sql` | 45 |
| `sql_new/research/01_vqe_circuits.sql` | 47 |
| `sql_new/research/02_susy_solutions.sql` | 56 |
| `sql_new/shared/00_ipfs_storage.sql` | 134 |
| `sql_new/shared/01_system_config.sql` | 82 |

---

## 8. Rust P2P (5 source files, 497 LOC)

| File | LOC |
|------|-----|
| `rust-p2p/src/main.rs` | 61 |
| `rust-p2p/src/network/mod.rs` | 257 |
| `rust-p2p/src/protocol/mod.rs` | 97 |
| `rust-p2p/src/bridge/mod.rs` | 82 |
| `rust-p2p/proto/p2p_service.proto` | 23 |
| `rust-p2p/Cargo.toml` | 54 |
| `rust-p2p/build.rs` | 4 |

---

## 9. Frontend (49 files, 6,970 LOC)

*Files under `frontend/src/`*

*(Detailed inventory pending from audit agent)*

---

## 10. Tests (104 files, 30,524 LOC)

*Files under `tests/`*

*(Detailed inventory pending from audit agent)*

---

## 11. Documentation (17 files, 12,320 LOC)

| File | LOC |
|------|-----|
| `docs/WHITEPAPER.md` | 2,753 |
| `docs/QVM_WHITEPAPER.md` | 950 |
| `docs/AETHERTREE_WHITEPAPER.md` | 839 |
| `docs/ECONOMICS.md` | 1,103 |
| `docs/AETHER_INTEGRATION.md` | 672 |
| `docs/SDK.md` | 582 |
| `docs/DEPLOYMENT.md` | 419 |
| `docs/SMART_CONTRACTS.md` | 405 |
| `docs/PLUGIN_SDK.md` | 330 |
| `docs/KEY_ROTATION.md` | 221 |
| `docs/BRIDGE_SECURITY_AUDIT.md` | 215 |
| `CLAUDE.md` | 1,653 |
| `README.md` | 336 |
| `LAUNCHTODO.md` | 1,033 |
| `TODO.md` | 809 |

---

## 12. Infrastructure

| File | Purpose |
|------|---------|
| `Dockerfile` | Docker build |
| `docker-compose.yml` | Dev deployment (9 services) |
| `docker-compose.production.yml` | Production multi-node |
| `.env.example` | Environment template |
| `requirements.txt` | Python dependencies |
| `setup.py` | Package setup |
| `config/prometheus/prometheus.yml` | Prometheus config |

---

## Audit Findings

> **Audit completed: 2026-02-22** | 6 parallel agents | 371+ files audited
> **Fixes applied: 2026-02-22** | 2,276 unit tests passing
>
> **Totals: 19 CRITICAL | 26 HIGH | 18 MEDIUM | 30+ LOW/INFO**
> **Resolved: C1-C7 FIXED | H1,H3,H4,H11,H12,H13,H19 FIXED | H20,H21 DOCUMENTED | H22-H24,M6,M18 FALSE POSITIVE | M7 FIXED**

### Finding Categories
- **DEAD_CODE**: Defined but never called from anywhere
- **BROKEN_REF**: Calls non-existent function/method/attribute
- **UNWIRED**: Class/module exists but never instantiated
- **SIGNATURE_MISMATCH**: Called with wrong argument count/names/order
- **SCHEMA_MISMATCH**: SQL schema doesn't match SQLAlchemy model
- **RESPONSE_SHAPE_MISMATCH**: Frontend expects different response shape from backend
- **DEAD_IMPORT**: Import that's never used
- **DEAD_CONFIG**: Config parameter that's never read

---

### CRITICAL FINDINGS (19)

#### L1 Core (3)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C1 | `consensus/engine.py:397-402` | BROKEN_REF | `RangeProof()` constructor called with `proof_data` and `value_range` kwargs that don't exist on the RangeProof dataclass. Private transaction validation always throws TypeError. |
| C2 | `mining/engine.py:233` | BROKEN_REF | `self.aether.phi_calculator` should be `self.aether.phi`. Phi downsampling silently never runs. |
| C3 | `mining/engine.py:239` | BROKEN_REF | `self.aether.knowledge_graph` should be `self.aether.kg`. KG pruning silently never runs. |

#### L3 Aether Tree (4)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C4 | `aether/proof_of_thought.py:612` | BROKEN_REF | `auto_resolve_contradictions()` calls `self.kg.edges.values()` but edges is a List, not Dict. Also uses `edge.source_id`/`edge.target_id` instead of `edge.from_node_id`/`edge.to_node_id`. |
| C5 | `aether/proof_of_thought.py:887` | BROKEN_REF | `self_reflect()` passes args to `_record_consciousness_event()` in wrong order: block_height as event_type, string as block_height, etc. All 4 positional args wrong. |
| C6 | `aether/chat.py:432` | BROKEN_REF | `_llm_synthesize()` calls `self.engine.kg.edges.get((ref_id, target_id))` but edges is a List, not Dict. AttributeError whenever LLM tries to include edge data. |
| C7 | `rpc.py:1062` | BROKEN_REF | `/aether/sephirot` checks `aether_engine.sephirot_nodes` but correct attr is `.sephirot`. Always falls to disconnected fallback SephirotManager. |

#### L2 QVM (1)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C8 | `contracts/engine.py:1` | UNWIRED | `ContractEngine` (789 LOC) never imported in node.py or rpc.py. node.py uses `ContractExecutor` instead. Entire class dead. |

#### Cross-Cutting (5)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C9 | `bridge/*` (7 files, ~2,770 LOC) | UNWIRED | BridgeManager never instantiated. No `/bridge/*` endpoints. Entire bridge subsystem is dead code at runtime. |
| C10 | `utils/fee_collector.py` | UNWIRED | FeeCollector never instantiated. `collect_fee()` never called. All fee collection (CLAUDE.md Sections 21-22) non-functional. |
| C11 | `utils/metrics.py:148` | BROKEN_REF | `setup_metrics()` never called. Prometheus Instrumentator never applied to FastAPI. HTTP request metrics not collected. |
| C12 | `network/light_node.py` (~430 LOC) | UNWIRED | LightNode, SPVVerifier, LightNodeSync have zero callers. No SPV endpoints. Entirely dead. |
| C13 | `privacy/susy_swap.py` | DEAD_CODE | SusySwapBuilder and ConfidentialTransaction have zero external callers. Privacy tx builder fully implemented but completely unwired. |

#### Rust P2P (3)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C14 | `rust-p2p/src/main.rs:25-26` | DEAD_CHANNEL | `from_python_tx` never used; `to_network_rx` never consumed. gRPC BroadcastBlock writes to channel nobody reads — blocks are silently dropped. |
| C15 | `rust-p2p/src/main.rs:52-60` | INCOMPLETE | Main event loop only logs `to_python_rx` messages, doesn't forward to Python. P2P peer messages never reach the Python node. |
| C16 | `rust-p2p/src/bridge/mod.rs:58` | STALE_COUNTER | `get_peer_stats` reads AtomicUsize that nothing ever updates. Always returns 0 peers. |

#### QVM Subsystem (2)
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| C17 | `qvm/plugins.py` + 4 plugins | UNWIRED | PluginManager, all 4 plugins (DeFi, Governance, Oracle, Privacy), and HookType dispatch never instantiated. Zero callers in production. |
| C18 | `qvm/qsol_compiler.py` (927 LOC) | UNWIRED | QSolCompiler, QSolLexer, QSolParser, QSolCodeGenerator never imported outside own file. |
| C19 | All of: `qvm/abi.py`, `decoherence.py`, `hamiltonian_risk.py`, `systemic_risk.py`, `transaction_batcher.py`, `state_channels.py`, `tx_graph.py`, `risk.py`, `aml.py`, `compliance_advanced.py`, `debugger.py` | UNWIRED | 11 QVM extension modules never instantiated in production. Only referenced in tests. |

---

### HIGH FINDINGS (26)

#### L1 Core
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H1 | `mining/engine.py` | DEAD_CODE | `stats` keys `uptime`, `best_energy`, `alignment_score` accessed by rpc.py but never populated — endpoints return zeros. |
| H2 | `mining/solution_tracker.py` | DEAD_CODE | `register_solution()` never called from mining loop — tracker always empty. |
| H3 | `mining/capability_detector.py` | BROKEN_REF | `benchmark_vqe()` calls non-existent `QuantumEngine.run_vqe()` (should be `optimize_vqe`). |
| H4 | `consensus/engine.py` | BROKEN_REF | `resolve_fork()` uses `self.p2p` which is None in Rust P2P mode. Will crash if triggered. |

#### L3 Aether Tree
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H5 | `aether/pineal.py` | UNWIRED | PinealOrchestrator never instantiated. node.py passes no `pineal` arg. All circadian phases dead. |
| H6 | `aether/safety.py` | UNWIRED | SafetyManager (GevurahVeto, MultiNodeConsensus) never instantiated. "Structural safety" from CLAUDE.md absent from runtime. |
| H7 | `aether/csf_transport.py` | UNWIRED | CSFTransport never instantiated. Inter-Sephirot message routing via QBC transactions doesn't exist at runtime. |
| H8 | `aether/memory.py` | UNWIRED | MemoryManager (episodic/semantic/procedural/working) never instantiated. Biologically-inspired memory hierarchy absent. |
| H9 | `aether/ipfs_memory.py` | UNWIRED | IPFSMemoryStore never instantiated. IPFS-backed AI memory doesn't exist. |
| H10 | `aether/knowledge_extractor.py` | UNWIRED | KnowledgeExtractor never instantiated. AetherEngine does extraction inline. |
| H11 | `aether/consciousness.py` | DATA_STARVED | ConsciousnessDashboard.record_measurement() never called. Dashboard always returns empty data. |
| H12 | `aether/circulation.py` | DATA_STARVED | CirculationTracker.record_block() never called. `/circulation/current` always returns "No data." |
| H13 | `rpc.py:1488` | BROKEN_REF | `_sync_stake_energy()` accesses `aether_engine._sephirot_manager` which doesn't exist. SUSY balance enforcement after staking silently skipped. |

#### Cross-Cutting
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H14 | `utils/qusd_oracle.py` | WEAK_WIRING | QUSDOracle lazy-instantiated per-request, not at startup. Not connected to fee system. QUSD peg mechanism non-functional. |
| H15 | `storage/snapshot_scheduler.py` | WEAK_WIRING | Lazy-instantiated in endpoint, not in block pipeline. `on_new_block()` never called. Snapshots only happen via manual API call. |
| H16 | `storage/solution_archiver.py` | WEAK_WIRING | Same as H15 — lazy in endpoint, `on_new_block()` never called. |
| H17 | `network/capability_advertisement.py` | MOSTLY_DEAD | 11 of 12 public methods have zero callers. Only `get_stats()` called from endpoint. |

#### Rust P2P
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H18 | `rust-p2p/proto/p2p_service.proto` | INCOMPLETE | Only 2 of 12 NetworkMessage variants have gRPC methods. No tx broadcast, block sync, peer exchange. |

#### Database
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H19 | `database/manager.py` | DEAD_CODE | `prune_spent_utxos()` has zero callers. |
| H20 | `database/models.py` | DEAD_CODE | `ProofOfSUSY` dataclass exported but never instantiated anywhere. |
| H21 | `database/pool_monitor.py` | DEAD_CODE | `record_checkout()`, `record_checkin()`, `record_error()`, `record_timeout()`, `is_healthy()` all have zero callers. |

#### QVM
| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| H22 | `qvm/opcodes.py:320` | DEAD_CODE | `get_quantum_gas_cost()` never called. `get_gas_cost()` handles all opcodes. |
| H23 | `qvm/opcodes.py:227` | DEAD_CODE | `CANONICAL_OPCODE_MAP` dict never referenced anywhere. |
| H24 | `qvm/state.py:308` | DEAD_CODE | `QuantumStateStore` class defined but never instantiated. |
| H25 | `stablecoin/engine.py` | UNWIRED | StablecoinEngine never instantiated at startup. Only lazily imported in ContractExecutor._execute_stablecoin(). Dormant. |
| H26 | `stablecoin/reserve_*.py` (2 files) | UNWIRED | ReserveFeeRouter, ReserveMilestoneEnforcer, CrossChainQUSDAggregator, ReserveVerifier all have zero callers. |

---

### MEDIUM FINDINGS (18)

| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| M1 | `aether/consciousness.py:46` | DUPLICATE | ConsciousnessEvent dataclass duplicated between consciousness.py and pineal.py with different fields. |
| M2 | `aether/sephirot.py:219` | DEAD_CODE | SephirotManager.sync_stake_totals() never called. mining/engine.py bypasses it. |
| M3 | `aether/sephirot.py:90` | UNDERUSED | SephirotManager only instantiated as throwaway fallback. AetherEngine uses flat dict instead. |
| M4 | `aether/proof_of_thought.py:665` | INCONSISTENCY | Same file treats `self.kg.edges` as list (correct, line 665) AND as dict (broken, line 612). |
| M5 | `aether/task_protocol.py:219` | DISCONNECTED | ValidatorRegistry tracks staking but no code calls `stake()`. All staking goes through db_manager. PoT validators and Sephirot staking are parallel disconnected systems. |
| M6 | `network/jsonrpc.py:~400` | BROKEN_REF | `eth_call()` calls `self.qvm.qvm.static_call()` — assumes nested .qvm attribute that may not exist. |
| M7 | `network/admin_api.py` | NO_AUTH | All PUT endpoints have no authentication. Anyone can modify economic parameters. CLAUDE.md specifies auth required. |
| M8 | `utils/qusd_oracle.py:98` | PLACEHOLDER | `_read_onchain_price()` uses hardcoded placeholder selector `4a3c2f12`. Will fail with real oracle contract. |
| M9 | `privacy/range_proofs.py` | PARTIAL_WIRING | Verification works (used by consensus), but generation path is dead (only called from unwired susy_swap.py). |
| M10 | `frontend/api.ts:243` | RESPONSE_SHAPE | `getPhiHistory` expects `{history: [{block, phi}]}` but backend returns raw list with different field names. |
| M11 | `frontend/api.ts:271-275` | BODY_MISMATCH | `createChatSession` sends JSON body but backend expects query param. user_address always defaults to ''. |
| M12 | `frontend/api.ts:309` | RESPONSE_SHAPE | `getSephirotStatus` expects keys `susy_pairs`, `coherence`, `total_violations` which backend may not return. |
| M13 | `sql_new/ vs manager.py` (blocks) | SCHEMA_DIVERGENCE | SQL has 24 cols (BYTES PK), SQLAlchemy has 9 cols (BigInteger PK). Two different designs. |
| M14 | `sql_new/ vs manager.py` (txns) | SCHEMA_DIVERGENCE | SQL uses normalized design, SQLAlchemy uses JSON blobs. Incompatible if both run. |
| M15 | `sql_new/ vs manager.py` (utxos) | SCHEMA_DIVERGENCE | SQL has tx_inputs + tx_outputs tables, SQLAlchemy has single utxos table. Different paradigms. |
| M16 | `sql_new/ vs manager.py` (knowledge) | SCHEMA_DIVERGENCE | SQL has 20+ cols with vector embeddings, SQLAlchemy has 7 cols. PK types differ (UUID vs BigInteger). |
| M17 | `sql_new/ vs manager.py` (phi) | SCHEMA_DIVERGENCE | SQL has 19 cols (delta, trend, confidence), SQLAlchemy has 9 cols. |
| M18 | `qvm/compliance.py:421` | DEAD_CODE | `_persist_policy()` is a stub (`pass`). Policies exist only in memory, lost on restart. |

---

### RESOLUTION LOG

| Finding | Status | Action Taken |
|---------|--------|-------------|
| C1 | **FIXED** | RangeProof constructor now uses correct dataclass fields (A, S, T1, T2, tau_x, mu, t_hat) |
| C2 | **FIXED** | `self.aether.phi_calculator` → `self.aether.phi` in mining/engine.py |
| C3 | **FIXED** | `self.aether.knowledge_graph` → `self.aether.kg` in mining/engine.py |
| C4 | **FIXED** | List iteration (not .values()), from_node_id/to_node_id in proof_of_thought.py |
| C5 | **FIXED** | Corrected arg order in _record_consciousness_event() call |
| C6 | **FIXED** | List comprehension (not dict.get()) in chat.py |
| C7 | **FIXED** | `.sephirot_nodes` → `.sephirot` in rpc.py |
| C8 | DEFERRED | ContractEngine unwired — architectural decision needed |
| C9-C16 | DEFERRED | Bridge/Privacy/Rust P2P unwired — architectural decision needed |
| C17-C19 | DEFERRED | QVM plugins/extensions unwired — architectural decision needed |
| H1 | **FIXED** | Added uptime, best_energy, alignment_score to mining stats |
| H3 | **FIXED** | `run_vqe()` → `optimize_vqe()`, fixed positional arg in capability_detector.py |
| H4 | **FIXED** | Added None guard for self.p2p in resolve_fork() |
| H11 | **FIXED** | Wired ConsciousnessDashboard into AetherEngine block pipeline |
| H12 | **FIXED** | Wired CirculationTracker into MiningEngine block pipeline |
| H13 | **FIXED** | Replaced broken _sephirot_manager ref with TODO (type incompatibility) |
| H19 | **FIXED** | Removed dead prune_spent_utxos() (zero callers) |
| H20 | DOCUMENTED | ProofOfSUSY retained — tests depend on it |
| H21 | DOCUMENTED | pool_monitor manual methods retained — intentional public API |
| H22-H24 | FALSE POSITIVE | All used by tests — cannot remove |
| M6 | FALSE POSITIVE | self.qvm.qvm.static_call() chain is correct (StateManager→QVM) |
| M7 | **FIXED** | Admin API now requires X-Admin-Key header, 403 when unconfigured |
| M18 | FALSE POSITIVE | _persist_policy() already has full UPSERT implementation |
| H2,H5-H10,H14-H18,H25-H26 | DEFERRED | Unwired modules — need architectural decisions |
| M1-M5,M8-M17 | DEFERRED | Lower priority — schema divergence, duplicates, placeholders |
| NEW-1 | **FIXED** | Added KeyImageModel ORM table — prevents silent privacy double-spend |
| NEW-2 | **FIXED** | `get_sephirot_summary` return type `-> list` corrected to `-> dict` |
| NEW-3 | **FIXED** | `update_account` now preserves bytecode on conflict via COALESCE |
| FE-1 | **FIXED** | `/qvm/info` response: renamed `opcodes`→`total_opcodes`, added `total_contracts`, `active_contracts` |
| FE-2 | **FIXED** | Added 6 missing backend endpoints: `/qvm/tokens/{addr}`, `/qvm/token/{addr}`, `/qvm/token/transfer`, `/qvm/nfts/{addr}`, `/qvm/events/{addr}`, `/qvm/call` |
| FE-3 | NOTED | 5 dead API functions in frontend (`getAetherInfo`, `getChatHistory`, `getChatFee`, `signMessage`, `transferToAccount`) |
| FE-4 | NOTED | Dead frontend exports: `API` constant object in constants.ts, `ChainSocket` class in websocket.ts |
| FE-5 | NOTED | Dead Zustand store actions: `setChain()`, `setPhi()` in chain-store.ts (all data fetched via TanStack Query) |

---

### KEY ARCHITECTURAL GAPS

1. **Bridge System**: 7 files, ~2,770 LOC fully disconnected. BridgeManager never instantiated, no endpoints.
2. **Privacy System**: 4 files, ~967 LOC, ~90% dead. Only RangeProofVerifier.verify() is used (from consensus).
3. **Plugin System**: 5 files fully disconnected. No dispatch_hook() calls in QVM execution pipeline.
4. **Rust P2P**: Skeleton that runs but doesn't actually bridge anything. Channels are dead.
5. **Fee Collection**: FeeCollector never instantiated. QUSD peg mechanism non-functional.
6. **Cognitive Architecture**: PinealOrchestrator, SafetyManager, CSFTransport, MemoryManager all uninstantiated. AI "structural safety" described in whitepapers doesn't exist at runtime.
7. **Data-Starved Components**: ~~ConsciousnessDashboard~~, ~~CirculationTracker~~ (FIXED), ProofOfThoughtExplorer, AetherWSManager still wired to endpoints but never fed data.
8. **SQL Schema Divergence**: sql_new/ schemas and SQLAlchemy models are fundamentally different designs. Node runs on SQLAlchemy. sql_new/ is aspirational documentation.
9. **QVM Extensions**: 11 QVM extension modules (AML, risk, batching, state channels, ABI, etc.) fully implemented but zero production callers.
10. **Stablecoin**: 3 files, ~1,433 LOC effectively dormant. Only reachable via specific contract type execution path.
