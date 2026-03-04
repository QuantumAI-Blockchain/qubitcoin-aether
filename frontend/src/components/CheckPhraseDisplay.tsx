"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface CheckPhraseDisplayProps {
  address: string;
  /** Show the full address alongside the check-phrase */
  showFull?: boolean;
  /** Pre-fetched check-phrase (avoids API call) */
  checkPhrase?: string;
  /** CSS class for the container */
  className?: string;
}

/**
 * Displays a QBC address with its human-readable check-phrase.
 *
 * Check-phrases are 3 BIP-39 words derived from the address hash,
 * making it easy to verify addresses verbally (e.g., "tiger-ocean-marble").
 *
 * Usage:
 *   <CheckPhraseDisplay address="a1b2c3..." />
 *   <CheckPhraseDisplay address="a1b2c3..." showFull checkPhrase="tiger-ocean-marble" />
 */
export function CheckPhraseDisplay({
  address,
  showFull = false,
  checkPhrase: preloaded,
  className = "",
}: CheckPhraseDisplayProps) {
  const [phrase, setPhrase] = useState(preloaded ?? "");
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(!preloaded);

  useEffect(() => {
    if (preloaded) return;
    let cancelled = false;
    setLoading(true);
    api
      .getCheckPhrase(address)
      .then((res) => {
        if (!cancelled) setPhrase(res.check_phrase);
      })
      .catch(() => {
        if (!cancelled) setPhrase("");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [address, preloaded]);

  const truncated = `${address.slice(0, 8)}...${address.slice(-6)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
    }
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-sm ${className}`}
    >
      <span className="text-text-primary">
        {showFull ? address : truncated}
      </span>
      {loading ? (
        <span className="text-text-secondary animate-pulse text-xs">...</span>
      ) : phrase ? (
        <span
          className="rounded bg-quantum-green/10 px-1.5 py-0.5 text-xs font-medium text-quantum-green"
          title={`Check-phrase for ${address}`}
        >
          {phrase}
        </span>
      ) : null}
      <button
        onClick={handleCopy}
        className="text-text-secondary hover:text-text-primary ml-0.5 text-xs transition"
        title="Copy address"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}
