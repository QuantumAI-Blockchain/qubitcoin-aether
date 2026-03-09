# Smart Contract Developer Guide

> **How to write, deploy, and interact with smart contracts on Qubitcoin's QVM.**

---

## 1. Overview

Qubitcoin's **Quantum Virtual Machine (QVM)** is a full EVM-compatible bytecode interpreter with quantum extensions. You can deploy Solidity contracts compiled with standard tools (solc, Hardhat, Foundry) and interact with them via MetaMask and ethers.js.

**Key features:**
- 155 standard EVM opcodes (full Ethereum compatibility)
- 10 quantum extension opcodes (0xF0-0xF9)
- Institutional compliance engine (KYC/AML at the VM level)
- Gas metering compatible with Ethereum tooling
- Keccak-256 hashing (EVM-compatible)

---

## 2. Getting Started

### 2.1 Prerequisites

- Solidity compiler: `solc ^0.8.20` or Hardhat/Foundry
- ethers.js v6 or web3.js
- A running Qubitcoin node at `http://localhost:5000`

### 2.2 Configure Hardhat

```javascript
// hardhat.config.js
module.exports = {
  solidity: "0.8.20",
  networks: {
    qubitcoin: {
      url: "http://localhost:5000/jsonrpc",
      chainId: 3303,
      accounts: [process.env.PRIVATE_KEY],
    },
    qubitcoin_testnet: {
      url: "https://testnet-rpc.qbc.network/jsonrpc",
      chainId: 3304,
      accounts: [process.env.PRIVATE_KEY],
    },
  },
};
```

### 2.3 Configure Foundry

```toml
# foundry.toml
[profile.default]
solc_version = "0.8.20"

[rpc_endpoints]
qubitcoin = "http://localhost:5000/jsonrpc"
```

---

## 3. Token Standards

### 3.1 QBC-20 (Fungible Tokens)

ERC-20 compatible. Standard interface for fungible tokens on QVM.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./QBC20.sol";

contract MyToken is QBC20 {
    constructor() QBC20("My Token", "MTK", 8, 1000000 * 10**8) {}
}
```

**Interface:**
```solidity
function name() external view returns (string);
function symbol() external view returns (string);
function decimals() external view returns (uint8);
function totalSupply() external view returns (uint256);
function balanceOf(address account) external view returns (uint256);
function transfer(address to, uint256 amount) external returns (bool);
function approve(address spender, uint256 amount) external returns (bool);
function allowance(address owner, address spender) external view returns (uint256);
function transferFrom(address from, address to, uint256 amount) external returns (bool);
```

### 3.2 QBC-721 (Non-Fungible Tokens)

ERC-721 compatible. Standard interface for NFTs on QVM.

```solidity
import "./QBC721.sol";

contract MyNFT is QBC721 {
    constructor() QBC721("My NFT Collection", "MNFT") {}

    function mintTo(address to, string memory uri) external {
        mint(to, uri);
    }
}
```

### 3.3 QBC-1155 (Multi-Token)

ERC-1155 compatible. Single contract for both fungible and non-fungible tokens.

```solidity
import "./QBC1155.sol";

contract GameItems is QBC1155 {
    uint256 public constant GOLD = 0;
    uint256 public constant SWORD = 1;

    constructor() QBC1155("https://game.example/api/item/{id}.json") {
        // Mint 1M gold (fungible)
        _mint(msg.sender, GOLD, 1000000, "");
        // Mint 1 legendary sword (non-fungible)
        _mint(msg.sender, SWORD, 1, "");
    }
}
```

### 3.4 ERC-20-QC (Compliance-Aware Token)

Extends QBC-20 with compliance checks at the VM level. Every transfer goes through
the QCOMPLIANCE opcode before execution.

```solidity
import "./ERC20QC.sol";

contract RegulatedToken is ERC20QC {
    constructor()
        ERC20QC(
            "Regulated Token",
            "REG",
            8,
            1000000 * 10**8,
            1  // Minimum KYC level required (BASIC)
        )
    {}
}
```

**Additional features over QBC-20:**
- `requiredKYCLevel` — minimum KYC level for transfers
- `complianceCheck()` — called before every transfer
- `setComplianceLevel()` — owner can update required level
- `frozen` mapping — freeze individual addresses
- `freeze(address)` / `unfreeze(address)` — compliance officer controls
- `complianceOfficer` role — separate from owner

---

## 4. Deployment

### 4.1 Deployment Fees

Deploying contracts costs QBC. The fee structure is:

```
Total Fee = BASE_FEE + (bytecode_size_kb × PER_KB_FEE)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| Base fee | 1.0 QBC | Minimum deployment cost |
| Per-KB fee | 0.1 QBC | Additional cost per KB of bytecode |
| Template discount | 50% | Discount for pre-audited templates |

Fees are dynamically priced via the QUSD oracle (target ~$5 USD per deploy).

#### Estimate Before Deploying

```bash
curl "http://localhost:5000/qvm/deploy/estimate?bytecode_size_kb=5.0&contract_type=token"
```

### 4.2 Deploy via ethers.js

```typescript
import { JsonRpcProvider, ContractFactory } from "ethers";

const provider = new JsonRpcProvider("http://localhost:5000/jsonrpc");
const factory = new ContractFactory(abi, bytecode, signer);
const contract = await factory.deploy(...constructorArgs);
await contract.waitForDeployment();
console.log("Deployed at:", await contract.getAddress());
```

### 4.3 Deploy via JSON-RPC

```bash
curl -X POST http://localhost:5000/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_sendTransaction",
    "params": [{
      "from": "0xYourAddress",
      "data": "0x608060405234801561001057600080fd5b50...",
      "gas": "0xF4240"
    }],
    "id": 1
  }'
```

### 4.4 Template Contracts

Pre-built, audited contract templates are available at a 50% fee discount:

| Template | Description | File |
|----------|-------------|------|
| `token` | QBC-20 fungible token | `contracts/templates.py` |
| `nft` | QBC-721 non-fungible token | `contracts/templates.py` |
| `launchpad` | Token sale/IDO contract | `contracts/templates.py` |
| `escrow` | Multi-party escrow | `contracts/templates.py` |
| `governance` | DAO voting/proposals | `contracts/templates.py` |

---

## 5. Contract Interaction

### 5.1 Read Contract State

```typescript
const contract = new Contract(address, abi, provider);
const balance = await contract.balanceOf(userAddress);
const name = await contract.name();
```

Or via raw JSON-RPC:

```bash
# eth_call (read-only)
curl -X POST http://localhost:5000/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
      "to": "0xContractAddress",
      "data": "0x70a08231000000000000000000000000YourAddress"
    }, "latest"],
    "id": 1
  }'
```

### 5.2 Write to Contract

```typescript
const contract = new Contract(address, abi, signer);
const tx = await contract.transfer(recipient, amount);
const receipt = await tx.wait();
```

### 5.3 Query Storage Directly

```bash
# Read storage slot 0 of a contract
curl http://localhost:5000/qvm/storage/0xContractAddress/0x0
```

### 5.4 Query Event Logs

```bash
curl -X POST http://localhost:5000/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_getLogs",
    "params": [{
      "address": "0xContractAddress",
      "topics": ["0xddf252ad..."],
      "fromBlock": "0x0",
      "toBlock": "latest"
    }],
    "id": 1
  }'
```

---

## 6. Quantum Opcodes in Contracts

The QVM supports 10 quantum extension opcodes. These are accessed via inline assembly
or through precompiled contract interfaces.

### 6.1 Quantum State Management

```solidity
// Create a 4-qubit quantum state (density matrix)
assembly {
    push1 4        // n_qubits = 4
    push1 0xF0     // QCREATE opcode
}

// Measure quantum state
assembly {
    push1 stateId
    push1 0xF1     // QMEASURE opcode
}
```

### 6.2 Compliance Check in Contract

```solidity
// Check if address is compliant before proceeding
assembly {
    push20 addr
    push1 0xF5     // QCOMPLIANCE
}
// Stack now contains compliance level (0-3)
```

### 6.3 Risk Score Query

```solidity
assembly {
    push20 addr
    push1 0xF6     // QRISK
}
// Stack: risk_score (0-100)
```

### 6.4 Gas Costs for Quantum Opcodes

Quantum operations have exponential gas scaling based on qubit count:

```
gas = base_cost + 5,000 × 2^n_qubits
```

Maximum 32 qubits supported. A 4-qubit QCREATE costs `5,000 + 80,000 = 85,000` gas.

---

## 7. Contract Verification

### 7.1 Source Verification

After deployment, you can verify contract source code matches deployed bytecode:

```bash
curl http://localhost:5000/qvm/contract/0xContractAddress
```

Returns contract metadata including bytecode hash, creator, and type.

### 7.2 Proxy Contracts

QVM supports the EIP-1967 transparent proxy pattern for upgradeable contracts:

- Implementation slot: `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`
- Admin slot: `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103`

Upgrades are tracked in an audit trail accessible via the admin API.

---

## 8. Security Best Practices

1. **Use template contracts** when possible — they are pre-audited and get fee discounts
2. **Check compliance** — use the QCOMPLIANCE opcode or ERC-20-QC standard for regulated tokens
3. **Test on testnet first** — Chain ID 3304 is the test network
4. **Mind gas limits** — Block gas limit is 30,000,000. Quantum ops are expensive.
5. **Reentrancy protection** — QVM enforces call depth limits and provides reentrancy guards
6. **Integer overflow** — QVM uses 256-bit unsigned arithmetic with wrapping (same as EVM)
7. **Access control** — Use `onlyOwner` modifiers or role-based access for sensitive functions

---

## 9. Contract File Reference

```
contracts/solidity/
├── tokens/
│   ├── QBC20.sol          # Fungible token standard
│   ├── QBC721.sol         # NFT standard
│   ├── QBC1155.sol        # Multi-token standard
│   └── ERC20QC.sol        # Compliance-aware token
├── qusd/
│   ├── QUSD.sol           # Stablecoin
│   ├── QUSDReserve.sol    # Reserve pool
│   ├── QUSDOracle.sol     # Price oracle
│   └── ...                # 4 more QUSD contracts
├── aether/
│   ├── AetherKernel.sol   # AGI orchestration
│   ├── ProofOfThought.sol # PoT validation
│   └── ...                # 15+ Aether contracts
└── bridge/
    └── wQBC.sol           # Wrapped QBC for cross-chain
```

---

*For the full API reference, see [Developer SDK Guide](SDK.md).*
*For Aether Tree integration, see [Aether Integration Guide](AETHER_INTEGRATION.md).*

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)
*For Aether Tree integration, see [Aether Integration Guide](AETHER_INTEGRATION.md).*
