#!/usr/bin/env python3
"""
Contract Verification Script for Qubitcoin Bridge Tokens

Verifies wQBC and wQUSD contracts on block explorer APIs (Etherscan-compatible)
for all deployed chains.

Usage:
    python3 scripts/deploy/verify_contracts.py
    python3 scripts/deploy/verify_contracts.py --chains polygon,arbitrum

Prerequisites:
    pip install requests py-solc-x
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("verify_contracts")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"
CONTRACTS_DIR = PROJECT_ROOT / "src" / "qubitcoin" / "contracts" / "solidity"

# Explorer API endpoints (all Etherscan-compatible)
# Etherscan V2 unified API — all chains use the same base URL with chainid param
# SnowTrace (Avalanche) still uses the old V1 API
EXPLORER_APIS: Dict[str, Dict[str, str]] = {
    "ethereum": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "Etherscan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "1",
    },
    "bsc": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "BscScan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "56",
    },
    "polygon": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "Polygonscan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "137",
    },
    "avalanche": {
        "api": "https://api.snowtrace.io/api",
        "name": "SnowTrace",
        "api_key_env": "SNOWTRACE_API_KEY",
    },
    "arbitrum": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "Arbiscan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "42161",
    },
    "optimism": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "Optimistic Etherscan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "10",
    },
    "base": {
        "api": "https://api.etherscan.io/v2/api",
        "name": "Basescan",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chainid": "8453",
    },
}


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file into a dict."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def flatten_source(contract_path: Path) -> str:
    """Flatten a Solidity file by inlining relative imports."""
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

            m = re.match(r'import\s+"([^"]+)"\s*;', stripped)
            if m:
                import_path = fpath.parent / m.group(1)
                _inline(import_path)
                continue

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


def verify_contract(
    api_url: str,
    api_key: str,
    contract_address: str,
    contract_name: str,
    source_code: str,
    compiler_version: str = "v0.8.28+commit.7893614a",
    optimization_runs: int = 200,
    evm_version: str = "shanghai",
    chain_id: str = "",
) -> Tuple[bool, str]:
    """Submit contract for verification on an Etherscan-compatible API.

    Returns (success, message).
    """
    import requests

    params = {
        "apikey": api_key,
        "module": "contract",
        "action": "verifysourcecode",
        "contractaddress": contract_address,
        "sourceCode": source_code,
        "codeformat": "solidity-single-file",
        "contractname": contract_name,
        "compilerversion": compiler_version,
        "optimizationUsed": "1",
        "runs": str(optimization_runs),
        "evmversion": evm_version,
        "licenseType": "3",  # MIT
    }
    # Etherscan V2 requires chainid as URL query parameter, not POST body
    url = api_url
    if chain_id:
        url = f"{api_url}?chainid={chain_id}"

    try:
        resp = requests.post(url, data=params, timeout=60)
        data = resp.json()

        if data.get("status") == "1":
            guid = data.get("result", "")
            logger.info(f"Verification submitted: GUID={guid}")
            return True, guid
        else:
            msg = data.get("result", data.get("message", "unknown error"))
            # "Already Verified" is a success
            if "already verified" in str(msg).lower():
                return True, "Already verified"
            return False, str(msg)

    except Exception as e:
        return False, str(e)


def check_verification_status(
    api_url: str, api_key: str, guid: str, chain_id: str = ""
) -> Tuple[bool, str]:
    """Check if contract verification is complete."""
    import requests

    params = {
        "apikey": api_key,
        "module": "contract",
        "action": "checkverifystatus",
        "guid": guid,
    }
    # Etherscan V2 requires chainid as URL query parameter
    url = api_url
    if chain_id:
        url = f"{api_url}?chainid={chain_id}"

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        result = data.get("result", "")

        if "pass" in result.lower() or "verified" in result.lower():
            return True, result
        elif "pending" in result.lower():
            return False, "pending"
        else:
            return False, result

    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify wQBC/wQUSD contracts on block explorers",
    )
    parser.add_argument(
        "--chains", type=str, default="",
        help="Comma-separated chains to verify (default: all deployed)",
    )
    parser.add_argument(
        "--api-key", type=str, default="",
        help="Override API key for all explorers (default: per-chain from .env)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CONTRACT VERIFICATION")
    print("  Verifying wQBC + wQUSD on block explorers")
    print("=" * 60)

    env_vars = parse_env_file(PROJECT_ROOT / ".env")

    # Load registry
    if not REGISTRY_PATH.exists():
        logger.error("contract_registry.json not found")
        sys.exit(1)

    registry = json.loads(REGISTRY_PATH.read_text())

    # Flatten contract sources
    logger.info("Flattening contract sources...")
    wqbc_source = flatten_source(CONTRACTS_DIR / "bridge" / "wQBC.sol")
    wqusd_source = flatten_source(CONTRACTS_DIR / "qusd" / "wQUSD.sol")
    logger.info(f"wQBC: {len(wqbc_source)} chars, wQUSD: {len(wqusd_source)} chars")

    # Determine chains to verify
    if args.chains:
        chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()]
    else:
        # Auto-detect from registry
        chains = []
        for key in registry:
            if key.startswith("external:") and key.endswith(":wQBC"):
                chain = key.split(":")[1]
                chains.append(chain)
        chains = sorted(set(chains))

    results: Dict[str, Dict[str, str]] = {}

    for chain in chains:
        explorer = EXPLORER_APIS.get(chain)
        if not explorer:
            logger.warning(f"No explorer API configured for {chain}, skipping")
            continue

        api_url = explorer["api"]
        api_key = args.api_key or env_vars.get(
            explorer["api_key_env"],
            env_vars.get("ETHERSCAN_API_KEY", ""),
        )

        if not api_key:
            logger.warning(
                f"[{chain}] No API key for {explorer['name']}. "
                f"Set {explorer['api_key_env']} in .env"
            )
            continue

        print(f"\n--- {chain.upper()} ({explorer['name']}) ---")
        results[chain] = {}

        for token, source, contract_name in [
            ("wQBC", wqbc_source, "wQBC"),
            ("wQUSD", wqusd_source, "wQUSD"),
        ]:
            reg_key = f"external:{chain}:{token}"
            entry = registry.get(reg_key, {})
            address = entry.get("address", "")

            if not address:
                logger.warning(f"[{chain}] {token} not deployed, skipping")
                results[chain][token] = "not_deployed"
                continue

            logger.info(f"[{chain}] Verifying {token} at {address}...")

            explorer_chainid = explorer.get("chainid", "")
            ok, msg = verify_contract(
                api_url=api_url,
                api_key=api_key,
                contract_address=address,
                contract_name=contract_name,
                source_code=source,
                chain_id=explorer_chainid,
            )

            if ok and msg != "Already verified":
                # Poll for completion
                guid = msg
                for attempt in range(10):
                    time.sleep(5)
                    done, status = check_verification_status(api_url, api_key, guid, explorer_chainid)
                    if done:
                        logger.info(f"[{chain}] {token} verified: {status}")
                        results[chain][token] = "verified"
                        break
                    elif status == "pending":
                        logger.info(f"[{chain}] {token} pending... (attempt {attempt + 1})")
                    else:
                        logger.warning(f"[{chain}] {token} verification: {status}")
                        results[chain][token] = f"failed: {status}"
                        break
                else:
                    results[chain][token] = "timeout"
            elif ok:
                results[chain][token] = "already_verified"
                logger.info(f"[{chain}] {token}: already verified")
            else:
                results[chain][token] = f"failed: {msg}"
                logger.error(f"[{chain}] {token} verification failed: {msg}")

            # Rate limit between requests
            time.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("  VERIFICATION SUMMARY")
    print("=" * 60)
    for chain, tokens in results.items():
        for token, status in tokens.items():
            print(f"  {chain:12s} {token:6s}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
