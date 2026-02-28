# AGENTS.md — AI Efficiency Guide for Qubitcoin

> **Purpose:** Prevent repeated mistakes. Every fact here was learned the hard way.
> Read this before touching code. See `CLAUDE.md` for full architecture reference.

---

## 1. DATA STRUCTURE FACTS

These are the #1 source of bugs. Memorize them.

### KnowledgeGraph (aether/knowledge_graph.py)
- `self.edges` is `List[KeterEdge]` — **NOT a dict**. Iterate directly, no `.values()`.
- `KeterEdge` fields: `from_node_id`, `to_node_id` — NOT `source_id`/`target_id`.
- `KeterNode` fields: `id`, `name`, `node_type`, `content`, `confidence`, `timestamp`.

### AetherEngine (aether/proof_of_thought.py)
- `self.phi` — float (NOT `.phi_calculator`)
- `self.kg` — KnowledgeGraph (NOT `.knowledge_graph`)
- `self.sephirot` — SephirotSystem (NOT `.sephirot_nodes`)

### Transaction (database/models.py)
- Fields: `txid`, `inputs`, `outputs`, `fee`, `to_address`, `data`
- **NOT** `sender`/`recipient`/`amount` — this is UTXO, not account model.

### TransactionReceipt
- `status: int` — 1=success, 0=revert
- **NOT** `.success` boolean.

### StateManager (qvm/state.py)
- `self.qvm.qvm.static_call()` is correct (StateManager.qvm → QVM.static_call())

### RangeProof (privacy/range_proofs.py)
- Dataclass fields: `commitment`, `A`, `S`, `T1`, `T2`, `tau_x`, `mu`, `t_hat`

### ComplianceEngine
- `compliance_engine.sanctions` is a `SanctionsList` object
- `SanctionsList._entries` is `Dict[str, SanctionsEntry]`
- `AMLMonitor` does NOT have a `sanctions_list` attribute

### FeeCollector (utils/fee_collector.py)
- Methods: `collect_fee()`, `get_audit_log(limit, fee_type)`, `get_total_fees_collected(fee_type)`, `get_stats()`

### BridgeManager (bridge/manager.py)
- `get_all_stats()` is async — NOT `get_stats()`

### StablecoinEngine (stablecoin/engine.py)
- `get_system_health()` returns `total_qusd`, `reserve_backing`, `cdp_debt`
- **NOT** `get_stats()`/`total_supply`/`backing_percentage`/`total_debt`

### PluginManager (qvm/plugins/)
- `register(plugin)` takes a QVMPlugin instance — NOT `(name, plugin)`
- `list_plugins()` returns list of dicts with `'name'` key
- `DeFiPlugin` is the correct class name (NOT `DEXPlugin`)

### HiggsCognitiveField (aether/higgs_field.py)
- `._cognitive_masses` is `Dict[SephirahRole, float]` — mass assignments per node
- `._field_value` is `float` — current Higgs field value
- `.params.vev` is `float` — vacuum expectation value (default 246.0)
- `EXPANSION_NODES = {Chochmah, Chesed, Netzach}` — couple to H_u
- `CONSTRAINT_NODES = {Binah, Gevurah, Hod}` — couple to H_d

### HiggsSUSYSwap (aether/higgs_field.py)
- `enforce_susy_balance_with_mass(block_height)` returns `int` (correction count)

### SephirahState (aether/sephirot.py)
- Now has `cognitive_mass: float` and `yukawa_coupling: float` fields (from Higgs mechanism)

### Contract Detection (dual tables)
- Template contracts: `contracts` table
- EVM bytecode: `accounts` table (where `code_hash != ''`)
- Always query BOTH when counting deployed contracts.

---

## 2. COMMON PITFALLS

### numpy float64 → CockroachDB
```python
# BAD: CockroachDB sees `np.float64` as schema "np"
db.store_hamiltonian(energy=energy)

# GOOD: Cast to Python float
db.store_hamiltonian(energy=float(energy))
```

### Qiskit V2 API
```python
# OLD (deprecated):
from qiskit.primitives import Estimator
result = estimator.run(circuit, observable).result()

# NEW (V2):
from qiskit.primitives import StatevectorEstimator
result = estimator.run([(circuit, observable)])
value = result[0].data.evs
```

### VQE Difficulty Direction
- **Higher difficulty = easier mining** (threshold is more generous)
- `ratio = actual_time / expected_time` — slow blocks RAISE difficulty
- The OPPOSITE of Bitcoin's PoW (where higher = harder)
- Hard fork at block 724 corrected the inverted formula

### Phi Calculator Scaling
- `sqrt(n_nodes / 500.0)` maturity factor — prevents trivially inflated Phi
- PHI_THRESHOLD = 3.0 requires ~500+ genuine knowledge nodes
- Old bug: `log2(n_nodes)` made Phi blow up trivially

### Thought Proof Bootstrap
- First 10 blocks (BOOTSTRAP_BLOCKS) allow empty reasoning_steps
- Chicken-and-egg: blocks need reasoning, reasoning needs committed blocks

### CockroachDB
- Pin v24.2.0+ for compatibility
- `start-single-node --insecure` (no `--listen-addr` flag in newer versions)
- Health check: `curl --fail http://localhost:8080/health?ready=1`

### Docker
- Rust binary name: `qubitcoin-p2p` (NOT `qbc-p2p`)
- Rust build needs rust:1.85+ (base64ct requires edition2024)
- Portainer: use `portainer/portainer-ce:lts` tag

### PHI_PRECISION
- `PHI_PRECISION = 1000` for float-to-uint256 conversion in Solidity
- On-chain Phi stored as `uint256(phi * 1000)`

---

## 3. ARCHITECTURE BOUNDARIES

### What Lives Where

| Boundary | Rule |
|----------|------|
| **L1 has NO gas** | Gas metering is QVM/L2 only |
| **QUSD is L2** | Smart contract suite on QVM, NOT L1 |
| **Fees are in .env** | All economic params are editable, never hardcode |
| **Keys in secure_key.env** | NEVER in `.env`, NEVER committed |
| **Schema = Model** | SQL schemas and SQLAlchemy models MUST match |

### 4-Repo Split Boundaries

```
qubitcoin-core:     consensus/ mining/ quantum/ database/ network/ storage/ privacy/ bridge/ stablecoin/
qubitcoin-qvm:      qvm/ contracts/ qubitcoin-qvm/ (Go)
qubitcoin-aether:   aether/ (33 modules)
qubitcoin-frontend: frontend/
qubitcoin-common:   database/ utils/ config.py (shared)
```

---

## 4. TEST COMMANDS

```bash
# Full suite (3,812+ tests)
pytest tests/ -v --tb=short

# By subsystem
pytest tests/unit/test_consensus.py -v
pytest tests/unit/test_mining.py -v
pytest tests/unit/test_qvm.py -v
pytest tests/unit/test_aether*.py -v
pytest tests/unit/test_privacy*.py -v
pytest tests/unit/test_bridge*.py -v
pytest tests/unit/test_on_chain*.py -v

# Integration (requires running node)
pytest tests/integration/ -v

# Validation
python3 tests/validation/test_system.py
python3 tests/validation/ultimate_genesis_validation.py

# Endpoints (requires running node)
bash tests/scripts/test_all_endpoints.sh
```

---

## 5. CODE REVIEW CHECKLIST

Before committing any change, verify:

- [ ] No hardcoded secrets, keys, or economic values
- [ ] Type hints on all function signatures
- [ ] `get_logger(__name__)` used (not print())
- [ ] `Config` class used for all config values
- [ ] SQL schema changes reflected in `database/models.py`
- [ ] `float()` cast on any numpy values going to database
- [ ] No `any` type in TypeScript (frontend)
- [ ] CRITICAL files (consensus, crypto, genesis, UTXO) changed only with approval
- [ ] Tests pass: `pytest tests/ -v --tb=short`
- [ ] No broken imports from moved/renamed files

---

## 6. KEY FILE LOCATIONS

| What | Where |
|------|-------|
| Node entry point | `src/run_node.py` |
| 22-component orchestrator | `src/qubitcoin/node.py` |
| Configuration | `src/qubitcoin/config.py` |
| 215+ REST endpoints | `src/qubitcoin/network/rpc.py` |
| 77 Prometheus metrics | `src/qubitcoin/utils/metrics.py` |
| ORM models | `src/qubitcoin/database/models.py` |
| 167-opcode QVM | `src/qubitcoin/qvm/vm.py` |
| AGI engine | `src/qubitcoin/aether/proof_of_thought.py` |
| Knowledge graph | `src/qubitcoin/aether/knowledge_graph.py` |
| Phi calculator | `src/qubitcoin/aether/phi_calculator.py` |
| On-chain AGI | `src/qubitcoin/aether/on_chain.py` |
| Launch checklist | `LAUNCHTODO.md` |
| Full architecture | `CLAUDE.md` |
| Codebase audit | `docs/audits/codebase-audit-2026-02-22.md` |
