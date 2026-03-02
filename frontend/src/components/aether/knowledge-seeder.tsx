"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { api } from "@/lib/api";

interface SeedResult {
  status: string;
  nodes_created: number;
  tokens_used: number;
  model: string;
  latency_ms: number;
  knowledge_nodes: number;
  phi_after: number;
}

function storageKey(address: string): string {
  return `qbc-openai-key-${address.toLowerCase()}`;
}

export function KnowledgeSeeder() {
  const { address, connected } = useWalletStore();
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SeedResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load saved key from localStorage when wallet changes
  useEffect(() => {
    if (address) {
      const saved = sessionStorage.getItem(storageKey(address));
      if (saved) setApiKey(saved);
      else setApiKey("");
    } else {
      setApiKey("");
    }
  }, [address]);

  // Persist key to localStorage when it changes
  const handleKeyChange = useCallback(
    (value: string) => {
      setApiKey(value);
      if (address) {
        if (value) sessionStorage.setItem(storageKey(address), value);
        else sessionStorage.removeItem(storageKey(address));
      }
    },
    [address],
  );

  const handleSeed = useCallback(async () => {
    if (!address || !apiKey || prompt.trim().length < 10) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.seedKnowledge({
        wallet_address: address,
        api_key: apiKey,
        prompt: prompt.trim(),
      });
      setResult(res);
      setPrompt("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    } finally {
      setLoading(false);
    }
  }, [address, apiKey, prompt]);

  if (!connected || !address) {
    return (
      <Card className="mb-4">
        <h3 className="mb-2 text-sm font-semibold text-text-secondary">Seed Knowledge</h3>
        <p className="text-xs text-text-secondary">Connect your wallet to seed the knowledge graph.</p>
      </Card>
    );
  }

  return (
    <Card className="mb-4">
      <h3 className="mb-3 text-sm font-semibold text-text-secondary">Seed Knowledge</h3>

      {/* API Key */}
      <label className="mb-1 block text-xs text-text-secondary">OpenAI API Key</label>
      <div className="relative mb-3">
        <input
          type={showKey ? "text" : "password"}
          value={apiKey}
          onChange={(e) => handleKeyChange(e.target.value)}
          placeholder="sk-..."
          className="w-full rounded-lg bg-bg-deep px-3 py-2 pr-14 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
        />
        <button
          type="button"
          onClick={() => setShowKey(!showKey)}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-[10px] text-text-secondary hover:text-text-primary"
        >
          {showKey ? "Hide" : "Show"}
        </button>
      </div>

      {/* Prompt */}
      <label className="mb-1 block text-xs text-text-secondary">Prompt</label>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Explain quantum entanglement in blockchain consensus..."
        rows={3}
        className="mb-3 w-full resize-none rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      />

      {/* Submit */}
      <button
        onClick={handleSeed}
        disabled={loading || !apiKey.startsWith("sk-") || prompt.trim().length < 10}
        className="w-full rounded-lg bg-quantum-violet px-4 py-2 text-xs font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-40"
      >
        {loading ? "Seeding..." : "Seed Knowledge Graph"}
      </button>

      {/* Result */}
      {result && (
        <div className="mt-3 rounded-lg border border-quantum-green/30 bg-quantum-green/5 p-3">
          <p className="text-xs font-semibold text-quantum-green">
            +{result.nodes_created} nodes created
          </p>
          <div className="mt-1 space-y-0.5 text-[10px] text-text-secondary">
            <p>Model: {result.model} | Tokens: {result.tokens_used}</p>
            <p>Latency: {result.latency_ms}ms | Total nodes: {result.knowledge_nodes}</p>
            <p>Phi: {result.phi_after.toFixed(4)}</p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      <p className="mt-2 text-[10px] text-text-secondary/60">
        Your API key is sent per-request and never stored on the server.
      </p>
    </Card>
  );
}
