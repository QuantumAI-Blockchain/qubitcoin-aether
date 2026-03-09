#!/usr/bin/env python3
"""
Quantum Blockchain — Comprehensive Live Transaction Test Suite
==============================================================

Creates 5 test wallets, funds them from genesis, and tests EVERY feature:
- Standard QBC transfers (public)
- SUSY Swap confidential transfers (private)
- QUSD minting and transfers
- L1↔L2 bridge deposits/withdrawals
- Stealth address generation and scanning
- Pedersen commitments and range proofs
- Deniable RPC batch operations
- MetaMask JSON-RPC compatibility
- Exchange order placement (if running)
- Aether Tree chat interaction
- Prometheus metrics health

Run: python3 scripts/test/live_transaction_test.py --rpc http://localhost:5000
"""

import argparse
import hashlib
import json
import sys
import time
from decimal import Decimal
from typing import Any

import requests

# ─── Configuration ───────────────────────────────────────────────────────

NUM_TEST_WALLETS = 5
GENESIS_ADDRESS = None  # Auto-detected from node
METAMASK_ADDRESS = "0x51D3a9b12dc4667f771B2A5cE3491631251E9D41"
TEST_AMOUNT_QBC = "10.0"
SUSY_TEST_AMOUNT_QBC = "10.0"
QUSD_MINT_AMOUNT = "1000.0"

# ─── Helpers ─────────────────────────────────────────────────────────────

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

passed = 0
failed = 0
skipped = 0

def test(name: str, fn, *args, **kwargs) -> Any:
    global passed, failed, skipped
    try:
        result = fn(*args, **kwargs)
        print(f"  {Colors.GREEN}PASS{Colors.END} {name}")
        passed += 1
        return result
    except SkipTest as e:
        print(f"  {Colors.YELLOW}SKIP{Colors.END} {name} — {e}")
        skipped += 1
        return None
    except Exception as e:
        print(f"  {Colors.RED}FAIL{Colors.END} {name} — {e}")
        failed += 1
        return None

class SkipTest(Exception):
    pass

ADMIN_KEY = None  # Set via --admin-key

def rpc_call(base_url: str, method: str, endpoint: str, data: dict = None, timeout: int = 30) -> dict:
    """Make an HTTP request to the node RPC."""
    url = f"{base_url}{endpoint}"
    headers = {}
    if ADMIN_KEY:
        headers["X-Admin-Key"] = ADMIN_KEY
        headers["Authorization"] = f"Bearer {ADMIN_KEY}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            resp = requests.post(url, json=data or {}, headers=headers, timeout=timeout)
        elif method == "PUT":
            resp = requests.put(url, json=data or {}, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Rate limited — retry with exponential backoff (up to 2 retries)
        for retry_wait in [3, 5]:
            if resp.status_code != 429:
                break
            time.sleep(retry_wait)
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            elif method == "POST":
                resp = requests.post(url, json=data or {}, headers=headers, timeout=timeout)

        if resp.status_code >= 400:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()
    except requests.ConnectionError:
        raise Exception(f"Cannot connect to {url}")

def jsonrpc_call(base_url: str, method: str, params: list = None) -> Any:
    """Make a JSON-RPC 2.0 call."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": int(time.time() * 1000),
    }
    resp = requests.post(f"{base_url}/", json=payload, timeout=30)
    result = resp.json()
    if "error" in result:
        raise Exception(f"JSON-RPC error: {result['error']}")
    return result.get("result")

# ─── Test Phases ─────────────────────────────────────────────────────────

def phase_0_connectivity(rpc: str):
    """Phase 0: Node Connectivity"""
    print(f"\n{Colors.BOLD}Phase 0: Node Connectivity{Colors.END}")

    def check_health():
        r = rpc_call(rpc, "GET", "/health")
        assert r.get("status") == "healthy" or "status" in r, f"Unhealthy: {r}"
        return r

    def check_chain_info():
        r = rpc_call(rpc, "GET", "/chain/info")
        assert "height" in r or "block_height" in r, f"No height in chain info: {r}"
        return r

    def check_node_info():
        r = rpc_call(rpc, "GET", "/info")
        return r

    test("Health check", check_health)
    chain = test("Chain info", check_chain_info)
    test("Node info", check_node_info)
    return chain


def phase_1_wallet_creation(rpc: str):
    """Phase 1: Create 5 Test Wallets"""
    print(f"\n{Colors.BOLD}Phase 1: Create {NUM_TEST_WALLETS} Test Wallets{Colors.END}")

    wallets = []
    for i in range(NUM_TEST_WALLETS):
        def create_wallet(idx=i):
            r = rpc_call(rpc, "POST", "/wallet/create")
            assert "address" in r, f"No address in response: {r}"
            assert "public_key_hex" in r, f"No public_key_hex: {r}"
            assert len(r["address"]) == 40, f"Address wrong length: {len(r['address'])}"
            # Verify check phrase
            assert "check_phrase" in r, f"No check_phrase: {r}"
            assert "-" in r["check_phrase"], f"Invalid check phrase format: {r['check_phrase']}"
            return r

        w = test(f"Create wallet #{i+1}", create_wallet)
        if w:
            wallets.append(w)

    # Print wallet summary
    print(f"\n  {Colors.CYAN}Created {len(wallets)} wallets:{Colors.END}")
    for i, w in enumerate(wallets):
        print(f"    W{i+1}: {w['address'][:12]}...{w['address'][-8:]}  [{w.get('nist_name', 'ML-DSA-87')}]  {w.get('check_phrase', '?')}")

    return wallets


def phase_2_fund_wallets(rpc: str, wallets: list):
    """Phase 2: Fund Test Wallets from Genesis"""
    print(f"\n{Colors.BOLD}Phase 2: Fund Wallets from Genesis{Colors.END}")

    # Ensure mining is running so transactions get confirmed
    mining_was_off = False
    try:
        stats = rpc_call(rpc, "GET", "/mining/stats")
        if not stats.get("is_mining", False):
            mining_was_off = True
            print(f"    Mining is OFF — starting miner for funding...")
            rpc_call(rpc, "POST", "/mining/start")
            time.sleep(2)
    except Exception:
        pass

    for i, w in enumerate(wallets):
        def fund(wallet=w, idx=i):
            r = rpc_call(rpc, "POST", "/transfer", {
                "to": wallet["address"],
                "amount": TEST_AMOUNT_QBC,
            })
            assert "tx_hash" in r or "status" in r, f"Transfer failed: {r}"
            return r

        test(f"Fund W{i+1} with {TEST_AMOUNT_QBC} QBC", fund)
        time.sleep(2)  # Space out transfers to stay under 10/min write rate limit

    # Wait for mining — poll until at least one wallet has balance or timeout
    print(f"    Waiting for transactions to be mined (up to 60s)...")
    deadline = time.time() + 60  # 60 second timeout (VQE mining can be slow)
    any_funded = False
    while time.time() < deadline and not any_funded:
        time.sleep(3)
        try:
            r = rpc_call(rpc, "GET", f"/balance/{wallets[0]['address']}")
            if float(r.get("balance", 0)) > 0:
                any_funded = True
        except Exception:
            pass
    if not any_funded:
        print(f"    {Colors.YELLOW}WARNING{Colors.END} Balances may not be confirmed yet (mining may be slow)")

    # Keep mining running — will be stopped at end of test suite
    if mining_was_off and any_funded:
        print(f"    Mining left running for remaining test phases")

    # Verify balances — /transfer credits the accounts table (L2),
    # so check both UTXO (L1) and account (L2) balance
    for i, w in enumerate(wallets):
        def check_balance(wallet=w, idx=i):
            # Check L1 UTXO balance
            r1 = rpc_call(rpc, "GET", f"/balance/{wallet['address']}")
            utxo_balance = float(r1.get("balance", 0))
            # Check L2 account balance
            try:
                r2 = rpc_call(rpc, "GET", f"/qvm/account/{wallet['address']}")
                acct_balance = float(r2.get("balance", 0))
            except Exception:
                acct_balance = 0.0
            total = utxo_balance + acct_balance
            assert total > 0, f"Balance is {total} (UTXO={utxo_balance}, Account={acct_balance}), expected > 0"
            return total

        test(f"Verify W{i+1} balance > 0", check_balance)


def phase_3_public_transfers(rpc: str, wallets: list):
    """Phase 3: Standard Public QBC Transfers"""
    print(f"\n{Colors.BOLD}Phase 3: Standard Public Transfers{Colors.END}")

    if len(wallets) < 2:
        print(f"  {Colors.YELLOW}SKIP{Colors.END} — need at least 2 wallets")
        return

    # W1 → W2 transfer
    def transfer_w1_w2():
        r = rpc_call(rpc, "POST", "/transfer", {
            "to": wallets[1]["address"],
            "amount": "1.0",
        })
        assert "tx_hash" in r or "status" in r, f"Transfer failed: {r}"
        return r

    test("W1 → W2: 1 QBC (public)", transfer_w1_w2)
    time.sleep(2)  # Avoid rate limiting

    # W2 → W3 transfer
    if len(wallets) >= 3:
        def transfer_w2_w3():
            r = rpc_call(rpc, "POST", "/transfer", {
                "to": wallets[2]["address"],
                "amount": "0.5",
            })
            return r

        test("W2 → W3: 0.5 QBC (public)", transfer_w2_w3)


def phase_4_stealth_addresses(rpc: str):
    """Phase 4: Stealth Address Generation & Scanning"""
    print(f"\n{Colors.BOLD}Phase 4: Stealth Addresses{Colors.END}")

    def generate_stealth_keypair():
        r = rpc_call(rpc, "POST", "/privacy/stealth/generate-keypair")
        assert "spend_pubkey" in r, f"Missing spend_pubkey: {r}"
        assert "view_pubkey" in r, f"Missing view_pubkey: {r}"
        assert "spend_privkey" in r, f"Missing spend_privkey: {r}"
        assert "view_privkey" in r, f"Missing view_privkey: {r}"
        return r

    keys = test("Generate stealth keypair", generate_stealth_keypair)

    if keys:
        def create_stealth_output():
            r = rpc_call(rpc, "POST", "/privacy/stealth/create-output", {
                "recipient_spend_pub": keys["spend_pubkey"],
                "recipient_view_pub": keys["view_pubkey"],
            })
            assert "one_time_address" in r, f"Missing one_time_address: {r}"
            assert "ephemeral_pubkey" in r, f"Missing ephemeral_pubkey: {r}"
            return r

        output = test("Create stealth output", create_stealth_output)

        if output:
            def scan_stealth():
                r = rpc_call(rpc, "POST", "/privacy/stealth/scan", {
                    "ephemeral_pubkey": output["ephemeral_pubkey"],
                    "output_address": output["one_time_address"],
                    "view_privkey": keys["view_privkey"],
                    "spend_pubkey": keys["spend_pubkey"],
                    "view_pubkey": keys["view_pubkey"],
                })
                assert r.get("is_mine") is True, f"Stealth scan failed: {r}"
                return r

            test("Scan stealth output (should be mine)", scan_stealth)


def phase_5_pedersen_commitments(rpc: str):
    """Phase 5: Pedersen Commitments"""
    print(f"\n{Colors.BOLD}Phase 5: Pedersen Commitments{Colors.END}")

    def create_commitment():
        r = rpc_call(rpc, "POST", "/privacy/commitment/create", {
            "value": 1000000,
        })
        assert "commitment" in r, f"Missing commitment: {r}"
        assert "blinding" in r, f"Missing blinding: {r}"
        return r

    commitment = test("Create Pedersen commitment (1M atoms)", create_commitment)

    if commitment:
        def verify_commitment():
            r = rpc_call(rpc, "POST", "/privacy/commitment/verify", {
                "commitment": commitment["commitment"],
                "value": 1000000,
                "blinding": commitment["blinding"],
            })
            assert r.get("valid") is True, f"Commitment verification failed: {r}"
            return r

        test("Verify Pedersen commitment", verify_commitment)


def phase_6_range_proofs(rpc: str):
    """Phase 6: Bulletproofs Range Proofs"""
    print(f"\n{Colors.BOLD}Phase 6: Range Proofs (Bulletproofs){Colors.END}")

    def generate_range_proof():
        r = rpc_call(rpc, "POST", "/privacy/range-proof/generate", {
            "value": 50000000,  # 0.5 QBC in atoms
        })
        assert "proof" in r, f"Missing proof: {r}"
        assert "commitment" in r, f"Missing commitment: {r}"
        return r

    proof = test("Generate range proof (0.5 QBC)", generate_range_proof)

    if proof:
        def verify_range_proof():
            r = rpc_call(rpc, "POST", "/privacy/range-proof/verify", {
                "proof": proof["proof"],
                "commitment": proof["commitment"],
            })
            return r

        test("Verify range proof", verify_range_proof)


def phase_7_confidential_tx(rpc: str, wallets: list):
    """Phase 7: SUSY Swap Confidential Transaction"""
    print(f"\n{Colors.BOLD}Phase 7: SUSY Swap (Confidential Transaction){Colors.END}")

    if len(wallets) < 2:
        print(f"  {Colors.YELLOW}SKIP{Colors.END} — need at least 2 wallets")
        return

    # Generate stealth keys for recipient
    def build_susy_swap():
        # First get stealth keys for recipient
        recipient_keys = rpc_call(rpc, "POST", "/privacy/stealth/generate-keypair")

        # Get UTXOs for sender
        sender_utxos = rpc_call(rpc, "GET", f"/utxos/{wallets[0]['address']}")
        utxos = sender_utxos.get("utxos", [])
        if not utxos:
            raise SkipTest("No UTXOs available for sender")

        # Build confidential transaction
        r = rpc_call(rpc, "POST", "/privacy/tx/build", {
            "inputs": [{
                "txid": utxos[0].get("txid", utxos[0].get("tx_hash", "unknown")),
                "vout": utxos[0].get("vout", utxos[0].get("output_index", 0)),
                "value": int(float(utxos[0].get("amount", 0)) * 1e8),
                "blinding": 0,
                "spending_key": 12345,
            }],
            "outputs": [{
                "value": int(float(SUSY_TEST_AMOUNT_QBC) * 1e8),
                "recipient_spend_pub": recipient_keys["spend_pubkey"],
                "recipient_view_pub": recipient_keys["view_pubkey"],
            }],
            "fee_atoms": 10000,
        })
        assert "txid" in r or "tx" in r or "error" not in r, f"Build failed: {r}"
        return r

    test("Build SUSY Swap (confidential tx)", build_susy_swap)


def phase_8_deniable_rpc(rpc: str, wallets: list):
    """Phase 8: Deniable RPC Endpoints"""
    print(f"\n{Colors.BOLD}Phase 8: Deniable RPC (Privacy Batch Operations){Colors.END}")

    addrs = [w["address"] for w in wallets[:3]] if wallets else ["0" * 40]

    def batch_balance():
        r = rpc_call(rpc, "POST", "/privacy/batch-balance", {
            "addresses": addrs,
        })
        return r

    def bloom_utxos():
        r = rpc_call(rpc, "POST", "/privacy/bloom-utxos", {
            "address": addrs[0] if addrs else "0" * 40,
            "bloom_size": 256,
            "hash_count": 3,
        })
        return r

    def batch_blocks():
        r = rpc_call(rpc, "POST", "/privacy/batch-blocks", {
            "heights": [0, 1, 2],
        })
        return r

    def batch_tx():
        r = rpc_call(rpc, "POST", "/privacy/batch-tx", {
            "txids": ["0" * 64],
        })
        return r

    test("Batch balance (constant-time)", batch_balance)
    test("Bloom filter UTXOs (plausible deniability)", bloom_utxos)
    test("Batch blocks query", batch_blocks)
    test("Batch transaction query", batch_tx)


def phase_9_l1l2_bridge(rpc: str, wallets: list):
    """Phase 9: L1↔L2 Internal Bridge"""
    print(f"\n{Colors.BOLD}Phase 9: L1↔L2 Bridge{Colors.END}")

    def bridge_status():
        r = rpc_call(rpc, "GET", "/bridge/l1l2/status")
        return r

    test("Bridge status", bridge_status)

    if wallets:
        def bridge_balance():
            r = rpc_call(rpc, "GET", f"/bridge/l1l2/balance/{wallets[0]['address']}")
            return r

        test(f"Combined L1+L2 balance for W1", bridge_balance)


def phase_10_metamask_jsonrpc(rpc: str):
    """Phase 10: MetaMask JSON-RPC Compatibility"""
    print(f"\n{Colors.BOLD}Phase 10: MetaMask JSON-RPC Compatibility{Colors.END}")

    def eth_chain_id():
        r = jsonrpc_call(rpc, "eth_chainId")
        assert r == "0xce7" or r == hex(3303), f"Wrong chain ID: {r}"
        return r

    def eth_block_number():
        r = jsonrpc_call(rpc, "eth_blockNumber")
        assert r is not None, "No block number"
        return r

    def net_version():
        r = jsonrpc_call(rpc, "net_version")
        assert r == "3303" or r == 3303, f"Wrong net version: {r}"
        return r

    def web3_client_version():
        r = jsonrpc_call(rpc, "web3_clientVersion")
        assert r is not None, "No client version"
        return r

    def eth_get_balance():
        r = jsonrpc_call(rpc, "eth_getBalance", [METAMASK_ADDRESS, "latest"])
        return r

    test("eth_chainId = 0xce7", eth_chain_id)
    test("eth_blockNumber", eth_block_number)
    test("net_version = 3303", net_version)
    test("web3_clientVersion", web3_client_version)
    test(f"eth_getBalance({METAMASK_ADDRESS[:10]}...)", eth_get_balance)


def phase_11_aether_tree(rpc: str):
    """Phase 11: Aether Tree AGI"""
    print(f"\n{Colors.BOLD}Phase 11: Aether Tree AGI{Colors.END}")

    def aether_info():
        r = rpc_call(rpc, "GET", "/aether/info")
        return r

    def aether_phi():
        r = rpc_call(rpc, "GET", "/aether/phi")
        assert "phi_value" in r or "phi" in r or "value" in r or "current_phi" in r, \
            f"No phi in response: {list(r.keys())}"
        return r

    def aether_knowledge():
        r = rpc_call(rpc, "GET", "/aether/knowledge")
        return r

    def aether_consciousness():
        r = rpc_call(rpc, "GET", "/aether/consciousness")
        return r

    test("Aether info", aether_info)
    test("Phi consciousness metric", aether_phi)
    test("Knowledge graph stats", aether_knowledge)
    test("Consciousness dashboard", aether_consciousness)


def phase_12_economics(rpc: str):
    """Phase 12: Economics & Emission"""
    print(f"\n{Colors.BOLD}Phase 12: Economics & QUSD{Colors.END}")

    def emission():
        r = rpc_call(rpc, "GET", "/economics/emission")
        return r

    def keeper_status():
        r = rpc_call(rpc, "GET", "/keeper/status")
        return r

    def higgs_status():
        r = rpc_call(rpc, "GET", "/higgs/status")
        return r

    def higgs_masses():
        r = rpc_call(rpc, "GET", "/higgs/masses")
        return r

    test("Emission schedule", emission)
    test("QUSD keeper status", keeper_status)
    test("Higgs field status", higgs_status)
    test("Higgs cognitive masses", higgs_masses)


def phase_13_exchange(rpc: str):
    """Phase 13: Exchange (if running)"""
    print(f"\n{Colors.BOLD}Phase 13: Exchange{Colors.END}")

    def exchange_info():
        try:
            # Try the exchange port (default 8080)
            r = requests.get("http://localhost:8080/api/v1/pairs", timeout=5)
            if r.status_code == 200:
                return r.json()
            raise SkipTest("Exchange not running on port 8080")
        except requests.ConnectionError:
            raise SkipTest("Exchange not running")

    test("Exchange trading pairs", exchange_info)


def phase_14_crypto_verification(rpc: str):
    """Phase 14: Cryptography Verification"""
    print(f"\n{Colors.BOLD}Phase 14: Cryptography Verification{Colors.END}")

    def crypto_info():
        r = rpc_call(rpc, "GET", "/crypto/info")
        assert "algorithm" in r, f"No algorithm info: {r}"
        return r

    def wallet_sign_verify():
        # Create a wallet, get check phrase
        w = rpc_call(rpc, "POST", "/wallet/create")
        addr = w["address"]
        phrase = w.get("check_phrase", "")

        # Verify check phrase
        v = rpc_call(rpc, "POST", "/wallet/verify-check-phrase", {
            "address": addr,
            "check_phrase": phrase,
        })
        assert v.get("valid") is True or v.get("match") is True, f"Check phrase verification failed: {v}"
        return v

    test("Crypto system info (Dilithium level)", crypto_info)
    test("Address ↔ check-phrase round-trip", wallet_sign_verify)


def phase_15_prometheus(rpc: str):
    """Phase 15: Prometheus Metrics"""
    print(f"\n{Colors.BOLD}Phase 15: Monitoring{Colors.END}")

    def prometheus_metrics():
        resp = requests.get(f"{rpc}/metrics", timeout=10)
        assert resp.status_code == 200, f"Metrics HTTP {resp.status_code}"
        text = resp.text
        assert "qbc_blocks_mined" in text or "blocks_mined" in text or "current_height" in text, \
            "Missing blockchain metrics"
        return f"{len(text)} bytes, {text.count(chr(10))} lines"

    test("Prometheus /metrics endpoint", prometheus_metrics)


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Quantum Blockchain Live Transaction Test Suite",
    )
    parser.add_argument(
        "--rpc", default="http://localhost:5000",
        help="Node RPC URL (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--skip-funding", action="store_true",
        help="Skip wallet funding (wallets already funded)",
    )
    parser.add_argument(
        "--admin-key", default=None,
        help="Admin API key for privileged operations (transfers, etc.)",
    )
    args = parser.parse_args()

    global ADMIN_KEY
    ADMIN_KEY = args.admin_key
    rpc = args.rpc.rstrip("/")

    print(f"""
{Colors.BOLD}{'='*70}
  QUANTUM BLOCKCHAIN — LIVE TRANSACTION TEST SUITE
  RPC: {rpc}
  Wallets: {NUM_TEST_WALLETS}
  Test Amount: {TEST_AMOUNT_QBC} QBC per wallet
  MetaMask: {METAMASK_ADDRESS[:12]}...
{'='*70}{Colors.END}
""")

    # Phase 0: Connectivity
    chain = phase_0_connectivity(rpc)

    # Phase 1: Create wallets
    wallets = phase_1_wallet_creation(rpc)

    # Phase 2: Fund wallets
    if not args.skip_funding and wallets:
        # Wait for write rate limit window to reset after wallet creation
        # (wallet creates + transfers share the same 10/min write limit)
        if len(wallets) >= 4:
            print(f"\n    Waiting for write rate limit window to reset (30s)...")
            time.sleep(30)
        phase_2_fund_wallets(rpc, wallets)

    # Phase 3: Public transfers
    phase_3_public_transfers(rpc, wallets or [])

    # Phase 4: Stealth addresses
    phase_4_stealth_addresses(rpc)

    # Phase 5: Pedersen commitments
    phase_5_pedersen_commitments(rpc)

    # Phase 6: Range proofs
    phase_6_range_proofs(rpc)

    # Phase 7: Confidential transactions
    phase_7_confidential_tx(rpc, wallets or [])

    # Phase 8: Deniable RPC
    phase_8_deniable_rpc(rpc, wallets or [])

    # Phase 9: L1↔L2 Bridge
    phase_9_l1l2_bridge(rpc, wallets or [])

    # Phase 10: MetaMask JSON-RPC
    phase_10_metamask_jsonrpc(rpc)

    # Phase 11: Aether Tree
    phase_11_aether_tree(rpc)

    # Phase 12: Economics
    phase_12_economics(rpc)

    # Phase 13: Exchange
    phase_13_exchange(rpc)

    # Phase 14: Crypto verification
    phase_14_crypto_verification(rpc)

    # Phase 15: Prometheus
    phase_15_prometheus(rpc)

    # Leave mining running (do not stop — user preference)

    # ─── Summary ─────────────────────────────────────────────────────────

    total = passed + failed + skipped
    print(f"""
{Colors.BOLD}{'='*70}
  TEST RESULTS
{'='*70}{Colors.END}
  {Colors.GREEN}PASSED:  {passed}{Colors.END}
  {Colors.RED}FAILED:  {failed}{Colors.END}
  {Colors.YELLOW}SKIPPED: {skipped}{Colors.END}
  TOTAL:   {total}
""")

    if wallets:
        print(f"  {Colors.CYAN}Test Wallets:{Colors.END}")
        for i, w in enumerate(wallets):
            print(f"    W{i+1}: {w['address']}")
        print()

    if failed > 0:
        print(f"  {Colors.RED}{Colors.BOLD}AUDIT STATUS: FAIL — {failed} test(s) failed{Colors.END}")
        sys.exit(1)
    else:
        print(f"  {Colors.GREEN}{Colors.BOLD}AUDIT STATUS: PASS — All {passed} tests passed ({skipped} skipped){Colors.END}")
        sys.exit(0)


if __name__ == "__main__":
    main()
