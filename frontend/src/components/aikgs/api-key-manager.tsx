"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore, type StoredKeyInfo } from "@/stores/aikgs-store";
import { api } from "@/lib/api";
import { LLM_PROVIDERS } from "@/lib/constants";

export function APIKeyManager() {
  const { address, connected } = useWalletStore();
  const { storedKeys, setStoredKeys } = useAIKGSStore();
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [label, setLabel] = useState("");
  const [isShared, setIsShared] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedProvider = LLM_PROVIDERS.find((p) => p.id === provider);

  // Set default model when provider changes
  useEffect(() => {
    if (selectedProvider && selectedProvider.models.length > 0) {
      setModel(selectedProvider.models[0] ?? "");
    } else {
      setModel("");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedProvider is derived from provider
  }, [provider]);

  // Fetch stored keys on mount
  useEffect(() => {
    if (!address) return;
    api.aikgsGetKeys(address).then((res) => setStoredKeys(res.keys)).catch((e) => console.error("[AIKGS] Failed to load keys:", e));
  }, [address, setStoredKeys]);

  const handleStore = useCallback(async () => {
    if (!address || !apiKey || !model) return;
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await api.aikgsStoreKey({
        owner_address: address,
        provider,
        api_key: apiKey,
        model,
        label: label || undefined,
        is_shared: isShared,
      });
      setSuccess(`Key stored: ${res.key_id.slice(0, 8)}...`);
      setApiKey("");
      setLabel("");
      // Refresh key list
      const updated = await api.aikgsGetKeys(address);
      setStoredKeys(updated.keys);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to store key");
    } finally {
      setLoading(false);
    }
  }, [address, apiKey, model, provider, label, isShared, setStoredKeys]);

  const handleRevoke = useCallback(
    async (keyId: string) => {
      if (!address) return;
      try {
        await api.aikgsRevokeKey({ owner_address: address, key_id: keyId });
        setStoredKeys(storedKeys.filter((k) => k.key_id !== keyId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Revoke failed");
      }
    },
    [address, storedKeys, setStoredKeys],
  );

  if (!connected || !address) {
    return (
      <Card className="mb-4">
        <h3 className="mb-2 text-sm font-semibold text-text-secondary">API Key Vault</h3>
        <p className="text-xs text-text-secondary">Connect your wallet to manage API keys.</p>
      </Card>
    );
  }

  return (
    <Card className="mb-4">
      <h3 className="mb-3 text-sm font-semibold glow-cyan">API Key Vault</h3>

      {/* Provider select */}
      <label className="mb-1 block text-xs text-text-secondary">Provider</label>
      <select
        value={provider}
        onChange={(e) => setProvider(e.target.value)}
        className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      >
        {LLM_PROVIDERS.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      {/* Model select */}
      <label className="mb-1 block text-xs text-text-secondary">Model</label>
      {selectedProvider && selectedProvider.models.length > 0 ? (
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
        >
          {selectedProvider.models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="model-name"
          className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
        />
      )}

      {/* API Key */}
      <label className="mb-1 block text-xs text-text-secondary">API Key</label>
      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="sk-... or key-..."
        className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      />

      {/* Label */}
      <label className="mb-1 block text-xs text-text-secondary">Label (optional)</label>
      <input
        type="text"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="My work key"
        className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      />

      {/* Shared toggle */}
      <label className="mb-3 flex items-center gap-2 text-xs text-text-secondary">
        <input
          type="checkbox"
          checked={isShared}
          onChange={(e) => setIsShared(e.target.checked)}
          className="rounded border-border-subtle bg-bg-deep accent-quantum-violet"
        />
        Share to community pool (earn 15% of rewards generated)
      </label>

      {/* Submit */}
      <button
        onClick={handleStore}
        disabled={loading || !apiKey || !model}
        className="w-full rounded-lg bg-quantum-violet px-4 py-2 text-xs font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-40"
      >
        {loading ? "Encrypting & Storing..." : "Store Key"}
      </button>

      {success && (
        <div className="contribution-flash mt-3 rounded-lg border border-quantum-green/30 bg-quantum-green/5 p-2">
          <p className="text-xs text-quantum-green">{success}</p>
        </div>
      )}
      {error && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 p-2">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Stored Keys List */}
      {storedKeys.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-semibold text-text-secondary">Your Keys</h4>
          <div className="space-y-2">
            {storedKeys.map((k) => (
              <div
                key={k.key_id}
                className="flex items-center justify-between rounded-lg bg-bg-deep p-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-text-primary">
                    {k.label || k.provider} — {k.model}
                  </p>
                  <p className="text-[10px] text-text-secondary">
                    Uses: {k.use_count} {k.is_shared && "| Shared"}
                  </p>
                </div>
                <button
                  onClick={() => handleRevoke(k.key_id)}
                  className="ml-2 shrink-0 rounded px-2 py-1 text-[10px] text-red-400 transition hover:bg-red-500/10"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-[10px] text-text-secondary/60">
        Keys are AES-256-GCM encrypted at rest. Never stored in plaintext.
      </p>
    </Card>
  );
}
