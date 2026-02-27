# QUSD Solidity Contracts -- Static Analysis Report

**Date:** 2026-02-27
**Auditor:** Automated static analysis (Claude Code)
**Scope:** All 9 files in `src/qubitcoin/contracts/solidity/qusd/`
**Solidity Version:** ^0.8.24 (overflow/underflow protection built-in)

---

## Summary

| Contract | File | LOC | Grade | Findings |
|----------|------|-----|-------|----------|
| QUSD | QUSD.sol | 204 | **B** | 2 minor |
| QUSDReserve | QUSDReserve.sol | 250 | **B** | 2 minor |
| QUSDDebtLedger | QUSDDebtLedger.sol | 216 | **A** | 0 |
| QUSDOracle | QUSDOracle.sol | 193 | **B** | 1 minor |
| QUSDStabilizer | QUSDStabilizer.sol | 222 | **B** | 2 minor |
| QUSDAllocation | QUSDAllocation.sol | 207 | **A** | 0 |
| QUSDGovernance | QUSDGovernance.sol | 283 | **B** | 2 minor |
| wQUSD | wQUSD.sol | 214 | **A** | 0 |
| MultiSigAdmin | MultiSigAdmin.sol | 338 | **A** | 0 |

**Overall Grade: B+** (no critical or high-severity issues)

---

## Grading Criteria

- **A** -- No issues found. Sound access control, no reentrancy, no unchecked calls.
- **B** -- Minor issues that do not affect correctness under normal operation but should be addressed before mainnet.
- **C** -- Moderate issues that could cause unexpected behavior or partial loss of funds under adversarial conditions.

---

## Methodology

Each contract was checked for:

1. **Reentrancy** -- State changes after external calls, missing reentrancy guards
2. **Overflow/Underflow** -- Handled by Solidity 0.8+ checked arithmetic (not an issue)
3. **Access Control** -- onlyOwner, onlyGovernance, onlyMinter modifiers
4. **Unchecked External Calls** -- Return values of external .call() not checked
5. **Front-Running** -- Time-dependent logic exploitable by miners/validators
6. **Timestamp Dependence** -- Use of block.timestamp for critical decisions
7. **Gas Limits** -- Unbounded loops, storage-heavy operations
8. **Missing Input Validation** -- Zero-address checks, range validation

---

## Per-Contract Findings

### 1. QUSD.sol -- Grade B

**Overview:** QBC-20 stablecoin with 0.05% transfer fee, mint/burn via authorized minters, pause/unpause.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| Q-1 | Minor | Access Control | `burn()` is public and has no minter restriction. Any holder can burn their own tokens. This is by design (deflationary), but should be documented explicitly because burn does NOT record debt reduction in the DebtLedger. Burned tokens still show as outstanding debt. |
| Q-2 | Minor | Input Validation | `setFeeBps()` allows setting fee to 0, which disables the fee mechanism entirely. Consider a minimum (e.g., 1 bps) or explicit documentation that 0 is intentional. |

**Positive notes:**
- Solidity 0.8.24 eliminates overflow/underflow.
- `_transferWithFee()` correctly deducts from sender before crediting, preventing reentrancy.
- `onlyMinter` restricts minting to owner and stabilizer.
- Pause mechanism present and functional.
- `feeBps` has a 1000 bps (10%) safety cap.

---

### 2. QUSDReserve.sol -- Grade B

**Overview:** Multi-asset reserve pool. Deposits reduce QUSD debt via DebtLedger cross-call.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| R-1 | Minor | Trust Assumption | `deposit()` accepts a caller-provided `usdValue` parameter. In production, this should be validated against the asset oracle price to prevent inflated reserve claims. Currently the caller can report any USD value for a deposit. |
| R-2 | Minor | Gas Limits | `computeTotalReserveValueUSD()` iterates all registered assets. If the asset list grows large (unlikely but possible), this could exceed block gas limits. Consider pagination or a maximum asset count. |

**Positive notes:**
- Reentrancy guard (`nonReentrant`) on `withdraw()`.
- Governance-only withdrawal with `onlyGovernance` modifier.
- Per-asset oracle integration with try-catch to isolate oracle failures.
- Pause mechanism present.
- `deactivateAsset()` available for removing compromised assets.

---

### 3. QUSDDebtLedger.sol -- Grade A

**Overview:** Immutable on-chain debt tracking with milestone events.

**No issues found.**

**Positive notes:**
- Clean separation of concerns: only QUSD can record debt, only Reserve can record payback.
- Milestone tracking with events at 5%, 15%, 30%, 50%, 100% backing.
- Snapshot functionality for historical auditing.
- Per-account debt tracking with partial payback support.
- `_backingBps()` handles division-by-zero (totalMinted == 0).
- Overflow protection via uint16 max capping in `_backingBps()`.

---

### 4. QUSDOracle.sol -- Grade B

**Overview:** Multi-source price feed using median aggregation.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| O-1 | Minor | Front-Running | `submitPrice()` immediately triggers `_aggregate()`. A front-running validator could observe a pending price submission and insert their own price before the honest feeder's transaction, skewing the median. This is mitigated by requiring `minFeeders >= 2`, but the window exists. Consider batching price submissions or using commit-reveal. |

**Positive notes:**
- Median aggregation (not average) resists outlier manipulation.
- Per-feeder staleness detection with event emission.
- Configurable `maxAge` for staleness threshold.
- `getPriceUnsafe()` available for fallback scenarios.
- `minFeeders` requirement prevents single-feeder manipulation.
- Insertion sort is appropriate for the small array (typically 2-5 feeders).

---

### 5. QUSDStabilizer.sol -- Grade B

**Overview:** Peg maintenance via buy/sell operations within configurable bands.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| S-1 | Minor | Trust Assumption | `buyQUSD()` and `sellQUSD()` accept `currentPrice` as a parameter instead of reading it from the oracle contract directly. This trusts the caller (owner) to provide an accurate price. A compromised owner key could manipulate stability operations. Consider reading from `oracleAddress` directly. |
| S-2 | Minor | Reentrancy | `buyQUSD()` calls `IQUSD(qusdToken).mint()` after modifying state. While QUSD.mint() is a trusted internal contract, the pattern should use checks-effects-interactions or a reentrancy guard for defense in depth. Same applies to `sellQUSD()` calling `burn()`. |

**Positive notes:**
- Configurable peg bands with minimum 0.01 spread enforced.
- `maxTradeSize` prevents oversized interventions.
- `triggerRebalance()` is callable by anyone (keeper pattern), enabling automated peg defense.
- Governance-only fund management.
- Pause mechanism present.

---

### 6. QUSDAllocation.sol -- Grade A

**Overview:** Vesting and distribution for initial 3.3B QUSD allocation.

**No issues found.**

**Positive notes:**
- Four-tier allocation with enforced share limits (50%/30%/15%/5%).
- Cliff and linear vesting correctly implemented.
- `_vestedAmount()` handles immediate release, cliff, and partial vesting.
- Per-beneficiary tracking prevents over-allocation.
- Cannot reinitialize (both `baseInitialized` and `initialized` flags).
- Clean dual-step initialization (initializeBase + initialize) for flexibility.

---

### 7. QUSDGovernance.sol -- Grade B

**Overview:** Proposal/vote/execute governance with 48-hour timelock and emergency multi-sig bypass.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| G-1 | Minor | Unchecked Call | In `execute()`, the return data from `prop.target.call(prop.callData)` is checked for success, but the error message encoding via `abi.encodePacked` with raw bytes may produce garbled revert messages. Consider using a custom error or truncating the return data. |
| G-2 | Minor | Access Control | `emergencySign()` does not check if the proposal is Active or Queued before allowing multi-sig execution. A proposal in any state (except Executed/Canceled) can be emergency-executed. This is likely by design for emergencies, but should be documented. |

**Positive notes:**
- 48-hour timelock prevents flash governance attacks.
- 7-day voting period with quorum requirement (4%).
- Delegation system prevents delegation chains (no transitive delegation).
- `hasVoted` tracking prevents double voting.
- `getVotingPower()` includes delegated votes.
- Proposal cancellation by proposer or owner.
- Vote weight verified against QBC token balance (`qbcToken.balanceOf`).

---

### 8. wQUSD.sol -- Grade A

**Overview:** Wrapped QUSD for cross-chain bridging with proof verification.

**No issues found.**

**Positive notes:**
- Reentrancy guard on `wrap()` and `unwrap()`.
- `processedProofs` mapping prevents replay attacks.
- Optional `proofVerifier` contract for external verification (upgradeable).
- `bridgeMint()` marks proof as processed BEFORE minting (prevents reentrancy).
- Pause mechanism on all transfer operations.
- Clean separation: `wrap/unwrap` for on-chain, `bridgeMint/bridgeBurn` for cross-chain.

---

### 9. MultiSigAdmin.sol -- Grade A

**Overview:** M-of-N multi-signature admin for QUSD critical functions.

**No issues found.**

**Positive notes:**
- Configurable threshold (2-10 signers).
- Action expiry (max 30 days) prevents stale approvals.
- Proposer auto-approval (counts as first signature).
- Signer management (add/remove) requires prior multi-sig approval.
- `_requireExecuted()` pattern ensures signer changes go through the full approval flow.
- Duplicate signer prevention in initialization.
- Threshold cannot exceed signer count.
- Minimum 2 signers enforced.

---

## Cross-Contract Integration Analysis

### Debt Lifecycle

The QUSD debt lifecycle spans three contracts:

1. **QUSD.mint()** -> calls **DebtLedger.recordDebt()** and **DebtLedger.recordAccountDebt()**
2. **QUSDReserve.deposit()** -> calls **DebtLedger.recordPayback()**
3. **DebtLedger** emits milestone events at 5/15/30/50/100% backing

**Finding:** `QUSD.burn()` does NOT call `DebtLedger.recordPayback()`. Burns reduce `totalSupply` but do not reduce outstanding debt. This means burned QUSD still appears as unreserved debt in the ledger. This is a design decision (burns are deflationary, not backing), but should be explicitly documented.

### Oracle Chain

`QUSDOracle` -> `QUSDStabilizer` (via manual price passing) -> `QUSDReserve` (via `revalue()`)

The price chain has a trust gap: the Stabilizer accepts manual price input instead of reading from the Oracle contract. This means the owner must be trusted to pass correct prices. A tighter integration would have the Stabilizer call `oracle.getPrice()` directly.

### Upgrade Path

All contracts use `Initializable` (proxy pattern compatible). The `MultiSigAdmin` provides multi-sig governance for admin functions. The upgrade path is:
1. Deploy new implementation
2. Multi-sig proposes upgrade
3. M-of-N approve
4. Execute points proxy to new implementation

---

## Recommendations

| Priority | Recommendation |
|----------|---------------|
| Medium | Add oracle-validated `usdValue` in QUSDReserve.deposit() instead of trusting caller |
| Medium | Have QUSDStabilizer read price directly from QUSDOracle instead of accepting as parameter |
| Low | Document that QUSD.burn() does not reduce DebtLedger debt |
| Low | Consider commit-reveal for QUSDOracle price submissions |
| Low | Add reentrancy guard to QUSDStabilizer.buyQUSD() and sellQUSD() |
| Low | Cap asset list length in QUSDReserve to prevent gas limit issues |

---

## Conclusion

The QUSD contract suite is well-structured with appropriate access controls, pause mechanisms, and defense patterns. All contracts use Solidity 0.8.24, eliminating overflow/underflow concerns. The primary areas for improvement are trust assumptions around price data flow (oracle -> stabilizer -> reserve) and the undocumented debt-burn gap. No critical vulnerabilities were found. The contracts are ready for testnet deployment; the medium-priority recommendations should be addressed before mainnet.
