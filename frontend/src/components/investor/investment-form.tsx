"use client";

import { useState, useCallback } from "react";
import { useInvestorStore } from "@/stores/investor-store";
import { useWalletStore } from "@/stores/wallet-store";

const TOKENS = ["ETH", "USDC", "USDT", "DAI"] as const;

// Mainnet stablecoin addresses
const TOKEN_ADDRESSES: Record<string, string> = {
  USDC: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
  USDT: "0xdAC17F958D2ee523a2206206994597C13D831ec7",
  DAI: "0x6B175474E89094C44Da98b954EedeAC495271d0F",
};

interface Props {
  ethPrice: number;
  contractAddress: string;
}

export function InvestmentForm({ ethPrice, contractAddress }: Props) {
  const { selectedToken, setSelectedToken, investAmount, setInvestAmount, qbcAddress, addressValidated, round } =
    useInvestorStore();
  const { address: ethAddress, connected: isConnected } = useWalletStore();
  const [txPending, setTxPending] = useState(false);
  const [txHash, setTxHash] = useState("");
  const [error, setError] = useState("");

  const price = round ? parseFloat(round.token_price_usd) : 0.001;
  const amount = parseFloat(investAmount) || 0;

  let usdValue = 0;
  if (selectedToken === "ETH") {
    usdValue = amount * ethPrice;
  } else {
    usdValue = amount; // stablecoins are 1:1 USD
  }
  const qbcAllocation = price > 0 ? usdValue / price : 0;

  const canInvest = isConnected && addressValidated && amount > 0 && usdValue >= 100;

  const handleInvest = useCallback(async () => {
    const ethereum = (window as any).ethereum;
    if (!canInvest || !ethereum) return;
    setTxPending(true);
    setError("");
    setTxHash("");

    try {
      const { BrowserProvider, Contract, parseEther, parseUnits } = await import("ethers");
      const provider = new BrowserProvider(ethereum);
      const signer = await provider.getSigner();

      const qbcAddrBytes = "0x" + qbcAddress;

      if (selectedToken === "ETH") {
        // investWithETH(bytes20 qbcAddress) payable
        const contract = new Contract(
          contractAddress,
          ["function investWithETH(bytes20 qbcAddress) external payable"],
          signer
        );
        const tx = await contract.investWithETH(qbcAddrBytes, {
          value: parseEther(investAmount),
        });
        setTxHash(tx.hash);
        await tx.wait();
      } else {
        // Approve + investWithStable
        const tokenAddr = TOKEN_ADDRESSES[selectedToken];
        const decimals = selectedToken === "DAI" ? 18 : 6;
        const amountParsed = parseUnits(investAmount, decimals);

        // Approve
        const erc20 = new Contract(
          tokenAddr,
          ["function approve(address spender, uint256 amount) external returns (bool)"],
          signer
        );
        const approveTx = await erc20.approve(contractAddress, amountParsed);
        await approveTx.wait();

        // Invest
        const contract = new Contract(
          contractAddress,
          ["function investWithStable(address token, uint256 amount, bytes20 qbcAddress) external"],
          signer
        );
        const tx = await contract.investWithStable(tokenAddr, amountParsed, qbcAddrBytes);
        setTxHash(tx.hash);
        await tx.wait();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Transaction failed";
      // Extract user-friendly error
      if (msg.includes("user rejected")) {
        setError("Transaction rejected by user");
      } else if (msg.includes("BelowMinInvestment")) {
        setError("Below minimum investment ($100)");
      } else if (msg.includes("ExceedsMaxInvestment")) {
        setError("Exceeds maximum investment ($500K)");
      } else if (msg.includes("ExceedsHardCap")) {
        setError("Hard cap reached");
      } else if (msg.includes("CooldownActive")) {
        setError("Cooldown active — wait 12 seconds");
      } else if (msg.includes("RoundNotActive")) {
        setError("Round not active");
      } else {
        setError(msg.slice(0, 200));
      }
    } finally {
      setTxPending(false);
    }
  }, [canInvest, qbcAddress, selectedToken, investAmount, contractAddress]);

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Step 3: Invest
      </h3>

      {/* Token selector */}
      <div className="mb-4 flex gap-2">
        {TOKENS.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedToken(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              selectedToken === t
                ? "bg-glow-cyan/20 text-glow-cyan"
                : "bg-white/5 text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Amount input */}
      <div className="mb-3">
        <input
          type="number"
          value={investAmount}
          onChange={(e) => setInvestAmount(e.target.value)}
          placeholder={`Amount in ${selectedToken}`}
          className="w-full rounded-lg border border-border-subtle bg-bg-deep px-4 py-3 font-mono text-lg text-text-primary placeholder:text-text-secondary/50 focus:border-glow-cyan focus:outline-none"
          min="0"
          step="any"
        />
      </div>

      {/* Conversion display */}
      {amount > 0 && (
        <div className="mb-4 rounded-lg bg-white/5 p-3 text-sm">
          <div className="flex justify-between">
            <span className="text-text-secondary">USD Value</span>
            <span className="font-mono text-text-primary">
              ${usdValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </span>
          </div>
          {selectedToken === "ETH" && (
            <div className="flex justify-between">
              <span className="text-text-secondary">ETH Price</span>
              <span className="font-mono text-text-secondary">
                ${ethPrice.toLocaleString()} (Chainlink)
              </span>
            </div>
          )}
          <div className="mt-1 flex justify-between border-t border-white/10 pt-1">
            <span className="text-text-secondary">QBC Allocation</span>
            <span className="font-mono font-bold text-glow-gold">
              {qbcAllocation.toLocaleString(undefined, { maximumFractionDigits: 0 })} QBC
            </span>
          </div>
        </div>
      )}

      {/* Bound address display */}
      {addressValidated && qbcAddress && (
        <div className="mb-4 text-xs text-text-secondary">
          QBC delivery: <span className="font-mono text-text-primary">{qbcAddress.slice(0, 8)}...{qbcAddress.slice(-8)}</span>
        </div>
      )}

      {/* Invest button */}
      <button
        onClick={handleInvest}
        disabled={!canInvest || txPending}
        className="w-full rounded-lg bg-gradient-to-r from-glow-cyan to-glow-gold py-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-bg-deep transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {txPending
          ? "Confirming..."
          : !isConnected
          ? "Connect Wallet First"
          : !addressValidated
          ? "Set QBC Address First"
          : amount <= 0
          ? "Enter Amount"
          : usdValue < 100
          ? "Minimum $100"
          : `Invest ${investAmount} ${selectedToken}`}
      </button>

      {/* Status messages */}
      {txHash && (
        <div className="mt-3 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">
          Transaction submitted:{" "}
          <a
            href={`https://etherscan.io/tx/${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono underline"
          >
            {txHash.slice(0, 10)}...{txHash.slice(-8)}
          </a>
        </div>
      )}
      {error && (
        <div className="mt-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <p className="mt-3 text-xs text-text-secondary">
        Funds go directly to treasury. Contract never holds funds.
      </p>
    </div>
  );
}
