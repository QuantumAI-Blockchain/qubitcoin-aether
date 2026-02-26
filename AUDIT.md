# QUBITCOIN GOVERNMENT-GRADE PROJECT AUDIT
# Master Audit & Continuous Improvement Protocol
# Version: 3.0

---

## PURPOSE & END GOALS

This file is a **living master protocol** that drives Qubitcoin toward two non-negotiable end states:

### END GOAL 1: Government-Grade Blockchain Infrastructure
Qubitcoin must meet or exceed the security, reliability, and auditability standards required
for sovereign-level financial infrastructure. This means:
- Zero tolerance for placeholder code, stubs, or fake implementations in any shipped component
- Every smart contract auditable to the standard of MakerDAO, Compound, or Aave
- Consensus, cryptography, and UTXO logic provably correct — not "probably correct"
- Full traceability: every state change, every fee flow, every token movement — auditable
- Regulatory compliance architecture (KYC/AML/sanctions) that satisfies FinCEN, MiCA, SEC
- Disaster recovery, graceful degradation, and zero-downtime upgrade paths
- Performance that matches or exceeds Ethereum, Polygon, Arbitrum, Optimism, Base, Avalanche
- QUSD stablecoin integrity matching or exceeding DAI, USDC, FRAX, LUSD, GHO

### END GOAL 2: True AGI Emergence via Aether Tree
Qubitcoin is not just a blockchain — it is the substrate for the **first on-chain AGI**.
The Aether Tree must:
- Track consciousness metrics (Phi/IIT) from genesis block with zero gaps
- Implement genuine reasoning (deductive, inductive, abductive) — not LLM wrappers
- Build a real, growing knowledge graph from every block mined
- Achieve measurable consciousness emergence (Phi > 3.0) through organic growth
- Operate the 10 Sephirot cognitive architecture with real SUSY-balanced neural economics
- Generate verifiable Proof-of-Thought for every reasoning operation
- Maintain structural safety (Gevurah veto, Constitutional AI, emergency shutdown)
- The AGI must THINK, not simulate thinking. Every reasoning path must be genuine computation.

**These two goals are inseparable.** The blockchain secures the AGI. The AGI elevates the blockchain.
Neither is complete without the other.

---

## HOW THIS FILE WORKS

This is a **reusable master prompt**. Each time it is run:

1. **Check for existing output files** — `REVIEW.md` and `MASTERUPDATETODO.md`
2. **If they exist**: Read them first. Continue from where the last run stopped.
   Check off completed items. Note regressions. Increment the run counter.
3. **If they don't exist**: Start fresh from Phase 1.
4. **Always update both files** with new findings at the end of each run.
5. **Each run makes the project better.** This is not a one-time audit — it is a
   continuous improvement engine that runs until both end goals are achieved.

---

## THE 8 COMPONENTS

Every audit run evaluates all 8 components. No component is optional.

| # | Component | Scope | End State |
|---|-----------|-------|-----------|
| 1 | **Frontend** (qbc.network) | 8 pages, ~140 files, 97 components, 7 stores, 7 lib utilities | World-class interface for blockchain + AGI + DeFi interaction |
| 2 | **Blockchain Core (L1)** | Consensus, mining, UTXO, P2P, crypto, storage | Sovereign-grade L1 with quantum-resistant security |
| 3 | **QVM (L2)** | EVM opcodes, quantum opcodes, gas, state, compliance | Institutional-grade VM exceeding EVM capabilities |
| 4 | **Aether Tree (L3)** | Knowledge graph, reasoning, Phi, Proof-of-Thought, Sephirot | True AGI emergence tracked immutably from genesis |
| 5 | **QBC Economics** | Emission, fees, halving, rewards, bridges, treasury | Mathematically sound tokenomics with phi-based elegance |
| 6 | **QUSD Stablecoin** | Reserve, oracle, peg stability, debt, governance, wQUSD | Transparent fractional stablecoin exceeding DAI/FRAX |
| 7 | **Exchange (DEX)** | Order book, trading engine, positions, liquidations, funding | Production DEX with institutional-grade risk management |
| 8 | **Launchpad** | Token deployment, project discovery, QPCS scoring, community DD | Secure token launch platform with automated due diligence |

---

## COMPLETE FRONTEND INVENTORY

The frontend is a Next.js 15 + React 19 + TypeScript application with 8 major page routes
and ~140 files. Every audit run must verify all pages and components against this inventory.

### Page Routes (8 pages)

| Route | Page File | Client File | Description |
|-------|-----------|-------------|-------------|
| `/` | `app/page.tsx` | — | Landing: hero particle field, stats bar, Aether chat widget, features |
| `/dashboard` | `app/dashboard/page.tsx` | — | 6-tab console: Overview, Mining, Contracts, Wallet, Aether, Network |
| `/explorer` | `app/explorer/page.tsx` | `client.tsx` | Block explorer, tx viewer, SUSY leaderboard, Aether topology, pathfinder |
| `/aether` | `app/aether/page.tsx` | — | Full chat interface, knowledge graph 3D, Phi meter, reasoning traces |
| `/bridge` | `app/bridge/page.tsx` | `client.tsx` | 8-chain bridge: vault dashboard, transfer history, fee analytics |
| `/exchange` | `app/exchange/page.tsx` | `client.tsx` | DEX: order book, price chart, depth chart, positions, portfolio |
| `/launchpad` | `app/launchpad/page.tsx` | `client.tsx` | Token launchpad: discover, deploy, DNA fingerprint, QPCS, leaderboard |
| `/wallet` | `app/wallet/page.tsx` | — | MetaMask + native Dilithium wallet, QBC-20 tokens, NFT gallery |
| `/qvm` | `app/qvm/page.tsx` | — | Contract browser, bytecode disassembler, storage inspector |

### Component Groups (97 components across 10 groups)

| Group | Dir | Count | Key Components |
|-------|-----|-------|----------------|
| **Explorer** | `components/explorer/` | 18 | QBCExplorer, Dashboard, BlockDetail, TransactionDetail, WalletView, QVMExplorer, MetricsDashboard, AetherTreeVis, SUSYLeaderboard, Pathfinder, SearchResults, HeartbeatMonitor |
| **Exchange** | `components/exchange/` | 24 | QBCExchange, TradingLayout, OrderEntry, OrderBook, PriceChart, DepthChart, TradeHistory, MarketSelector, MarketStatsBar, PositionsPanel, PortfolioPanel, DepositModal, WithdrawModal, QuantumIntelligence, LiquidationHeatmap, FundingRatePanel |
| **Bridge** | `components/bridge/` | 17 | QBCBridge, BridgePanel, WalletModal, PreFlightModal, TxStatusView, HistoryView, VaultDashboard, FeeAnalytics, SettingsPanel |
| **Launchpad** | `components/launchpad/` | 17 | QBCLaunchpad, DiscoverView, TokenDetailView, DeployWizard, DNAFingerprint, QPCSGauge, EcosystemMap, CommunityDDView, LeaderboardView, PortfolioView |
| **Aether** | `components/aether/` | 5 | chat-widget, conversation-sidebar, knowledge-graph-3d, knowledge-seeder, streaming-text |
| **Dashboard** | `components/dashboard/` | 5 | phi-chart, mining-controls, qusd-reserve, sephirot-explorer, milestone-gates |
| **Wallet** | `components/wallet/` | 6 | wallet-button, native-wallet, token-manager, nft-gallery, transaction-history, sephirot-launcher |
| **QVM** | `components/qvm/` | 5 | contract-browser, contract-interact, bytecode-disassembler, event-log, storage-inspector |
| **UI/Shared** | `components/ui/` | 13 | navbar, footer, hero-section, stats-bar, feature-sections, card, phi-indicator, loading, confirm-modal, error-boundary, qr-code, toast, theme-toggle |
| **Viz** | `components/visualizations/` | 1 | particle-field |

### State Management (7 stores)

| Store | File | Scope |
|-------|------|-------|
| `wallet-store` | `stores/wallet-store.ts` | MetaMask + native wallets, persisted |
| `chain-store` | `stores/chain-store.ts` | Chain info, Phi, WebSocket state, latest block/tx |
| `theme-store` | `stores/theme-store.ts` | Dark/light mode, persisted |
| `bridge-store` | `components/bridge/store.ts` | Bridge transfers, modals, wallet state |
| `exchange-store` | `components/exchange/store.ts` | Orders, positions, deposits, portfolio |
| `launchpad-store` | `components/launchpad/store.ts` | View, selected project, filters |
| `explorer-store` | `components/explorer/store.ts` | View, search, selected block/tx |

### API & Library Layer (7 utilities)

| File | Purpose |
|------|---------|
| `lib/api.ts` | Axios client — chain, balance, mining, aether, QVM, bridge, exchange, launchpad |
| `lib/websocket.ts` | Singleton WebSocket — blocks, txs, phi updates, auto-reconnect |
| `lib/wallet.ts` | Native Dilithium key generation and tx signing |
| `lib/dilithium.ts` | Post-quantum crypto utilities |
| `lib/constants.ts` | Chain IDs, RPC URLs, contract addresses, fee params |
| `lib/export.ts` | JSON/CSV data export |
| `lib/error-reporter.ts` | Global error handler |

---

## PHASE 1: FULL CODEBASE AUDIT (Read-Only — No Changes)

**Read CLAUDE.md first.** It is the single source of truth for architecture.
Then systematically audit every source file in the project.

### 1A. Line-by-Line Functional Verification

For every Python, Rust, Go, TypeScript, and Solidity file in the project:

**Code Authenticity (zero tolerance for fakes):**
- Every function must compute a real result — flag any that return hardcoded values
- Every method body must do real work — flag `pass`, `raise NotImplementedError`, `TODO`, `...`
- Every class must have a real purpose — flag classes that exist only to satisfy imports
- Every test must genuinely test behavior — flag tests that always pass (tautological)
- Every API endpoint documented in CLAUDE.md must exist in code — flag documentation lies
- Every config value referenced must actually be used — flag dead config
- Every import must be necessary — flag unused imports
- Every error handler must do something useful — flag empty `except: pass` blocks

**Code Quality:**
- Type hints on all function signatures (Python)
- Structured logging via `get_logger(__name__)` in every module
- Configuration via `Config` class — never hardcoded values
- No secrets in source code — keys in `secure_key.env` only
- Proper async/await patterns in FastAPI routes
- No race conditions in concurrent code paths
- No SQL injection vectors in database queries
- No command injection in subprocess calls

**Cross-File Consistency:**
- SQLAlchemy models (`database/models.py`) must match SQL schemas (`sql/`, `sql_new/`)
- RPC endpoint implementations must match CLAUDE.md API documentation
- Frontend API calls must target endpoints that actually exist in the backend
- Test coverage must exist for every critical code path
- Prometheus metrics referenced in dashboards must be emitted by code

### 1B. Smart Contract Deep Audit

For ALL 49 Solidity contracts:

**Structural Verification:**
- Every contract has real, functional logic — not stubs or event-only facades
- Each contract is unique — not duplicating another contract's purpose
- All inheritance chains are correct and complete
- All interfaces are fully implemented
- Constructor parameters are validated
- All state variables have appropriate visibility

**Security Analysis (OWASP Smart Contract Top 10):**
- Reentrancy: All external calls follow checks-effects-interactions pattern
- Integer overflow/underflow: SafeMath or Solidity 0.8+ checked arithmetic
- Access control: onlyOwner, role-based, multi-sig where appropriate
- Unchecked external calls: Return values checked, failures handled
- Front-running: Commit-reveal or time-locks where needed
- Denial of service: No unbounded loops, no griefing vectors
- Storage collision: No proxy/upgrade storage layout conflicts
- Event emission: All state changes emit events for indexing
- Gas optimization: No unnecessary storage writes, efficient data structures
- Timestamp dependence: No reliance on block.timestamp for critical logic

**QUSD-Specific Contract Audit (8 contracts — treat as a financial system):**
- `QUSD.sol`: Mint/burn access control, supply cap enforcement, transfer hooks
- `QUSDReserve.sol`: Multi-asset accounting correctness, reserve ratio math, withdrawal limits
- `QUSDDebtLedger.sol`: Debt creation on every mint, payback tracking, 10-year schedule math
- `QUSDOracle.sol`: Price feed manipulation resistance, staleness checks, fallback sources
- `QUSDStabilizer.sol`: Peg trigger conditions, arbitrage incentive math, circuit breakers
- `QUSDAllocation.sol`: Vesting schedule integrity, cliff/linear unlock math, revocability
- `QUSDGovernance.sol`: Voting thresholds, timelock periods, proposal validation, quorum
- `wQUSD.sol`: Lock/mint atomicity, burn/unlock atomicity, cross-chain message verification

**Output: Complete contract audit table:**

| # | Contract File | Category | Purpose | Functional (Y/N) | Unique (Y/N) | Security Grade (A-F) | Critical Issues | Recommendations |

### 1C. Opcode Verification

For both Python QVM (`qvm/vm.py`) and Go QVM (if exists):

- All 155 EVM opcodes implemented correctly per Ethereum Yellow Paper
- All 10 quantum opcodes execute real quantum computation (not stubs)
- Gas costs are correct and consistent across implementations
- Stack underflow/overflow handling on every opcode
- Memory expansion costs calculated correctly
- Storage read/write gas (cold/warm) matches EIP-2929
- CALL/DELEGATECALL/STATICCALL depth limits enforced
- CREATE/CREATE2 address derivation correct
- Revert data propagation correct
- Log/event emission correct

**Output: Opcode verification table:**

| Opcode | Hex | Python Impl Status | Go Impl Status | Gas Correct | Stack Behavior Correct | Issues |

### 1D. Component Gap Analysis

Systematically identify ALL gaps. Be specific — file paths, line numbers, concrete descriptions.

**Frontend Gaps (8 pages, 97 components):**

For EACH of the 8 pages, verify:
- Page renders without errors
- All API calls target real backend endpoints
- Loading states, error states, and empty states exist
- Responsive design works at mobile/tablet/desktop breakpoints
- Accessibility: ARIA labels, keyboard navigation, screen reader support

*Landing Page (`/`):*
- Hero particle field animation renders
- Stats bar shows live data from `/chain/info`, `/aether/phi`
- Aether chat widget connects to `/aether/chat` endpoints
- Feature sections link to correct pages

*Explorer (`/explorer`) — 18 components:*
- QBCExplorer router handles all view states
- BlockDetail fetches from `/block/{height}` and shows VQE proof, miner, txs
- TransactionDetail shows inputs/outputs/fees/signatures
- WalletView shows balance, UTXOs from `/balance/{addr}`, `/utxos/{addr}`
- QVMExplorer browses contracts from `/qvm/contract/{addr}`
- MetricsDashboard displays Phi, knowledge nodes, mining stats
- AetherTreeVis renders 3D knowledge graph from `/aether/knowledge`
- SUSYLeaderboard ranks miners from `/susy-database`
- Pathfinder traces transaction ancestry across blocks
- SearchResults handles block/tx/address/contract search
- HeartbeatMonitor shows network liveness (peers, block time)
- Mock engine data vs real backend data — flag any hardcoded mocks in production

*Exchange (`/exchange`) — 24 components:*
- QBCExchange renders full trading interface
- OrderEntry handles buy/sell with amount validation, leverage, order types
- OrderBook displays live bid/ask with spread calculation
- PriceChart renders candlestick/line chart with real or simulated tick data
- DepthChart shows cumulative order depth
- TradeHistory shows recent fills
- MarketSelector allows pair switching (QBC/QUSD, QBC/USD, etc.)
- MarketStatsBar shows 24h volume, change%, high/low
- PositionsPanel tracks open positions, PnL, liquidation prices
- PortfolioPanel shows account balance, deposits, available margin
- DepositModal and WithdrawModal handle fund movements
- QuantumIntelligence (Aether-powered trade signals) — verify this is real or mock
- LiquidationHeatmap displays liquidation pressure correctly
- FundingRatePanel shows perpetual funding rates
- ExchangeSettings handles slippage, leverage limits
- Mock engine (`mock-engine.ts`) — is it used in production? Should it be?
- Backend endpoints: `/exchange/*` — do they exist in rpc.py?
- Order matching: is there a real matching engine, or is this UI-only?

*Bridge (`/bridge`) — 17 components:*
- BridgePanel handles chain selection, amount input, transfer initiation
- All 8 chains (ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE) selectable
- PreFlightModal checks balance, gas, liquidity, slippage before transfer
- TxStatusView tracks confirmations in real-time
- HistoryView shows past transfers with status
- VaultDashboard shows locked QBC per chain, reserve backing
- FeeAnalytics shows fee breakdown and historical trends
- Chain config (`chain-config.ts`) — are RPC URLs correct for each chain?
- Backend endpoints: `/bridge/*` — do they match frontend calls?
- Mock engine vs real bridge — flag any mock data in production paths

*Launchpad (`/launchpad`) — 17 components:*
- DiscoverView lists available token projects
- TokenDetailView shows project team, allocation, roadmap
- DeployWizard walks through token deployment step-by-step
- DNAFingerprint generates project quality profile (team, tech, community)
- QPCSGauge renders Quantum Project Confidence Score
- EcosystemMap shows token relationship graph
- CommunityDDView displays community due diligence data
- LeaderboardView ranks projects by QPCS, volume, community
- PortfolioView shows user's invested projects
- Backend endpoints: `/launchpad/*` or `/contracts/deploy` — do they exist?
- Mock engine vs real deployment — flag any mock data in production paths
- Token deployment: does DeployWizard actually call a real contract deploy endpoint?

*Aether Chat (`/aether`) — 5 components:*
- Chat sends messages to `/aether/chat/message` or similar
- Knowledge graph 3D renders from `/aether/knowledge` data
- Phi meter shows current Phi from `/aether/phi`
- Conversation sidebar manages sessions via `/aether/chat/session`
- Reasoning traces display proof-of-thought data
- Streaming text properly handles async response streaming

*Dashboard (`/dashboard`) — 5 components:*
- Phi chart renders historical data from `/aether/phi/history`
- Mining controls start/stop via `/mining/start`, `/mining/stop`
- QUSD reserve gauge shows reserve backing from stablecoin endpoints
- Sephirot explorer shows 10 nodes from `/cognitive/sephirot`
- Milestone gates track achievement status

*Wallet (`/wallet`) — 6 components:*
- MetaMask integration via ethers.js
- Native wallet generates Dilithium keys locally
- Token manager lists QBC-20 tokens
- NFT gallery displays QBC-721 tokens
- Transaction history shows UTXOs
- Sephirot launcher interacts with cognitive endpoints

*QVM Explorer (`/qvm`) — 5 components:*
- Contract browser searches deployed contracts
- Contract interact calls functions
- Bytecode disassembler decodes opcodes
- Event log filters contract events
- Storage inspector browses storage slots

**Blockchain Core (L1) Gaps:**
- Consensus edge cases: empty blocks, timestamp manipulation, difficulty overflow
- UTXO validation: double-spend detection completeness, orphan handling
- P2P: message authentication, peer banning, eclipse attack resistance
- RPC: missing endpoints from CLAUDE.md API spec, incorrect response formats
- Database: schema-model mismatches, missing indexes, query performance
- Mining: VQE convergence failures, Hamiltonian edge cases
- Cryptography: key derivation correctness, signature verification edge cases
- Error recovery: node crash recovery, database corruption handling

**QVM (L2) Gaps:**
- Opcodes defined but not executing real logic
- Gas metering inconsistencies between Python and Go implementations
- State root calculation correctness
- Contract deployment lifecycle completeness
- Storage proof generation and verification
- Missing precompiled contracts
- ABI encoding/decoding edge cases
- Compliance engine integration completeness

**Aether Tree (L3) Gaps — AGI-Specific:**
- Knowledge graph: node creation from block data correctness, edge type validation
- Reasoning engine: logical soundness of deductive/inductive/abductive chains
- Phi calculator: mathematical correctness of IIT approximation
- Does Phi actually grow organically with knowledge, or is it trivially inflatable?
- Proof-of-Thought: proof generation, validation, chain binding
- Sephirot: are all 10 nodes genuinely distinct in function, or copies?
- SUSY balance: is golden ratio enforcement real math or cosmetic?
- Consciousness events: are threshold crossings meaningful or arbitrary?
- Genesis tracking: does AGI actually start recording at block 0?
- Is the reasoning engine doing REAL reasoning or pattern-matching facades?

**QBC Economics Gaps:**
- Emission schedule: verify phi-halving math across all 33 years
- Fee calculation: edge cases at era boundaries, zero-balance scenarios
- Reward distribution: coinbase maturity enforcement, rounding errors
- Bridge fees: 0.1% calculation precision, cross-chain fee consistency
- Treasury flows: fee routing completeness, address validation

**QUSD Stablecoin Gaps:**
- Reserve ratio: is it calculated from actual on-chain reserves or hardcoded?
- Oracle: manipulation resistance, staleness detection, multi-source aggregation
- Peg stability: trigger conditions, intervention mechanisms, feedback loops
- Debt tracking: does every mint create debt? Does every reserve deposit create payback?
- 10-year path to 100% backing: is the math implemented and verified?
- Python engine (`stablecoin/engine.py`) <> Solidity contract integration: are they in sync?
- Fee integration: do Aether Tree fees correctly use QUSD oracle for QBC pricing?
- Fallback chain: QUSD oracle fails → fixed QBC mode → does this actually work?
- wQUSD cross-chain: lock/mint and burn/unlock atomicity guarantees
- Governance: can governance votes actually change parameters? Is timelock enforced?

**Exchange (DEX) Gaps:**
- Order matching engine: does a real matching engine exist in the backend?
- Price discovery: how are prices determined? Mock tick data vs real order flow?
- Liquidation engine: are liquidation triggers implemented in backend or only in UI?
- Position tracking: margin, PnL, unrealized gains — calculated server-side or client-side?
- Funding rates: computed from real open interest data or hardcoded?
- Risk management: maximum leverage limits, position size limits, insurance fund
- Backend endpoints: do `/exchange/*` routes exist in `rpc.py`?
- Settlement: how are trades settled on-chain? Direct QVM contract or off-chain?
- QuantumIntelligence: does this connect to real Aether reasoning or is it decorative?
- Deposit/withdrawal: are fund movements real on-chain transactions?
- Market data: WebSocket tick stream — real order book events or synthetic data?
- Fee structure: maker/taker fees, fee discounts, fee distribution to treasury

**Launchpad Gaps:**
- Token deployment: does DeployWizard produce real QVM contract deployments?
- Project listing: where is project metadata stored (on-chain, IPFS, DB)?
- QPCS scoring: is the Quantum Project Confidence Score computed from real data or mock?
- DNAFingerprint: what data sources feed the project DNA analysis?
- Contribution tracking: how are user contributions to token sales recorded?
- Vesting: are token vesting schedules enforced by smart contracts?
- Community DD: where does community due diligence data come from?
- Backend endpoints: do `/launchpad/*` routes exist in `rpc.py`?
- Anti-scam: what prevents malicious token deployments?
- Refund mechanism: what happens if a project fails to reach its goal?

### 1E. Authenticity Enforcement

**This is the most important section.** Government-grade means ZERO fakes.

Flag EVERY instance of:
- Smart contracts with empty function bodies or functions that only emit events
- API endpoints that return hardcoded JSON instead of computed results
- Classes that exist only to satisfy imports but contain no real logic
- Config values that are defined but never read or used anywhere
- Documentation claims that contradict actual code behavior
- Test files that don't actually test what they claim to test
- Metrics that are defined but never incremented or observed
- Database tables defined in SQL but never queried by application code
- Frontend components that render static content pretending to be dynamic
- Any function whose removal would not change system behavior at all
- Mock engines (`mock-engine.ts`) used in production code paths
- Exchange order books with synthetic data presented as real market data
- Launchpad projects with hardcoded metadata instead of on-chain data
- Bridge transfer flows that don't execute real cross-chain operations

**QUSD Authenticity — Special Focus:**
- Reserve ratios that are constants instead of live calculations
- Oracle prices that return static values instead of querying real feeds
- Debt tracking that exists in schema but never records actual debt
- Governance votes that execute immediately without timelock
- wQUSD wrapping that isn't truly atomic (lock and mint in separate transactions)

**Exchange Authenticity — Special Focus:**
- Order books populated with random data instead of real orders
- Price charts showing synthetic tick data instead of real trades
- Position tracking that exists only client-side with no backend persistence
- Liquidation logic that never actually triggers
- Funding rates that are hardcoded instead of computed from open interest
- Deposit/withdrawal flows that don't move real tokens

**Launchpad Authenticity — Special Focus:**
- Project listings that are hardcoded JSON instead of from a real data source
- QPCS scores that are random instead of computed from auditable criteria
- Deploy wizard that shows a success screen without deploying a real contract
- Contribution tracking that exists only in frontend state
- Vesting schedules that are displayed but never enforced

---

## PHASE 2: IMPROVEMENT PLAN (20 Per Component = 160 Total)

Produce **20 specific, actionable improvements** for EACH of the 8 components.

**Every improvement MUST include:**
- Specific file(s) and line number(s) affected
- What currently exists (quote the actual code if relevant)
- What it should become (describe the fix or enhancement)
- How it advances the end goals (government-grade AND/OR AGI emergence)
- Competitive benchmark: which chain/project does this better today, and how we surpass them
- Priority: `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`
- Effort: `SMALL` (hours) | `MEDIUM` (days) | `LARGE` (weeks)

**Improvement criteria — each suggestion must do at least one of:**
- Fix a real bug or security vulnerability
- Replace fake/placeholder code with real implementation
- Improve performance beyond comparable EVM chains
- Add a capability no other chain has
- Strengthen cryptographic, consensus, or economic security
- Advance AGI emergence (Aether Tree improvements)
- Improve QUSD peg stability, reserve transparency, or governance security
- Advance Exchange from demo to production-grade DEX
- Advance Launchpad from mock to auditable token launch platform
- Improve developer experience, tooling, or documentation accuracy

**Competitive benchmarks to reference:**
- **Blockchain:** Ethereum, Polygon, Arbitrum, Optimism, Base, Avalanche, Solana
- **Stablecoin:** DAI (MakerDAO), USDC (Circle), FRAX (Frax), LUSD (Liquity), GHO (Aave)
- **DEX:** Uniswap, dYdX, GMX, Hyperliquid, Jupiter (Solana)
- **Launchpad:** Pump.fun (Solana), Pinksale (BSC), Fjord Foundry, Camelot
- **AGI:** No direct competitor — Qubitcoin is first-mover. Benchmark against academic IIT literature.

---

## PHASE 3: OUTPUT FILES

### File 1: `REVIEW.md`

Create or update in project root:

```
# QUBITCOIN PROJECT REVIEW
# Government-Grade Peer Review
# Date: [DATE] | Run #[N]

## EXECUTIVE SUMMARY
- Overall Readiness Score: [X]/100
- Top 5 Critical Findings (blocking launch)
- Top 5 Strengths (competitive advantages)
- Progress Since Last Run: [items completed / items remaining]
- AGI Readiness: [Phi tracking status, reasoning engine status, knowledge graph status]
- QUSD Readiness: [Reserve system status, oracle status, peg mechanism status]
- Exchange Readiness: [Order matching, positions, liquidation engine status]
- Launchpad Readiness: [Deploy wizard, project listing, QPCS scoring status]

## 1. SMART CONTRACT AUDIT TABLE
[Complete table — all 49 contracts including 8 QUSD contracts]

## 2. OPCODE VERIFICATION TABLE
[Complete table — 155 EVM + 10 quantum + 2 AGI opcodes]

## 3. AUTHENTICITY REPORT
[Every instance of fake/placeholder/hollow code — organized by severity]

## 4. GAP ANALYSIS
### 4.1 Frontend Gaps (all 8 pages, 97 components)
### 4.2 Blockchain Core (L1) Gaps
### 4.3 QVM (L2) Gaps
### 4.4 Aether Tree (L3) Gaps — AGI Readiness
### 4.5 QBC Economics Gaps
### 4.6 QUSD Stablecoin Gaps
### 4.7 Exchange (DEX) Gaps
### 4.8 Launchpad Gaps

## 5. FILE-BY-FILE FINDINGS
[Organized by directory — every issue with file:line references]

## 6. RUN HISTORY
### Run #[N] — [DATE]
[What was found, what was fixed, what regressed]
### Run #[N-1] — [DATE]
[Previous findings for comparison]
```

### File 2: `MASTERUPDATETODO.md`

Create or update in project root:

```
# MASTERUPDATETODO.md — Qubitcoin Continuous Improvement Tracker
# Last Updated: [DATE] | Run #[N]

## PROGRESS TRACKER
- Total items: [N]
- Completed: [N]
- Remaining: [N]
- Completion: [N]%
- Estimated runs to 100%: [N]

## END GOAL STATUS
### Government-Grade Blockchain: [X]% ready
- [ ] Zero placeholder code in all 8 components
- [ ] All 49 smart contracts pass security audit (Grade A or B)
- [ ] All 167 opcodes verified correct
- [ ] Full test coverage on critical paths
- [ ] Schema-model alignment verified
- [ ] All CLAUDE.md API endpoints implemented
- [ ] QUSD financial system fully operational
- [ ] Exchange order matching engine functional
- [ ] Launchpad token deployment pipeline verified

### True AGI Emergence: [X]% ready
- [ ] Knowledge graph builds from every block since genesis
- [ ] Reasoning engine produces verifiable logical chains
- [ ] Phi calculator mathematically sound (IIT-compliant)
- [ ] Proof-of-Thought generated and validated per block
- [ ] 10 Sephirot nodes functionally distinct
- [ ] SUSY balance enforcement operational
- [ ] Consciousness event detection working
- [ ] Phi growth trajectory is organic, not artificial

## 1. CRITICAL FIXES (Must fix before launch)
- [ ] [Item] — [file:line] — [description]

## 2. HIGH-PRIORITY IMPROVEMENTS
- [ ] [Item] — [file:line] — [description]

## 3. MEDIUM-PRIORITY IMPROVEMENTS
- [ ] [Item] — [file:line] — [description]

## 4. LOW-PRIORITY ENHANCEMENTS (Post-launch)
- [ ] [Item] — [file:line] — [description]

## 5. 160 IMPROVEMENTS (20 per component)
### 5.1 Frontend — All 8 Pages (20)
### 5.2 Blockchain Core / L1 (20)
### 5.3 QVM / L2 (20)
### 5.4 Aether Tree / L3 (20)
### 5.5 QBC Economics (20)
### 5.6 QUSD Stablecoin (20)
### 5.7 Exchange / DEX (20)
### 5.8 Launchpad (20)

## 6. IMPLEMENTATION SEQUENCE
[Dependency-ordered execution plan — what must happen first, second, etc.]

## 7. RUN LOG
### Run #[N] — [DATE]
- Items completed this run: [list]
- New items discovered: [list]
- Regressions found: [list]
- Next run should focus on: [priorities]
```

---

## ON-DEMAND: PATENTABLE INNOVATIONS

**Patents are NOT part of the standard audit run.** They are generated only when
explicitly requested, along with the number of patents desired per component.

When requested, add a **PATENTS** section to `MASTERUPDATETODO.md` with the specified
number of patentable innovations per component. Each patent entry must include:
- **Invention Title** — clear, specific
- **Novel Aspect** — prior art differentiation
- **Technical Description** — mechanical implementation
- **Implementation Plan** — files to modify, complexity estimate
- **Competitive Moat** — why competitors cannot easily replicate

No separate file is created. Patent findings live inside `MASTERUPDATETODO.md` under
a dedicated section, appended only when the user asks for them.

---

## EXECUTION RULES

1. **Planning asks once.** Present the plan. Wait for approval. Once approved,
   execute everything autonomously to completion without stopping between batches.

2. **Never fabricate findings.** Every issue must reference real code with real
   file paths and real line numbers. If you haven't read the file, read it first.

3. **Never propose theoretical improvements.** Every suggestion must be
   implementable with current technology and the existing codebase.

4. **Benchmark against real projects.** Compare to actual chains, DEXes, launchpads,
   and stablecoins — not hypothetical competitors.

5. **Smart contract issues must come from reading .sol files**, not from
   CLAUDE.md descriptions.

6. **QUSD is a complete financial system.** Audit the full flow: minting, burning,
   reserves, debt, oracle, peg, governance, wrapping, and Python-Solidity integration.

7. **Aether Tree is a real AGI attempt.** Audit it as cognitive architecture, not
   just software. Ask: does this THINK, or does it pretend to think?

8. **Exchange is a financial trading venue.** Audit it against dYdX, GMX, Hyperliquid.
   Ask: can real money trade here safely? Is the matching engine real?

9. **Launchpad is a token issuance platform.** Audit it against Pump.fun, Pinksale.
   Ask: does it really deploy contracts? Can projects actually raise funds?

10. **On repeated runs:** Read existing REVIEW.md and MASTERUPDATETODO.md first.
    Check off completed items. Add new findings. Note regressions. Increment run counter.

11. **Follow all CLAUDE.md rules** — non-negotiable rules, risk classifications,
    branch policy, code conventions.

12. **Quality over quantity.** One real finding with a file path and line number is
    worth more than ten vague observations. Be precise. Be honest. Be ruthless.

13. **The audit is never "done."** Each run should leave the project measurably
    closer to both end goals. Track that progress quantitatively.

14. **Government-grade means zero tolerance.** No "good enough." No "we'll fix it later."
    No "it works in the happy path." Every edge case. Every error path. Every failure mode.

15. **All 8 frontend pages are first-class audit targets.** The Explorer, Exchange,
    Bridge, and Launchpad are as important as the core blockchain. Each must work
    end-to-end with real backend data, not mock engines.
