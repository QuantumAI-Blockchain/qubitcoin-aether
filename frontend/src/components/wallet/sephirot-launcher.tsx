"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type SephirotNode, type SephirotStake } from "@/lib/api";
import { signTransaction } from "@/lib/dilithium";
import { useWalletStore } from "@/stores/wallet-store";
import { Card } from "@/components/ui/card";

const NODE_COLORS: Record<number, string> = {
  0: "from-purple-500/20 to-purple-900/10 border-purple-500/30",
  1: "from-blue-500/20 to-blue-900/10 border-blue-500/30",
  2: "from-cyan-500/20 to-cyan-900/10 border-cyan-500/30",
  3: "from-green-500/20 to-green-900/10 border-green-500/30",
  4: "from-red-500/20 to-red-900/10 border-red-500/30",
  5: "from-yellow-500/20 to-yellow-900/10 border-yellow-500/30",
  6: "from-emerald-500/20 to-emerald-900/10 border-emerald-500/30",
  7: "from-orange-500/20 to-orange-900/10 border-orange-500/30",
  8: "from-indigo-500/20 to-indigo-900/10 border-indigo-500/30",
  9: "from-teal-500/20 to-teal-900/10 border-teal-500/30",
};

export function SephirotLauncher() {
  const { nativeWallets, activeNativeWallet } = useWalletStore();
  const activeWallet = nativeWallets.find(
    (w) => w.address === activeNativeWallet,
  );

  const { data: nodesData } = useQuery({
    queryKey: ["sephirot-nodes"],
    queryFn: () => api.getSephirotNodes(),
    refetchInterval: 30_000,
  });

  const { data: stakesData, refetch: refetchStakes } = useQuery({
    queryKey: ["sephirot-stakes", activeWallet?.address],
    queryFn: () => api.getMyStakes(activeWallet!.address),
    enabled: !!activeWallet,
    refetchInterval: 15_000,
  });

  const { data: rewardsData, refetch: refetchRewards } = useQuery({
    queryKey: ["sephirot-rewards", activeWallet?.address],
    queryFn: () => api.getMyRewards(activeWallet!.address),
    enabled: !!activeWallet,
    refetchInterval: 15_000,
  });

  const nodes = nodesData?.nodes ?? [];
  const stakes = stakesData?.stakes ?? [];
  const pendingRewards = parseFloat(rewardsData?.pending_claim ?? "0");
  const totalEarned = parseFloat(rewardsData?.total_earned ?? "0");
  const totalStaked = stakes
    .filter((s) => s.status === "active")
    .reduce((sum, s) => sum + parseFloat(s.amount), 0);

  if (!activeWallet) {
    return (
      <Card>
        <p className="text-center text-text-secondary">
          Select a Native Wallet from the Native Wallet tab to stake on Sephirot
          nodes.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card glow="violet">
        <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold">
          Sephirot Nodes — Aether Tree Neural Network
        </h3>
        <p className="mt-1 text-xs text-text-secondary">
          Stake QBC on the Tree of Life cognitive nodes. Rewards come from
          Proof-of-Thought reasoning bounties — more Aether usage means more
          rewards.
        </p>
      </Card>

      {/* Node Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {nodes.map((node) => (
          <NodeCard key={node.id} node={node} wallet={activeWallet} onStaked={() => { refetchStakes(); refetchRewards(); }} />
        ))}
      </div>

      {/* My Stakes */}
      {stakes.length > 0 && (
        <Card>
          <h4 className="mb-3 font-[family-name:var(--font-heading)] font-semibold">
            My Active Stakes
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-light text-xs text-text-secondary">
                  <th className="pb-2">Node</th>
                  <th className="pb-2">Amount</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Earned</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {stakes.map((s) => (
                  <StakeRow
                    key={s.stake_id}
                    stake={s}
                    wallet={activeWallet}
                    onAction={() => { refetchStakes(); refetchRewards(); }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Totals + Claim */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex gap-8">
            <div>
              <p className="text-xs text-text-secondary">Total Staked</p>
              <p className="font-[family-name:var(--font-mono)] text-lg font-bold text-quantum-violet">
                {totalStaked.toLocaleString(undefined, {
                  maximumFractionDigits: 4,
                })}{" "}
                QBC
              </p>
            </div>
            <div>
              <p className="text-xs text-text-secondary">Total Earned</p>
              <p className="font-[family-name:var(--font-mono)] text-lg font-bold text-quantum-green">
                {totalEarned.toLocaleString(undefined, {
                  maximumFractionDigits: 4,
                })}{" "}
                QBC
              </p>
            </div>
          </div>
          <ClaimButton
            wallet={activeWallet}
            pending={pendingRewards}
            onClaimed={() => { refetchStakes(); refetchRewards(); }}
          />
        </div>
      </Card>

      {/* Reward Explainer */}
      <div className="rounded-lg border border-surface-light bg-surface/50 p-4 text-xs text-text-secondary">
        <p className="font-semibold text-text-primary">
          How Sephirot Rewards Work
        </p>
        <p className="mt-1">
          Rewards come from{" "}
          <span className="text-quantum-green">
            Proof-of-Thought task bounties
          </span>
          , not block mining. Users submit reasoning tasks with QBC bounties to
          the Aether Tree. Sephirot nodes solve tasks, validators verify (67%+
          consensus), and 10% of bounties are split among validators. The more
          the Aether Tree is used, the more rewards flow to stakers. ~5% APY
          estimated.
        </p>
      </div>
    </div>
  );
}

/* ---- Node Card ---- */

function NodeCard({
  node,
  wallet,
  onStaked,
}: {
  node: SephirotNode;
  wallet: { address: string; publicKeyHex: string };
  onStaked: () => void;
}) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div
        className={`rounded-xl border bg-gradient-to-b p-3 transition hover:scale-[1.02] ${NODE_COLORS[node.id] ?? "border-surface-light"}`}
      >
        <p className="text-xs font-bold text-text-primary">{node.name}</p>
        <p className="text-[10px] text-text-secondary">{node.title}</p>
        <p className="mt-1 text-[10px] leading-tight text-text-secondary">
          {node.function}
        </p>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="font-[family-name:var(--font-mono)] text-xs text-quantum-green">
            ~{node.apy_estimate}% APY
          </span>
          <span className="text-[10px] text-text-secondary">
            {node.current_stakers} stakers
          </span>
        </div>
        <p className="font-[family-name:var(--font-mono)] text-[10px] text-text-secondary">
          {parseFloat(node.total_staked).toLocaleString()} QBC staked
        </p>
        <button
          onClick={() => setShowModal(true)}
          className="mt-2 w-full rounded-lg bg-quantum-green/20 py-1.5 text-xs font-semibold text-quantum-green transition hover:bg-quantum-green/30"
        >
          Stake
        </button>
      </div>

      {showModal && (
        <StakeModal
          node={node}
          wallet={wallet}
          onClose={() => setShowModal(false)}
          onStaked={() => {
            setShowModal(false);
            onStaked();
          }}
        />
      )}
    </>
  );
}

/* ---- Stake Modal ---- */

function StakeModal({
  node,
  wallet,
  onClose,
  onStaked,
}: {
  node: SephirotNode;
  wallet: { address: string; publicKeyHex: string };
  onClose: () => void;
  onStaked: () => void;
}) {
  const [amount, setAmount] = useState(String(node.min_stake));
  const [privateKey, setPrivateKey] = useState("");
  const [staking, setStaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStake = useCallback(async () => {
    if (!amount || !privateKey) return;
    setStaking(true);
    setError(null);
    try {
      const txData = {
        action: "stake",
        address: wallet.address,
        amount,
        node_id: node.id,
      };
      const sigHex = await signTransaction(privateKey, txData);
      await api.stakeSephirot({
        address: wallet.address,
        node_id: node.id,
        amount,
        signature_hex: sigHex,
        public_key_hex: wallet.publicKeyHex,
      });
      onStaked();
    } catch (e) {
      setError(String(e));
    } finally {
      setStaking(false);
    }
  }, [amount, privateKey, wallet, node, onStaked]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-xl border border-surface-light bg-surface p-6">
        <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold">
          Stake on {node.name}
        </h3>
        <p className="mt-1 text-xs text-text-secondary">{node.function}</p>

        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Amount (min {node.min_stake} QBC)
            </label>
            <input
              type="number"
              min={node.min_stake}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Private Key (sign only — not stored)
            </label>
            <input
              type="password"
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
              placeholder="Enter private key..."
              className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="rounded-lg border border-surface-light px-4 py-2 text-sm text-text-secondary transition hover:border-text-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleStake}
              disabled={staking || !privateKey || parseFloat(amount) < node.min_stake}
              className="rounded-lg bg-quantum-green px-6 py-2 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
            >
              {staking ? "Staking..." : "Confirm Stake"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Stake Row ---- */

function StakeRow({
  stake,
  wallet,
  onAction,
}: {
  stake: SephirotStake;
  wallet: { address: string; publicKeyHex: string };
  onAction: () => void;
}) {
  const [privateKey, setPrivateKey] = useState("");
  const [showUnstake, setShowUnstake] = useState(false);
  const [loading, setLoading] = useState(false);

  const pendingReward =
    parseFloat(stake.rewards_earned) - parseFloat(stake.rewards_claimed);

  const handleUnstake = useCallback(async () => {
    if (!privateKey) return;
    setLoading(true);
    try {
      const txData = {
        action: "unstake",
        address: wallet.address,
        stake_id: stake.stake_id,
      };
      const sigHex = await signTransaction(privateKey, txData);
      await api.unstakeSephirot({
        address: wallet.address,
        stake_id: stake.stake_id,
        signature_hex: sigHex,
        public_key_hex: wallet.publicKeyHex,
      });
      setShowUnstake(false);
      setPrivateKey("");
      onAction();
    } catch (e) {
      alert(`Unstake failed: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [privateKey, wallet, stake, onAction]);

  // Unstaking countdown
  let statusLabel = stake.status;
  if (stake.status === "unstaking" && stake.unstake_requested_at) {
    const unlockDate = new Date(stake.unstake_requested_at);
    unlockDate.setDate(unlockDate.getDate() + 7);
    const daysLeft = Math.max(
      0,
      Math.ceil((unlockDate.getTime() - Date.now()) / 86400000),
    );
    statusLabel = `Unstaking (${daysLeft}d left)`;
  }

  return (
    <>
      <tr className="border-b border-surface-light/50">
        <td className="py-2 text-text-primary">{stake.node_name ?? `Node ${stake.node_id}`}</td>
        <td className="py-2 font-[family-name:var(--font-mono)] text-text-primary">
          {parseFloat(stake.amount).toLocaleString()} QBC
        </td>
        <td className="py-2">
          <span
            className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
              stake.status === "active"
                ? "bg-quantum-green/20 text-quantum-green"
                : "bg-amber-500/20 text-amber-400"
            }`}
          >
            {statusLabel}
          </span>
        </td>
        <td className="py-2 font-[family-name:var(--font-mono)] text-quantum-green">
          +{pendingReward.toFixed(4)} QBC
        </td>
        <td className="py-2 text-right">
          {stake.status === "active" && (
            <button
              onClick={() => setShowUnstake(!showUnstake)}
              className="text-xs text-text-secondary underline hover:text-red-400"
            >
              Unstake
            </button>
          )}
        </td>
      </tr>
      {showUnstake && (
        <tr>
          <td colSpan={5} className="py-2">
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={privateKey}
                onChange={(e) => setPrivateKey(e.target.value)}
                placeholder="Private key to sign unstake..."
                className="flex-1 rounded-lg bg-void px-3 py-1.5 font-[family-name:var(--font-mono)] text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-red-500/50"
              />
              <button
                onClick={handleUnstake}
                disabled={loading || !privateKey}
                className="rounded bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-400 transition hover:bg-red-500/30 disabled:opacity-50"
              >
                {loading ? "..." : "Confirm Unstake"}
              </button>
              <button
                onClick={() => {
                  setShowUnstake(false);
                  setPrivateKey("");
                }}
                className="text-xs text-text-secondary"
              >
                Cancel
              </button>
            </div>
            <p className="mt-1 text-[10px] text-amber-400">
              7-day unstaking delay. Funds returned as UTXO after cooldown.
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

/* ---- Claim Button ---- */

function ClaimButton({
  wallet,
  pending,
  onClaimed,
}: {
  wallet: { address: string; publicKeyHex: string };
  pending: number;
  onClaimed: () => void;
}) {
  const [privateKey, setPrivateKey] = useState("");
  const [showClaim, setShowClaim] = useState(false);
  const [claiming, setClaiming] = useState(false);

  const handleClaim = useCallback(async () => {
    if (!privateKey) return;
    setClaiming(true);
    try {
      const txData = { action: "claim_rewards", address: wallet.address };
      const sigHex = await signTransaction(privateKey, txData);
      await api.claimRewards({
        address: wallet.address,
        signature_hex: sigHex,
        public_key_hex: wallet.publicKeyHex,
      });
      setShowClaim(false);
      setPrivateKey("");
      onClaimed();
    } catch (e) {
      alert(`Claim failed: ${e}`);
    } finally {
      setClaiming(false);
    }
  }, [privateKey, wallet, onClaimed]);

  if (pending <= 0) {
    return (
      <button
        disabled
        className="rounded-lg bg-surface-light px-4 py-2 text-sm text-text-secondary opacity-50"
      >
        No Rewards to Claim
      </button>
    );
  }

  return (
    <div>
      {!showClaim ? (
        <button
          onClick={() => setShowClaim(true)}
          className="rounded-lg bg-quantum-green px-4 py-2 text-sm font-semibold text-void transition hover:bg-quantum-green/80"
        >
          Claim{" "}
          {pending.toLocaleString(undefined, { maximumFractionDigits: 4 })} QBC
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <input
            type="password"
            value={privateKey}
            onChange={(e) => setPrivateKey(e.target.value)}
            placeholder="Private key..."
            className="w-48 rounded-lg bg-void px-3 py-1.5 font-[family-name:var(--font-mono)] text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-green/50"
          />
          <button
            onClick={handleClaim}
            disabled={claiming || !privateKey}
            className="rounded-lg bg-quantum-green px-3 py-1.5 text-xs font-semibold text-void disabled:opacity-50"
          >
            {claiming ? "..." : "Confirm"}
          </button>
          <button
            onClick={() => {
              setShowClaim(false);
              setPrivateKey("");
            }}
            className="text-xs text-text-secondary"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
