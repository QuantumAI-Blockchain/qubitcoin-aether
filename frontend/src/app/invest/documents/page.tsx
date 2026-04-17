"use client";

import { InvestorNav } from "@/components/investor/investor-nav";

export default function DocumentsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 pt-24 pb-16">
      <InvestorNav />

      <h1 className="mb-6 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-text-primary">
        Documents
      </h1>

      <div className="space-y-6">
        {/* Token Sale Terms */}
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-glow-cyan">
            Token Sale Terms
          </h3>
          <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
            <p>
              <strong className="text-text-primary">Price:</strong> 1 QBC = $1 USD.
              ETH investments are converted at the current Chainlink ETH/USD oracle rate.
              Stablecoin investments (USDC, USDT, DAI) are accepted at face value.
            </p>
            <p>
              <strong className="text-text-primary">Hard Cap:</strong> $10,000,000 USD.
            </p>
            <p>
              <strong className="text-text-primary">What You Receive:</strong> For every
              $1 invested, you receive 1 QBC + 1 QUSD + a proportional share of the
              lifetime revenue pool.
            </p>
            <p>
              <strong className="text-text-primary">Vesting:</strong> 6-month cliff + 24-month
              linear unlock. First tokens claimable 6 months after TGE. Fully vested 30 months
              after TGE.
            </p>
            <p>
              <strong className="text-text-primary">Revenue Share:</strong> 10% of all protocol
              fees are distributed perpetually to seed investors, proportional to their investment.
              Revenue sources include Exchange trading fees and Aether Tree chat fees — recurring
              for life with no expiration.
            </p>
            <p>
              <strong className="text-text-primary">Example:</strong> A $1,000,000 investment
              (10% of the round) receives 1,000,000 QBC + 1,000,000 QUSD + 10% of the recurring
              revenue pool (1% of all protocol fees) — forever.
            </p>
            <p>
              <strong className="text-text-primary">Delivery:</strong> QBC and QUSD tokens are
              delivered on the Quantum Blockchain (not Ethereum). You must bind a QBC address
              before investing.
            </p>
          </div>
        </div>

        {/* Revenue Sources */}
        <div className="rounded-xl border border-glow-cyan/20 bg-glow-cyan/5 p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-glow-cyan">
            Revenue Sources
          </h3>
          <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
            <p>
              The 10% investor revenue pool is funded by recurring protocol fees from:
            </p>
            <div className="space-y-2">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 inline-block h-2 w-2 rounded-full bg-glow-gold" />
                <div>
                  <strong className="text-text-primary">Exchange Trading Fees</strong>
                  <p className="text-xs">Every trade on the Quantum DEX generates a fee. 10% of all exchange fees flow to the investor revenue pool.</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="mt-0.5 inline-block h-2 w-2 rounded-full bg-glow-cyan" />
                <div>
                  <strong className="text-text-primary">Aether Tree Chat Fees</strong>
                  <p className="text-xs">Every interaction with the on-chain AI costs a micro-fee in QBC. 10% of all Aether fees flow to the investor revenue pool.</p>
                </div>
              </div>
            </div>
            <p className="text-xs italic">
              As the network grows and more users trade and interact with Aether Tree,
              revenue to investors grows proportionally. There is no cap or expiration on
              revenue share — it runs for the lifetime of the protocol.
            </p>
          </div>
        </div>

        {/* Fund Allocation */}
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-glow-gold">
            Fund Allocation
          </h3>
          <div className="space-y-3 text-sm">
            {[
              { label: "Liquidity", pct: 60, color: "bg-glow-cyan", desc: "DEX liquidity pools (QBC/ETH, QBC/USDC, QUSD pairs)" },
              { label: "Development", pct: 15, color: "bg-violet-500", desc: "Core protocol development, audits, infrastructure" },
              { label: "Marketing", pct: 10, color: "bg-glow-gold", desc: "Community growth, partnerships, exchange listings" },
              { label: "Security", pct: 10, color: "bg-red-500", desc: "Smart contract audits, bug bounties, penetration testing" },
              { label: "Operations", pct: 5, color: "bg-blue-500", desc: "Legal, compliance, node infrastructure, team" },
            ].map((item) => (
              <div key={item.label}>
                <div className="mb-1 flex justify-between">
                  <span className="text-text-primary font-medium">{item.label}</span>
                  <span className="font-mono text-text-primary">{item.pct}%</span>
                </div>
                <div className="mb-1 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${item.pct}%` }} />
                </div>
                <p className="text-xs text-text-secondary">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Disclosure */}
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-amber-400">
            Risk Disclosure
          </h3>
          <div className="space-y-2 text-sm text-text-secondary leading-relaxed">
            <p>
              Investing in cryptocurrency involves significant risk. QBC is a new blockchain
              network and token values may fluctuate significantly. Do not invest more than you
              can afford to lose.
            </p>
            <p>
              The smart contracts have been developed with security best practices (CEI pattern,
              reentrancy guards, Chainlink oracle validation) but have not been formally audited
              by a third party.
            </p>
            <p>
              Revenue share depends on protocol adoption and fee generation. There is no guarantee
              of returns. Past performance of similar protocols does not indicate future results.
            </p>
            <p>
              QUSD is a stablecoin native to the Quantum Blockchain. Its peg to $1 USD is
              maintained algorithmically and may not always hold at exactly $1.
            </p>
          </div>
        </div>

        {/* Contract Addresses */}
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
            Contract Addresses
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-secondary">SeedRound (Ethereum)</span>
              <span className="font-mono text-text-primary">TBD</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">InvestorVesting (QBC)</span>
              <span className="font-mono text-text-primary">TBD</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">RevenueDistributor (QBC)</span>
              <span className="font-mono text-text-primary">TBD</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
