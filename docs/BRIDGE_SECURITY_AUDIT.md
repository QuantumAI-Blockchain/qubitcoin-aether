# Bridge Security Audit Preparation

> **Security checklist and threat model for Qubitcoin cross-chain bridges.**
> Use this document to prepare for a formal security audit.

---

## 1. Scope

### In-Scope Components

| Component | File | Lines | Risk |
|-----------|------|-------|------|
| Bridge base interface | `bridge/base.py` | ~354 | HIGH |
| Ethereum/EVM bridge | `bridge/ethereum.py` | ~398 | CRITICAL |
| Solana bridge | `bridge/solana.py` | ~200 | CRITICAL |
| Bridge manager | `bridge/manager.py` | ~150 | HIGH |
| Bridge proof store | `bridge/proof_store.py` | ~200 | HIGH |
| wQBC contract | `bridge/wQBC.sol` | ~100 | CRITICAL |
| BridgeVault contract | `bridge/BridgeVault.sol` | ~150 | CRITICAL |

### Out of Scope

- QVM bytecode interpreter (separate audit)
- Consensus/mining engine (separate audit)
- Frontend wallet integration (lower risk)

---

## 2. Architecture Overview

```
Qubitcoin L1                     Target Chain (e.g., Ethereum)
┌──────────┐                     ┌──────────────┐
│  User    │── Lock QBC ──────→ │ BridgeVault  │
│  Wallet  │                     │   (L1)       │
└──────────┘                     └──────┬───────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ Bridge Validator  │
                              │  (off-chain)      │
                              └──────┬───────────┘
                                     │
                                     ▼
                              ┌──────────────────┐
                              │  wQBC.sol (ERC-20)│
                              │  on target chain  │
                              └──────────────────┘

Deposit:  Lock QBC on L1 → Validator observes → Mint wQBC on target
Withdraw: Burn wQBC on target → Validator observes → Unlock QBC on L1
```

---

## 3. Threat Model

### 3.1 Attacker Profiles

| Profile | Capability | Goal |
|---------|-----------|------|
| **External Attacker** | No access to infrastructure | Steal locked QBC or mint unauthorized wQBC |
| **Malicious Validator** | Controls 1+ bridge validators | Approve fraudulent mints/withdrawals |
| **Network Attacker** | Can manipulate RPC endpoints | Feed false data to bridge |
| **Smart Contract Attacker** | Can deploy malicious contracts | Exploit bridge contract vulnerabilities |

### 3.2 Attack Vectors

| # | Attack | Severity | Component |
|---|--------|----------|-----------|
| 1 | **Double-spend on deposit** — Submit same QBC UTXO to multiple chains | CRITICAL | `base.py`, `manager.py` |
| 2 | **Replay attack** — Replay a burn event to unlock QBC multiple times | CRITICAL | `proof_store.py`, `ethereum.py` |
| 3 | **Race condition** — Deposit detected but mint fails; QBC locked forever | HIGH | `ethereum.py` |
| 4 | **Fake RPC endpoint** — Validator reads from compromised RPC | HIGH | `ethereum.py` |
| 5 | **Insufficient confirmations** — Process tx before finality | HIGH | Chain configs |
| 6 | **Oracle manipulation** — Manipulate bridge fee calculation | MEDIUM | `oracle_plugin.py` |
| 7 | **Gas price griefing** — Force bridge to overpay gas on target chain | MEDIUM | `ethereum.py` |
| 8 | **Signature forgery** — Forge validator signatures on mint/burn | CRITICAL | `wQBC.sol` |
| 9 | **Reentrancy on withdraw** — Reenter unlock during withdrawal | HIGH | `BridgeVault.sol` |
| 10 | **Bridge key compromise** — Steal validator signing key | CRITICAL | `secure_key.env` |

---

## 4. Security Checklist

### 4.1 Smart Contracts (Solidity)

- [ ] **Reentrancy protection** — All external calls follow checks-effects-interactions
- [ ] **Access control** — Only authorized validators can mint/burn
- [ ] **Integer overflow** — All arithmetic is safe (Solidity ^0.8 defaults)
- [ ] **Replay protection** — Nonces or unique IDs prevent reprocessing
- [ ] **Pause mechanism** — Emergency pause halts all bridge operations
- [ ] **Upgrade safety** — Proxy pattern uses EIP-1967 storage slots
- [ ] **Event emission** — All state changes emit events for monitoring
- [ ] **Gas limits** — No unbounded loops or arrays
- [ ] **Withdrawal delay** — Time-lock on large withdrawals
- [ ] **Multi-sig requirement** — Critical operations require N-of-M signatures

### 4.2 Off-Chain Bridge Logic (Python)

- [ ] **UTXO verification** — Deposit UTXOs verified on L1 before minting
- [ ] **Confirmation depth** — Sufficient confirmations per chain:
  - Ethereum: 12 blocks (~3 min)
  - Polygon: 128 blocks (~4 min)
  - BSC: 20 blocks (~1 min) — **Review: may be insufficient**
  - Arbitrum: 1 block (L2 finality backed by Ethereum)
  - Optimism: 1 block (L2 finality backed by Ethereum)
  - Avalanche: 1 block (sub-second finality)
  - Base: 1 block (L2 finality backed by Ethereum)
- [ ] **RPC endpoint validation** — Verify RPC responses are authentic
- [ ] **Multiple RPC sources** — Cross-reference data from 2+ independent RPCs
- [ ] **Nonce management** — Bridge transactions use proper nonce sequencing
- [ ] **Error recovery** — Failed mints can be retried without double-mint
- [ ] **Timeout handling** — Stale pending operations are cleaned up
- [ ] **Logging and monitoring** — All bridge operations are logged with context
- [ ] **Rate limiting** — Deposit/withdrawal rate limits per address and globally
- [ ] **Daily transfer limits** — Cap total bridge volume per 24h period

### 4.3 Key Management

- [ ] **Private keys in secure_key.env** — Never in `.env` or code
- [ ] **Key rotation procedure** documented (see `docs/KEY_ROTATION.md`)
- [ ] **HSM integration** for production validator keys
- [ ] **Separate keys per chain** — Don't reuse signing keys across chains
- [ ] **Key backup and recovery** procedure documented
- [ ] **Access logging** — Track who accesses key material

### 4.4 Network Security

- [ ] **TLS for all RPC connections** — No plaintext HTTP to target chains
- [ ] **Certificate pinning** for known RPC endpoints
- [ ] **Connection timeout** — Don't hang on unresponsive RPCs
- [ ] **DNS security** — Validate RPC hostnames against known good values
- [ ] **Firewall rules** — Bridge validator only accessible from known IPs

### 4.5 Monitoring and Alerting

- [ ] **Balance monitoring** — Alert if locked QBC != total minted wQBC
- [ ] **Anomaly detection** — Alert on unusual deposit/withdrawal patterns
- [ ] **Validator health** — Monitor validator uptime and response times
- [ ] **Chain reorg detection** — Detect and handle chain reorganizations
- [ ] **Fee monitoring** — Alert if bridge fees deviate from expected range

---

## 5. Confirmation Depth Analysis

| Chain | Current Config | Recommended | Reasoning |
|-------|---------------|-------------|-----------|
| Ethereum | 12 blocks | 12-20 blocks | Standard. 20 for high-value txs. |
| Polygon | 128 blocks | 128+ blocks | PoS with fast blocks. 128 is reasonable. |
| BSC | 20 blocks | 50+ blocks | Higher centralization risk. Increase depth. |
| Arbitrum | 1 block | 1 block + L1 finality | L2; wait for L1 batch confirmation. |
| Optimism | 1 block | 1 block + L1 finality | L2; wait for L1 batch confirmation. |
| Avalanche | 1 block | 1 block | Sub-second finality. Safe at 1. |
| Base | 1 block | 1 block + L1 finality | L2; wait for L1 batch confirmation. |

---

## 6. Known Issues to Address Before Audit

### 6.1 Missing Features

| Feature | Status | Priority |
|---------|--------|----------|
| Federated validator set (7-of-11 multi-sig) | Not implemented | CRITICAL |
| Validator economic bonding (10K+ QBC stake) | Not implemented | CRITICAL |
| Bridge event monitoring (multi-source) | Not implemented | HIGH |
| Daily transfer limits | Not implemented | HIGH |
| Bridge insurance fund | Not implemented | MEDIUM |
| Deep confirmation requirements | Partially implemented | HIGH |
| Emergency pause mechanism | Not implemented | CRITICAL |

### 6.2 Code Quality Issues

| Issue | File | Severity |
|-------|------|----------|
| Bridge proof verification is a stub | `bridge/proof_store.py` | HIGH |
| No nonce tracking for bridge transactions | `ethereum.py` | HIGH |
| Error handling could swallow critical failures | `manager.py` | MEDIUM |
| No retry logic for failed mints | `ethereum.py` | MEDIUM |

---

## 7. Recommended Audit Firms

For a formal security audit, consider:

- **Trail of Bits** — Smart contract and bridge audits
- **OpenZeppelin** — Solidity-focused audits
- **Quantstamp** — Automated + manual auditing
- **Halborn** — Bridge-specific security expertise
- **Consensys Diligence** — Ethereum ecosystem focus

**Estimated audit scope:** 2-4 weeks, $50K-$150K depending on depth.

---

## 8. Pre-Audit Preparation Tasks

1. [ ] Implement federated validator set with multi-sig
2. [ ] Add daily transfer limits per chain
3. [ ] Implement emergency pause on all bridge contracts
4. [ ] Add balance reconciliation monitoring
5. [ ] Complete bridge proof verification (not stub)
6. [ ] Add retry logic for failed cross-chain transactions
7. [ ] Document all bridge state transitions
8. [ ] Write comprehensive bridge integration tests
9. [ ] Deploy to testnet and run adversarial testing
10. [ ] Prepare audit documentation package (architecture, code, tests)

---

**Responsible Disclosure:** info@qbc.network | **Website:** [qbc.network](https://qbc.network)
