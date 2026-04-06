#!/usr/bin/env python3
"""
Deploy AetherAPISubscription.sol behind ERC-1967 proxy.

Uses existing ProxyAdmin from contract_registry.json.
Initializes with deployer as owner and gateway.

Usage:
    python3 scripts/deploy/deploy_aether_api_subscription.py [--dry-run]
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from deploy_contracts import (
    ContractDeployer,
    RPCClient,
    encode_address,
    function_selector,
    get_logger,
)

logger = get_logger("deploy_aether_api_sub")

REGISTRY_PATH = Path(__file__).parent.parent.parent / "contract_registry.json"
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
KEY_PATH = Path(__file__).parent.parent.parent / "secure_key.env"


def load_env(path: Path) -> dict:
    """Load key=value pairs from a file."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rpc-url", default="http://localhost:5000")
    args = parser.parse_args()

    # Load keys
    env = load_env(ENV_PATH)
    keys = load_env(KEY_PATH)

    deployer_address = keys.get("ADDRESS", env.get("ADDRESS", ""))
    if deployer_address and not deployer_address.startswith("0x"):
        deployer_address = "0x" + deployer_address
    private_key = keys.get("PRIVATE_KEY_HEX", "")
    public_key = keys.get("PUBLIC_KEY_HEX", "")
    gateway_address = env.get("AETHER_FEE_TREASURY_ADDRESS", deployer_address)
    if gateway_address and not gateway_address.startswith("0x"):
        gateway_address = "0x" + gateway_address

    if not deployer_address or not private_key:
        logger.error("Missing ADDRESS or PRIVATE_KEY_HEX in secure_key.env")
        sys.exit(1)

    # Load existing registry
    registry = {}
    if REGISTRY_PATH.exists():
        registry = json.load(REGISTRY_PATH.open())

    if "AetherAPISubscription" in registry:
        logger.info("AetherAPISubscription already deployed: %s", registry["AetherAPISubscription"])
        logger.info("Skipping (idempotent).")
        return

    proxy_admin = registry.get("ProxyAdmin", {}).get("address")
    if not proxy_admin:
        logger.error("ProxyAdmin not found in registry — deploy base contracts first")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Deploying AetherAPISubscription")
    logger.info("  RPC:     %s", args.rpc_url)
    logger.info("  Owner:   %s", deployer_address)
    logger.info("  Gateway: %s", gateway_address)
    logger.info("  Proxy Admin: %s", proxy_admin)
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN — would deploy AetherAPISubscription with proxy")
        logger.info("  initialize(%s, %s)", deployer_address, gateway_address)
        return

    # Create RPC client
    rpc = RPCClient(args.rpc_url, deployer_address, private_key, public_key)
    rpc.nonce = rpc.get_nonce()
    logger.info("Deployer nonce: %d", rpc.nonce)

    # Create deployer
    sol_dir = str(Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "contracts" / "solidity")
    deployer = ContractDeployer(rpc, sol_dir)
    deployer.proxy_admin_address = proxy_admin
    deployer.registry = registry

    # Step 1: Deploy implementation
    logger.info("Step 1: Deploying implementation...")
    impl_addr = deployer.deploy_impl("AetherAPISubscription_impl")

    # Step 2: Encode initialize(owner, gateway) calldata
    # function selector for initialize(address,address)
    sig = "initialize(address,address)"
    sel = function_selector(sig)

    # Pad addresses to 32 bytes
    owner_clean = deployer_address.removeprefix("0x").lower().zfill(64)
    gateway_clean = gateway_address.removeprefix("0x").lower().zfill(64)
    init_data = sel.hex() + owner_clean + gateway_clean

    logger.info("Step 2: Deploying proxy with init data...")
    logger.info("  init selector: %s", sel.hex())
    proxy_addr = deployer.deploy_proxy("AetherAPISubscription", impl_addr, init_data)

    logger.info("=" * 60)
    logger.info("AetherAPISubscription deployed!")
    logger.info("  Implementation: %s", impl_addr)
    logger.info("  Proxy:          %s", proxy_addr)
    logger.info("=" * 60)

    # Save registry
    deployer.save_registry = lambda p: None  # we'll save ourselves
    registry["AetherAPISubscription"] = {
        "proxy": proxy_addr,
        "implementation": impl_addr,
    }
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    logger.info("Registry updated: %s", REGISTRY_PATH)


if __name__ == "__main__":
    main()
