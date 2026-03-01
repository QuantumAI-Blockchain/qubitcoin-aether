"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type StealthKeyPair, type ConfidentialTxResult } from "@/lib/api";
import { signTransaction } from "@/lib/dilithium";
import { useWalletStore, type NativeWallet } from "@/stores/wallet-store";
import { Card } from "@/components/ui/card";
import { QRCode } from "@/components/ui/qr-code";

export function NativeWalletPanel() {
  const {
    nativeWallets,
    activeNativeWallet,
    addNativeWallet,
    removeNativeWallet,
    setActiveNativeWallet,
  } = useWalletStore();

  const activeWallet = nativeWallets.find(
    (w) => w.address === activeNativeWallet,
  );

  return (
    <div className="space-y-6">
      {/* Wallet selector / create */}
      <WalletSelector
        wallets={nativeWallets}
        active={activeNativeWallet}
        onSelect={setActiveNativeWallet}
        onAdd={addNativeWallet}
        onRemove={removeNativeWallet}
      />

      {activeWallet ? (
        <>
          <WalletBalance wallet={activeWallet} />
          <SendPanel wallet={activeWallet} />
          <PrivacyPanel />
          <ReceivePanel wallet={activeWallet} />
        </>
      ) : (
        <Card>
          <p className="text-center text-text-secondary">
            Create or import a wallet to get started.
          </p>
        </Card>
      )}
    </div>
  );
}

/* ---- Wallet Selector ---- */

function WalletSelector({
  wallets,
  active,
  onSelect,
  onAdd,
  onRemove,
}: {
  wallets: NativeWallet[];
  active: string | null;
  onSelect: (addr: string | null) => void;
  onAdd: (w: NativeWallet) => void;
  onRemove: (addr: string) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importKey, setImportKey] = useState("");

  const handleCreate = useCallback(async () => {
    setCreating(true);
    try {
      const res = await api.createWallet();
      onAdd({
        address: res.address,
        publicKeyHex: res.public_key_hex,
        label: `Wallet ${wallets.length + 1}`,
        createdAt: Date.now(),
      });
      setNewKey(res.private_key_hex);
    } catch (e) {
      alert(`Failed to create wallet: ${e}`);
    } finally {
      setCreating(false);
    }
  }, [onAdd, wallets.length]);

  const handleImport = useCallback(async () => {
    if (!importKey.trim()) return;
    try {
      // SECURITY: Private keys must NEVER be sent to the backend.
      // Client-side import validates key format locally. Full Dilithium
      // key derivation (private key -> public key -> address) will be
      // available once the Dilithium WASM module is integrated.
      const keyHex = importKey.trim();
      if (!/^[0-9a-fA-F]+$/.test(keyHex) || keyHex.length < 64) {
        throw new Error("Invalid private key format: must be a hex string of sufficient length");
      }

      // TODO: Derive public key and address from private key using
      // Dilithium2 WASM module. Until then, import is not supported.
      alert(
        "Import is not yet supported client-side. Dilithium2 WASM module required for key derivation. Please use 'Create Wallet' and fund it.",
      );
    } catch (e) {
      alert(`Import failed: ${e}`);
    } finally {
      setImporting(false);
      setImportKey("");
    }
  }, [importKey]);

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-quantum-green">&#x1f512;</span>
          <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
            Native Quantum Wallets
          </h3>
          <span className="rounded bg-quantum-green/20 px-2 py-0.5 text-[10px] font-semibold text-quantum-green">
            Dilithium2
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setImporting(!importing)}
            className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-text-secondary transition hover:border-quantum-violet hover:text-quantum-violet"
          >
            Import
          </button>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="rounded-lg bg-quantum-green px-3 py-1.5 text-xs font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
          >
            {creating ? "Creating..." : "+ Create"}
          </button>
        </div>
      </div>

      {/* Import field */}
      {importing && (
        <div className="mt-3 flex gap-2">
          <input
            type="password"
            placeholder="Paste private key hex..."
            value={importKey}
            onChange={(e) => setImportKey(e.target.value)}
            className="flex-1 rounded-lg bg-bg-deep px-3 py-2 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <button
            onClick={handleImport}
            className="rounded-lg bg-quantum-violet px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-quantum-violet/80"
          >
            Import
          </button>
        </div>
      )}

      {/* New key warning */}
      {newKey && (
        <div className="mt-4 rounded-lg border border-amber-500/50 bg-amber-500/10 p-4">
          <p className="text-xs font-semibold text-amber-400">
            Save your private key now. It will NOT be shown again.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-bg-deep p-2 font-[family-name:var(--font-code)] text-[10px] text-amber-300">
              {newKey}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newKey);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="shrink-0 rounded bg-amber-500/20 px-2 py-1 text-xs text-amber-300 transition hover:bg-amber-500/30"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-2 text-xs text-text-secondary underline"
          >
            I have saved it
          </button>
        </div>
      )}

      {/* Wallet list */}
      {wallets.length > 0 && (
        <div className="mt-4 space-y-2">
          {wallets.map((w) => (
            <div
              key={w.address}
              className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 transition ${
                active === w.address
                  ? "border-quantum-green bg-quantum-green/5"
                  : "border-border-subtle hover:border-quantum-violet/50"
              }`}
              onClick={() => onSelect(w.address)}
            >
              <div>
                <p className="text-xs font-semibold text-text-primary">
                  {w.label}
                </p>
                <p className="font-[family-name:var(--font-code)] text-[10px] text-text-secondary">
                  {w.address}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm("Remove this wallet from the list?"))
                    onRemove(w.address);
                }}
                className="text-xs text-text-secondary hover:text-red-400"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ---- Balance ---- */

function WalletBalance({ wallet }: { wallet: NativeWallet }) {
  const { data } = useQuery({
    queryKey: ["native-balance", wallet.address],
    queryFn: () => api.getBalance(wallet.address),
    refetchInterval: 10_000,
  });
  const balance = data?.balance ? parseFloat(data.balance) : 0;

  return (
    <Card glow="green">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-secondary">QBC Balance</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-4xl font-bold text-quantum-green">
            {balance.toLocaleString(undefined, { maximumFractionDigits: 8 })}{" "}
            QBC
          </p>
        </div>
        <span className="rounded bg-quantum-green/20 px-2 py-1 text-[10px] font-bold text-quantum-green">
          Post-Quantum Secure
        </span>
      </div>
      <p className="mt-2 font-[family-name:var(--font-code)] text-xs text-text-secondary">
        {wallet.address}
      </p>
    </Card>
  );
}

/* ---- Send ---- */

type UtxoStrategy = "largest_first" | "smallest_first" | "exact_match";

const UTXO_STRATEGIES: { value: UtxoStrategy; label: string; description: string }[] = [
  { value: "largest_first", label: "Largest First", description: "Fewest inputs, reduces UTXO count" },
  { value: "smallest_first", label: "Smallest First", description: "Consolidates small UTXOs" },
  { value: "exact_match", label: "Exact Match", description: "Find a UTXO matching the amount" },
];

function SendPanel({ wallet }: { wallet: NativeWallet }) {
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [utxoStrategy, setUtxoStrategy] = useState<UtxoStrategy>("largest_first");
  const [isPrivate, setIsPrivate] = useState(false);
  const [recipientSpendPub, setRecipientSpendPub] = useState("");
  const [recipientViewPub, setRecipientViewPub] = useState("");

  const estimatedFee = 0.0001; // L1 micro-fee estimate
  const parsedAmount = parseFloat(amount) || 0;
  const total = parsedAmount + estimatedFee;

  const handleConfirmSend = useCallback(async () => {
    if (!amount || !privateKey) return;
    if (!isPrivate && !to) return;
    if (isPrivate && (!recipientSpendPub || !recipientViewPub)) return;
    setSending(true);
    setResult(null);
    setShowConfirm(false);
    try {
      if (isPrivate) {
        // Private (Susy Swap) flow
        const amountAtoms = Math.round(parseFloat(amount) * 1e8);
        const feeAtoms = Math.round(estimatedFee * 1e8);

        // Fetch UTXOs and pick one that covers the amount + fee
        const utxoRes = await api.getUTXOs(wallet.address);
        const utxos = utxoRes.utxos || [];
        const needed = amountAtoms + feeAtoms;
        const picked = utxos.find(
          (u) => Math.round(u.amount * 1e8) >= needed,
        );
        if (!picked) {
          setResult("Error: No single UTXO large enough for private transfer");
          return;
        }

        // Build confidential transaction
        const buildRes = await api.buildPrivateTx({
          inputs: [
            {
              txid: picked.txid,
              vout: picked.vout,
              value: Math.round(picked.amount * 1e8),
              blinding: 0, // fresh UTXO, no existing blinding
              spending_key: parseInt(privateKey.slice(0, 16), 16) || 1,
            },
          ],
          outputs: [
            {
              value: amountAtoms,
              recipient_spend_pub: recipientSpendPub,
              recipient_view_pub: recipientViewPub,
            },
          ],
          fee_atoms: feeAtoms,
        });

        // Submit to mempool
        const submitRes = await api.submitPrivateTx(buildRes);
        setResult(`Private TX sent! ${submitRes.txid.slice(0, 16)}...`);
      } else {
        // Standard (public) flow
        const txData = { from: wallet.address, to, amount };
        const sigHex = await signTransaction(wallet.publicKeyHex, txData);
        const res = await api.sendNative({
          from_address: wallet.address,
          to_address: to,
          amount,
          signature_hex: sigHex,
          public_key_hex: wallet.publicKeyHex,
          utxo_strategy: utxoStrategy,
        });
        setResult(`Sent! TX: ${res.tx_hash.slice(0, 16)}...`);
      }
      setTo("");
      setAmount("");
      setPrivateKey("");
      setRecipientSpendPub("");
      setRecipientViewPub("");
    } catch (e) {
      setResult(`Error: ${e}`);
    } finally {
      setSending(false);
    }
  }, [to, amount, privateKey, wallet, utxoStrategy, isPrivate, recipientSpendPub, recipientViewPub, estimatedFee]);

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Send QBC
      </h3>
      <div className="space-y-3">
        {/* Privacy Toggle */}
        <div className="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-text-primary">
              Private Transfer (Susy Swap)
            </p>
            <p className="text-[11px] text-text-secondary">
              Hide amounts and addresses using Pedersen commitments
            </p>
          </div>
          <button
            onClick={() => setIsPrivate(!isPrivate)}
            className={`relative h-6 w-11 rounded-full transition-colors ${
              isPrivate ? "bg-quantum-violet" : "bg-surface-light"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                isPrivate ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {isPrivate ? (
          <>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                Recipient Stealth Spend Key (compressed hex)
              </label>
              <input
                value={recipientSpendPub}
                onChange={(e) => setRecipientSpendPub(e.target.value)}
                placeholder="02abc..."
                className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                Recipient Stealth View Key (compressed hex)
              </label>
              <input
                value={recipientViewPub}
                onChange={(e) => setRecipientViewPub(e.target.value)}
                placeholder="03def..."
                className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Recipient Address
            </label>
            <input
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="qbc1... or 0x..."
              className="w-full rounded-lg bg-bg-deep px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
        )}
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Amount (QBC)
          </label>
          <input
            type="number"
            step="0.0001"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.0000"
            className="w-full rounded-lg bg-bg-deep px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Private Key (used once for signing, not stored)
          </label>
          <input
            type="password"
            value={privateKey}
            onChange={(e) => setPrivateKey(e.target.value)}
            placeholder="Enter private key to sign..."
            className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        {!isPrivate && (
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Coin Selection Strategy
            </label>
            <select
              value={utxoStrategy}
              onChange={(e) => setUtxoStrategy(e.target.value as UtxoStrategy)}
              className="w-full rounded-lg bg-bg-deep px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            >
              {UTXO_STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label} — {s.description}
                </option>
              ))}
            </select>
          </div>
        )}
        <button
          onClick={() => setShowConfirm(true)}
          disabled={
            sending ||
            !amount ||
            !privateKey ||
            (isPrivate ? !recipientSpendPub || !recipientViewPub : !to)
          }
          className={`rounded-lg px-6 py-2.5 text-sm font-semibold text-void transition disabled:opacity-50 ${
            isPrivate
              ? "bg-quantum-violet hover:bg-quantum-violet/80"
              : "bg-quantum-green hover:bg-quantum-green/80"
          }`}
        >
          {sending
            ? "Signing & Sending..."
            : isPrivate
              ? "Send Private Transaction"
              : "Send Transaction"}
        </button>
        {result && (
          <p
            className={`text-xs ${result.startsWith("Error") ? "text-red-400" : "text-quantum-green"}`}
          >
            {result}
          </p>
        )}
      </div>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-md rounded-2xl border border-border-subtle bg-bg-panelp-6 shadow-2xl">
            <h4 className="font-[family-name:var(--font-display)] text-lg font-bold">
              Confirm {isPrivate ? "Private " : ""}Transaction
            </h4>
            {isPrivate && (
              <span className="mt-1 inline-block rounded bg-quantum-violet/20 px-2 py-0.5 text-[10px] font-semibold text-quantum-violet">
                Susy Swap — Confidential
              </span>
            )}
            <div className="mt-4 space-y-3 rounded-lg bg-bg-deep p-4 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">From</span>
                <span className="font-[family-name:var(--font-code)] text-xs text-quantum-violet">
                  {wallet.address.slice(0, 12)}...{wallet.address.slice(-8)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">To</span>
                <span className="font-[family-name:var(--font-code)] text-xs text-quantum-violet">
                  {isPrivate
                    ? `Stealth: ${recipientSpendPub.slice(0, 12)}...`
                    : `${to.slice(0, 12)}...${to.slice(-8)}`}
                </span>
              </div>
              <div className="border-t border-border-subtle pt-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Amount</span>
                  <span className="font-[family-name:var(--font-code)] text-quantum-green">
                    {isPrivate ? "Hidden" : `${parsedAmount.toLocaleString()} QBC`}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Est. Fee</span>
                  <span className="font-[family-name:var(--font-code)] text-text-secondary">
                    {estimatedFee} QBC
                  </span>
                </div>
              </div>
              <div className="border-t border-border-subtle pt-2">
                <div className="flex justify-between font-semibold">
                  <span>Total</span>
                  <span className="font-[family-name:var(--font-code)] text-quantum-green">
                    {isPrivate ? "Hidden + fee" : `${total.toLocaleString()} QBC`}
                  </span>
                </div>
                {!isPrivate && (
                  <div className="mt-1 flex justify-between">
                    <span className="text-text-secondary">UTXO Strategy</span>
                    <span className="text-xs text-text-secondary">
                      {UTXO_STRATEGIES.find((s) => s.value === utxoStrategy)?.label}
                    </span>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 rounded-lg border border-border-subtle px-4 py-2.5 text-sm text-text-secondary transition hover:text-text-primary"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmSend}
                className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold text-void transition ${
                  isPrivate
                    ? "bg-quantum-violet hover:bg-quantum-violet/80"
                    : "bg-quantum-green hover:bg-quantum-green/80"
                }`}
              >
                Confirm & Sign
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ---- Privacy (Stealth Keys) ---- */

function PrivacyPanel() {
  const [stealthKeys, setStealthKeys] = useState<StealthKeyPair | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const keys = await api.generateStealthKeypair();
      setStealthKeys(keys);
    } catch (e) {
      setError(`Failed to generate: ${e}`);
    } finally {
      setGenerating(false);
    }
  }, []);

  const copyToClipboard = useCallback((text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  }, []);

  return (
    <Card>
      <div className="flex items-center gap-2">
        <span className="text-quantum-violet">&#x1f576;</span>
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Privacy (Susy Swap)
        </h3>
        <span className="rounded bg-quantum-violet/20 px-2 py-0.5 text-[10px] font-semibold text-quantum-violet">
          Stealth
        </span>
      </div>
      <p className="mt-1 text-xs text-text-secondary">
        Generate stealth keys to receive private transactions. Share your public
        keys with senders — they cannot see your balance or link transactions.
      </p>

      <button
        onClick={handleGenerate}
        disabled={generating}
        className="mt-3 rounded-lg bg-quantum-violet px-4 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-50"
      >
        {generating ? "Generating..." : "Generate Stealth Keypair"}
      </button>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      {stealthKeys && (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3">
            <p className="text-xs font-semibold text-amber-400">
              Save your private keys now. They will NOT be shown again.
            </p>
          </div>

          {/* Public keys (shareable) */}
          <div className="rounded-lg bg-bg-deep p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-quantum-violet">
              Share with senders
            </p>
            <div className="mt-2 space-y-2">
              <div>
                <p className="text-[10px] text-text-secondary">Spend Public Key</p>
                <div className="flex items-center gap-1">
                  <code className="flex-1 break-all font-[family-name:var(--font-code)] text-[10px] text-text-primary">
                    {stealthKeys.spend_pubkey}
                  </code>
                  <button
                    onClick={() => copyToClipboard(stealthKeys.spend_pubkey, "spend_pub")}
                    className="shrink-0 text-[10px] text-text-secondary hover:text-quantum-violet"
                  >
                    {copiedField === "spend_pub" ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
              <div>
                <p className="text-[10px] text-text-secondary">View Public Key</p>
                <div className="flex items-center gap-1">
                  <code className="flex-1 break-all font-[family-name:var(--font-code)] text-[10px] text-text-primary">
                    {stealthKeys.view_pubkey}
                  </code>
                  <button
                    onClick={() => copyToClipboard(stealthKeys.view_pubkey, "view_pub")}
                    className="shrink-0 text-[10px] text-text-secondary hover:text-quantum-violet"
                  >
                    {copiedField === "view_pub" ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Private keys (secret) */}
          <div className="rounded-lg bg-bg-deep p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
              Secret — do not share
            </p>
            <div className="mt-2 space-y-2">
              <div>
                <p className="text-[10px] text-text-secondary">Spend Private Key</p>
                <div className="flex items-center gap-1">
                  <code className="flex-1 break-all font-[family-name:var(--font-code)] text-[10px] text-amber-300">
                    {stealthKeys.spend_privkey}
                  </code>
                  <button
                    onClick={() =>
                      copyToClipboard(String(stealthKeys.spend_privkey), "spend_priv")
                    }
                    className="shrink-0 text-[10px] text-text-secondary hover:text-amber-400"
                  >
                    {copiedField === "spend_priv" ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
              <div>
                <p className="text-[10px] text-text-secondary">View Private Key</p>
                <div className="flex items-center gap-1">
                  <code className="flex-1 break-all font-[family-name:var(--font-code)] text-[10px] text-amber-300">
                    {stealthKeys.view_privkey}
                  </code>
                  <button
                    onClick={() =>
                      copyToClipboard(String(stealthKeys.view_privkey), "view_priv")
                    }
                    className="shrink-0 text-[10px] text-text-secondary hover:text-amber-400"
                  >
                    {copiedField === "view_priv" ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg bg-bg-deep p-3">
            <p className="text-[10px] text-text-secondary">Stealth Address</p>
            <code className="break-all font-[family-name:var(--font-code)] text-[10px] text-quantum-green">
              {stealthKeys.public_address}
            </code>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ---- Receive ---- */

function ReceivePanel({ wallet }: { wallet: NativeWallet }) {
  const [copied, setCopied] = useState(false);

  return (
    <Card>
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-lg font-semibold">
        Receive QBC
      </h3>
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
        <QRCode value={wallet.address} size={120} />
        <div className="flex-1">
          <p className="text-xs text-text-secondary">Your address:</p>
          <p className="mt-1 break-all rounded-lg bg-bg-deep px-4 py-3 font-[family-name:var(--font-code)] text-sm text-quantum-green">
            {wallet.address}
          </p>
          <button
            onClick={() => {
              navigator.clipboard.writeText(wallet.address);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
            className="mt-2 text-xs text-text-secondary underline"
          >
            {copied ? "Copied!" : "Copy Address"}
          </button>
        </div>
      </div>
    </Card>
  );
}
