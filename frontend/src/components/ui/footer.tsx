import Link from "next/link";

const navLinks = [
  { href: "/aether", label: "Aether Tree" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/explorer", label: "Block Explorer" },
  { href: "/wallet", label: "Wallet" },
  { href: "/bridge", label: "Bridge" },
  { href: "/qvm", label: "QVM Explorer" },
];

const resourceLinks = [
  { href: "/docs/whitepaper", label: "Whitepaper" },
  { href: "/docs/qvm", label: "QVM Docs" },
  { href: "/docs/aether", label: "Aether Tree Docs" },
  { href: "/docs/economics", label: "Economics" },
  { href: "/docs/qusd", label: "QUSD Stablecoin" },
  { href: "/docs/exchange", label: "Exchange" },
];

const socialLinks = [
  { href: "https://github.com/QuantumAI-Blockchain", label: "GitHub", icon: "github" },
  { href: "https://x.com/qu_bitcoin", label: "X / Twitter", icon: "x" },
  { href: "https://t.me/QuantumAI_Blockchain", label: "Telegram", icon: "telegram" },
];

function SocialIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "github":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
          <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
        </svg>
      );
    case "x":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      );
    case "telegram":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
          <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
        </svg>
      );
    default:
      return null;
  }
}

export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-bg-panel">
      <div className="mx-auto max-w-7xl px-4 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div>
            <span className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight glow-cyan">
              QBC
            </span>
            <p className="mt-3 font-[family-name:var(--font-reading)] text-sm leading-relaxed text-text-secondary">
              Physics-secured digital assets with post-quantum cryptography and
              the Aether Tree on-chain AGI engine.
            </p>
            <div className="mt-4 flex gap-3">
              {socialLinks.map(({ href, label, icon }) => (
                <a
                  key={icon}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={label}
                  className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-border-subtle hover:text-glow-cyan"
                >
                  <SocialIcon icon={icon} />
                </a>
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div>
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-[10px] font-semibold uppercase tracking-widest text-text-secondary">Navigate</h3>
            <ul className="space-y-2">
              {navLinks.map(({ href, label }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="font-[family-name:var(--font-reading)] text-sm text-text-secondary transition-colors hover:text-glow-cyan"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-[10px] font-semibold uppercase tracking-widest text-text-secondary">Resources</h3>
            <ul className="space-y-2">
              {resourceLinks.map(({ href, label }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="font-[family-name:var(--font-reading)] text-sm text-text-secondary transition-colors hover:text-glow-cyan"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Chain Info */}
          <div>
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-[10px] font-semibold uppercase tracking-widest text-text-secondary">Chain</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="font-[family-name:var(--font-reading)] text-text-secondary">Chain ID</dt>
                <dd className="font-[family-name:var(--font-code)] text-text-primary">3303</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-[family-name:var(--font-reading)] text-text-secondary">Block Time</dt>
                <dd className="font-[family-name:var(--font-code)] text-text-primary">3.3s</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-[family-name:var(--font-reading)] text-text-secondary">Max Supply</dt>
                <dd className="font-[family-name:var(--font-code)] text-text-primary">3.3B</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-[family-name:var(--font-reading)] text-text-secondary">Consensus</dt>
                <dd className="font-[family-name:var(--font-code)] text-text-primary">PoSA</dd>
              </div>
            </dl>
          </div>

          {/* Live Contracts */}
          <div className="sm:col-span-2 lg:col-span-4">
            <h3 className="mb-3 font-[family-name:var(--font-display)] text-[10px] font-semibold uppercase tracking-widest text-text-secondary">Verified Contracts</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1.5 font-[family-name:var(--font-display)] text-[9px] font-semibold uppercase tracking-widest" style={{ color: "#627eea" }}>Ethereum</p>
                <ul className="space-y-1 text-xs">
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">wQBC:</span>
                    <a href="https://etherscan.io/token/0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67" target="_blank" rel="noopener noreferrer" className="font-[family-name:var(--font-code)] text-glow-cyan transition-colors hover:underline">0xB7c8…Fa67</a>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">wQUSD:</span>
                    <a href="https://etherscan.io/token/0x884867d25552b6117F85428405aeAA208A8CAdB3" target="_blank" rel="noopener noreferrer" className="font-[family-name:var(--font-code)] text-glow-cyan transition-colors hover:underline">0x8848…CAdB3</a>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">Pool:</span>
                    <span className="font-[family-name:var(--font-code)] text-text-secondary">Uniswap V3 · 0.3%</span>
                  </li>
                </ul>
              </div>
              <div>
                <p className="mb-1.5 font-[family-name:var(--font-display)] text-[9px] font-semibold uppercase tracking-widest" style={{ color: "#f3ba2f" }}>BNB Chain</p>
                <ul className="space-y-1 text-xs">
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">wQBC:</span>
                    <a href="https://bscscan.com/token/0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147" target="_blank" rel="noopener noreferrer" className="font-[family-name:var(--font-code)] text-glow-cyan transition-colors hover:underline">0xA8dA…6147</a>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">wQUSD:</span>
                    <a href="https://bscscan.com/token/0xD137C89ed83d1D54802d07487bf1AF6e0b409BE3" target="_blank" rel="noopener noreferrer" className="font-[family-name:var(--font-code)] text-glow-cyan transition-colors hover:underline">0xD137…BE3</a>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="font-[family-name:var(--font-reading)] text-text-secondary">Pool:</span>
                    <a href="https://bscscan.com/address/0x3927EfB12bDaf7E2d9930A3581177a0646456abd" target="_blank" rel="noopener noreferrer" className="font-[family-name:var(--font-code)] text-text-secondary transition-colors hover:underline">PancakeSwap V2 · 0.25%</a>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-border-subtle pt-6 sm:flex-row">
          <p className="font-[family-name:var(--font-reading)] text-xs text-text-secondary">
            &copy; 2026 Quantum Blockchain. MIT License.
          </p>
          <p className="font-[family-name:var(--font-code)] text-[10px] tracking-wide text-text-secondary">
            Proof-of-SUSY-Alignment &middot; Dilithium5 &middot; QVM (167 Opcodes) &middot; Aether Tree AGI &middot; Multi-Chain Bridge
          </p>
        </div>
      </div>
    </footer>
  );
}
