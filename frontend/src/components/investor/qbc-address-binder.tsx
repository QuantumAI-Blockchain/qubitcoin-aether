"use client";

import { useState, useCallback } from "react";
import { useInvestorStore } from "@/stores/investor-store";
import { investorApi } from "@/lib/investor-api";
import { api } from "@/lib/api";
import { generateKeypair, SecurityLevel } from "@/lib/dilithium";

export function QBCAddressBinder() {
  const {
    qbcAddress, setQbcAddress,
    checkPhrase, setCheckPhrase,
    addressValidated, setAddressValidated,
  } = useInvestorStore();

  const [mode, setMode] = useState<"choose" | "generate" | "import">("choose");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [generatedKeys, setGeneratedKeys] = useState<{
    address: string;
    public_key_hex: string;
    check_phrase: string;
  } | null>(null);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // Client-side key generation via WASM
      let result: { address: string; public_key_hex: string; check_phrase: string };
      try {
        const kp = await generateKeypair(SecurityLevel.LEVEL5);
        result = {
          address: kp.address,
          public_key_hex: kp.publicKeyHex,
          check_phrase: kp.checkPhrase,
        };
        // Store private key for user to save
        sessionStorage.setItem(`qbc-sk-${kp.address}`, kp.secretKeyHex);
      } catch {
        // Fallback to server-side (address + pk only)
        const res = await api.createWallet(5);
        result = {
          address: res.address,
          public_key_hex: res.public_key_hex,
          check_phrase: res.check_phrase,
        };
      }
      setGeneratedKeys(result);
      setQbcAddress(result.address);
      setCheckPhrase(result.check_phrase);
      setAddressValidated(true);
      setMode("generate");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate wallet");
    } finally {
      setLoading(false);
    }
  }, [setQbcAddress, setCheckPhrase, setAddressValidated]);

  const handleValidate = useCallback(async (addr: string) => {
    if (addr.length !== 40) return;
    setLoading(true);
    setError("");
    try {
      const result = await investorApi.validateQBCAddress(addr);
      if (result.valid) {
        setCheckPhrase(result.check_phrase || "");
        setAddressValidated(true);
      } else {
        setError(result.error || "Invalid address");
        setAddressValidated(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setLoading(false);
    }
  }, [setCheckPhrase, setAddressValidated]);

  if (mode === "choose") {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
        <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
          Step 2: Set Your QBC Address
        </h3>
        <p className="mb-4 text-sm text-text-secondary">
          Your QBC tokens will be delivered to this address after TGE. This is{" "}
          <span className="font-bold text-amber-400">PERMANENT</span> — you cannot change it after investing.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="flex-1 rounded-lg bg-glow-cyan/20 px-4 py-3 text-sm font-medium text-glow-cyan transition hover:bg-glow-cyan/30 disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate New QBC Wallet"}
          </button>
          <button
            onClick={() => setMode("import")}
            className="flex-1 rounded-lg border border-border-subtle px-4 py-3 text-sm font-medium text-text-secondary transition hover:border-glow-cyan hover:text-text-primary"
          >
            I Have One
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      </div>
    );
  }

  if (mode === "generate" && generatedKeys) {
    return (
      <div className="rounded-xl border border-green-500/30 bg-bg-panel p-6">
        <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-green-400">
          QBC Wallet Generated
        </h3>
        <div className="space-y-3">
          <div>
            <div className="text-xs text-text-secondary">QBC Address</div>
            <div className="font-mono text-sm text-text-primary break-all">
              {generatedKeys.address}
            </div>
          </div>
          <div>
            <div className="text-xs text-text-secondary">Check-phrase</div>
            <div className="font-mono text-sm font-bold text-glow-gold">
              {generatedKeys.check_phrase}
            </div>
          </div>
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
            <p className="text-xs text-amber-300">
              Save your private key securely. It was shown during generation and cannot be recovered.
              Your QBC address is bound permanently upon your first investment.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Import mode
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Enter Your QBC Address
      </h3>
      <input
        type="text"
        value={qbcAddress}
        onChange={(e) => {
          const v = e.target.value.toLowerCase().replace(/[^a-f0-9]/g, "").slice(0, 40);
          setQbcAddress(v);
          setAddressValidated(false);
          if (v.length === 40) handleValidate(v);
        }}
        placeholder="40-character hex address"
        className="w-full rounded-lg border border-border-subtle bg-bg-deep px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-glow-cyan focus:outline-none"
        maxLength={40}
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-text-secondary">{qbcAddress.length}/40 characters</span>
        {addressValidated && checkPhrase && (
          <span className="text-xs font-medium text-green-400">
            Check-phrase: <span className="font-mono text-glow-gold">{checkPhrase}</span>
          </span>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      <button
        onClick={() => setMode("choose")}
        className="mt-3 text-xs text-text-secondary hover:text-text-primary"
      >
        &larr; Back
      </button>
    </div>
  );
}
