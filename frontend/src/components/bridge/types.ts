/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Type Definitions (strict, zero any)
   ───────────────────────────────────────────────────────────────────────── */

export type ChainId = "qbc_mainnet" | "ethereum" | "bnb" | "solana";
export type ExternalChainId = "ethereum" | "bnb" | "solana";
export type TokenType = "QBC" | "QUSD";
export type WrappedToken = "wQBC" | "wQUSD";
export type OperationType = "wrap" | "unwrap";
export type BridgeStatus = "complete" | "pending" | "failed" | "refunded";

export type BridgeView =
  | "bridge"
  | "tx"
  | "history"
  | "vault"
  | "fees";

export interface ChainInfo {
  id: ChainId;
  name: string;
  shortName: string;
  chainIdHex: string;
  rpcUrl: string | null;
  wqbcAddr: string | null;
  wqusdAddr: string | null;
  explorerUrl: string;
  explorerTxPath: string;
  nativeSymbol: string;
  available: boolean;
  confirmations: number;
  color: string;
  walletType: "evm" | "solana" | "qbc";
}

export interface VaultState {
  qbcLocked: number;
  qusdLocked: number;
  wqbcByChain: Record<ExternalChainId, number>;
  wqusdByChain: Record<ExternalChainId, number>;
  totalWqbc: number;
  totalWqusd: number;
  backingRatioQbc: 1.0;
  backingRatioQusd: 1.0;
  vaultAddrQbc: string;
  vaultAddrQusd: string;
  dailyWrapVol: number;
  dailyUnwrapVol: number;
  dailyLimit: number;
  dailyUsed: number;
  dailyResetIn: number;
  backingHistory: Array<{ date: string; qbcLocked: number; wqbcCirculating: number; ratio: 1.0 }>;
  wrapUnwrapHistory: Array<{ date: string; wrapped: number; unwrapped: number; netBalance: number }>;
}

export interface BridgeTx {
  id: string;
  operation: OperationType;
  token: TokenType;
  sourceChain: ChainId;
  destinationChain: ChainId;
  amountSent: number;
  amountReceived: number;
  protocolFee: number;
  relayerFee: number;
  destinationGasFee: number;
  totalFee: number;
  totalFeePercent: number;
  sourceAddress: string;
  destinationAddress: string;
  sourceTxHash: string;
  destinationTxHash: string | null;
  status: BridgeStatus;
  initiatedAt: number;
  completedAt: number | null;
  bridgeTimeSeconds: number | null;
  dilithiumSig: string;
  susyAlignmentAtOp: number;
  aetherRelayNodeId: string;
  crossChainMsgHash: string;
  bridgeProtocolVersion: string;
  eventLog: Array<{ timestamp: number; message: string }>;
  confirmations: {
    source: number;
    sourceRequired: number;
    destination: number | null;
    destinationRequired: number;
  };
}

export interface FeeEstimate {
  operation: OperationType;
  token: TokenType;
  chain: ExternalChainId;
  amount: number;
  protocolFeePercent: number;
  relayerFeePercent: number;
  protocolFee: number;
  relayerFee: number;
  destGasNative: number;
  destGasUsd: number;
  destGasQbcEquiv: number;
  totalFeeToken: number;
  totalFeePercent: number;
  amountReceived: number;
  estTimeSeconds: { min: number; max: number };
  updatedAt: number;
}

export interface GasPrice {
  chain: ChainId;
  gwei: number | null;
  nativeAmount: number;
  usdEquiv: number;
  updatedAt: number;
}

export interface WalletState {
  qbc: {
    connected: boolean;
    address: string | null;
    balanceQbc: number;
    balanceQusd: number;
    gasBalance: number;
  };
  evm: {
    connected: boolean;
    address: string | null;
    chainId: string | null;
    provider: string | null;
    balances: Record<ExternalChainId, { native: number; wqbc: number; wqusd: number }>;
  };
  solana: {
    connected: boolean;
    address: string | null;
    balanceSol: number;
    wqbc: number;
    wqusd: number;
  };
}

export interface TickerItem {
  label: string;
  value: string;
  color?: string;
}

export interface PreFlightCheck {
  id: string;
  label: string;
  status: "pending" | "checking" | "pass" | "fail" | "action";
  detail?: string;
  actionLabel?: string;
}

export interface BridgeSettings {
  currencyPrimary: "qbc" | "usd";
  timestampFormat: "relative" | "absolute";
  defaultOperation: OperationType;
  defaultToken: TokenType;
  customReceiveAddress: boolean;
  expertMode: boolean;
  notifications: {
    onComplete: boolean;
    onDelayed: boolean;
    onLowGas: boolean;
  };
}
