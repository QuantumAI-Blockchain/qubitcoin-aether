"use client";

import { useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { api, type AIKGSContribution } from "@/lib/api";
import { KNOWLEDGE_DOMAINS } from "@/lib/constants";

interface UploadResult {
  contribution_id: number;
  quality_score: number;
  novelty_score: number;
  combined_score: number;
  tier: string;
  reward_amount: number;
  knowledge_node_id: number | null;
}

function tierClass(tier: string): string {
  switch (tier) {
    case "bronze": return "tier-bronze";
    case "silver": return "tier-silver";
    case "gold": return "tier-gold";
    case "diamond": return "tier-diamond";
    default: return "text-text-secondary";
  }
}

export function UploadPanel() {
  const { address, connected } = useWalletStore();
  const { setProfile, setRecentContributions } = useAIKGSStore();
  const [content, setContent] = useState("");
  const [domain, setDomain] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!address || content.trim().length < 20) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.aikgsSubmitContribution({
        contributor_address: address,
        content: content.trim(),
        domain: domain || undefined,
      });
      setResult(res);
      setContent("");

      // Refresh profile and contributions
      const [profileRes, contribRes] = await Promise.all([
        api.aikgsGetProfile(address),
        api.aikgsGetContributions(address, 10),
      ]);
      setProfile(profileRes);
      setRecentContributions(contribRes.contributions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setLoading(false);
    }
  }, [address, content, domain, setProfile, setRecentContributions]);

  if (!connected || !address) {
    return (
      <Card className="mb-4">
        <h3 className="mb-2 text-sm font-semibold text-text-secondary">Contribute Knowledge</h3>
        <p className="text-xs text-text-secondary">Connect your wallet to contribute to the knowledge graph.</p>
      </Card>
    );
  }

  return (
    <Card className="mb-4">
      <h3 className="mb-3 text-sm font-semibold glow-emerald">Contribute Knowledge</h3>

      {/* Domain */}
      <label className="mb-1 block text-xs text-text-secondary">Domain (auto-detected if empty)</label>
      <select
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      >
        <option value="">Auto-detect</option>
        {KNOWLEDGE_DOMAINS.map((d) => (
          <option key={d} value={d}>
            {d.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </option>
        ))}
      </select>

      {/* Content */}
      <label className="mb-1 block text-xs text-text-secondary">Knowledge Content</label>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Share factual knowledge, insights, or explanations. Quality and novelty determine your reward tier..."
        rows={5}
        className="mb-1 w-full resize-none rounded-lg bg-bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
      />
      <p className="mb-3 text-right text-[10px] text-text-secondary">
        {content.length} chars {content.length < 20 && "| Min 20"}
      </p>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={loading || content.trim().length < 20}
        className="w-full rounded-lg bg-quantum-green px-4 py-2.5 text-xs font-semibold text-bg-deep transition hover:bg-quantum-green/80 disabled:opacity-40"
      >
        {loading ? "Scoring & Recording..." : "Submit Contribution"}
      </button>

      {/* Result */}
      {result && (
        <div className="contribution-flash mt-3 rounded-lg border border-quantum-green/30 bg-quantum-green/5 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className={`text-sm font-bold ${tierClass(result.tier)}`}>
              {result.tier.toUpperCase()} TIER
            </span>
            <span className="reward-glow rounded-lg bg-golden/10 px-2 py-1 text-sm font-bold text-golden">
              +{result.reward_amount.toFixed(4)} QBC
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-xs font-semibold text-text-primary">{result.quality_score.toFixed(2)}</p>
              <p className="text-[10px] text-text-secondary">Quality</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-text-primary">{result.novelty_score.toFixed(2)}</p>
              <p className="text-[10px] text-text-secondary">Novelty</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-text-primary">{result.combined_score.toFixed(2)}</p>
              <p className="text-[10px] text-text-secondary">Combined</p>
            </div>
          </div>
          {result.knowledge_node_id && (
            <p className="mt-2 text-[10px] text-text-secondary">
              Knowledge Node #{result.knowledge_node_id}
            </p>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 p-2">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      <p className="mt-2 text-[10px] text-text-secondary/60">
        Contributions are scored for quality and novelty. Higher tiers earn larger rewards.
      </p>
    </Card>
  );
}
