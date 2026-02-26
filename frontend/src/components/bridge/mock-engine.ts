/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Deterministic Mock Data Engine
   mulberry32 PRNG — same seed = identical data every reload
   ───────────────────────────────────────────────────────────────────────── */

import type {
  ChainId,
  ExternalChainId,
  TokenType,
  OperationType,
  BridgeStatus,
  VaultState,
  BridgeTx,
  FeeEstimate,
  GasPrice,
  TickerItem,
} from "./types";

/* ── PRNG ─────────────────────────────────────────────────────────────── */

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ── Helper generators ────────────────────────────────────────────────── */

function round6(n: number): number {
  return Math.round(n * 1000000) / 1000000;
}

function hexStr(rng: () => number, len: number): string {
  const chars = "0123456789abcdef";
  let s = "";
  for (let i = 0; i < len; i++) s += chars[(rng() * 16) | 0];
  return s;
}

function qbcAddress(rng: () => number): string {
  return "QBC1" + hexStr(rng, 38);
}

function evmAddress(rng: () => number): string {
  return "0x" + hexStr(rng, 40);
}

const BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function solAddress(rng: () => number): string {
  let s = "";
  for (let i = 0; i < 44; i++) s += BASE58_ALPHABET[(rng() * 58) | 0];
  return s;
}

function evmTxHash(rng: () => number): string {
  return "0x" + hexStr(rng, 64);
}

function solTxHash(rng: () => number): string {
  let s = "";
  for (let i = 0; i < 88; i++) s += BASE58_ALPHABET[(rng() * 58) | 0];
  return s;
}

function pick<T>(rng: () => number, arr: readonly T[]): T {
  return arr[(rng() * arr.length) | 0];
}

function rangeInt(rng: () => number, min: number, max: number): number {
  return min + ((rng() * (max - min + 1)) | 0);
}

function rangeFloat(rng: () => number, min: number, max: number): number {
  return min + rng() * (max - min);
}

/* ── Constants ────────────────────────────────────────────────────────── */

const EXTERNAL_CHAINS: readonly ExternalChainId[] = ["ethereum", "bnb", "solana"];
const TOKENS: readonly TokenType[] = ["QBC", "QUSD"];
const NOW = Math.floor(Date.now() / 1000);

const CHAIN_CONFIRMATIONS: Record<ChainId, number> = {
  qbc_mainnet: 6,
  ethereum: 12,
  bnb: 15,
  solana: 32,
};

const CHAIN_GAS_COST: Record<ExternalChainId, { min: number; max: number }> = {
  ethereum: { min: 2.5, max: 8.0 },
  bnb: { min: 0.3, max: 1.2 },
  solana: { min: 0.005, max: 0.02 },
};

const CHAIN_EST_TIME: Record<ExternalChainId, { min: number; max: number }> = {
  ethereum: { min: 180, max: 600 },
  bnb: { min: 60, max: 180 },
  solana: { min: 15, max: 60 },
};

/* ── BridgeMockEngine ─────────────────────────────────────────────────── */

export class BridgeMockEngine {
  private rng: () => number;
  private _vaultState: VaultState | null = null;
  private _transactions: BridgeTx[] = [];
  private _gasPrices: GasPrice[] = [];
  private _built = false;

  constructor(private seed: number = 3301) {
    this.rng = mulberry32(seed);
  }

  build(): this {
    if (this._built) return this;
    this._built = true;

    this._vaultState = this._generateVaultState();
    this._transactions = this._generateTransactions(200);
    this._gasPrices = this._generateGasPrices();
    return this;
  }

  /* ── Vault State ──────────────────────────────────────────────────── */

  private _generateVaultState(): VaultState {
    const qbcLocked = 1_247_832;
    const qusdLocked = 284_921;

    // Distribute wQBC across chains — must sum to exactly qbcLocked
    const wqbcEth = round6(qbcLocked * 0.52);
    const wqbcBnb = round6(qbcLocked * 0.31);
    const wqbcSol = round6(qbcLocked - wqbcEth - wqbcBnb);

    // Distribute wQUSD across chains — must sum to exactly qusdLocked
    const wqusdEth = round6(qusdLocked * 0.48);
    const wqusdBnb = round6(qusdLocked * 0.35);
    const wqusdSol = round6(qusdLocked - wqusdEth - wqusdBnb);

    const dailyUsed = rangeInt(this.rng, 0, 50000);
    const dailyResetIn = rangeInt(this.rng, 3600, 86400);

    // 30 days of backing history
    const backingHistory: VaultState["backingHistory"] = [];
    for (let d = 29; d >= 0; d--) {
      const date = new Date((NOW - d * 86400) * 1000).toISOString().slice(0, 10);
      const variation = round6(qbcLocked + rangeFloat(this.rng, -20000, 20000));
      backingHistory.push({
        date,
        qbcLocked: variation,
        wqbcCirculating: variation,
        ratio: 1.0 as 1.0,
      });
    }

    // 30 days of wrap/unwrap history
    const wrapUnwrapHistory: VaultState["wrapUnwrapHistory"] = [];
    let netBalance = 0;
    for (let d = 29; d >= 0; d--) {
      const date = new Date((NOW - d * 86400) * 1000).toISOString().slice(0, 10);
      const wrapped = round6(rangeFloat(this.rng, 40000, 130000));
      const unwrapped = round6(rangeFloat(this.rng, 30000, 100000));
      netBalance = round6(netBalance + wrapped - unwrapped);
      wrapUnwrapHistory.push({
        date,
        wrapped,
        unwrapped,
        netBalance,
      });
    }

    return {
      qbcLocked,
      qusdLocked,
      wqbcByChain: {
        ethereum: wqbcEth,
        bnb: wqbcBnb,
        solana: wqbcSol,
      },
      wqusdByChain: {
        ethereum: wqusdEth,
        bnb: wqusdBnb,
        solana: wqusdSol,
      },
      totalWqbc: qbcLocked,
      totalWqusd: qusdLocked,
      backingRatioQbc: 1.0 as 1.0,
      backingRatioQusd: 1.0 as 1.0,
      vaultAddrQbc: qbcAddress(this.rng),
      vaultAddrQusd: qbcAddress(this.rng),
      dailyWrapVol: 84_291,
      dailyUnwrapVol: 61_847,
      dailyLimit: 100_000,
      dailyUsed,
      dailyResetIn,
      backingHistory,
      wrapUnwrapHistory,
    };
  }

  /* ── Transactions ─────────────────────────────────────────────────── */

  private _generateTransactions(count: number): BridgeTx[] {
    const txs: BridgeTx[] = [];
    const half = count / 2; // 100 wrap, 100 unwrap

    for (let i = 0; i < count; i++) {
      const operation: OperationType = i < half ? "wrap" : "unwrap";
      const token: TokenType = pick(this.rng, TOKENS);
      const externalChain: ExternalChainId = pick(this.rng, EXTERNAL_CHAINS);

      const sourceChain: ChainId = operation === "wrap" ? "qbc_mainnet" : externalChain;
      const destinationChain: ChainId = operation === "wrap" ? externalChain : "qbc_mainnet";

      const amountSent = round6(rangeFloat(this.rng, 10, 50000));

      // Fee calculation
      const protocolFee = round6(amountSent * 0.001);
      const relayerFee = round6(amountSent * 0.0005);
      const gasCost = CHAIN_GAS_COST[externalChain];
      const destinationGasFee = round6(rangeFloat(this.rng, gasCost.min, gasCost.max));
      const totalFee = round6(protocolFee + relayerFee + destinationGasFee);
      const amountReceived = round6(amountSent - totalFee);
      const totalFeePercent = round6((totalFee / amountSent) * 100);

      // Status distribution: ~92% complete, ~5% pending, ~2% failed, ~1% refunded
      const roll = this.rng();
      let status: BridgeStatus;
      if (roll < 0.92) status = "complete";
      else if (roll < 0.97) status = "pending";
      else if (roll < 0.99) status = "failed";
      else status = "refunded";

      // Timestamps
      const initiatedAt = NOW - rangeInt(this.rng, 300, 2592000); // 5min to 30 days ago
      const estTime = CHAIN_EST_TIME[externalChain];
      const bridgeTimeSeconds =
        status === "complete"
          ? rangeInt(this.rng, estTime.min, estTime.max)
          : status === "refunded"
            ? rangeInt(this.rng, estTime.max, estTime.max * 3)
            : null;
      const completedAt =
        status === "complete" || status === "refunded"
          ? initiatedAt + (bridgeTimeSeconds ?? 0)
          : null;

      // Addresses and tx hashes — format depends on chain
      const sourceAddress = this._addressForChain(sourceChain);
      const destinationAddress = this._addressForChain(destinationChain);
      const sourceTxHash = this._txHashForChain(sourceChain);
      const destinationTxHash =
        status === "complete" || status === "refunded"
          ? this._txHashForChain(destinationChain)
          : null;

      // Confirmations
      const sourceRequired = CHAIN_CONFIRMATIONS[sourceChain];
      const destinationRequired = CHAIN_CONFIRMATIONS[destinationChain];
      let sourceConf: number;
      let destConf: number | null;
      if (status === "complete" || status === "refunded") {
        sourceConf = sourceRequired;
        destConf = destinationRequired;
      } else if (status === "pending") {
        sourceConf = rangeInt(this.rng, 0, sourceRequired - 1);
        destConf = sourceConf >= sourceRequired ? rangeInt(this.rng, 0, destinationRequired - 1) : null;
      } else {
        // failed
        sourceConf = rangeInt(this.rng, 0, sourceRequired);
        destConf = null;
      }

      // Event log: 5-8 entries
      const eventCount = rangeInt(this.rng, 5, 8);
      const eventLog: BridgeTx["eventLog"] = [];
      const eventMessages = this._generateEventMessages(operation, token, externalChain, status, eventCount);
      for (let e = 0; e < eventCount; e++) {
        const eventTimestamp =
          initiatedAt + Math.floor(((completedAt ?? initiatedAt + 600) - initiatedAt) * (e / (eventCount - 1)));
        eventLog.push({
          timestamp: eventTimestamp,
          message: eventMessages[e],
        });
      }

      // QBC-specific fields
      const dilithiumSig = hexStr(this.rng, 128);
      const susyAlignmentAtOp = round6(rangeFloat(this.rng, 0.8, 1.0));
      const aetherRelayNodeId = "aether-relay-" + hexStr(this.rng, 8);
      const crossChainMsgHash = "0x" + hexStr(this.rng, 64);

      const id = "btx-" + hexStr(this.rng, 16);

      txs.push({
        id,
        operation,
        token,
        sourceChain,
        destinationChain,
        amountSent,
        amountReceived,
        protocolFee,
        relayerFee,
        destinationGasFee,
        totalFee,
        totalFeePercent,
        sourceAddress,
        destinationAddress,
        sourceTxHash,
        destinationTxHash,
        status,
        initiatedAt,
        completedAt,
        bridgeTimeSeconds,
        dilithiumSig,
        susyAlignmentAtOp,
        aetherRelayNodeId,
        crossChainMsgHash,
        bridgeProtocolVersion: "v2.1.0",
        eventLog,
        confirmations: {
          source: sourceConf,
          sourceRequired,
          destination: destConf,
          destinationRequired,
        },
      });
    }

    // Sort by initiatedAt descending (newest first)
    txs.sort((a, b) => b.initiatedAt - a.initiatedAt);
    return txs;
  }

  private _addressForChain(chain: ChainId): string {
    switch (chain) {
      case "qbc_mainnet":
        return qbcAddress(this.rng);
      case "ethereum":
      case "bnb":
        return evmAddress(this.rng);
      case "solana":
        return solAddress(this.rng);
    }
  }

  private _txHashForChain(chain: ChainId): string {
    switch (chain) {
      case "qbc_mainnet":
      case "ethereum":
      case "bnb":
        return evmTxHash(this.rng);
      case "solana":
        return solTxHash(this.rng);
    }
  }

  private _generateEventMessages(
    operation: OperationType,
    token: TokenType,
    externalChain: ExternalChainId,
    status: BridgeStatus,
    count: number
  ): string[] {
    const wrapped = token === "QBC" ? "wQBC" : "wQUSD";
    const chainName =
      externalChain === "ethereum" ? "Ethereum" : externalChain === "bnb" ? "BNB Chain" : "Solana";

    if (operation === "wrap") {
      const messages = [
        `Bridge request initiated: wrap ${token} to ${wrapped}`,
        `${token} deposit detected on QBC mainnet`,
        `Dilithium signature verified by Aether relay`,
        `SUSY alignment check passed`,
        `${token} locked in vault contract`,
        `Cross-chain message relayed to ${chainName}`,
        `${wrapped} minting transaction submitted on ${chainName}`,
        `${wrapped} minted and delivered to destination address`,
      ];
      if (status === "failed") {
        messages[count - 1] = `Bridge operation failed: ${chainName} transaction reverted`;
      } else if (status === "refunded") {
        messages[count - 1] = `Refund initiated: ${token} unlocked and returned to sender`;
      }
      return messages.slice(0, count);
    } else {
      const messages = [
        `Bridge request initiated: unwrap ${wrapped} to ${token}`,
        `${wrapped} burn detected on ${chainName}`,
        `Cross-chain message received from ${chainName}`,
        `Dilithium signature verified by Aether relay`,
        `SUSY alignment check passed`,
        `Burn proof validated against vault state`,
        `${token} unlock transaction submitted on QBC mainnet`,
        `${token} unlocked and delivered to destination address`,
      ];
      if (status === "failed") {
        messages[count - 1] = `Bridge operation failed: burn proof validation rejected`;
      } else if (status === "refunded") {
        messages[count - 1] = `Refund initiated: ${wrapped} re-minted on ${chainName}`;
      }
      return messages.slice(0, count);
    }
  }

  /* ── Gas Prices ───────────────────────────────────────────────────── */

  private _generateGasPrices(): GasPrice[] {
    const updatedAt = NOW - rangeInt(this.rng, 5, 30);
    return [
      {
        chain: "qbc_mainnet" as ChainId,
        gwei: null,
        nativeAmount: 0.0001,
        usdEquiv: 0.00005,
        updatedAt,
      },
      {
        chain: "ethereum" as ChainId,
        gwei: round6(rangeFloat(this.rng, 15, 25)),
        nativeAmount: round6(rangeFloat(this.rng, 0.003, 0.008)),
        usdEquiv: round6(rangeFloat(this.rng, 8, 22)),
        updatedAt,
      },
      {
        chain: "bnb" as ChainId,
        gwei: round6(rangeFloat(this.rng, 3, 5)),
        nativeAmount: round6(rangeFloat(this.rng, 0.0005, 0.002)),
        usdEquiv: round6(rangeFloat(this.rng, 0.3, 1.2)),
        updatedAt,
      },
      {
        chain: "solana" as ChainId,
        gwei: null,
        nativeAmount: 0.000005,
        usdEquiv: round6(rangeFloat(this.rng, 0.005, 0.02)),
        updatedAt,
      },
    ];
  }

  /* ── Public accessors ─────────────────────────────────────────────── */

  get vaultState(): VaultState {
    return this._vaultState!;
  }

  get transactions(): BridgeTx[] {
    return this._transactions;
  }

  get gasPrices(): GasPrice[] {
    return this._gasPrices;
  }

  getTransaction(id: string): BridgeTx | undefined {
    return this._transactions.find((tx) => tx.id === id);
  }

  estimateFee(
    operation: OperationType,
    token: TokenType,
    chain: ExternalChainId,
    amount: number
  ): FeeEstimate {
    const protocolFeePercent = 0.1; // 0.1%
    const relayerFeePercent = 0.05; // 0.05%
    const protocolFee = round6(amount * 0.001);
    const relayerFee = round6(amount * 0.0005);

    // Gas costs based on chain
    const gasMap: Record<ExternalChainId, { native: number; usd: number; qbcEquiv: number }> = {
      ethereum: { native: 0.005, usd: 14.0, qbcEquiv: 5.2 },
      bnb: { native: 0.001, usd: 0.65, qbcEquiv: 0.24 },
      solana: { native: 0.000005, usd: 0.01, qbcEquiv: 0.004 },
    };

    const gas = gasMap[chain];
    const totalFeeToken = round6(protocolFee + relayerFee + gas.qbcEquiv);
    const totalFeePercent = round6((totalFeeToken / amount) * 100);
    const amountReceived = round6(amount - totalFeeToken);

    const estTime = CHAIN_EST_TIME[chain];

    return {
      operation,
      token,
      chain,
      amount,
      protocolFeePercent,
      relayerFeePercent,
      protocolFee,
      relayerFee,
      destGasNative: gas.native,
      destGasUsd: gas.usd,
      destGasQbcEquiv: gas.qbcEquiv,
      totalFeeToken,
      totalFeePercent,
      amountReceived,
      estTimeSeconds: { min: estTime.min, max: estTime.max },
      updatedAt: NOW,
    };
  }

  getTickerItems(): TickerItem[] {
    const v = this._vaultState!;
    const completedCount = this._transactions.filter((t) => t.status === "complete").length;
    const pendingCount = this._transactions.filter((t) => t.status === "pending").length;
    const totalVolume = this._transactions.reduce((s, t) => s + t.amountSent, 0);

    return [
      { label: "QBC Locked", value: v.qbcLocked.toLocaleString() + " QBC", color: "#00ff88" },
      { label: "QUSD Locked", value: v.qusdLocked.toLocaleString() + " QUSD", color: "#7c3aed" },
      { label: "Backing Ratio", value: "1:1", color: "#22c55e" },
      { label: "24h Wrap Vol", value: v.dailyWrapVol.toLocaleString() + " QBC" },
      { label: "24h Unwrap Vol", value: v.dailyUnwrapVol.toLocaleString() + " QBC" },
      { label: "Completed Txns", value: completedCount.toString(), color: "#00ff88" },
      { label: "Pending Txns", value: pendingCount.toString(), color: "#f59e0b" },
      { label: "Total Volume", value: Math.floor(totalVolume).toLocaleString() + " QBC" },
      { label: "wQBC on ETH", value: v.wqbcByChain.ethereum.toLocaleString() + " wQBC" },
      { label: "wQBC on BNB", value: v.wqbcByChain.bnb.toLocaleString() + " wQBC" },
      { label: "wQBC on SOL", value: v.wqbcByChain.solana.toLocaleString() + " wQBC" },
      { label: "Protocol Fee", value: "0.10%" },
      { label: "Relayer Fee", value: "0.05%" },
      { label: "Bridge Version", value: "v2.1.0", color: "#94a3b8" },
    ];
  }

  getHistoryFiltered(filters: {
    operation?: OperationType;
    token?: TokenType;
    chain?: ExternalChainId;
    status?: BridgeStatus;
    search?: string;
  }): BridgeTx[] {
    let results = this._transactions;

    if (filters.operation) {
      results = results.filter((tx) => tx.operation === filters.operation);
    }

    if (filters.token) {
      results = results.filter((tx) => tx.token === filters.token);
    }

    if (filters.chain) {
      results = results.filter(
        (tx) => tx.sourceChain === filters.chain || tx.destinationChain === filters.chain
      );
    }

    if (filters.status) {
      results = results.filter((tx) => tx.status === filters.status);
    }

    if (filters.search) {
      const q = filters.search.toLowerCase();
      results = results.filter(
        (tx) =>
          tx.id.toLowerCase().includes(q) ||
          tx.sourceAddress.toLowerCase().includes(q) ||
          tx.destinationAddress.toLowerCase().includes(q) ||
          tx.sourceTxHash.toLowerCase().includes(q) ||
          (tx.destinationTxHash && tx.destinationTxHash.toLowerCase().includes(q))
      );
    }

    return results;
  }
}

/* ── Singleton ────────────────────────────────────────────────────────── */

let _instance: BridgeMockEngine | null = null;

export function getBridgeMockEngine(): BridgeMockEngine {
  if (!_instance) {
    _instance = new BridgeMockEngine(3301).build();
  }
  return _instance;
}
