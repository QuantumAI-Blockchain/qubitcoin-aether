"use client";

import { useState, useCallback, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";
import { RPC_URL } from "@/lib/constants";

// ─── Admin API helpers ──────────────────────────────────────────────

async function adminFetch<T>(
  path: string,
  apiKey: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${RPC_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": apiKey,
      ...init?.headers,
    },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function adminGet<T>(path: string, apiKey: string): Promise<T> {
  return adminFetch<T>(path, apiKey);
}

function adminPut<T>(path: string, apiKey: string, body: unknown): Promise<T> {
  return adminFetch<T>(path, apiKey, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ─── Interfaces ─────────────────────────────────────────────────────

interface AetherFeeConfig {
  chat_fee_qbc: number;
  chat_fee_usd_target: number;
  pricing_mode: string;
  min_qbc: number;
  max_qbc: number;
  update_interval: number;
  treasury_address: string;
  query_fee_multiplier: number;
  free_tier_messages: number;
}

interface ContractFeeConfig {
  deploy_base_fee_qbc: number;
  deploy_per_kb_fee_qbc: number;
  deploy_fee_usd_target: number;
  pricing_mode: string;
  treasury_address: string;
  execute_base_fee_qbc: number;
  template_discount: number;
}

interface TreasuryInfo {
  aether_treasury: string;
  contract_treasury: string;
  aether_balance?: string;
  contract_balance?: string;
}

interface EconomicsOverview {
  aether_fees: AetherFeeConfig;
  contract_fees: ContractFeeConfig;
  treasury: TreasuryInfo;
}

interface ChainInfo {
  height: number;
  total_supply: number;
  max_supply: number;
  current_era: number;
  current_reward: number;
  difficulty: number;
  percent_emitted: string;
}

interface EmissionSchedule {
  schedule: Array<{
    year: number;
    emission: number;
    total_supply: number;
    percent_emitted: number;
    era: number;
  }>;
  max_supply: number;
  phi: number;
}

// ─── Auth Gate ──────────────────────────────────────────────────────

function AuthGate({
  apiKey,
  setApiKey,
}: {
  apiKey: string;
  setApiKey: (k: string) => void;
}) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      setApiKey(input.trim());
    }
  };

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card glow="violet" className="w-full max-w-md">
        <h2 className="mb-2 text-center font-[family-name:var(--font-display)] text-xl font-bold">
          Admin Access
        </h2>
        <p className="mb-6 text-center text-sm text-text-secondary">
          Enter the admin API key to access the configuration panel.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Admin Key
            </label>
            <input
              type="password"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter X-Admin-Key..."
              autoFocus
              className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-quantum-violet px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-quantum-violet/80"
          >
            Authenticate
          </button>
        </form>
      </Card>
    </div>
  );
}

// ─── Admin Page ─────────────────────────────────────────────────────

const TABS = ["Fees", "Treasury", "Economics"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPage() {
  const [apiKey, setApiKey] = useState("");
  const [tab, setTab] = useState<Tab>("Fees");

  if (!apiKey) {
    return (
      <div className="mx-auto max-w-7xl px-4 pt-20 pb-12">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold glow-cyan">
          Admin
        </h1>
        <p className="mt-1 font-[family-name:var(--font-display)] text-[10px] uppercase tracking-[0.3em] text-text-secondary">
          Node Configuration
        </p>
        <AuthGate apiKey={apiKey} setApiKey={setApiKey} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pt-20 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold glow-cyan">
            Admin
          </h1>
          <p className="mt-1 font-[family-name:var(--font-display)] text-[10px] uppercase tracking-[0.3em] text-text-secondary">
            Node Configuration
          </p>
        </div>
        <button
          onClick={() => setApiKey("")}
          className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-text-secondary transition hover:border-quantum-red hover:text-quantum-red"
        >
          Lock
        </button>
      </div>

      {/* Tabs */}
      <div className="mt-6 flex gap-1 border-b border-border-subtle">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2 font-[family-name:var(--font-display)] text-[11px] uppercase tracking-widest transition-colors ${
              tab === t ? "glow-cyan" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
            {tab === t && (
              <motion.span
                layoutId="admin-tab"
                className="absolute inset-x-0 -bottom-[1px] h-0.5 bg-glow-cyan"
                style={{ boxShadow: "0 0 8px rgba(0,212,255,0.5)" }}
              />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "Fees" && <FeesTab apiKey={apiKey} />}
        {tab === "Treasury" && <TreasuryTab apiKey={apiKey} />}
        {tab === "Economics" && <EconomicsTab apiKey={apiKey} />}
      </div>
    </div>
  );
}

// ─── Reusable field component ───────────────────────────────────────

function Field({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number";
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-text-secondary">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-lg bg-bg-deep px-3 py-2 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50 disabled:opacity-50"
      />
      {hint && <p className="mt-0.5 text-[10px] text-text-secondary">{hint}</p>}
    </div>
  );
}

function StatusBadge({ status }: { status: "success" | "error" | "idle" | "loading" }) {
  if (status === "idle") return null;
  const classes =
    status === "success"
      ? "bg-quantum-green/20 text-quantum-green"
      : status === "error"
        ? "bg-quantum-red/20 text-quantum-red"
        : "bg-quantum-violet/20 text-quantum-violet";
  const text =
    status === "success"
      ? "Saved"
      : status === "error"
        ? "Error"
        : "Saving...";
  return (
    <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${classes}`}>
      {text}
    </span>
  );
}

// ─── Fees Tab ───────────────────────────────────────────────────────

function FeesTab({ apiKey }: { apiKey: string }) {
  const queryClient = useQueryClient();

  const { data: economics, isLoading } = useQuery({
    queryKey: ["adminEconomics", apiKey],
    queryFn: () => adminGet<EconomicsOverview>("/admin/economics", apiKey),
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <PhiSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AetherFeePanel
        initial={economics?.aether_fees}
        apiKey={apiKey}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ["adminEconomics"] })}
      />
      <ContractFeePanel
        initial={economics?.contract_fees}
        apiKey={apiKey}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ["adminEconomics"] })}
      />
    </div>
  );
}

function AetherFeePanel({
  initial,
  apiKey,
  onSaved,
}: {
  initial: AetherFeeConfig | undefined;
  apiKey: string;
  onSaved: () => void;
}) {
  const [chatFee, setChatFee] = useState(String(initial?.chat_fee_qbc ?? "0.01"));
  const [usdTarget, setUsdTarget] = useState(String(initial?.chat_fee_usd_target ?? "0.005"));
  const [pricingMode, setPricingMode] = useState(initial?.pricing_mode ?? "qusd_peg");
  const [minQbc, setMinQbc] = useState(String(initial?.min_qbc ?? "0.001"));
  const [maxQbc, setMaxQbc] = useState(String(initial?.max_qbc ?? "1.0"));
  const [updateInterval, setUpdateInterval] = useState(String(initial?.update_interval ?? "100"));
  const [treasury, setTreasury] = useState(initial?.treasury_address ?? "");
  const [queryMultiplier, setQueryMultiplier] = useState(String(initial?.query_fee_multiplier ?? "2.0"));
  const [freeTier, setFreeTier] = useState(String(initial?.free_tier_messages ?? "5"));

  const mutation = useMutation({
    mutationFn: () =>
      adminPut<{ status: string }>("/admin/aether/fees", apiKey, {
        chat_fee_qbc: parseFloat(chatFee),
        chat_fee_usd_target: parseFloat(usdTarget),
        pricing_mode: pricingMode,
        min_qbc: parseFloat(minQbc),
        max_qbc: parseFloat(maxQbc),
        update_interval: parseInt(updateInterval, 10),
        treasury_address: treasury,
        query_fee_multiplier: parseFloat(queryMultiplier),
        free_tier_messages: parseInt(freeTier, 10),
      }),
    onSuccess: () => onSaved(),
  });

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      mutation.mutate();
    },
    [mutation],
  );

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Aether Chat Fees
        </h3>
        <StatusBadge
          status={
            mutation.isPending
              ? "loading"
              : mutation.isSuccess
                ? "success"
                : mutation.isError
                  ? "error"
                  : "idle"
          }
        />
      </div>
      {mutation.isError && (
        <p className="mb-3 text-xs text-quantum-red">
          {mutation.error instanceof Error ? mutation.error.message : "Failed to save"}
        </p>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field
            label="Chat Fee (QBC)"
            value={chatFee}
            onChange={setChatFee}
            type="number"
            hint="Base fee per message"
          />
          <Field
            label="USD Target"
            value={usdTarget}
            onChange={setUsdTarget}
            type="number"
            hint="Target USD equivalent"
          />
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Pricing Mode
            </label>
            <select
              value={pricingMode}
              onChange={(e) => setPricingMode(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            >
              <option value="qusd_peg">QUSD Peg</option>
              <option value="fixed_qbc">Fixed QBC</option>
              <option value="direct_usd">Direct USD</option>
            </select>
            <p className="mt-0.5 text-[10px] text-text-secondary">
              How fees are calculated
            </p>
          </div>
          <Field
            label="Min QBC"
            value={minQbc}
            onChange={setMinQbc}
            type="number"
            hint="Floor fee"
          />
          <Field
            label="Max QBC"
            value={maxQbc}
            onChange={setMaxQbc}
            type="number"
            hint="Ceiling fee"
          />
          <Field
            label="Update Interval (blocks)"
            value={updateInterval}
            onChange={setUpdateInterval}
            type="number"
            hint="Price refresh cadence"
          />
          <Field
            label="Query Multiplier"
            value={queryMultiplier}
            onChange={setQueryMultiplier}
            type="number"
            hint="Deep queries cost Nx"
          />
          <Field
            label="Free Tier Messages"
            value={freeTier}
            onChange={setFreeTier}
            type="number"
            hint="Free messages per session"
          />
          <Field
            label="Treasury Address"
            value={treasury}
            onChange={setTreasury}
            hint="Fee recipient address"
          />
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-lg bg-quantum-violet px-6 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-50"
          >
            {mutation.isPending ? "Saving..." : "Save Aether Fees"}
          </button>
        </div>
      </form>
    </Card>
  );
}

function ContractFeePanel({
  initial,
  apiKey,
  onSaved,
}: {
  initial: ContractFeeConfig | undefined;
  apiKey: string;
  onSaved: () => void;
}) {
  const [baseFee, setBaseFee] = useState(String(initial?.deploy_base_fee_qbc ?? "1.0"));
  const [perKbFee, setPerKbFee] = useState(String(initial?.deploy_per_kb_fee_qbc ?? "0.1"));
  const [usdTarget, setUsdTarget] = useState(String(initial?.deploy_fee_usd_target ?? "5.0"));
  const [pricingMode, setPricingMode] = useState(initial?.pricing_mode ?? "qusd_peg");
  const [treasury, setTreasury] = useState(initial?.treasury_address ?? "");
  const [execFee, setExecFee] = useState(String(initial?.execute_base_fee_qbc ?? "0.01"));
  const [templateDiscount, setTemplateDiscount] = useState(String(initial?.template_discount ?? "0.5"));

  const mutation = useMutation({
    mutationFn: () =>
      adminPut<{ status: string }>("/admin/contract/fees", apiKey, {
        deploy_base_fee_qbc: parseFloat(baseFee),
        deploy_per_kb_fee_qbc: parseFloat(perKbFee),
        deploy_fee_usd_target: parseFloat(usdTarget),
        pricing_mode: pricingMode,
        treasury_address: treasury,
        execute_base_fee_qbc: parseFloat(execFee),
        template_discount: parseFloat(templateDiscount),
      }),
    onSuccess: () => onSaved(),
  });

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      mutation.mutate();
    },
    [mutation],
  );

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Contract Deployment Fees
        </h3>
        <StatusBadge
          status={
            mutation.isPending
              ? "loading"
              : mutation.isSuccess
                ? "success"
                : mutation.isError
                  ? "error"
                  : "idle"
          }
        />
      </div>
      {mutation.isError && (
        <p className="mb-3 text-xs text-quantum-red">
          {mutation.error instanceof Error ? mutation.error.message : "Failed to save"}
        </p>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field
            label="Base Deploy Fee (QBC)"
            value={baseFee}
            onChange={setBaseFee}
            type="number"
            hint="Fixed deployment cost"
          />
          <Field
            label="Per-KB Fee (QBC)"
            value={perKbFee}
            onChange={setPerKbFee}
            type="number"
            hint="Additional per KB of bytecode"
          />
          <Field
            label="USD Target"
            value={usdTarget}
            onChange={setUsdTarget}
            type="number"
            hint="Target USD equivalent for deploy"
          />
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Pricing Mode
            </label>
            <select
              value={pricingMode}
              onChange={(e) => setPricingMode(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            >
              <option value="qusd_peg">QUSD Peg</option>
              <option value="fixed_qbc">Fixed QBC</option>
              <option value="direct_usd">Direct USD</option>
            </select>
          </div>
          <Field
            label="Execute Base Fee (QBC)"
            value={execFee}
            onChange={setExecFee}
            type="number"
            hint="Per contract call"
          />
          <Field
            label="Template Discount"
            value={templateDiscount}
            onChange={setTemplateDiscount}
            type="number"
            hint="0.5 = 50% off for templates"
          />
          <Field
            label="Treasury Address"
            value={treasury}
            onChange={setTreasury}
            hint="Fee recipient address"
          />
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-lg bg-quantum-violet px-6 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-50"
          >
            {mutation.isPending ? "Saving..." : "Save Contract Fees"}
          </button>
        </div>
      </form>
    </Card>
  );
}

// ─── Treasury Tab ───────────────────────────────────────────────────

function TreasuryTab({ apiKey }: { apiKey: string }) {
  const { data: economics, isLoading } = useQuery({
    queryKey: ["adminEconomics", apiKey],
    queryFn: () => adminGet<EconomicsOverview>("/admin/economics", apiKey),
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <PhiSpinner />
      </div>
    );
  }

  const treasury = economics?.treasury;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card glow="green">
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">
            Aether Fee Treasury
          </h3>
          <p className="break-all font-[family-name:var(--font-code)] text-sm text-quantum-green">
            {treasury?.aether_treasury || "(not configured)"}
          </p>
          {treasury?.aether_balance && (
            <p className="mt-2 font-[family-name:var(--font-code)] text-xl font-bold">
              {treasury.aether_balance} QBC
            </p>
          )}
        </Card>
        <Card glow="violet">
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">
            Contract Fee Treasury
          </h3>
          <p className="break-all font-[family-name:var(--font-code)] text-sm text-quantum-violet">
            {treasury?.contract_treasury || "(not configured)"}
          </p>
          {treasury?.contract_balance && (
            <p className="mt-2 font-[family-name:var(--font-code)] text-xl font-bold">
              {treasury.contract_balance} QBC
            </p>
          )}
        </Card>
      </div>

      {/* Fee summary cards */}
      <Card>
        <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
          Fee Configuration Summary
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs text-text-secondary">Aether Chat Fee</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold text-quantum-green">
              {economics?.aether_fees?.chat_fee_qbc ?? "---"} QBC
            </p>
            <p className="text-[10px] text-text-secondary">
              ~${economics?.aether_fees?.chat_fee_usd_target ?? "---"} USD target
            </p>
          </div>
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs text-text-secondary">Aether Pricing Mode</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold">
              {economics?.aether_fees?.pricing_mode ?? "---"}
            </p>
          </div>
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs text-text-secondary">Contract Deploy Fee</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold text-quantum-violet">
              {economics?.contract_fees?.deploy_base_fee_qbc ?? "---"} QBC
            </p>
            <p className="text-[10px] text-text-secondary">
              + {economics?.contract_fees?.deploy_per_kb_fee_qbc ?? "---"} QBC/KB
            </p>
          </div>
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs text-text-secondary">Template Discount</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold">
              {economics?.contract_fees?.template_discount != null
                ? `${(economics.contract_fees.template_discount * 100).toFixed(0)}%`
                : "---"}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ─── Economics Tab ───────────────────────────────────────────────────

function EconomicsTab({ apiKey }: { apiKey: string }) {
  const { data: chain, isLoading: chainLoading } = useQuery({
    queryKey: ["chainInfoAdmin"],
    queryFn: () => adminGet<ChainInfo>("/chain/info", apiKey),
    refetchInterval: 10_000,
    retry: 1,
  });

  const { data: emission, isLoading: emissionLoading } = useQuery({
    queryKey: ["emissionAdmin"],
    queryFn: () => adminGet<EmissionSchedule>("/economics/simulate", apiKey),
    retry: 1,
  });

  if (chainLoading || emissionLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <PhiSpinner />
      </div>
    );
  }

  const totalSupply = chain?.total_supply ?? 0;
  const maxSupply = chain?.max_supply ?? 3_300_000_000;
  const percentEmitted = totalSupply > 0 ? ((totalSupply / maxSupply) * 100).toFixed(4) : "0";
  const inflationRate =
    chain?.current_reward && chain?.total_supply
      ? (
          ((chain.current_reward * (365.25 * 24 * 3600) / 3.3) / chain.total_supply) *
          100
        ).toFixed(4)
      : "---";

  return (
    <div className="space-y-6">
      {/* Chain snapshot */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <p className="text-xs text-text-secondary">Block Height</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {chain?.height?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Total Supply</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold text-quantum-green">
            {totalSupply > 0 ? formatSupply(totalSupply) : "---"}
          </p>
          <p className="text-[10px] text-text-secondary">
            {percentEmitted}% of {formatSupply(maxSupply)}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Current Block Reward</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {chain?.current_reward?.toFixed(4) ?? "---"} QBC
          </p>
          <p className="text-[10px] text-text-secondary">
            Era {chain?.current_era ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Difficulty</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {chain?.difficulty?.toFixed(6) ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Annualized Inflation</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold text-golden">
            {inflationRate}%
          </p>
          <p className="text-[10px] text-text-secondary">
            Based on current reward / total supply
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Phi Halving</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {emission?.phi?.toFixed(6) ?? "1.618034"}
          </p>
          <p className="text-[10px] text-text-secondary">
            Golden ratio divisor per era
          </p>
        </Card>
      </div>

      {/* Emission schedule */}
      {emission?.schedule && emission.schedule.length > 0 && (
        <Card>
          <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
            Emission Schedule
          </h3>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-bg-panel">
                <tr className="border-b border-border-subtle text-left text-xs text-text-secondary">
                  <th className="pb-2 pr-4">Year</th>
                  <th className="pb-2 pr-4">Era</th>
                  <th className="pb-2 pr-4 text-right">Emission (QBC)</th>
                  <th className="pb-2 pr-4 text-right">Total Supply</th>
                  <th className="pb-2 text-right">% Emitted</th>
                </tr>
              </thead>
              <tbody className="font-[family-name:var(--font-code)]">
                {emission.schedule.map((row) => (
                  <tr
                    key={row.year}
                    className="border-b border-border-subtle/30"
                  >
                    <td className="py-2 pr-4 text-xs">{row.year}</td>
                    <td className="py-2 pr-4 text-xs text-quantum-violet">{row.era}</td>
                    <td className="py-2 pr-4 text-right text-xs">
                      {formatSupply(row.emission)}
                    </td>
                    <td className="py-2 pr-4 text-right text-xs text-quantum-green">
                      {formatSupply(row.total_supply)}
                    </td>
                    <td className="py-2 text-right text-xs text-text-secondary">
                      {row.percent_emitted.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ─── Helpers ────────────────────────────────────────────────────────

function formatSupply(supply: number): string {
  if (supply >= 1e9) return `${(supply / 1e9).toFixed(2)}B QBC`;
  if (supply >= 1e6) return `${(supply / 1e6).toFixed(2)}M QBC`;
  if (supply >= 1e3) return `${(supply / 1e3).toFixed(2)}K QBC`;
  return `${supply.toFixed(2)} QBC`;
}
