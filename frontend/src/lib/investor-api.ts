import { get, post } from "./api";

/* ---- Types ---- */

export interface RoundInfo {
  active: boolean;
  token_price_usd: string;
  hard_cap_usd: string;
  total_raised_usd: string;
  investors: number;
  start_time: string;
  end_time: string;
  percent_filled: number;
  contract_address: string;
}

export interface InvestorStatus {
  has_invested: boolean;
  qbc_address: string | null;
  invested_usd: string;
  qbc_allocated: string;
  investment_count: number;
  vesting_claimed_qbc?: string;
  revenue_claimed_qbc?: string;
}

export interface InvestmentRecord {
  id: string;
  eth_address: string;
  qbc_address: string;
  token_symbol: string;
  usd_value: string;
  qbc_allocated: string;
  eth_tx_hash: string;
  eth_block: number;
  created_at: string;
}

export interface InvestmentsPage {
  investments: InvestmentRecord[];
  total: number;
  page: number;
  pages: number;
}

export interface ValidateQBCResult {
  valid: boolean;
  check_phrase: string | null;
  error: string | null;
}

export interface VestingInfo {
  qbc_address: string;
  total_qbc: string;
  total_qusd: string;
  vested_qbc: string;
  vested_qusd: string;
  claimed_qbc: string;
  claimed_qusd: string;
  claimable_qbc: string;
  claimable_qusd: string;
  vested_fraction: number;
  cliff_duration_days: number;
  vesting_duration_days: number;
  tge_timestamp: number;
  tge_set: boolean;
}

export interface RevenueInfo {
  qbc_address: string;
  shares_usd: string;
  share_percentage: number;
  total_claimed: string;
  pending: string;
}

export interface MerkleProof {
  qbc_address: string;
  proof: string[];
  leaf: string;
  qbc_amount: string;
  qusd_amount: string;
  status: string;
  message: string;
}

export interface TreasuryTx {
  hash: string;
  from: string;
  token: string;
  amount: string;
  usd_value: string;
  timestamp: number;
  block: number;
  etherscan_url: string;
}

export interface TokenBalance {
  amount: string;
  usd_value: string;
  decimals: number;
  contract?: string;
}

export interface TreasuryInfo {
  address: string;
  total_raised_usd: string;
  eth_price_usd?: string;
  etherscan_url: string;
  balances: Record<string, TokenBalance>;
  transactions: TreasuryTx[];
}

/* ---- API ---- */

export const investorApi = {
  getRoundInfo: () => get<RoundInfo>("/investor/round/info"),

  getStatus: (ethAddress: string) =>
    get<InvestorStatus>(`/investor/status/${ethAddress}`),

  getInvestments: (page = 1, limit = 20) =>
    get<InvestmentsPage>(`/investor/investments?page=${page}&limit=${limit}`),

  validateQBCAddress: (qbcAddress: string) =>
    post<ValidateQBCResult>("/investor/validate-qbc-address", {
      qbc_address: qbcAddress,
    }),

  getVesting: (qbcAddress: string) =>
    get<VestingInfo>(`/investor/vesting/${qbcAddress}`),

  getRevenue: (qbcAddress: string) =>
    get<RevenueInfo>(`/investor/revenue/${qbcAddress}`),

  getMerkleProof: (qbcAddress: string) =>
    get<MerkleProof>(`/investor/merkle-proof/${qbcAddress}`),

  getTreasury: () => get<TreasuryInfo>("/investor/treasury"),
} as const;
