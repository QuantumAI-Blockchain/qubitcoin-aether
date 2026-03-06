#!/usr/bin/env python3
"""
Contract Deployment Script for Qubitcoin
Deploys all 40 contracts behind transparent proxy (QBCProxy + ProxyAdmin).

Usage:
    python3 scripts/deploy_contracts.py [--rpc-url URL] [--deployer-key FILE]

Deployment order follows dependency tiers. Each contract is deployed as:
  1. Deploy implementation (raw bytecode)
  2. Deploy QBCProxy(implementation, proxyAdmin, initData)
  3. Record proxy address in registry

The registry is saved to contract_registry.json for the frontend/backend to use.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests

from qubitcoin.config import Config
from qubitcoin.utils.logger import get_logger

logger = get_logger("deploy_contracts")

# ─── ABI Encoding Helpers ──────────────────────────────────────────────────

def encode_address(addr: str) -> bytes:
    """Encode an address as a 32-byte ABI word."""
    addr = addr.removeprefix("0x").lower()
    return bytes.fromhex(addr.zfill(64))

def encode_uint256(val: int) -> bytes:
    """Encode a uint256 as a 32-byte ABI word."""
    return val.to_bytes(32, "big")

def encode_string(s: str) -> bytes:
    """Encode a string as ABI dynamic data (offset + length + padded data)."""
    encoded = s.encode("utf-8")
    length = len(encoded)
    padded_len = ((length + 31) // 32) * 32
    return encode_uint256(length) + encoded.ljust(padded_len, b"\x00")

def encode_uint8(val: int) -> bytes:
    """Encode a uint8 as a 32-byte ABI word."""
    return encode_uint256(val)

def selector(sig: str) -> bytes:
    """Compute the 4-byte function selector from a signature."""
    from hashlib import sha3_256
    # Use keccak256 for Solidity compatibility
    import hashlib as _hl
    k = _hl.new("sha3_256")
    # Actually QVM uses SHA3-256 / Keccak-256
    # For selector matching, use the same hash the QVM uses
    return hashlib.sha256(sig.encode()).digest()[:4]

def keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (EVM standard)."""
    import hashlib as _hl
    return _hl.sha3_256(data).digest()

def function_selector(sig: str) -> bytes:
    """4-byte function selector using keccak256."""
    return keccak256(sig.encode())[:4]


# ─── RPC Client ──────────────────────────────────────────────────────────────

class RPCClient:
    """Thin client for QBC JSON-RPC and REST endpoints."""

    def __init__(self, base_url: str, deployer_address: str, private_key_hex: str, public_key_hex: str):
        self.base_url = base_url.rstrip("/")
        self.deployer = deployer_address
        self.private_key_hex = private_key_hex
        self.public_key_hex = public_key_hex
        self.nonce = 0  # Track deployer nonce locally

    def _post_jsonrpc(self, method: str, params: list) -> dict:
        """Send a JSON-RPC request with retry on 429."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        for attempt in range(10):
            r = requests.post(f"{self.base_url}/", json=payload, timeout=30)
            if r.status_code == 429:
                wait = min(2 ** attempt, 30)
                logger.warning(f"Rate limited (429), waiting {wait}s (attempt {attempt+1}/10)...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            result = r.json()
            if result.get("error"):
                raise RuntimeError(f"RPC error: {result['error']}")
            time.sleep(0.3)  # Base delay to avoid rate limits
            return result.get("result")
        raise RuntimeError(f"RPC rate limited after 10 retries: {method}")

    def _post_rest(self, path: str, data: dict) -> dict:
        """Send a REST POST request."""
        r = requests.post(f"{self.base_url}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def _get_rest(self, path: str) -> dict:
        """Send a REST GET request."""
        r = requests.get(f"{self.base_url}{path}", timeout=30)
        r.raise_for_status()
        return r.json()

    def get_nonce(self) -> int:
        """Get the current nonce for the deployer account."""
        result = self._post_jsonrpc("eth_getTransactionCount", [self.deployer, "latest"])
        if isinstance(result, str):
            return int(result, 16)
        return int(result)

    def deploy_bytecode(self, bytecode_hex: str, gas: int = 10_000_000) -> Optional[str]:
        """Deploy raw bytecode and return the contract address."""
        tx = {
            "from": self.deployer,
            "data": "0x" + bytecode_hex,
            "gas": hex(gas),
            "nonce": hex(self.nonce),
            "value": "0x0",
        }
        result = self._post_jsonrpc("eth_sendTransaction", [tx])
        self.nonce += 1

        if result:
            # The result should be a tx hash; we need to get the receipt
            receipt = self._get_receipt(result)
            if receipt and receipt.get("contractAddress"):
                return receipt["contractAddress"]
            elif receipt and receipt.get("contract_address"):
                return receipt["contract_address"]
        return None

    def send_tx(self, to: str, data_hex: str, gas: int = 5_000_000, value: int = 0) -> Optional[str]:
        """Send a transaction to a contract."""
        tx = {
            "from": self.deployer,
            "to": to,
            "data": "0x" + data_hex,
            "gas": hex(gas),
            "nonce": hex(self.nonce),
            "value": hex(value),
        }
        result = self._post_jsonrpc("eth_sendTransaction", [tx])
        self.nonce += 1
        return result

    def _get_receipt(self, tx_hash: str) -> Optional[dict]:
        """Get transaction receipt. Polls until tx is mined (up to ~30s)."""
        for attempt in range(30):
            try:
                result = self._post_jsonrpc("eth_getTransactionReceipt", [tx_hash])
                if result:
                    return result
            except Exception:
                pass
            time.sleep(1.0)
        logger.warning(f"Receipt not found after 30s: {tx_hash}")
        return None

    def call(self, to: str, data_hex: str) -> Optional[str]:
        """eth_call (read-only)."""
        result = self._post_jsonrpc("eth_call", [
            {"from": self.deployer, "to": to, "data": "0x" + data_hex},
            "latest"
        ])
        return result


# ─── Contract Deployer ───────────────────────────────────────────────────────

class ContractDeployer:
    """Orchestrates deployment of all contracts behind proxies."""

    # Placeholder bytecode for contracts (in production, read from compiled artifacts)
    # For now we use a minimal deployment bytecode pattern:
    #   PUSH runtime_code | CODECOPY | RETURN
    MINIMAL_RUNTIME = bytes([
        0x60, 0x01,  # PUSH1 0x01 (minimal non-empty runtime)
        0x60, 0x00,  # PUSH1 0x00
        0x53,        # MSTORE8
        0x60, 0x01,  # PUSH1 0x01
        0x60, 0x00,  # PUSH1 0x00
        0xf3,        # RETURN
    ])

    def __init__(self, rpc: RPCClient, sol_dir: str):
        self.rpc = rpc
        self.sol_dir = Path(sol_dir)
        self.registry: Dict[str, Dict[str, str]] = {}
        self.proxy_admin_address: Optional[str] = None

    def _read_sol(self, rel_path: str) -> str:
        """Read a Solidity file and return its content."""
        full = self.sol_dir / rel_path
        return full.read_text()

    def _make_init_code(self, runtime_hex: str = "") -> str:
        """Create minimal deployment init code that returns runtime bytecode.

        QVM executes init code and stores the returned bytes as the contract's
        runtime bytecode.  This helper wraps any runtime hex (or a placeholder)
        in a tiny deployer preamble:

            PUSH<len> PUSH1 <offset> PUSH1 0 CODECOPY
            PUSH<len> PUSH1 0 RETURN
            <runtime bytes>
        """
        if not runtime_hex:
            # Placeholder runtime: single STOP opcode
            runtime_hex = "00"
        runtime = bytes.fromhex(runtime_hex)
        rlen = len(runtime)

        # Build init code
        init = bytearray()
        # CODECOPY(destOffset=0, offset=initCodeLen, size=rlen)
        init_prefix_len = 0  # placeholder, computed after building
        # We'll build, measure, then rebuild

        def build(offset: int) -> bytearray:
            code = bytearray()
            # PUSH rlen
            if rlen <= 0xFF:
                code += bytes([0x60, rlen])
            else:
                code += bytes([0x61]) + rlen.to_bytes(2, "big")
            # PUSH offset
            if offset <= 0xFF:
                code += bytes([0x60, offset])
            else:
                code += bytes([0x61]) + offset.to_bytes(2, "big")
            # PUSH 0
            code += bytes([0x60, 0x00])
            # CODECOPY
            code += bytes([0x39])
            # PUSH rlen
            if rlen <= 0xFF:
                code += bytes([0x60, rlen])
            else:
                code += bytes([0x61]) + rlen.to_bytes(2, "big")
            # PUSH 0
            code += bytes([0x60, 0x00])
            # RETURN
            code += bytes([0xf3])
            return code

        # First pass to get init code length
        init1 = build(0)
        init_len = len(init1)
        # Second pass with correct offset
        init2 = build(init_len)
        assert len(init2) == init_len, f"Init code length changed: {len(init2)} vs {init_len}"

        full_code = init2 + runtime
        return full_code.hex()

    def deploy_impl(self, name: str, runtime_hex: str = "") -> str:
        """Deploy an implementation contract (no proxy)."""
        init_code = self._make_init_code(runtime_hex)
        addr = self.rpc.deploy_bytecode(init_code)
        if not addr:
            raise RuntimeError(f"Failed to deploy implementation: {name}")
        logger.info(f"  Impl deployed: {name} → {addr}")
        return addr

    def deploy_proxy(self, name: str, impl_addr: str, init_data_hex: str = "") -> str:
        """Deploy a QBCProxy pointing to impl, with ProxyAdmin as admin.

        Since QBCProxy's constructor takes (impl, admin, initData), we encode
        these as constructor args appended to the proxy's init code.

        For QVM, we deploy the proxy as a contract whose runtime is the
        proxy fallback logic (DELEGATECALL to impl). The constructor stores
        impl and admin in ERC-1967 slots and optionally delegatecalls initData.
        """
        if not self.proxy_admin_address:
            raise RuntimeError("ProxyAdmin must be deployed first")

        # Build proxy init code that:
        # 1. Stores implementation in ERC-1967 slot
        # 2. Stores admin in ERC-1967 slot
        # 3. Optionally delegatecalls initData
        # 4. Returns proxy runtime (delegatecall fallback)

        impl_addr_clean = impl_addr.removeprefix("0x").lower().zfill(40)
        admin_addr_clean = self.proxy_admin_address.removeprefix("0x").lower().zfill(40)

        # ERC-1967 slots
        IMPL_SLOT = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
        ADMIN_SLOT = "b53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

        # Build init code as raw bytecode
        init = bytearray()

        # Store implementation address in ERC-1967 slot
        # PUSH20 impl_addr
        init += bytes([0x73]) + bytes.fromhex(impl_addr_clean)
        # PUSH32 IMPL_SLOT
        init += bytes([0x7f]) + bytes.fromhex(IMPL_SLOT)
        # SSTORE
        init += bytes([0x55])

        # Store admin address in ERC-1967 slot
        # PUSH20 admin_addr
        init += bytes([0x73]) + bytes.fromhex(admin_addr_clean)
        # PUSH32 ADMIN_SLOT
        init += bytes([0x7f]) + bytes.fromhex(ADMIN_SLOT)
        # SSTORE
        init += bytes([0x55])

        # If initData provided, delegatecall to impl with initData
        if init_data_hex:
            init_data = bytes.fromhex(init_data_hex)
            dlen = len(init_data)

            # Store initData in memory at offset 0
            # Use CODECOPY to load initData from end of init code
            init_data_offset = 0  # will be patched
            # For simplicity, store initData word-by-word with MSTORE
            for i in range(0, dlen, 32):
                chunk = init_data[i:i+32].ljust(32, b"\x00")
                # PUSH32 chunk
                init += bytes([0x7f]) + chunk
                # PUSH1 offset
                init += bytes([0x60, i])
                # MSTORE
                init += bytes([0x52])

            # DELEGATECALL(gas, impl, inOffset=0, inSize=dlen, retOffset=0, retSize=0)
            # PUSH1 0 (retSize)
            init += bytes([0x60, 0x00])
            # PUSH1 0 (retOffset)
            init += bytes([0x60, 0x00])
            # PUSH dlen (inSize)
            if dlen <= 0xFF:
                init += bytes([0x60, dlen])
            else:
                init += bytes([0x61]) + dlen.to_bytes(2, "big")
            # PUSH1 0 (inOffset)
            init += bytes([0x60, 0x00])
            # PUSH20 impl_addr
            init += bytes([0x73]) + bytes.fromhex(impl_addr_clean)
            # GAS
            init += bytes([0x5a])
            # DELEGATECALL
            init += bytes([0xf4])
            # POP result (ignore success for init)
            init += bytes([0x50])

        # Return proxy runtime code (DELEGATECALL fallback)
        # The runtime code loads impl from ERC-1967 slot and delegates
        runtime = self._build_proxy_runtime()
        rlen = len(runtime)

        # CODECOPY runtime to memory
        runtime_offset = len(init) + (
            2 + (2 if rlen > 0xFF else 2) + 1 +  # push rlen, push offset, push 0, codecopy
            (2 if rlen > 0xFF else 2) + 2 + 1     # push rlen, push 0, return
        )
        # Recalculate with actual sizes
        tail = bytearray()
        # PUSH rlen
        if rlen <= 0xFF:
            tail += bytes([0x60, rlen])
        else:
            tail += bytes([0x61]) + rlen.to_bytes(2, "big")
        runtime_offset_actual = len(init) + len(tail) + 2 + 1 + (2 if rlen <= 0xFF else 3) + 2 + 1
        # PUSH runtime_offset
        if runtime_offset_actual <= 0xFF:
            tail += bytes([0x60, runtime_offset_actual])
        else:
            tail += bytes([0x61]) + runtime_offset_actual.to_bytes(2, "big")
        # PUSH1 0
        tail += bytes([0x60, 0x00])
        # CODECOPY
        tail += bytes([0x39])
        # PUSH rlen
        if rlen <= 0xFF:
            tail += bytes([0x60, rlen])
        else:
            tail += bytes([0x61]) + rlen.to_bytes(2, "big")
        # PUSH1 0
        tail += bytes([0x60, 0x00])
        # RETURN
        tail += bytes([0xf3])

        # Recalculate offset with actual tail length
        actual_offset = len(init) + len(tail)
        # Rebuild tail with correct offset
        tail2 = bytearray()
        if rlen <= 0xFF:
            tail2 += bytes([0x60, rlen])
        else:
            tail2 += bytes([0x61]) + rlen.to_bytes(2, "big")
        if actual_offset <= 0xFF:
            tail2 += bytes([0x60, actual_offset])
        else:
            tail2 += bytes([0x61]) + actual_offset.to_bytes(2, "big")
        tail2 += bytes([0x60, 0x00, 0x39])  # PUSH1 0, CODECOPY
        if rlen <= 0xFF:
            tail2 += bytes([0x60, rlen])
        else:
            tail2 += bytes([0x61]) + rlen.to_bytes(2, "big")
        tail2 += bytes([0x60, 0x00, 0xf3])  # PUSH1 0, RETURN

        # Verify offset is still correct after rebuilding tail
        new_offset = len(init) + len(tail2)
        if new_offset != actual_offset:
            # Third pass if lengths changed
            tail3 = bytearray()
            if rlen <= 0xFF:
                tail3 += bytes([0x60, rlen])
            else:
                tail3 += bytes([0x61]) + rlen.to_bytes(2, "big")
            if new_offset <= 0xFF:
                tail3 += bytes([0x60, new_offset])
            else:
                tail3 += bytes([0x61]) + new_offset.to_bytes(2, "big")
            tail3 += bytes([0x60, 0x00, 0x39])
            if rlen <= 0xFF:
                tail3 += bytes([0x60, rlen])
            else:
                tail3 += bytes([0x61]) + rlen.to_bytes(2, "big")
            tail3 += bytes([0x60, 0x00, 0xf3])
            tail2 = tail3

        full_init = bytes(init) + bytes(tail2) + runtime
        addr = self.rpc.deploy_bytecode(full_init.hex())
        if not addr:
            raise RuntimeError(f"Failed to deploy proxy: {name}")

        self.registry[name] = {
            "proxy": addr,
            "implementation": impl_addr,
        }
        logger.info(f"  Proxy deployed: {name} → {addr} (impl: {impl_addr})")
        return addr

    def _build_proxy_runtime(self) -> bytes:
        """Build minimal proxy runtime bytecode (DELEGATECALL fallback).

        Runtime logic:
            1. Load implementation address from ERC-1967 slot
            2. Copy calldata to memory
            3. DELEGATECALL to implementation
            4. Copy returndata
            5. Return or revert based on success
        """
        IMPL_SLOT = bytes.fromhex("360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc")

        code = bytearray()

        # calldatacopy(0, 0, calldatasize)
        code += bytes([0x36])  # CALLDATASIZE
        code += bytes([0x60, 0x00])  # PUSH1 0
        code += bytes([0x60, 0x00])  # PUSH1 0
        code += bytes([0x37])  # CALLDATACOPY

        # Load implementation from storage
        # PUSH32 IMPL_SLOT
        code += bytes([0x7f]) + IMPL_SLOT
        # SLOAD
        code += bytes([0x54])

        # DELEGATECALL(gas, impl, 0, calldatasize, 0, 0)
        code += bytes([0x60, 0x00])  # PUSH1 0 (retSize)
        code += bytes([0x60, 0x00])  # PUSH1 0 (retOffset)
        code += bytes([0x36])        # CALLDATASIZE (inSize)
        code += bytes([0x60, 0x00])  # PUSH1 0 (inOffset)
        # Stack: retSize, retOffset, inSize, inOffset — need: gas, addr, inOff, inSz, retOff, retSz
        # Correct order for DELEGATECALL: gas, addr, inOffset, inSize, retOffset, retSize
        # Rebuild in correct order:

        code2 = bytearray()
        # calldatacopy(destOffset=0, offset=0, size=calldatasize)
        code2 += bytes([0x36])          # CALLDATASIZE
        code2 += bytes([0x60, 0x00])    # PUSH1 0
        code2 += bytes([0x60, 0x00])    # PUSH1 0
        code2 += bytes([0x37])          # CALLDATACOPY

        # Prepare DELEGATECALL args (pushed in reverse order for stack)
        code2 += bytes([0x60, 0x00])    # PUSH1 0     → retSize
        code2 += bytes([0x60, 0x00])    # PUSH1 0     → retOffset
        code2 += bytes([0x36])          # CALLDATASIZE → inSize
        code2 += bytes([0x60, 0x00])    # PUSH1 0     → inOffset
        # Load impl address
        code2 += bytes([0x7f]) + IMPL_SLOT  # PUSH32 IMPL_SLOT
        code2 += bytes([0x54])              # SLOAD → impl address
        # GAS
        code2 += bytes([0x5a])          # GAS
        # DELEGATECALL
        code2 += bytes([0xf4])

        # returndatacopy(0, 0, returndatasize)
        code2 += bytes([0x3d])          # RETURNDATASIZE
        code2 += bytes([0x60, 0x00])    # PUSH1 0
        code2 += bytes([0x60, 0x00])    # PUSH1 0
        code2 += bytes([0x3e])          # RETURNDATACOPY

        # if success: return(0, returndatasize) else: revert(0, returndatasize)
        # Stack has DELEGATECALL result (0 or 1)
        # But we already consumed it... need to dup before returndatacopy
        # Let's redo:

        code3 = bytearray()
        # calldatacopy(0, 0, calldatasize)
        code3 += bytes([0x36, 0x60, 0x00, 0x60, 0x00, 0x37])

        # DELEGATECALL(gas, impl, 0, calldatasize, 0, 0)
        code3 += bytes([0x60, 0x00])    # retSize = 0
        code3 += bytes([0x60, 0x00])    # retOffset = 0
        code3 += bytes([0x36])          # inSize = calldatasize
        code3 += bytes([0x60, 0x00])    # inOffset = 0
        code3 += bytes([0x7f]) + IMPL_SLOT
        code3 += bytes([0x54])          # SLOAD → addr
        code3 += bytes([0x5a])          # GAS
        code3 += bytes([0xf4])          # DELEGATECALL → success

        # returndatacopy(0, 0, returndatasize)
        code3 += bytes([0x3d, 0x60, 0x00, 0x60, 0x00, 0x3e])

        # Stack: [success]
        # If success == 0: revert(0, returndatasize)
        # Else: return(0, returndatasize)
        # PUSH jumpdest for success case
        success_pc = len(code3) + 5 + 1  # PUSH1 + JUMPI + ... adjusted below
        # Actually let's use a simpler pattern:
        # ISZERO → if fail jump to revert
        code3 += bytes([0x15])          # ISZERO (success → 0 means revert)

        revert_pc = len(code3) + 3      # PUSH1 revert_pc, JUMPI
        return_start = revert_pc        # after JUMPI
        # Wait, let me compute carefully

        # After ISZERO, stack = [!success]
        # PUSH1 <revert_label>
        # JUMPI → if !success, jump to revert
        # (fall through to return)

        # return(0, returndatasize)
        # Then revert(0, returndatasize)

        # Let me just hardcode the offsets:
        # Current position: len(code3) after ISZERO
        pos = len(code3)
        # PUSH1 revert_label (pos + 2 + 3d + 60 00 + f3 = pos + 2 + 6)
        return_block = bytes([0x3d, 0x60, 0x00, 0xf3])  # RETURNDATASIZE, PUSH1 0, RETURN
        revert_label = pos + 2 + len(return_block)  # skip PUSH1+JUMPI + return block
        code3 += bytes([0x60, revert_label])  # PUSH1 revert_label
        code3 += bytes([0x57])                # JUMPI

        # Return path (success)
        code3 += bytes([0x3d, 0x60, 0x00, 0xf3])  # RETURNDATASIZE, PUSH1 0, RETURN

        # Revert path
        code3 += bytes([0x5b])                # JUMPDEST
        code3 += bytes([0x3d, 0x60, 0x00, 0xfd])  # RETURNDATASIZE, PUSH1 0, REVERT

        return bytes(code3)

    def deploy_with_proxy(self, name: str, init_data_hex: str = "") -> str:
        """Deploy implementation + proxy, return proxy address."""
        impl = self.deploy_impl(name)
        proxy = self.deploy_proxy(name, impl, init_data_hex)
        return proxy

    def encode_initialize_kernel(self) -> str:
        """Encode AetherKernel.initializeBase() call."""
        return function_selector("initializeBase()").hex()

    def encode_initialize_address(self, func_sig: str, addr: str) -> str:
        """Encode initialize(address) call."""
        sel = function_selector(func_sig)
        return (sel + encode_address(addr)).hex()

    def encode_initialize_2addr(self, func_sig: str, addr1: str, addr2: str) -> str:
        """Encode initialize(address,address) call."""
        sel = function_selector(func_sig)
        return (sel + encode_address(addr1) + encode_address(addr2)).hex()

    def encode_initialize_addr_uint(self, func_sig: str, addr: str, val: int) -> str:
        """Encode initialize(address,uint256) call."""
        sel = function_selector(func_sig)
        return (sel + encode_address(addr) + encode_uint256(val)).hex()

    def save_registry(self, path: str = "contract_registry.json"):
        """Save the deployment registry to a JSON file."""
        with open(path, "w") as f:
            json.dump(self.registry, f, indent=2)
        logger.info(f"Registry saved to {path} ({len(self.registry)} contracts)")

    def deploy_all(self):
        """Deploy all contracts in dependency order."""
        logger.info("=" * 60)
        logger.info("QUBITCOIN CONTRACT DEPLOYMENT")
        logger.info("=" * 60)

        # ── Step 0: Deploy ProxyAdmin (no proxy, direct deploy) ──────────
        logger.info("\n[Step 0] Deploying ProxyAdmin...")
        self.proxy_admin_address = self.deploy_impl("ProxyAdmin")
        self.registry["ProxyAdmin"] = {
            "address": self.proxy_admin_address,
            "type": "direct",
        }
        logger.info(f"  ProxyAdmin: {self.proxy_admin_address}")

        # ── Step 1: Deploy AetherKernel ──────────────────────────────────
        logger.info("\n[Step 1] Deploying AetherKernel...")
        init_data = self.encode_initialize_kernel()
        kernel = self.deploy_with_proxy("AetherKernel", init_data)

        # ── Step 2: Deploy Kernel dependencies ───────────────────────────
        logger.info("\n[Step 2] Deploying Kernel dependencies...")

        node_registry = self.deploy_with_proxy(
            "NodeRegistry",
            self.encode_initialize_address("initialize(address)", kernel)
        )

        message_bus = self.deploy_with_proxy(
            "MessageBus",
            self.encode_initialize_addr_uint(
                "initialize(address,uint256)", kernel, 1_000_000  # 0.01 QBC baseFee
            )
        )

        susy_engine = self.deploy_with_proxy(
            "SUSYEngine",
            self.encode_initialize_2addr("initialize(address,address)", kernel, node_registry)
        )

        consciousness = self.deploy_with_proxy(
            "ConsciousnessDashboard",
            self.encode_initialize_address("initialize(address)", kernel)
        )

        # Call AetherKernel.initializeDependencies(nodeRegistry, messageBus, susyEngine, consciousness)
        logger.info("  Calling AetherKernel.initializeDependencies...")
        deps_sel = function_selector(
            "initializeDependencies(address,address,address,address)"
        )
        deps_data = (
            deps_sel
            + encode_address(node_registry)
            + encode_address(message_bus)
            + encode_address(susy_engine)
            + encode_address(consciousness)
        )
        self.rpc.send_tx(kernel, deps_data.hex())

        # ── Step 3: Deploy remaining Aether contracts ────────────────────
        logger.info("\n[Step 3] Deploying Aether Tree contracts...")

        validator_registry = self.deploy_with_proxy(
            "ValidatorRegistry",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        proof_of_thought = self.deploy_with_proxy(
            "ProofOfThought",
            self.encode_initialize_2addr(
                "initialize(address,address)", kernel, validator_registry
            )
        )
        task_market = self.deploy_with_proxy(
            "TaskMarket",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        # RewardDistributor.initialize(address _kernel, address _qbcToken)
        # QBC20 token is deployed in Step 6; initialize post-deploy or pass placeholder
        reward_distributor = self.deploy_with_proxy("RewardDistributor")

        phase_sync = self.deploy_with_proxy(
            "PhaseSync",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        global_workspace = self.deploy_with_proxy(
            "GlobalWorkspace",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        synaptic_staking = self.deploy_with_proxy(
            "SynapticStaking",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        ventricle_router = self.deploy_with_proxy(
            "VentricleRouter",
            self.encode_initialize_address("initialize(address)", message_bus)
        )

        gas_oracle = self.deploy_with_proxy(
            "GasOracle",
            self.encode_initialize_addr_uint(
                "initialize(address,uint256)", kernel, 100_000_000  # 1.0 QBC initial base fee
            )
        )
        treasury_dao = self.deploy_with_proxy(
            "TreasuryDAO",
            function_selector("initialize()").hex()
        )

        # Safety contracts
        constitutional_ai = self.deploy_with_proxy(
            "ConstitutionalAI",
            self.encode_initialize_address("initialize(address)", kernel)
        )
        emergency_shutdown = self.deploy_with_proxy(
            "EmergencyShutdown",
            self.encode_initialize_address("initialize(address)", kernel)
        )

        # ── Step 4: Deploy 10 Sephirot ───────────────────────────────────
        logger.info("\n[Step 4] Deploying 10 Sephirot nodes...")
        sephirot_names = [
            "SephirahKeter", "SephirahChochmah", "SephirahBinah",
            "SephirahChesed", "SephirahGevurah", "SephirahTiferet",
            "SephirahNetzach", "SephirahHod", "SephirahYesod",
            "SephirahMalkuth",
        ]
        sephirot_addrs = []
        for name in sephirot_names:
            addr = self.deploy_with_proxy(
                name,
                self.encode_initialize_address("initialize(address)", kernel)
            )
            sephirot_addrs.append(addr)

        # Register Sephirot in NodeRegistry (optional — can be done later)
        # kernel.registerNode(nodeId, nodeAddress, name) for each

        # ── Step 5: Deploy UpgradeGovernor ────────────────────────────────
        logger.info("\n[Step 5] Deploying UpgradeGovernor...")
        upgrade_governor = self.deploy_with_proxy(
            "UpgradeGovernor",
            self.encode_initialize_address(
                "initialize(address)", self.proxy_admin_address
            )
        )

        # ── Step 6: Deploy Token Standards ───────────────────────────────
        logger.info("\n[Step 6] Deploying token standards...")

        # QBC20 — reference token (no initial supply for the reference impl)
        qbc20_sel = function_selector(
            "initialize(string,string,uint8,uint256)"
        )
        # Dynamic encoding for strings is complex; use placeholder for now
        qbc20 = self.deploy_with_proxy("QBC20")

        qbc721 = self.deploy_with_proxy("QBC721")
        qbc1155 = self.deploy_with_proxy("QBC1155")
        erc20qc = self.deploy_with_proxy("ERC20QC")

        # ── Step 7: Deploy QUSD suite ────────────────────────────────────
        logger.info("\n[Step 7] Deploying QUSD stablecoin suite...")

        qusd_oracle = self.deploy_with_proxy(
            "QUSDOracle",
            (function_selector("initialize(uint256)")
             + encode_uint256(1000)  # maxAge = 1000 blocks
            ).hex()
        )

        qusd_governance = self.deploy_with_proxy("QUSDGovernance")
        qusd_reserve = self.deploy_with_proxy("QUSDReserve")

        # QUSD token — mints 3.3B to deployer
        qusd = self.deploy_with_proxy(
            "QUSD",
            self.encode_initialize_address(
                "initialize(address)",
                qusd_reserve  # reserve address
            )
        )

        qusd_debt_ledger = self.deploy_with_proxy(
            "QUSDDebtLedger",
            self.encode_initialize_2addr(
                "initialize(address,address)", qusd, qusd_reserve
            )
        )

        qusd_stabilizer = self.deploy_with_proxy("QUSDStabilizer")
        qusd_allocation = self.deploy_with_proxy("QUSDAllocation")
        wqusd = self.deploy_with_proxy("wQUSD")

        # QUSDFlashLoan — flash loan provider for QUSD
        qusd_flash_loan = self.deploy_with_proxy("QUSDFlashLoan")

        # ── Step 8: Deploy Bridge contracts ──────────────────────────────
        logger.info("\n[Step 8] Deploying bridge contracts...")

        bridge_vault = self.deploy_with_proxy("BridgeVault")

        bridge_wqbc = self.deploy_with_proxy("bridge_wQBC")
        tokens_wqbc = self.deploy_with_proxy("tokens_wQBC")

        # ── Done ─────────────────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info(f"DEPLOYMENT COMPLETE: {len(self.registry)} contracts")
        logger.info("=" * 60)

        self.save_registry()

        # Print summary
        logger.info("\nContract Registry:")
        for name, info in self.registry.items():
            if "proxy" in info:
                logger.info(f"  {name}: proxy={info['proxy']}, impl={info['implementation']}")
            else:
                logger.info(f"  {name}: {info.get('address', 'N/A')} (direct)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Deploy Qubitcoin contracts")
    parser.add_argument("--rpc-url", default="http://localhost:5000",
                        help="RPC endpoint URL")
    parser.add_argument("--deployer-key", default="secure_key.env",
                        help="Path to deployer key file")
    args = parser.parse_args()

    # Load deployer keys
    key_path = Path(args.deployer_key)
    if not key_path.exists():
        key_path = Path(__file__).parent.parent / "secure_key.env"
    if not key_path.exists():
        logger.error(f"Key file not found: {key_path}")
        logger.error("Run: python3 scripts/setup/generate_keys.py")
        sys.exit(1)

    keys = {}
    for line in key_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()

    deployer = keys.get("ADDRESS", "")
    if deployer and not deployer.startswith("0x"):
        deployer = "0x" + deployer
    private_key = keys.get("PRIVATE_KEY_HEX", "")
    public_key = keys.get("PUBLIC_KEY_HEX", "")

    if not deployer:
        logger.error("No ADDRESS found in key file")
        sys.exit(1)

    logger.info(f"Deployer: {deployer}")
    logger.info(f"RPC URL: {args.rpc_url}")

    # Check node is running
    try:
        r = requests.get(f"{args.rpc_url}/health", timeout=5)
        r.raise_for_status()
        logger.info("Node health check passed")
    except Exception as e:
        logger.error(f"Node not reachable at {args.rpc_url}: {e}")
        sys.exit(1)

    # Create RPC client
    rpc = RPCClient(args.rpc_url, deployer, private_key, public_key)
    rpc.nonce = rpc.get_nonce()
    logger.info(f"Deployer nonce: {rpc.nonce}")

    # Deploy
    sol_dir = Path(__file__).parent.parent / "src" / "qubitcoin" / "contracts" / "solidity"
    deployer_obj = ContractDeployer(rpc, str(sol_dir))

    try:
        deployer_obj.deploy_all()
    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        # Save partial registry
        deployer_obj.save_registry("contract_registry_partial.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
