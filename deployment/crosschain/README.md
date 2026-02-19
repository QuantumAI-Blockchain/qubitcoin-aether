# Cross-Chain Deployment Templates

Deployment configurations for wQBC and wQUSD on supported external chains.

## Supported Chains

| Chain | Token | Contract |
|-------|-------|----------|
| Ethereum (ETH) | wQBC, wQUSD | ERC-20 (Solidity) |
| Polygon (MATIC) | wQBC, wQUSD | ERC-20 (Solidity) |
| BNB Chain (BSC) | wQBC, wQUSD | BEP-20 (Solidity) |
| Avalanche (AVAX) | wQBC, wQUSD | ERC-20 (Solidity) |
| Arbitrum (ARB) | wQBC, wQUSD | ERC-20 (Solidity) |
| Optimism (OP) | wQBC, wQUSD | ERC-20 (Solidity) |
| Base | wQBC, wQUSD | ERC-20 (Solidity) |

## Deployment

Each chain directory contains a `deploy.json` with:
- Contract source reference
- Constructor arguments
- Bridge operator address (placeholder)
- Chain-specific RPC and explorer URLs

The wQBC.sol and wQUSD.sol contracts in `contracts/solidity/tokens/` and
`contracts/solidity/qusd/` are chain-agnostic ERC-20 contracts. The same
Solidity source deploys on all EVM-compatible chains.
