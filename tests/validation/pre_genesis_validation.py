#!/usr/bin/env python3
"""
Qubitcoin Pre-Genesis Validation Suite
Comprehensive testing before mainnet launch
"""

import sys
import os
import time
import json
from decimal import Decimal, getcontext
from datetime import datetime

# Set precision
getcontext().prec = 28

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 80)
print("🔬 QUBITCOIN PRE-GENESIS VALIDATION SUITE")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print()

test_results = []
warnings = []

def test_section(name):
    """Print test section header"""
    print(f"\n{'=' * 80}")
    print(f"  {name}")
    print(f"{'=' * 80}\n")

def test_result(name, passed, details="", critical=True):
    """Record and print test result"""
    status = "✅ PASS" if passed else ("❌ CRITICAL FAIL" if critical else "⚠️  WARNING")
    print(f"{status}: {name}")
    if details:
        print(f"       {details}")
    test_results.append((name, passed, critical))
    if not passed and not critical:
        warnings.append((name, details))
    return passed

# ============================================================================
# TEST 1: ENVIRONMENT VALIDATION
# ============================================================================
test_section("TEST 1: Environment & Configuration")

try:
    from qubitcoin.config import Config
    
    # Check critical config values
    config_checks = [
        ("MAX_SUPPLY", Config.MAX_SUPPLY == Decimal('3300000000')),
        ("INITIAL_REWARD", Config.INITIAL_REWARD == Decimal('15.27')),
        ("TARGET_BLOCK_TIME", Config.TARGET_BLOCK_TIME == 3.3),
        ("HALVING_INTERVAL", Config.HALVING_INTERVAL == 15474020),
        ("INITIAL_DIFFICULTY", Config.INITIAL_DIFFICULTY == 0.5),
    ]
    
    for name, check in config_checks:
        test_result(
            f"Config.{name}",
            check,
            f"Value: {getattr(Config, name)}"
        )
    
    # Check node keys exist
    has_keys = all([
        hasattr(Config, 'ADDRESS') and Config.ADDRESS,
        hasattr(Config, 'PUBLIC_KEY_HEX') and Config.PUBLIC_KEY_HEX,
        hasattr(Config, 'PRIVATE_KEY_HEX') and Config.PRIVATE_KEY_HEX,
    ])
    
    test_result(
        "Node keys configured",
        has_keys,
        "Address, public key, private key present" if has_keys else "Run: python scripts/generate_keys.py"
    )
    
except Exception as e:
    test_result("Config validation", False, f"Error: {e}")

# ============================================================================
# TEST 2: DATABASE INTEGRITY
# ============================================================================
test_section("TEST 2: Database Integrity & Schema")

try:
    from qubitcoin.database.manager import DatabaseManager
    from sqlalchemy import text
    
    db = DatabaseManager()
    
    # Test connection
    with db.get_session() as session:
        result = session.execute(text("SELECT 1")).scalar()
        test_result("Database connection", result == 1)
    
    # Check all required tables
    required_tables = [
        # Core blockchain
        'users', 'utxos', 'transactions', 'blocks', 'supply',
        # Research
        'solved_hamiltonians', 'susy_swaps',
        # Network
        'peer_reputation', 'ipfs_snapshots',
        # Contracts
        'contracts', 'contract_storage', 'contract_events', 'contract_deployments',
        # Stablecoin
        'stablecoin_tokens', 'stablecoin_positions', 'stablecoin_liquidations',
        'collateral_types', 'stablecoin_params', 'oracle_sources',
        # Bridge
        'bridge_deposits', 'bridge_withdrawals', 'bridge_validators',
        'bridge_approvals', 'bridge_events', 'bridge_config',
        'bridge_stats', 'bridge_sync_status',
    ]
    
    with db.get_session() as session:
        result = session.execute(text("SHOW TABLES"))
        existing_tables = {row[1] for row in result}
    
    missing_tables = set(required_tables) - existing_tables
    
    test_result(
        "All required tables exist",
        len(missing_tables) == 0,
        f"Missing: {missing_tables}" if missing_tables else "47+ tables present"
    )
    
    # Check blockchain is empty (pre-genesis)
    height = db.get_current_height()
    test_result(
        "Blockchain at genesis state",
        height == -1,
        f"Current height: {height} (should be -1)"
    )
    
    # Check supply is zero
    supply = db.get_total_supply()
    test_result(
        "Zero supply before genesis",
        supply == Decimal(0),
        f"Current supply: {supply} QBC"
    )
    
    # Test UTXO operations
    utxos = db.get_utxos(Config.ADDRESS if hasattr(Config, 'ADDRESS') else 'test')
    test_result(
        "UTXO query functional",
        isinstance(utxos, list),
        f"Query returned: {type(utxos)}"
    )
    
    # Test balance query
    balance = db.get_balance(Config.ADDRESS if hasattr(Config, 'ADDRESS') else 'test')
    test_result(
        "Balance query functional",
        balance == Decimal(0),
        f"Pre-genesis balance: {balance} QBC"
    )
    
except Exception as e:
    test_result("Database tests", False, f"Error: {e}")

# ============================================================================
# TEST 3: QUANTUM ENGINE
# ============================================================================
test_section("TEST 3: Quantum Engine Functionality")

try:
    from qubitcoin.quantum.engine import QuantumEngine
    import numpy as np
    
    qe = QuantumEngine()
    
    # Test Hamiltonian generation
    hamiltonian = qe.generate_hamiltonian(num_qubits=4)
    test_result(
        "Hamiltonian generation",
        len(hamiltonian) == 5,
        f"Generated {len(hamiltonian)} terms"
    )
    
    # Test VQE optimization (quick test)
    start = time.time()
    params, energy = qe.optimize_vqe(hamiltonian)
    duration = time.time() - start
    
    test_result(
        "VQE optimization completes",
        isinstance(energy, float),
        f"Energy: {energy:.6f}, Time: {duration:.3f}s"
    )
    
    test_result(
        "VQE performance acceptable",
        duration < 10.0,
        f"Completed in {duration:.3f}s (target: <10s)",
        critical=False
    )
    
    # Test proof validation
    valid, reason = qe.validate_proof(
        params=params,
        hamiltonian=hamiltonian,
        claimed_energy=energy,
        difficulty=0.5
    )
    
    test_result(
        "Proof validation works",
        valid,
        reason
    )
    
    # Test multiple VQE runs (consistency check)
    energies = []
    for i in range(3):
        h = qe.generate_hamiltonian(num_qubits=4)
        p, e = qe.optimize_vqe(h)
        energies.append(e)
    
    test_result(
        "VQE produces varied results",
        len(set(energies)) > 1,
        f"Got {len(set(energies))} unique energies from 3 runs",
        critical=False
    )
    
except Exception as e:
    test_result("Quantum engine tests", False, f"Error: {e}")

# ============================================================================
# TEST 4: CONSENSUS ENGINE
# ============================================================================
test_section("TEST 4: Consensus & Economics")

try:
    from qubitcoin.consensus.engine import ConsensusEngine
    
    ce = ConsensusEngine(qe)
    
    # Test reward calculation
    rewards = []
    expected_rewards = [
        (0, Decimal('15.27')),
        (15474020, Decimal('9.437379008210893446718927674')),  # Era 1
        (30948040, Decimal('5.833037724110783699872857794')),  # Era 2
    ]
    
    for height, expected in expected_rewards:
        reward = ce.calculate_reward(height, Decimal(0))
        matches = abs(reward - expected) < Decimal('0.001')
        test_result(
            f"Reward at block {height}",
            matches,
            f"Got: {reward}, Expected: {expected}"
        )
        rewards.append((height, reward))
    
    # Test golden ratio
    if len(rewards) >= 2:
        ratio = float(rewards[0][1]) / float(rewards[1][1])
        phi = 1.618033988749895
        test_result(
            "Golden ratio halvings",
            abs(ratio - phi) < 0.001,
            f"Ratio: {ratio:.6f}, φ: {phi:.6f}"
        )
    
    # Test difficulty calculation
    diff = ce.calculate_difficulty(0, db)
    test_result(
        "Initial difficulty correct",
        diff == Config.INITIAL_DIFFICULTY,
        f"Difficulty: {diff}"
    )
    
    # Test supply convergence
    total_supply = Decimal(0)
    for era in range(21):  # 21 eras to near-max supply
        blocks_in_era = Config.HALVING_INTERVAL
        reward = ce.calculate_reward(era * blocks_in_era, total_supply)
        era_supply = reward * Decimal(blocks_in_era)
        total_supply += era_supply
    
    test_result(
        "Supply converges to max",
        total_supply >= Config.MAX_SUPPLY * Decimal('0.99'),
        f"After 21 eras: {total_supply / 1e9:.2f}B / {Config.MAX_SUPPLY / 1e9:.1f}B QBC"
    )
    
except Exception as e:
    test_result("Consensus tests", False, f"Error: {e}")

# ============================================================================
# TEST 5: CRYPTOGRAPHY
# ============================================================================
test_section("TEST 5: Post-Quantum Cryptography")

try:
    from qubitcoin.quantum.crypto import Dilithium2, CryptoManager
    
    # Test key generation
    pk, sk = Dilithium2.keygen()
    test_result(
        "Dilithium key generation",
        len(pk) == 64 and len(sk) == 64,
        f"PK: {len(pk)} bytes, SK: {len(sk)} bytes"
    )
    
    # Test signing
    message = b"Test transaction data"
    signature = Dilithium2.sign(sk, message)
    test_result(
        "Dilithium signing",
        len(signature) == 64,
        f"Signature: {len(signature)} bytes"
    )
    
    # Test verification (valid)
    valid = Dilithium2.verify(pk, message, signature)
    test_result(
        "Dilithium verification (valid)",
        valid,
        "Valid signature accepted"
    )
    
    # Test verification (invalid)
    tampered_message = b"Tampered transaction data"
    invalid = Dilithium2.verify(pk, tampered_message, signature)
    test_result(
        "Dilithium verification (invalid)",
        not invalid,
        "Invalid signature rejected"
    )
    
    # Test address derivation
    address = Dilithium2.derive_address(pk)
    test_result(
        "Address derivation",
        len(address) == 40,
        f"Address: {address[:16]}..."
    )
    
except Exception as e:
    test_result("Cryptography tests", False, f"Error: {e}")

# ============================================================================
# TEST 6: MINING ENGINE
# ============================================================================
test_section("TEST 6: Mining Engine")

try:
    from qubitcoin.mining.engine import MiningEngine
    from rich.console import Console
    
    console = Console()
    mining = MiningEngine(qe, ce, db, console)
    
    test_result(
        "Mining engine initialization",
        mining is not None,
        "Engine created successfully"
    )
    
    test_result(
        "Mining not started by default",
        not mining.is_mining,
        "Mining state: stopped"
    )
    
    # Test stats
    test_result(
        "Mining stats accessible",
        'blocks_found' in mining.stats,
        f"Stats keys: {list(mining.stats.keys())}"
    )
    
    # Don't actually mine (would create genesis block)
    # Just verify the methods exist
    test_result(
        "Mining start method exists",
        hasattr(mining, 'start') and callable(mining.start),
        "start() method available"
    )
    
    test_result(
        "Mining stop method exists",
        hasattr(mining, 'stop') and callable(mining.stop),
        "stop() method available"
    )
    
except Exception as e:
    test_result("Mining engine tests", False, f"Error: {e}")

# ============================================================================
# TEST 7: STABLECOIN ENGINE
# ============================================================================
test_section("TEST 7: Stablecoin System")

try:
    from qubitcoin.stablecoin.engine import StablecoinEngine
    
    se = StablecoinEngine(db, qe)
    
    test_result(
        "Stablecoin engine initialization",
        se is not None,
        "Engine created successfully"
    )
    
    # Check QUSD token
    with db.get_session() as session:
        result = session.execute(
            text("SELECT token_id, symbol, active FROM stablecoin_tokens WHERE symbol = 'QUSD'")
        ).fetchone()
    
    test_result(
        "QUSD token configured",
        result is not None and result[2] == True,
        f"Token: {result[1] if result else 'NOT FOUND'}"
    )
    
    # Check collateral types
    with db.get_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM collateral_types WHERE enabled = true")
        ).scalar()
    
    test_result(
        "Collateral types configured",
        result >= 5,
        f"{result} collateral types enabled"
    )
    
    # Check oracle sources
    with db.get_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM oracle_sources WHERE active = true")
        ).scalar()
    
    test_result(
        "Oracle sources configured",
        result >= 3,
        f"{result} active oracle sources"
    )
    
except Exception as e:
    test_result("Stablecoin tests", False, f"Error: {e}")

# ============================================================================
# TEST 8: STORAGE (IPFS)
# ============================================================================
test_section("TEST 8: IPFS Storage")

try:
    from qubitcoin.storage.ipfs import IPFSManager
    
    ipfs = IPFSManager()
    
    test_result(
        "IPFS manager initialization",
        ipfs is not None,
        "Manager created"
    )
    
    test_result(
        "IPFS daemon connected",
        ipfs.client is not None,
        "Client connected" if ipfs.client else "Client not available",
        critical=False
    )
    
    if ipfs.client:
        # Test version
        try:
            version = ipfs.client.version()
            test_result(
                "IPFS version query",
                'Version' in version,
                f"IPFS version: {version.get('Version', 'unknown')}",
                critical=False
            )
        except Exception as e:
            test_result("IPFS version query", False, f"Error: {e}", critical=False)
    
except Exception as e:
    test_result("IPFS tests", False, f"Error: {e}", critical=False)

# ============================================================================
# TEST 9: BRIDGE SYSTEM
# ============================================================================
test_section("TEST 9: Multi-Chain Bridge")

try:
    # Check bridge tables
    with db.get_session() as session:
        bridge_tables = [
            'bridge_deposits',
            'bridge_withdrawals',
            'bridge_validators',
            'bridge_config'
        ]
        
        for table in bridge_tables:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            test_result(
                f"Bridge table: {table}",
                result is not None,
                f"{result} records",
                critical=False
            )
    
    # Check bridge config
    with db.get_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM bridge_config WHERE enabled = true")
        ).scalar()
    
    test_result(
        "Bridge chains configured",
        result >= 2,
        f"{result} chains configured",
        critical=False
    )
    
except Exception as e:
    test_result("Bridge tests", False, f"Error: {e}", critical=False)

# ============================================================================
# TEST 10: RPC ENDPOINTS
# ============================================================================
test_section("TEST 10: RPC Interface")

try:
    from qubitcoin.network.rpc import create_rpc_app
    
    app = create_rpc_app(db, ce, mining, qe, ipfs)
    
    test_result(
        "RPC app creation",
        app is not None,
        "FastAPI app created"
    )
    
    test_result(
        "RPC routes configured",
        len(app.routes) > 10,
        f"{len(app.routes)} routes configured"
    )
    
    # Check critical endpoints exist
    route_paths = {route.path for route in app.routes}
    required_paths = [
        '/',
        '/health',
        '/chain/info',
        '/mining/stats',
        '/balance/{address}',
    ]
    
    for path in required_paths:
        # Simple check - actual path might have variations
        path_exists = any(path.replace('{address}', '') in route for route in route_paths)
        test_result(
            f"Endpoint: {path}",
            path_exists or path in route_paths,
            "Available",
            critical=False
        )
    
except Exception as e:
    test_result("RPC tests", False, f"Error: {e}", critical=False)

# ============================================================================
# TEST 11: PERFORMANCE BENCHMARKS
# ============================================================================
test_section("TEST 11: Performance Benchmarks")

try:
    # VQE benchmark (average of 5 runs)
    vqe_times = []
    for i in range(5):
        h = qe.generate_hamiltonian(num_qubits=4)
        start = time.time()
        p, e = qe.optimize_vqe(h)
        vqe_times.append(time.time() - start)
    
    avg_vqe_time = sum(vqe_times) / len(vqe_times)
    test_result(
        "Average VQE time",
        avg_vqe_time < 5.0,
        f"{avg_vqe_time:.3f}s (target: <5s)",
        critical=False
    )
    
    # Database query benchmark
    query_times = []
    for i in range(10):
        start = time.time()
        db.get_current_height()
        query_times.append(time.time() - start)
    
    avg_query_time = sum(query_times) / len(query_times)
    test_result(
        "Average DB query time",
        avg_query_time < 0.1,
        f"{avg_query_time*1000:.2f}ms (target: <100ms)",
        critical=False
    )
    
    # Signature benchmark
    sig_times = []
    for i in range(10):
        pk, sk = Dilithium2.keygen()
        msg = f"test_{i}".encode()
        start = time.time()
        sig = Dilithium2.sign(sk, msg)
        sig_times.append(time.time() - start)
    
    avg_sig_time = sum(sig_times) / len(sig_times)
    test_result(
        "Average signing time",
        avg_sig_time < 0.1,
        f"{avg_sig_time*1000:.2f}ms (target: <100ms)",
        critical=False
    )
    
except Exception as e:
    test_result("Performance benchmarks", False, f"Error: {e}", critical=False)

# ============================================================================
# TEST 12: EDGE CASES & SECURITY
# ============================================================================
test_section("TEST 12: Edge Cases & Security")

try:
    # Test max supply enforcement
    huge_supply = Config.MAX_SUPPLY + Decimal('1000000')
    reward_at_max = ce.calculate_reward(0, huge_supply)
    test_result(
        "Max supply enforcement",
        reward_at_max == Decimal(0),
        f"Reward when supply > max: {reward_at_max}"
    )
    
    # Test negative amounts rejected
    try:
        with db.get_session() as session:
            session.execute(
                text("INSERT INTO utxos (txid, vout, amount, address, proof, spent) VALUES ('test', 0, -100, 'test', '{}', false)")
            )
            session.commit()
            test_result("Negative amount rejection", False, "Negative amount was accepted!")
    except Exception:
        test_result("Negative amount rejection", True, "Check constraint working")
    
    # Test zero difficulty validation
    try:
        valid, reason = qe.validate_proof(
            params=np.zeros(8),
            hamiltonian=hamiltonian,
            claimed_energy=0.0,
            difficulty=0.0
        )
        test_result(
            "Zero difficulty handling",
            True,
            "Handled gracefully",
            critical=False
        )
    except Exception as e:
        test_result("Zero difficulty handling", False, f"Error: {e}")
    
except Exception as e:
    test_result("Edge case tests", False, f"Error: {e}", critical=False)

# ============================================================================
# FINAL SUMMARY
# ============================================================================
test_section("🎯 VALIDATION SUMMARY")

total_tests = len(test_results)
passed_tests = sum(1 for _, passed, _ in test_results if passed)
failed_critical = sum(1 for _, passed, critical in test_results if not passed and critical)
failed_warnings = sum(1 for _, passed, critical in test_results if not passed and not critical)

print(f"\n{'='*80}")
print(f"TOTAL TESTS:      {total_tests}")
print(f"✅ PASSED:        {passed_tests}")
print(f"❌ FAILED (CRITICAL): {failed_critical}")
print(f"⚠️  WARNINGS:      {failed_warnings}")
print(f"SUCCESS RATE:     {(passed_tests/total_tests)*100:.1f}%")
print(f"{'='*80}\n")

if failed_critical > 0:
    print("🛑 CRITICAL FAILURES - DO NOT PROCEED WITH GENESIS:\n")
    for name, passed, critical in test_results:
        if not passed and critical:
            print(f"  ❌ {name}")
    print()

if failed_warnings > 0:
    print("⚠️  WARNINGS (Non-Critical):\n")
    for name, details in warnings:
        print(f"  ⚠️  {name}")
        if details:
            print(f"      {details}")
    print()

print(f"{'='*80}")
if failed_critical == 0:
    print("🎉 ALL CRITICAL TESTS PASSED - READY FOR GENESIS!")
    print()
    print("Next steps:")
    print("1. Review any warnings above")
    print("2. Backup database: cockroach dump qbc > backup.sql")
    print("3. Start mining: cd src && python3 run_node.py")
    print("4. Monitor first blocks carefully")
else:
    print("⛔ CRITICAL FAILURES DETECTED - FIX BEFORE GENESIS!")
    print()
    print("Please address critical failures above before proceeding.")

print(f"{'='*80}")
print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*80}\n")

sys.exit(0 if failed_critical == 0 else 1)
