#!/usr/bin/env python3
"""
Bridge Deployment Script for Qubitcoin

Deploys wQBC and wQUSD wrapped tokens to external EVM chains (Ethereum, BSC,
Polygon, etc.) and optionally Solana. Also handles transferring the initial
3.3B QUSD from deployer to a dedicated treasury address on QBC.

Usage:
    # Deploy to ETH + BNB
    python3 scripts/deploy/deploy_bridge.py --chains ethereum,bsc

    # Dry run (compile, check balances, no gas spent)
    python3 scripts/deploy/deploy_bridge.py --chains ethereum,bsc --dry-run

    # Deploy to Solana only
    python3 scripts/deploy/deploy_bridge.py --chains solana

    # Transfer QUSD to treasury only (no bridge deployment)
    python3 scripts/deploy/deploy_bridge.py --qusd-treasury-transfer --skip-bridge

    # All together
    python3 scripts/deploy/deploy_bridge.py --chains ethereum,bsc,solana --qusd-treasury-transfer

Prerequisites:
    pip install web3 py-solc-x
    # For Solana: install anchor CLI + solana CLI

Idempotent: skips contracts already in contract_registry.json under
"external:{chain}:wQBC" / "external:{chain}:wQUSD" keys.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.config import Config
from qubitcoin.utils.logger import get_logger

logger = get_logger("deploy_bridge")

# ─── Constants ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"
DEPLOY_JSON_PATH = PROJECT_ROOT / "deployment" / "crosschain" / "deploy.json"
ARTIFACTS_DIR = PROJECT_ROOT / "deployment" / "crosschain" / "artifacts"
CONTRACTS_DIR = PROJECT_ROOT / "src" / "qubitcoin" / "contracts" / "solidity"

# EVM chain configurations (subset of deploy.json, used as defaults)
EVM_CHAINS: Dict[str, Dict[str, Any]] = {
    "ethereum": {"chainId": 1, "name": "Ethereum Mainnet", "gasStrategy": "eip1559"},
    "bsc": {"chainId": 56, "name": "BNB Smart Chain", "gasStrategy": "legacy"},
    "polygon": {"chainId": 137, "name": "Polygon PoS", "gasStrategy": "eip1559"},
    "avalanche": {"chainId": 43114, "name": "Avalanche C-Chain", "gasStrategy": "eip1559"},
    "arbitrum": {"chainId": 42161, "name": "Arbitrum One", "gasStrategy": "eip1559"},
    "optimism": {"chainId": 10, "name": "Optimism", "gasStrategy": "eip1559"},
    "base": {"chainId": 8453, "name": "Base", "gasStrategy": "eip1559"},
}


# ─── ABI Encoding Helpers ────────────────────────────────────────────────────

def keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (EVM standard)."""
    try:
        import sha3
        return sha3.keccak_256(data).digest()
    except ImportError:
        try:
            from Crypto.Hash import keccak as _keccak
            return _keccak.new(digest_bits=256, data=data).digest()
        except ImportError:
            return hashlib.sha3_256(data).digest()


def function_selector(sig: str) -> bytes:
    """Compute 4-byte function selector from signature string."""
    return keccak256(sig.encode())[:4]


def encode_address(addr: str) -> bytes:
    """Encode an address as a 32-byte ABI word."""
    addr = addr.removeprefix("0x").lower()
    return bytes.fromhex(addr.zfill(64))


def encode_uint256(val: int) -> bytes:
    """Encode a uint256 as a 32-byte ABI word."""
    return val.to_bytes(32, "big")


# ─── Env File Parser ─────────────────────────────────────────────────────────

def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env / secure_key.env file into a dict."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


# ─── Registry ────────────────────────────────────────────────────────────────

def load_registry() -> Dict[str, Any]:
    """Load the contract registry (or empty dict if missing)."""
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def save_registry(registry: Dict[str, Any]) -> None:
    """Atomically save the contract registry."""
    tmp = REGISTRY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(registry, indent=2) + "\n")
    tmp.replace(REGISTRY_PATH)
    logger.info(f"Registry saved: {REGISTRY_PATH}")


# ─── Solidity Compiler ───────────────────────────────────────────────────────

class SolidityCompiler:
    """Compile Solidity contracts for external chain deployment via py-solc-x."""

    def __init__(self, solc_version: str = "0.8.28") -> None:
        self.solc_version = solc_version
        self._ensure_solcx()

    def _ensure_solcx(self) -> None:
        """Install the required solc version if not present."""
        try:
            import solcx
            installed = [str(v) for v in solcx.get_installed_solc_versions()]
            if self.solc_version not in installed:
                logger.info(f"Installing solc {self.solc_version}...")
                solcx.install_solc(self.solc_version)
            solcx.set_solc_version(self.solc_version)
        except ImportError:
            raise RuntimeError(
                "py-solc-x not installed. Run: pip install py-solc-x"
            )

    def _flatten_source(self, contract_path: Path) -> str:
        """Flatten a Solidity file by inlining its relative imports.

        Handles single-depth imports like:
            import "../proxy/Initializable.sol";
            import "../interfaces/IQBC20.sol";

        Deduplicates pragma and SPDX-License lines.
        """
        seen_files: set = set()
        seen_pragmas: set = set()
        lines_out: List[str] = []

        def _inline(fpath: Path) -> None:
            canonical = fpath.resolve()
            if canonical in seen_files:
                return
            seen_files.add(canonical)

            if not fpath.exists():
                raise FileNotFoundError(f"Import not found: {fpath}")

            for line in fpath.read_text().splitlines():
                stripped = line.strip()

                # Handle relative imports
                m = re.match(r'import\s+"([^"]+)"\s*;', stripped)
                if m:
                    import_path = fpath.parent / m.group(1)
                    _inline(import_path)
                    continue

                # Deduplicate SPDX and pragma
                if stripped.startswith("// SPDX-License"):
                    if stripped not in seen_pragmas:
                        seen_pragmas.add(stripped)
                        lines_out.append(line)
                    continue

                if stripped.startswith("pragma solidity"):
                    if stripped not in seen_pragmas:
                        seen_pragmas.add(stripped)
                        lines_out.append(line)
                    continue

                lines_out.append(line)

        _inline(contract_path)
        return "\n".join(lines_out)

    def compile_contract(
        self, contract_path: Path, contract_name: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Compile a contract and return (bytecode_hex, abi).

        Uses source flattening to resolve local imports, then compiles
        via solcx.compile_standard().
        """
        import solcx

        source = self._flatten_source(contract_path)
        filename = contract_path.name

        input_json = {
            "language": "Solidity",
            "sources": {filename: {"content": source}},
            "settings": {
                "outputSelection": {
                    filename: {
                        contract_name: ["abi", "evm.bytecode.object"]
                    }
                },
                "optimizer": {"enabled": True, "runs": 200},
                "evmVersion": "shanghai",
            },
        }

        output = solcx.compile_standard(input_json, allow_paths=[str(CONTRACTS_DIR)])

        contracts = output.get("contracts", {}).get(filename, {})
        if contract_name not in contracts:
            available = list(contracts.keys())
            raise RuntimeError(
                f"Contract '{contract_name}' not found in compiled output. "
                f"Available: {available}"
            )

        contract_out = contracts[contract_name]
        bytecode = contract_out["evm"]["bytecode"]["object"]
        abi = contract_out["abi"]

        # Cache artifact
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        artifact = {
            "contractName": contract_name,
            "abi": abi,
            "bytecode": bytecode,
            "compiler": f"solc-{self.solc_version}",
            "source": str(contract_path.relative_to(PROJECT_ROOT)),
        }
        artifact_path = ARTIFACTS_DIR / f"{contract_name}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")
        logger.info(f"Artifact cached: {artifact_path.name} ({len(bytecode) // 2} bytes)")

        return bytecode, abi


# ─── EVM Chain Deployer ──────────────────────────────────────────────────────

class EVMChainDeployer:
    """Deploy contracts to any EVM-compatible chain via web3.py."""

    def __init__(
        self,
        chain_name: str,
        rpc_url: str,
        private_key: str,
        expected_chain_id: int,
    ) -> None:
        self.chain_name = chain_name
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.expected_chain_id = expected_chain_id
        self.w3: Any = None
        self.account: Any = None

    def connect(self) -> None:
        """Connect to the EVM chain and validate chain ID."""
        from web3 import Web3

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(
                f"Cannot connect to {self.chain_name} RPC: {self.rpc_url}"
            )

        chain_id = self.w3.eth.chain_id
        if chain_id != self.expected_chain_id:
            raise ValueError(
                f"Chain ID mismatch on {self.chain_name}: "
                f"expected {self.expected_chain_id}, got {chain_id}"
            )

        # BSC returns non-standard extraData — inject POA middleware
        if chain_id == 56:
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                logger.info("BSC POA middleware injected")
            except ImportError:
                logger.warning("ExtraDataToPOAMiddleware not available, BSC may fail")

        self.account = self.w3.eth.account.from_key(self.private_key)
        balance = self.w3.eth.get_balance(self.account.address)
        balance_eth = self.w3.from_wei(balance, "ether")

        logger.info(
            f"Connected to {self.chain_name} (chain {chain_id}), "
            f"deployer={self.account.address}, "
            f"balance={balance_eth:.6f} native"
        )

        if balance == 0:
            raise ValueError(
                f"Deployer has zero balance on {self.chain_name}. "
                f"Fund {self.account.address} before deploying."
            )

    def deploy_contract(
        self,
        bytecode: str,
        abi: List[Dict[str, Any]],
        contract_name: str,
        gas_limit: int = 3_000_000,
    ) -> Tuple[str, str]:
        """Deploy a contract and return (contract_address, tx_hash).

        Uses local signing with eth_sendRawTransaction (works with remote RPCs).
        """
        from web3 import Web3

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        contract = self.w3.eth.contract(abi=abi, bytecode="0x" + bytecode)

        # Build deployment transaction
        tx: Dict[str, Any] = {
            "from": self.account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "chainId": self.expected_chain_id,
            "data": contract.bytecode,
        }

        # Gas pricing strategy
        chain_cfg = EVM_CHAINS.get(self.chain_name, {})
        if chain_cfg.get("gasStrategy") == "eip1559":
            latest = self.w3.eth.get_block("latest")
            base_fee = latest.get("baseFeePerGas", 0)
            max_priority = self.w3.to_wei(2, "gwei")
            tx["maxFeePerGas"] = base_fee * 2 + max_priority
            tx["maxPriorityFeePerGas"] = max_priority
        else:
            tx["gasPrice"] = self.w3.eth.gas_price

        # Sign and send
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        logger.info(
            f"[{self.chain_name}] Deploying {contract_name}... tx={tx_hash_hex[:16]}..."
        )

        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"[{self.chain_name}] {contract_name} deployment FAILED. "
                f"tx={tx_hash_hex}"
            )

        address = receipt["contractAddress"]
        gas_used = receipt["gasUsed"]
        logger.info(
            f"[{self.chain_name}] {contract_name} deployed at {address} "
            f"(gas={gas_used:,}, tx={tx_hash_hex[:16]}...)"
        )
        return address, tx_hash_hex

    def call_initialize(
        self,
        contract_address: str,
        init_data: bytes,
        gas_limit: int = 500_000,
    ) -> str:
        """Call initialize() on a deployed contract. Returns tx hash."""
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx: Dict[str, Any] = {
            "from": self.account.address,
            "to": self.w3.to_checksum_address(contract_address),
            "nonce": nonce,
            "gas": gas_limit,
            "chainId": self.expected_chain_id,
            "data": "0x" + init_data.hex(),
        }

        chain_cfg = EVM_CHAINS.get(self.chain_name, {})
        if chain_cfg.get("gasStrategy") == "eip1559":
            latest = self.w3.eth.get_block("latest")
            base_fee = latest.get("baseFeePerGas", 0)
            max_priority = self.w3.to_wei(2, "gwei")
            tx["maxFeePerGas"] = base_fee * 2 + max_priority
            tx["maxPriorityFeePerGas"] = max_priority
        else:
            tx["gasPrice"] = self.w3.eth.gas_price

        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"[{self.chain_name}] initialize() FAILED at {contract_address}. "
                f"tx={tx_hash_hex}"
            )

        logger.info(
            f"[{self.chain_name}] initialize() OK at {contract_address} "
            f"(gas={receipt['gasUsed']:,})"
        )
        return tx_hash_hex


# ─── Solana Deployer ─────────────────────────────────────────────────────────

class SolanaDeployer:
    """Deploy Anchor programs to Solana (requires anchor + solana CLI)."""

    def __init__(self, cluster: str = "mainnet-beta") -> None:
        self.cluster = cluster

    def check_tools(self) -> bool:
        """Verify anchor and solana CLI are installed."""
        for tool in ("anchor", "solana"):
            if shutil.which(tool) is None:
                logger.error(f"{tool} CLI not found. Install it first.")
                return False
        logger.info("Solana toolchain OK (anchor + solana CLI found)")
        return True

    def deploy_program(
        self,
        program_dir: Path,
        keypair_path: str,
    ) -> Optional[str]:
        """Build and deploy an Anchor program. Returns program ID or None."""
        if not program_dir.exists():
            logger.error(f"Solana program directory not found: {program_dir}")
            return None

        env = os.environ.copy()
        env["ANCHOR_WALLET"] = keypair_path

        # Build
        logger.info(f"Building Solana program: {program_dir.name}...")
        result = subprocess.run(
            ["anchor", "build"],
            cwd=str(program_dir),
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            logger.error(f"anchor build failed:\n{result.stderr}")
            return None

        # Deploy
        logger.info(
            f"Deploying {program_dir.name} to {self.cluster}..."
        )
        result = subprocess.run(
            [
                "anchor", "deploy",
                "--provider.cluster", self.cluster,
                "--provider.wallet", keypair_path,
            ],
            cwd=str(program_dir),
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            logger.error(f"anchor deploy failed:\n{result.stderr}")
            return None

        # Extract program ID from output
        for line in result.stdout.splitlines():
            if "Program Id:" in line:
                program_id = line.split("Program Id:")[-1].strip()
                logger.info(
                    f"Solana program deployed: {program_dir.name} = {program_id}"
                )
                return program_id

        logger.warning("Could not extract program ID from anchor output")
        return None


# ─── QUSD Treasury Transfer ──────────────────────────────────────────────────

class QUSDTreasuryTransfer:
    """Transfer initial 3.3B QUSD from deployer to treasury on QBC chain."""

    def __init__(self, qbc_rpc_url: str, deployer_address: str) -> None:
        self.rpc_url = qbc_rpc_url.rstrip("/")
        self.deployer = deployer_address

    def _post_jsonrpc(self, method: str, params: list) -> Any:
        """Send JSON-RPC to QBC node."""
        import requests
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        r = requests.post(f"{self.rpc_url}/", json=payload, timeout=30)
        r.raise_for_status()
        result = r.json()
        if result.get("error"):
            raise RuntimeError(f"QBC RPC error: {result['error']}")
        return result.get("result")

    def check_qusd_balance(self, address: str, qusd_contract: str) -> int:
        """Read QUSD balance for an address (returns raw amount with decimals)."""
        # balanceOf(address) selector = 0x70a08231
        sel = function_selector("balanceOf(address)")
        data = "0x" + (sel + encode_address(address)).hex()
        result = self._post_jsonrpc(
            "eth_call",
            [{"to": qusd_contract, "data": data}, "latest"],
        )
        if result and result != "0x":
            return int(result, 16)
        return 0

    def transfer_qusd(
        self,
        qusd_contract: str,
        treasury_address: str,
        amount: int,
        dry_run: bool = False,
    ) -> Optional[str]:
        """Transfer QUSD from deployer to treasury.

        Args:
            qusd_contract: QUSD token contract address on QBC
            treasury_address: Destination treasury address
            amount: Raw amount (with decimals, e.g. 3.3B * 10^8)
            dry_run: If True, only check balance without sending

        Returns:
            Transaction hash or None on dry-run
        """
        balance = self.check_qusd_balance(self.deployer, qusd_contract)
        human_balance = balance / 10**8
        human_amount = amount / 10**8

        logger.info(
            f"QUSD deployer balance: {human_balance:,.2f} QUSD "
            f"(target transfer: {human_amount:,.2f} QUSD)"
        )

        if balance < amount:
            raise ValueError(
                f"Insufficient QUSD balance: have {human_balance:,.2f}, "
                f"need {human_amount:,.2f}"
            )

        if dry_run:
            logger.info("[DRY RUN] Would transfer QUSD to treasury — skipping")
            return None

        # transfer(address,uint256) = 0xa9059cbb
        sel = function_selector("transfer(address,uint256)")
        data = sel + encode_address(treasury_address) + encode_uint256(amount)

        nonce_result = self._post_jsonrpc(
            "eth_getTransactionCount", [self.deployer, "latest"]
        )
        nonce = int(nonce_result, 16) if isinstance(nonce_result, str) else int(nonce_result)

        tx = {
            "from": self.deployer,
            "to": qusd_contract,
            "data": "0x" + data.hex(),
            "gas": hex(500_000),
            "nonce": hex(nonce),
            "value": "0x0",
        }

        tx_hash = self._post_jsonrpc("eth_sendTransaction", [tx])
        logger.info(
            f"QUSD treasury transfer sent: {human_amount:,.2f} QUSD → "
            f"{treasury_address[:16]}... (tx={tx_hash})"
        )
        return tx_hash


# ─── Bridge Orchestrator ─────────────────────────────────────────────────────

class BridgeOrchestrator:
    """Top-level orchestrator for cross-chain bridge deployment."""

    def __init__(
        self,
        keys: Dict[str, str],
        env_vars: Dict[str, str],
        registry: Dict[str, Any],
        dry_run: bool = False,
    ) -> None:
        self.keys = keys
        self.env = env_vars
        self.registry = registry
        self.dry_run = dry_run
        self.compiler: Optional[SolidityCompiler] = None

    def _get_compiler(self) -> SolidityCompiler:
        """Lazy-init Solidity compiler."""
        if self.compiler is None:
            self.compiler = SolidityCompiler()
        return self.compiler

    def _get_rpc_url(self, chain: str) -> str:
        """Resolve RPC URL for a chain from env vars or deploy.json."""
        env_key = f"{chain.upper()}_RPC_URL"
        url = self.env.get(env_key, os.getenv(env_key, ""))
        if url:
            return url

        # Fall back to deploy.json
        if DEPLOY_JSON_PATH.exists():
            deploy_cfg = json.loads(DEPLOY_JSON_PATH.read_text())
            chain_cfg = deploy_cfg.get("chains", {}).get(chain, {})
            return chain_cfg.get("rpc", "")

        return ""

    def deploy_evm(self, chains: List[str]) -> Dict[str, Dict[str, str]]:
        """Deploy wQBC + wQUSD to EVM chains.

        Returns dict mapping "external:{chain}:{token}" → deployment info.
        """
        results: Dict[str, Dict[str, str]] = {}
        eth_private_key = self.keys.get("ETH_DEPLOYER_PRIVATE_KEY", "")
        if not eth_private_key:
            logger.error(
                "ETH_DEPLOYER_PRIVATE_KEY not found in secure_key.env. "
                "Cannot deploy to EVM chains."
            )
            return results

        bridge_operator = (
            self.env.get("BRIDGE_OPERATOR_ADDRESS", "")
            or os.getenv("BRIDGE_OPERATOR_ADDRESS", "")
        )

        compiler = self._get_compiler()

        # Compile wQBC and wQUSD once
        logger.info("Compiling wQBC (bridge)...")
        wqbc_path = CONTRACTS_DIR / "bridge" / "wQBC.sol"
        wqbc_bytecode, wqbc_abi = compiler.compile_contract(wqbc_path, "wQBC")

        logger.info("Compiling wQUSD...")
        wqusd_path = CONTRACTS_DIR / "qusd" / "wQUSD.sol"
        wqusd_bytecode, wqusd_abi = compiler.compile_contract(wqusd_path, "wQUSD")

        for chain in chains:
            if chain == "solana":
                continue  # Solana handled separately

            chain_cfg = EVM_CHAINS.get(chain)
            if not chain_cfg:
                logger.warning(f"Unknown EVM chain: {chain}, skipping")
                continue

            rpc_url = self._get_rpc_url(chain)
            if not rpc_url:
                logger.error(
                    f"No RPC URL for {chain}. Set {chain.upper()}_RPC_URL in .env "
                    f"or update deployment/crosschain/deploy.json"
                )
                continue

            chain_id = chain_cfg["chainId"]

            # Check if already deployed
            wqbc_key = f"external:{chain}:wQBC"
            wqusd_key = f"external:{chain}:wQUSD"
            if wqbc_key in self.registry and wqusd_key in self.registry:
                existing_wqbc = self.registry[wqbc_key].get("address", "")
                existing_wqusd = self.registry[wqusd_key].get("address", "")
                if existing_wqbc and existing_wqusd:
                    logger.info(
                        f"[{chain}] Already deployed: wQBC={existing_wqbc[:16]}..., "
                        f"wQUSD={existing_wqusd[:16]}... (skipping)"
                    )
                    continue

            if self.dry_run:
                logger.info(
                    f"[DRY RUN] [{chain}] Would deploy wQBC + wQUSD "
                    f"(chain_id={chain_id}, rpc={rpc_url[:40]}...)"
                )
                continue

            # Connect
            deployer = EVMChainDeployer(chain, rpc_url, eth_private_key, chain_id)
            try:
                deployer.connect()
            except Exception as e:
                logger.error(f"[{chain}] Connection failed: {e}")
                continue

            # Deploy wQBC
            try:
                wqbc_addr, wqbc_tx = deployer.deploy_contract(
                    wqbc_bytecode, wqbc_abi, "wQBC"
                )

                # Initialize wQBC: initialize(bridge)
                # bridge = deployer address initially (will be updated to relayer)
                bridge_addr = bridge_operator or deployer.account.address
                init_data = (
                    function_selector("initialize(address)")
                    + encode_address(bridge_addr)
                )
                deployer.call_initialize(wqbc_addr, init_data)

                self.registry[wqbc_key] = {
                    "address": wqbc_addr,
                    "chainId": chain_id,
                    "deployer": deployer.account.address,
                    "txHash": wqbc_tx,
                    "bridge": bridge_addr,
                }
                results[wqbc_key] = self.registry[wqbc_key]
                save_registry(self.registry)

            except Exception as e:
                logger.error(f"[{chain}] wQBC deployment failed: {e}")
                continue

            # Deploy wQUSD
            try:
                wqusd_addr, wqusd_tx = deployer.deploy_contract(
                    wqusd_bytecode, wqusd_abi, "wQUSD"
                )

                # Initialize wQUSD: initialize(qusdToken, bridgeOperator)
                # qusdToken = address(0) on external chains (no native QUSD)
                # bridgeOperator = deployer or configured operator
                operator = bridge_operator or deployer.account.address
                init_data = (
                    function_selector("initialize(address,address)")
                    + encode_address("0x0000000000000000000000000000000000000000")
                    + encode_address(operator)
                )
                deployer.call_initialize(wqusd_addr, init_data)

                self.registry[wqusd_key] = {
                    "address": wqusd_addr,
                    "chainId": chain_id,
                    "deployer": deployer.account.address,
                    "txHash": wqusd_tx,
                    "bridgeOperator": operator,
                }
                results[wqusd_key] = self.registry[wqusd_key]
                save_registry(self.registry)

            except Exception as e:
                logger.error(f"[{chain}] wQUSD deployment failed: {e}")
                continue

            logger.info(
                f"[{chain}] Bridge deployment complete: "
                f"wQBC={wqbc_addr}, wQUSD={wqusd_addr}"
            )

        return results

    def deploy_solana(self, keypair_path: str) -> Dict[str, Dict[str, str]]:
        """Deploy wqbc + wqusd Anchor programs to Solana."""
        results: Dict[str, Dict[str, str]] = {}

        # Check if already deployed
        wqbc_key = "external:solana:wQBC"
        wqusd_key = "external:solana:wQUSD"
        if wqbc_key in self.registry and wqusd_key in self.registry:
            existing_wqbc = self.registry[wqbc_key].get("programId", "")
            existing_wqusd = self.registry[wqusd_key].get("programId", "")
            if existing_wqbc and existing_wqusd:
                logger.info(
                    f"[solana] Already deployed: wQBC={existing_wqbc[:16]}..., "
                    f"wQUSD={existing_wqusd[:16]}... (skipping)"
                )
                return results

        deployer = SolanaDeployer(
            cluster=os.getenv("SOLANA_CLUSTER", "mainnet-beta")
        )

        if not deployer.check_tools():
            logger.error("Solana deployment aborted: missing tools")
            return results

        if not keypair_path:
            logger.error(
                "SOLANA_DEPLOYER_KEYPAIR_PATH not set in secure_key.env. "
                "Cannot deploy to Solana."
            )
            return results

        if not Path(keypair_path).exists():
            logger.error(f"Solana keypair file not found: {keypair_path}")
            return results

        if self.dry_run:
            logger.info("[DRY RUN] [solana] Would deploy wqbc + wqusd programs")
            return results

        # Deploy wqbc
        wqbc_dir = PROJECT_ROOT / "deployment" / "solana" / "wqbc"
        if wqbc_dir.exists():
            program_id = deployer.deploy_program(wqbc_dir, keypair_path)
            if program_id:
                self.registry[wqbc_key] = {"programId": program_id}
                results[wqbc_key] = self.registry[wqbc_key]
                save_registry(self.registry)
        else:
            logger.warning(
                f"Solana wqbc program directory not found: {wqbc_dir}. "
                f"Create an Anchor project there first."
            )

        # Deploy wqusd
        wqusd_dir = PROJECT_ROOT / "deployment" / "solana" / "wqusd"
        if wqusd_dir.exists():
            program_id = deployer.deploy_program(wqusd_dir, keypair_path)
            if program_id:
                self.registry[wqusd_key] = {"programId": program_id}
                results[wqusd_key] = self.registry[wqusd_key]
                save_registry(self.registry)
        else:
            logger.warning(
                f"Solana wqusd program directory not found: {wqusd_dir}. "
                f"Create an Anchor project there first."
            )

        return results

    def transfer_qusd(
        self,
        qbc_rpc_url: str,
        deployer_address: str,
        qusd_contract: str,
        treasury_address: str,
    ) -> Optional[str]:
        """Transfer initial 3.3B QUSD to treasury address on QBC chain."""
        if not qusd_contract:
            # Try to read from registry
            qusd_entry = self.registry.get("QUSD", {})
            qusd_contract = qusd_entry.get("proxy", "")
            if not qusd_contract:
                logger.error(
                    "QUSD contract address not found. Deploy QUSD first "
                    "(Phase 8) or set QUSD_TOKEN_ADDRESS in .env"
                )
                return None

        if not treasury_address:
            logger.error(
                "QUSD_TREASURY_ADDRESS not set. Configure it in .env first."
            )
            return None

        transfer = QUSDTreasuryTransfer(qbc_rpc_url, deployer_address)

        # 3.3B QUSD with 8 decimals
        amount = 3_300_000_000 * 10**8

        return transfer.transfer_qusd(
            qusd_contract, treasury_address, amount, dry_run=self.dry_run
        )


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy Qubitcoin bridge contracts to external chains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --chains ethereum,bsc
  %(prog)s --chains ethereum,bsc --dry-run
  %(prog)s --chains solana
  %(prog)s --qusd-treasury-transfer --skip-bridge
  %(prog)s --chains ethereum,bsc,solana --qusd-treasury-transfer
        """,
    )
    parser.add_argument(
        "--chains",
        type=str,
        default="",
        help="Comma-separated list of chains to deploy to "
             "(ethereum,bsc,polygon,avalanche,arbitrum,optimism,base,solana)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compile and validate without deploying (no gas spent)",
    )
    parser.add_argument(
        "--qusd-treasury-transfer",
        action="store_true",
        help="Transfer initial QUSD supply from deployer to treasury",
    )
    parser.add_argument(
        "--skip-bridge",
        action="store_true",
        help="Skip bridge deployment (use with --qusd-treasury-transfer)",
    )
    parser.add_argument(
        "--key-file",
        type=str,
        default="",
        help="Path to secure_key.env (default: <project_root>/secure_key.env)",
    )
    parser.add_argument(
        "--qbc-rpc-url",
        type=str,
        default="http://localhost:5000",
        help="QBC node RPC URL (default: http://localhost:5000)",
    )

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("  QUBITCOIN BRIDGE DEPLOYMENT")
    print("  Cross-chain wQBC + wQUSD deployment")
    print("=" * 60)

    # Load keys
    key_path = Path(args.key_file) if args.key_file else PROJECT_ROOT / "secure_key.env"
    keys = parse_env_file(key_path)
    if key_path.exists():
        logger.info(f"Loaded keys from {key_path}")
    else:
        logger.warning(f"Key file not found: {key_path}")

    # Load env vars (from .env or os.environ)
    env_path = PROJECT_ROOT / ".env"
    env_vars = parse_env_file(env_path)

    # Load registry
    registry = load_registry()
    logger.info(f"Registry loaded: {len(registry)} entries")

    # QBC deployer identity
    qbc_address = keys.get("ADDRESS", Config.ADDRESS)
    if not qbc_address:
        logger.warning("No QBC ADDRESS found in secure_key.env")

    # Create orchestrator
    orchestrator = BridgeOrchestrator(
        keys=keys,
        env_vars=env_vars,
        registry=registry,
        dry_run=args.dry_run,
    )

    # Parse chains
    chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()]

    # Step 1: QUSD Treasury Transfer
    if args.qusd_treasury_transfer:
        print("\n--- QUSD Treasury Transfer ---")
        qusd_contract = (
            env_vars.get("QUSD_TOKEN_ADDRESS", "")
            or os.getenv("QUSD_TOKEN_ADDRESS", "")
            or Config.QUSD_TOKEN_ADDRESS
        )
        treasury = (
            env_vars.get("QUSD_TREASURY_ADDRESS", "")
            or os.getenv("QUSD_TREASURY_ADDRESS", "")
            or Config.QUSD_TREASURY_ADDRESS
        )
        orchestrator.transfer_qusd(
            qbc_rpc_url=args.qbc_rpc_url,
            deployer_address=qbc_address,
            qusd_contract=qusd_contract,
            treasury_address=treasury,
        )

    # Step 2: Bridge Deployment
    if not args.skip_bridge and chains:
        # EVM chains
        evm_chains = [c for c in chains if c != "solana"]
        if evm_chains:
            print(f"\n--- EVM Bridge Deployment: {', '.join(evm_chains)} ---")
            orchestrator.deploy_evm(evm_chains)

        # Solana
        if "solana" in chains:
            print("\n--- Solana Bridge Deployment ---")
            solana_keypair = keys.get("SOLANA_DEPLOYER_KEYPAIR_PATH", "")
            orchestrator.deploy_solana(solana_keypair)

    # Summary
    print("\n" + "=" * 60)
    print("  DEPLOYMENT SUMMARY")
    print("=" * 60)

    external_keys = sorted(k for k in registry if k.startswith("external:"))
    if external_keys:
        for key in external_keys:
            entry = registry[key]
            addr = entry.get("address") or entry.get("programId") or "N/A"
            chain_id = entry.get("chainId", "")
            print(f"  {key}: {addr[:20]}... (chain={chain_id})")
    else:
        print("  No external bridge contracts deployed yet.")

    if args.dry_run:
        print("\n  [DRY RUN] No transactions were sent.")

    print("=" * 60)


if __name__ == "__main__":
    main()
