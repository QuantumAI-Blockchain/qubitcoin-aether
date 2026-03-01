"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { api, type AIKGSAffiliateInfo } from "@/lib/api";

export function AffiliateTree() {
  const { address, connected } = useWalletStore();
  const { affiliateInfo, setAffiliateInfo } = useAIKGSStore();
  const [referralLink, setReferralLink] = useState("");
  const [telegramLink, setTelegramLink] = useState("");
  const [inputCode, setInputCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Load affiliate info
  useEffect(() => {
    if (!address) return;
    setLoading(true);
    Promise.all([
      api.aikgsGetAffiliate(address).catch(() => null),
      api.aikgsGetReferralLink(address).catch(() => null),
    ])
      .then(([aff, link]) => {
        if (aff) setAffiliateInfo(aff);
        if (link) {
          setReferralLink(link.link);
          setTelegramLink(link.telegram_link);
        }
      })
      .finally(() => setLoading(false));
  }, [address, setAffiliateInfo]);

  const handleRegister = useCallback(async () => {
    if (!address) return;
    setRegistering(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await api.aikgsRegisterAffiliate({
        address,
        referral_code: inputCode || undefined,
      });
      setSuccess(`Registered! Code: ${res.referral_code}`);
      setInputCode("");
      // Refresh data
      const [aff, link] = await Promise.all([
        api.aikgsGetAffiliate(address),
        api.aikgsGetReferralLink(address),
      ]);
      setAffiliateInfo(aff);
      setReferralLink(link.link);
      setTelegramLink(link.telegram_link);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  }, [address, inputCode, setAffiliateInfo]);

  const copyLink = useCallback(async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  }, []);

  if (!connected || !address) {
    return (
      <Card className="mb-4">
        <h3 className="mb-2 text-sm font-semibold text-text-secondary">Affiliate Program</h3>
        <p className="text-xs text-text-secondary">Connect your wallet to access the affiliate program.</p>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card className="mb-4">
        <div className="flex h-32 items-center justify-center">
          <div className="phi-spin h-6 w-6 rounded-full border-2 border-quantum-violet/30 border-t-quantum-violet" />
        </div>
      </Card>
    );
  }

  // Not registered yet
  if (!affiliateInfo) {
    return (
      <Card className="mb-4">
        <h3 className="mb-3 text-sm font-semibold glow-cyan">Join Affiliate Program</h3>
        <p className="mb-3 text-xs text-text-secondary">
          Earn 10% L1 + 5% L2 commissions on rewards from your referrals.
        </p>

        <label className="mb-1 block text-xs text-text-secondary">Referral Code (if referred)</label>
        <input
          type="text"
          value={inputCode}
          onChange={(e) => setInputCode(e.target.value.toUpperCase())}
          placeholder="QBC-XXXXXXXX"
          className="mb-3 w-full rounded-lg bg-bg-deep px-3 py-2 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
        />

        <button
          onClick={handleRegister}
          disabled={registering}
          className="w-full rounded-lg bg-quantum-violet px-4 py-2 text-xs font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-40"
        >
          {registering ? "Registering..." : "Register"}
        </button>

        {error && (
          <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 p-2">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}
        {success && (
          <div className="contribution-flash mt-3 rounded-lg border border-quantum-green/30 bg-quantum-green/5 p-2">
            <p className="text-xs text-quantum-green">{success}</p>
          </div>
        )}
      </Card>
    );
  }

  // Registered — show stats & links
  const totalCommission = affiliateInfo.total_l1_commission + affiliateInfo.total_l2_commission;

  return (
    <Card className="mb-4">
      <h3 className="mb-3 text-sm font-semibold glow-cyan">Affiliate Program</h3>

      {/* Stats */}
      <div className="mb-4 grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-bg-deep p-3 text-center">
          <p className="text-lg font-bold text-quantum-green">{affiliateInfo.l1_referrals}</p>
          <p className="text-[10px] text-text-secondary">L1 Referrals</p>
        </div>
        <div className="rounded-lg bg-bg-deep p-3 text-center">
          <p className="text-lg font-bold text-quantum-violet">{affiliateInfo.l2_referrals}</p>
          <p className="text-[10px] text-text-secondary">L2 Referrals</p>
        </div>
        <div className="rounded-lg bg-bg-deep p-3 text-center">
          <p className="text-lg font-bold glow-gold">{totalCommission.toFixed(4)}</p>
          <p className="text-[10px] text-text-secondary">Earned (QBC)</p>
        </div>
      </div>

      {/* Commission breakdown */}
      <div className="mb-4 rounded-lg bg-bg-deep p-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="text-text-secondary">L1 Commission (10%)</span>
          <span className="text-quantum-green">{affiliateInfo.total_l1_commission.toFixed(4)} QBC</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-secondary">L2 Commission (5%)</span>
          <span className="text-quantum-violet">{affiliateInfo.total_l2_commission.toFixed(4)} QBC</span>
        </div>
      </div>

      {/* Referral code */}
      <div className="mb-3">
        <label className="mb-1 block text-xs text-text-secondary">Your Referral Code</label>
        <div className="flex items-center gap-2 rounded-lg bg-bg-deep p-2">
          <code className="flex-1 text-sm font-semibold referral-shimmer">
            {affiliateInfo.referral_code}
          </code>
          <button
            onClick={() => copyLink(affiliateInfo.referral_code)}
            className="shrink-0 rounded px-2 py-1 text-[10px] text-text-secondary transition hover:bg-border-subtle hover:text-text-primary"
          >
            Copy
          </button>
        </div>
      </div>

      {/* Share links */}
      {referralLink && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={referralLink}
              className="min-w-0 flex-1 rounded-lg bg-bg-deep px-3 py-2 font-[family-name:var(--font-code)] text-[10px] text-text-secondary"
            />
            <button
              onClick={() => copyLink(referralLink)}
              className="shrink-0 rounded-lg bg-quantum-violet/20 px-3 py-2 text-[10px] font-semibold text-quantum-violet transition hover:bg-quantum-violet/30"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          {telegramLink && (
            <a
              href={telegramLink}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full rounded-lg bg-[#229ED9]/20 px-4 py-2 text-center text-xs font-semibold text-[#229ED9] transition hover:bg-[#229ED9]/30"
            >
              Share via Telegram
            </a>
          )}
        </div>
      )}

      {affiliateInfo.referrer_address && (
        <p className="mt-3 text-[10px] text-text-secondary">
          Referred by: {affiliateInfo.referrer_address.slice(0, 10)}...
        </p>
      )}
    </Card>
  );
}
