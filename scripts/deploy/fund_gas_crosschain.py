#!/usr/bin/env python3
"""
Cross-Chain Gas Funding Script for Qubitcoin Bridge Deployment

Uses the LI.FI API to swap BNB on BSC → native gas tokens on target chains
(Polygon, Avalanche, Arbitrum, Optimism, Base).

Usage:
    python3 scripts/deploy/fund_gas_crosschain.py
    python3 scripts/deploy/fund_gas_crosschain.py --chains polygon,arbitrum
    python3 scripts/deploy/fund_gas_crosschain.py --dry-run

Prerequisites:
    pip install web3 requests
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("fund_gas_crosschain")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Chain configs: chain_name → (lifi_chain_id, native_token_address, amount_wei, symbol)
# LI.FI uses standard chain IDs. Native token = 0xEeeee... or 0x0000...
NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"
BNB_CHAIN_ID = 56

TARGET_CHAINS: Dict[str, Dict[str, Any]] = {
    "polygon": {
        "chainId": 137,
        "symbol": "POL",
        "amount_native": "1.0",  # 1 POL (~$0.50)
        "amount_wei": int(1.0 * 10**18),
    },
    "avalanche": {
        "chainId": 43114,
        "symbol": "AVAX",
        "amount_native": "0.1",  # 0.1 AVAX (~$3)
        "amount_wei": int(0.1 * 10**18),
    },
    "arbitrum": {
        "chainId": 42161,
        "symbol": "ETH",
        "amount_native": "0.005",  # 0.005 ETH (~$15) for deploy + mint
        "amount_wei": int(0.005 * 10**18),
    },
    "optimism": {
        "chainId": 10,
        "symbol": "ETH",
        "amount_native": "0.005",  # 0.005 ETH (~$15)
        "amount_wei": int(0.005 * 10**18),
    },
    "base": {
        "chainId": 8453,
        "symbol": "ETH",
        "amount_native": "0.005",  # 0.005 ETH (~$15)
        "amount_wei": int(0.005 * 10**18),
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


def get_lifi_quote(
    from_chain_id: int,
    to_chain_id: int,
    from_token: str,
    to_token: str,
    from_amount: str,
    from_address: str,
) -> Optional[Dict[str, Any]]:
    """Get a cross-chain swap quote from LI.FI API."""
    import requests

    url = "https://li.quest/v1/quote"
    params = {
        "fromChain": str(from_chain_id),
        "toChain": str(to_chain_id),
        "fromToken": from_token,
        "toToken": to_token,
        "fromAmount": from_amount,
        "fromAddress": from_address,
        "toAddress": from_address,
        "slippage": "0.03",  # 3% slippage tolerance
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"LI.FI quote failed ({resp.status_code}): {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"LI.FI quote request failed: {e}")
        return None


def get_lifi_quote_by_dest_amount(
    from_chain_id: int,
    to_chain_id: int,
    from_token: str,
    to_token: str,
    to_amount_wei: int,
    from_address: str,
) -> Optional[Dict[str, Any]]:
    """Get a reverse quote — specify how much you want to RECEIVE on dest chain.

    LI.FI doesn't support toAmount directly, so we estimate by getting a
    forward quote with a generous BNB amount, then scale.
    """
    import requests

    # First, try the /quote/contractCalls or use a generous estimate
    # Use 0.01 BNB as probe amount to get exchange rate
    probe_amount = str(int(0.01 * 10**18))  # 0.01 BNB
    probe_quote = get_lifi_quote(
        from_chain_id, to_chain_id, from_token, to_token,
        probe_amount, from_address,
    )
    if not probe_quote:
        return None

    # Extract how much dest token we'd get from 0.01 BNB
    estimate = probe_quote.get("estimate", {})
    to_amount_str = estimate.get("toAmount", "0")
    to_amount_probe = int(to_amount_str) if to_amount_str else 0

    if to_amount_probe <= 0:
        logger.error("LI.FI returned zero destination amount for probe")
        return None

    # Scale: how much BNB do we need to get to_amount_wei on dest?
    probe_bnb = 0.01 * 10**18
    ratio = to_amount_wei / to_amount_probe
    needed_bnb = int(probe_bnb * ratio * 1.15)  # +15% buffer for slippage/fees

    logger.info(
        f"Probe: 0.01 BNB → {to_amount_probe / 10**18:.6f} dest token. "
        f"Need {to_amount_wei / 10**18:.6f}, sending {needed_bnb / 10**18:.6f} BNB"
    )

    # Now get real quote with calculated BNB amount
    return get_lifi_quote(
        from_chain_id, to_chain_id, from_token, to_token,
        str(needed_bnb), from_address,
    )


def execute_lifi_tx(
    w3: Any,
    account: Any,
    quote: Dict[str, Any],
    chain_name: str,
) -> Optional[str]:
    """Execute a LI.FI swap transaction on BSC."""
    tx_request = quote.get("transactionRequest", {})
    if not tx_request:
        logger.error(f"[{chain_name}] No transactionRequest in LI.FI quote")
        return None

    to_addr = tx_request.get("to", "")
    data = tx_request.get("data", "0x")
    value = int(tx_request.get("value", "0"), 16) if isinstance(tx_request.get("value"), str) else int(tx_request.get("value", 0))
    gas_limit = int(tx_request.get("gasLimit", "0"), 16) if isinstance(tx_request.get("gasLimit"), str) else int(tx_request.get("gasLimit", 500000))

    nonce = w3.eth.get_transaction_count(account.address)

    tx = {
        "from": account.address,
        "to": w3.to_checksum_address(to_addr),
        "value": value,
        "data": data,
        "nonce": nonce,
        "gas": gas_limit if gas_limit > 0 else 500_000,
        "chainId": BNB_CHAIN_ID,
        "gasPrice": w3.eth.gas_price,
    }

    try:
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"[{chain_name}] Bridge tx sent: {tx_hash_hex[:16]}...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            logger.error(f"[{chain_name}] Bridge tx FAILED: {tx_hash_hex}")
            return None

        logger.info(
            f"[{chain_name}] Bridge tx confirmed! gas={receipt['gasUsed']:,} "
            f"tx={tx_hash_hex}"
        )
        return tx_hash_hex

    except Exception as e:
        logger.error(f"[{chain_name}] Bridge tx failed: {e}")
        return None


def check_balance(rpc_url: str, address: str, chain_name: str) -> int:
    """Check native balance on a chain."""
    from web3 import Web3

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            logger.warning(f"[{chain_name}] Cannot connect to {rpc_url}")
            return 0
        return w3.eth.get_balance(w3.to_checksum_address(address))
    except Exception as e:
        logger.warning(f"[{chain_name}] Balance check failed: {e}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fund gas on target chains from BNB via LI.FI",
    )
    parser.add_argument(
        "--chains", type=str, default="",
        help="Comma-separated chains (default: all 5 target chains)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show quotes without executing transactions",
    )
    parser.add_argument(
        "--skip-funded", action="store_true", default=True,
        help="Skip chains that already have gas (default: true)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force funding even if chain already has gas",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CROSS-CHAIN GAS FUNDING (BNB → Target Chains)")
    print("  Using LI.FI bridge aggregator")
    print("=" * 60)

    # Load keys
    keys = parse_env_file(PROJECT_ROOT / "secure_key.env")
    env_vars = parse_env_file(PROJECT_ROOT / ".env")

    private_key = keys.get("ETH_DEPLOYER_PRIVATE_KEY", "")
    if not private_key:
        logger.error("ETH_DEPLOYER_PRIVATE_KEY not found in secure_key.env")
        sys.exit(1)

    # Connect to BSC
    from web3 import Web3

    bsc_rpc = env_vars.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
    w3 = Web3(Web3.HTTPProvider(bsc_rpc))

    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except ImportError:
        pass

    if not w3.is_connected():
        logger.error(f"Cannot connect to BSC: {bsc_rpc}")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    bnb_balance = w3.eth.get_balance(account.address)
    bnb_eth = w3.from_wei(bnb_balance, "ether")

    logger.info(f"Deployer: {account.address}")
    logger.info(f"BNB balance: {bnb_eth:.6f} BNB")

    if bnb_balance == 0:
        logger.error("Zero BNB balance. Cannot fund target chains.")
        sys.exit(1)

    # Select chains
    if args.chains:
        chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()]
    else:
        chains = list(TARGET_CHAINS.keys())

    # RPC URLs for balance checks
    rpc_urls: Dict[str, str] = {
        "polygon": env_vars.get("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com"),
        "avalanche": env_vars.get("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
        "arbitrum": env_vars.get("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "optimism": env_vars.get("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
        "base": env_vars.get("BASE_RPC_URL", "https://mainnet.base.org"),
    }

    results: Dict[str, str] = {}

    for chain in chains:
        cfg = TARGET_CHAINS.get(chain)
        if not cfg:
            logger.warning(f"Unknown chain: {chain}, skipping")
            continue

        print(f"\n--- {chain.upper()} (chain {cfg['chainId']}) ---")

        # Check if already funded
        if args.skip_funded and not args.force:
            rpc = rpc_urls.get(chain, "")
            if rpc:
                existing = check_balance(rpc, account.address, chain)
                if existing > 0:
                    existing_eth = existing / 10**18
                    logger.info(
                        f"[{chain}] Already funded: {existing_eth:.6f} {cfg['symbol']} — skipping"
                    )
                    results[chain] = f"already_funded ({existing_eth:.6f})"
                    continue

        # Get LI.FI quote
        logger.info(
            f"[{chain}] Requesting quote: BNB → {cfg['amount_native']} {cfg['symbol']}"
        )
        quote = get_lifi_quote_by_dest_amount(
            from_chain_id=BNB_CHAIN_ID,
            to_chain_id=cfg["chainId"],
            from_token=NATIVE_TOKEN,
            to_token=NATIVE_TOKEN,
            to_amount_wei=cfg["amount_wei"],
            from_address=account.address,
        )

        if not quote:
            logger.error(f"[{chain}] Failed to get LI.FI quote")
            results[chain] = "quote_failed"
            continue

        estimate = quote.get("estimate", {})
        from_amount = int(estimate.get("fromAmount", "0"))
        to_amount = int(estimate.get("toAmount", "0"))
        tool_name = quote.get("toolDetails", {}).get("name", "unknown")

        logger.info(
            f"[{chain}] Quote: {from_amount / 10**18:.6f} BNB → "
            f"{to_amount / 10**18:.6f} {cfg['symbol']} via {tool_name}"
        )

        if args.dry_run:
            logger.info(f"[{chain}] [DRY RUN] Would execute bridge tx")
            results[chain] = f"dry_run (would send {from_amount / 10**18:.6f} BNB)"
            continue

        # Execute
        tx_hash = execute_lifi_tx(w3, account, quote, chain)
        if tx_hash:
            results[chain] = f"funded (tx={tx_hash[:16]}...)"
        else:
            results[chain] = "tx_failed"

        # Brief pause between chains to avoid nonce issues
        time.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("  GAS FUNDING SUMMARY")
    print("=" * 60)
    for chain, status in results.items():
        print(f"  {chain:12s}: {status}")

    # Final BNB balance
    final_bnb = w3.eth.get_balance(account.address)
    spent = (bnb_balance - final_bnb) / 10**18
    print(f"\n  BNB spent: {spent:.6f} BNB")
    print(f"  BNB remaining: {final_bnb / 10**18:.6f} BNB")
    print("=" * 60)


if __name__ == "__main__":
    main()
