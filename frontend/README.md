# Qubitcoin Frontend

Production web application for the Qubitcoin blockchain at [qbc.network](https://qbc.network). Built with Next.js 16, React 19, TypeScript 5.x, and TailwindCSS 4. Features live chain monitoring, an AI chat interface (Aether Tree), wallet integration, contract management, and bridge operations. Deployed via Cloudflare Tunnel.

## Key Features

- **Landing Page** — Quantum particle field visualization, live chain statistics, Aether chat widget.
- **Aether Chat** — Full-page conversational interface to the Aether Tree AI engine with streaming responses.
- **Dashboard** — Real-time mining metrics, network health, contract console, and chain explorer.
- **Wallet** — MetaMask integration via ethers.js v6, native QBC wallet, CRYSTALS-Dilithium key generation (WASM).
- **Bridge** — Multi-chain bridge interface for cross-chain transfers.
- **Exchange** — On-chain exchange interface for QBC trading pairs.
- **Explorer** — Block and transaction explorer with search.
- **QVM Console** — Contract browser, bytecode disassembler, storage inspector.
- **3D Visualization** — Three.js + React Three Fiber for network and knowledge graph rendering.

## Quick Start

```bash
# Install dependencies
pnpm install

# Development
pnpm dev          # http://localhost:3000

# Production build
pnpm build
pnpm start        # http://localhost:3000

# Exposed via Cloudflare Tunnel → qbc.network
```

## Architecture

```
frontend/
├── src/
│   ├── app/                 # Next.js App Router
│   │   ├── page.tsx         # Landing page
│   │   ├── aether/          # Aether Tree chat
│   │   ├── dashboard/       # Mining, network, contracts
│   │   ├── wallet/          # Wallet management
│   │   ├── bridge/          # Cross-chain bridge
│   │   ├── exchange/        # Trading interface
│   │   ├── explorer/        # Block/tx explorer
│   │   ├── qvm/             # QVM contract tools
│   │   ├── rewards/         # Staking and rewards
│   │   ├── launchpad/       # Token launch platform
│   │   └── invest/          # Seed round (restricted)
│   ├── components/          # Shared React components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utilities, API clients, constants
│   ├── stores/              # Zustand state management
│   └── styles/              # Global styles, TailwindCSS
├── public/                  # Static assets
├── tests/                   # Vitest unit + Playwright E2E
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### Technology Stack

| Layer            | Technology                              |
|------------------|-----------------------------------------|
| Framework        | Next.js 16 (App Router, RSC)            |
| UI               | React 19 + TypeScript 5.x (strict)      |
| Styling          | TailwindCSS 4 + Framer Motion           |
| State            | Zustand (global) + TanStack Query (API) |
| 3D / Viz         | Three.js + React Three Fiber + D3       |
| Wallet           | ethers.js v6 (MetaMask, WalletConnect)  |
| Package Manager  | pnpm                                    |

### API Integration

| Endpoint          | Description                    |
|-------------------|--------------------------------|
| `api.qbc.network` | REST API (chain, wallet, mining) |
| `qbc.network/rpc` | JSON-RPC proxy to node (MetaMask) |
| `/aether/*`       | Aether Tree AI endpoints       |

### Design System

- **Background:** `#0a0a0f` | **Primary:** `#00ff88` | **Accent:** `#7c3aed`
- **Typography:** Space Grotesk (headings), Inter (body), JetBrains Mono (code)

## Testing

```bash
# Unit tests
pnpm test

# E2E tests
pnpm test:e2e

# Type checking
pnpm tsc --noEmit
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Frontend Repo](https://github.com/QuantumAI-Blockchain/qubitcoin-frontend)
- [Live Site](https://qbc.network)
