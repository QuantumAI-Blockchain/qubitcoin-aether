"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
      // Sign a test message to derive the public key
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000"}/wallet/sign`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_hash:
              "0000000000000000000000000000000000000000000000000000000000000000",
            private_key_hex: importKey.trim(),
          }),
        },
      );
      if (!resp.ok) throw new Error("Invalid private key");

      // Derive address from the private key via a create call
      // For import we create a new wallet then the user should use the address
      alert(
        "Import is not yet supported client-side. Please use 'Create Wallet' and fund it.",
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
          <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold">
            Native Quantum Wallets
          </h3>
          <span className="rounded bg-quantum-green/20 px-2 py-0.5 text-[10px] font-semibold text-quantum-green">
            Dilithium2
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setImporting(!importing)}
            className="rounded-lg border border-surface-light px-3 py-1.5 text-xs text-text-secondary transition hover:border-quantum-violet hover:text-quantum-violet"
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
            className="flex-1 rounded-lg bg-void px-3 py-2 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
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
            <code className="flex-1 break-all rounded bg-void p-2 font-[family-name:var(--font-mono)] text-[10px] text-amber-300">
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
                  : "border-surface-light hover:border-quantum-violet/50"
              }`}
              onClick={() => onSelect(w.address)}
            >
              <div>
                <p className="text-xs font-semibold text-text-primary">
                  {w.label}
                </p>
                <p className="font-[family-name:var(--font-mono)] text-[10px] text-text-secondary">
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
          <p className="mt-1 font-[family-name:var(--font-mono)] text-4xl font-bold text-quantum-green">
            {balance.toLocaleString(undefined, { maximumFractionDigits: 8 })}{" "}
            QBC
          </p>
        </div>
        <span className="rounded bg-quantum-green/20 px-2 py-1 text-[10px] font-bold text-quantum-green">
          Post-Quantum Secure
        </span>
      </div>
      <p className="mt-2 font-[family-name:var(--font-mono)] text-xs text-text-secondary">
        {wallet.address}
      </p>
    </Card>
  );
}

/* ---- Send ---- */

function SendPanel({ wallet }: { wallet: NativeWallet }) {
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const estimatedFee = 0.0001; // L1 micro-fee estimate
  const parsedAmount = parseFloat(amount) || 0;
  const total = parsedAmount + estimatedFee;

  const handleConfirmSend = useCallback(async () => {
    if (!to || !amount || !privateKey) return;
    setSending(true);
    setResult(null);
    setShowConfirm(false);
    try {
      const txData = {
        from: wallet.address,
        to,
        amount,
      };
      const sigHex = await signTransaction(privateKey, txData);
      const res = await api.sendNative({
        from_address: wallet.address,
        to_address: to,
        amount,
        signature_hex: sigHex,
        public_key_hex: wallet.publicKeyHex,
      });
      setResult(`Sent! TX: ${res.tx_hash.slice(0, 16)}...`);
      setTo("");
      setAmount("");
      setPrivateKey("");
    } catch (e) {
      setResult(`Error: ${e}`);
    } finally {
      setSending(false);
    }
  }, [to, amount, privateKey, wallet]);

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Send QBC
      </h3>
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Recipient Address
          </label>
          <input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="qbc1... or 0x..."
            className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
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
            className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
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
            className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <button
          onClick={() => setShowConfirm(true)}
          disabled={sending || !to || !amount || !privateKey}
          className="rounded-lg bg-quantum-green px-6 py-2.5 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
        >
          {sending ? "Signing & Sending..." : "Send Transaction"}
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
          <div className="mx-4 w-full max-w-md rounded-2xl border border-surface-light bg-surface p-6 shadow-2xl">
            <h4 className="font-[family-name:var(--font-heading)] text-lg font-bold">
              Confirm Transaction
            </h4>
            <div className="mt-4 space-y-3 rounded-lg bg-void p-4 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">From</span>
                <span className="font-[family-name:var(--font-mono)] text-xs text-quantum-violet">
                  {wallet.address.slice(0, 12)}...{wallet.address.slice(-8)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">To</span>
                <span className="font-[family-name:var(--font-mono)] text-xs text-quantum-violet">
                  {to.slice(0, 12)}...{to.slice(-8)}
                </span>
              </div>
              <div className="border-t border-surface-light pt-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Amount</span>
                  <span className="font-[family-name:var(--font-mono)] text-quantum-green">
                    {parsedAmount.toLocaleString()} QBC
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Est. Fee</span>
                  <span className="font-[family-name:var(--font-mono)] text-text-secondary">
                    {estimatedFee} QBC
                  </span>
                </div>
              </div>
              <div className="border-t border-surface-light pt-2">
                <div className="flex justify-between font-semibold">
                  <span>Total</span>
                  <span className="font-[family-name:var(--font-mono)] text-quantum-green">
                    {total.toLocaleString()} QBC
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 rounded-lg border border-surface-light px-4 py-2.5 text-sm text-text-secondary transition hover:text-text-primary"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmSend}
                className="flex-1 rounded-lg bg-quantum-green px-4 py-2.5 text-sm font-semibold text-void transition hover:bg-quantum-green/80"
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

/* ---- Receive ---- */

function ReceivePanel({ wallet }: { wallet: NativeWallet }) {
  const [copied, setCopied] = useState(false);

  return (
    <Card>
      <h3 className="mb-3 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Receive QBC
      </h3>
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
        <QRCode value={wallet.address} size={120} />
        <div className="flex-1">
          <p className="text-xs text-text-secondary">Your address:</p>
          <p className="mt-1 break-all rounded-lg bg-void px-4 py-3 font-[family-name:var(--font-mono)] text-sm text-quantum-green">
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
