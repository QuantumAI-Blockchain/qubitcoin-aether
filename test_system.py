#!/usr/bin/env python3
"""
Qubitcoin Comprehensive System Test
Tests all components before genesis launch
"""

import sys
import os
import importlib.util
from decimal import Decimal

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 70)
print("QUBITCOIN COMPREHENSIVE SYSTEM TEST")
print("=" * 70)
print()

test_results = []

def test_section(name):
    """Print test section header"""
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}\n")

def test_result(name, passed, details=""):
    """Record and print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"       {details}")
    test_results.append((name, passed))
    return passed

# ============================================================================
# PHASE 1: FILE STRUCTURE
# ============================================================================
test_section("PHASE 1: File Structure Verification")

required_files = [
    'src/qubitcoin/__init__.py',
    'src/qubitcoin/config.py',
    'src/qubitcoin/node.py',
    'src/qubitcoin/database/manager.py',
    'src/qubitcoin/database/models.py',
    'src/qubitcoin/quantum/engine.py',
    'src/qubitcoin/quantum/crypto.py',
    'src/qubitcoin/consensus/engine.py',
    'src/qubitcoin/mining/engine.py',
    'src/qubitcoin/network/rpc.py',
    'src/qubitcoin/storage/ipfs.py',
    'src/qubitcoin/stablecoin/engine.py',
    'src/qubitcoin/contracts/engine.py',
    'src/qubitcoin/contracts/executor.py',
    'src/qubitcoin/bridge/__init__.py',
    'src/qubitcoin/bridge/base.py',
    'src/qubitcoin/bridge/ethereum.py',
    'src/qubitcoin/bridge/solana.py',
    'src/qubitcoin/bridge/manager.py',
    'src/qubitcoin/utils/logger.py',
    'src/qubitcoin/utils/metrics.py',
    'src/run_node.py',
    'scripts/multi_chain_bridge.sql',
    '.env.bridge',
]

for filepath in required_files:
    exists = os.path.exists(filepath)
    test_result(f"File exists: {filepath}", exists)

# ============================================================================
# PHASE 2: PYTHON IMPORTS
# ============================================================================
test_section("PHASE 2: Python Module Import Tests")

modules_to_test = [
    ('qubitcoin', 'Main module'),
    ('qubitcoin.config', 'Configuration'),
    ('qubitcoin.database', 'Database layer'),
    ('qubitcoin.quantum', 'Quantum engine'),
    ('qubitcoin.consensus', 'Consensus engine'),
    ('qubitcoin.mining', 'Mining engine'),
    ('qubitcoin.network', 'Network/RPC'),
    ('qubitcoin.storage', 'IPFS storage'),
    ('qubitcoin.stablecoin', 'Stablecoin engine'),
    ('qubitcoin.contracts', 'Contract system'),
    ('qubitcoin.bridge', 'Bridge module'),
    ('qubitcoin.utils', 'Utilities'),
]

for module_name, description in modules_to_test:
    try:
        module = importlib.import_module(module_name)
        test_result(f"Import {module_name}", True, description)
    except Exception as e:
        test_result(f"Import {module_name}", False, f"Error: {e}")

# ============================================================================
# PHASE 3: CONFIGURATION VALIDATION
# ============================================================================
test_section("PHASE 3: Configuration Validation")

try:
    from qubitcoin.config import Config
    
    # Check critical config values
    test_result("Config.MAX_SUPPLY exists", hasattr(Config, 'MAX_SUPPLY'))
    test_result("Config.INITIAL_REWARD exists", hasattr(Config, 'INITIAL_REWARD'))
    test_result("Config.TARGET_BLOCK_TIME exists", hasattr(Config, 'TARGET_BLOCK_TIME'))
    
    # Verify values
    test_result("MAX_SUPPLY is Decimal", isinstance(Config.MAX_SUPPLY, Decimal))
    test_result("INITIAL_REWARD is Decimal", isinstance(Config.INITIAL_REWARD, Decimal))
    
    # Check SUSY economics
    if hasattr(Config, 'MAX_SUPPLY'):
        test_result(
            "MAX_SUPPLY = 3.3B",
            Config.MAX_SUPPLY == Decimal('3300000000'),
            f"Actual: {Config.MAX_SUPPLY}"
        )
    
    if hasattr(Config, 'INITIAL_REWARD'):
        test_result(
            "INITIAL_REWARD = 15.27",
            Config.INITIAL_REWARD == Decimal('15.27'),
            f"Actual: {Config.INITIAL_REWARD}"
        )
    
    if hasattr(Config, 'TARGET_BLOCK_TIME'):
        test_result(
            "TARGET_BLOCK_TIME = 3.3s",
            Config.TARGET_BLOCK_TIME == 3.3,
            f"Actual: {Config.TARGET_BLOCK_TIME}"
        )
    
    if hasattr(Config, 'HALVING_INTERVAL'):
        test_result(
            "HALVING_INTERVAL = 15,474,020",
            Config.HALVING_INTERVAL == 15474020,
            f"Actual: {Config.HALVING_INTERVAL}"
        )

except Exception as e:
    test_result("Config module", False, f"Error: {e}")

# ============================================================================
# PHASE 4: DATABASE CONNECTION
# ============================================================================
test_section("PHASE 4: Database Connectivity")

try:
    from qubitcoin.database.manager import DatabaseManager
    
    db = DatabaseManager()
    test_result("DatabaseManager initialization", True)
    
    # Test basic query
    with db.get_session() as session:
        from sqlalchemy import text
        result = session.execute(text("SELECT 1"))
        test_result("Database connection", result.scalar() == 1)
    
    # Check blockchain height
    height = db.get_current_height()
    test_result("Get blockchain height", True, f"Current height: {height}")
    
    # Check total supply
    supply = db.get_total_supply()
    test_result("Get total supply", True, f"Current supply: {supply} QBC")
    
except Exception as e:
    test_result("Database tests", False, f"Error: {e}")

# ============================================================================
# PHASE 5: DATABASE TABLES
# ============================================================================
test_section("PHASE 5: Database Schema Verification")

required_tables = [
    # Core tables
    'users', 'utxos', 'transactions', 'blocks', 'supply',
    # Research tables
    'solved_hamiltonians', 'susy_swaps',
    # Network tables
    'peer_reputation', 'ipfs_snapshots',
    # Contract tables
    'contracts', 'contract_storage', 'contract_events', 'contract_deployments',
    # Stablecoin tables
    'stablecoin_tokens', 'stablecoin_positions', 'stablecoin_liquidations',
    'collateral_types', 'stablecoin_params', 'oracle_sources',
    # Bridge tables
    'bridge_deposits', 'bridge_withdrawals', 'bridge_validators',
    'bridge_approvals', 'bridge_events', 'bridge_config',
    'bridge_stats', 'bridge_sync_status',
]

try:
    with db.get_session() as session:
        from sqlalchemy import text
        result = session.execute(text("SHOW TABLES"))
        existing_tables = [row[1] for row in result]
    
    for table in required_tables:
        exists = table in existing_tables
        test_result(f"Table: {table}", exists)
    
    test_result(
        "Total tables",
        len(existing_tables) >= 45,
        f"Found {len(existing_tables)} tables"
    )

except Exception as e:
    test_result("Table verification", False, f"Error: {e}")

# ============================================================================
# PHASE 6: COMPONENT INITIALIZATION
# ============================================================================
test_section("PHASE 6: Component Initialization Tests")

try:
    from qubitcoin.quantum.engine import QuantumEngine
    qe = QuantumEngine()
    test_result("QuantumEngine initialization", True)
    test_result("QuantumEngine has estimator", qe.estimator is not None)
except Exception as e:
    test_result("QuantumEngine", False, f"Error: {e}")

try:
    from qubitcoin.consensus.engine import ConsensusEngine
    ce = ConsensusEngine(qe)
    test_result("ConsensusEngine initialization", True)
except Exception as e:
    test_result("ConsensusEngine", False, f"Error: {e}")

try:
    from qubitcoin.stablecoin.engine import StablecoinEngine
    se = StablecoinEngine(db, qe)
    test_result("StablecoinEngine initialization", True)
except Exception as e:
    test_result("StablecoinEngine", False, f"Error: {e}")

try:
    from qubitcoin.contracts.executor import ContractExecutor
    cx = ContractExecutor(db, qe)
    test_result("ContractExecutor initialization", True)
except Exception as e:
    test_result("ContractExecutor", False, f"Error: {e}")

try:
    from qubitcoin.storage.ipfs import IPFSManager
    ipfs = IPFSManager()
    test_result("IPFSManager initialization", True)
    test_result("IPFS connected", ipfs.client is not None)
except Exception as e:
    test_result("IPFSManager", False, f"Error: {e}")

# ============================================================================
# PHASE 7: BRIDGE MODULE
# ============================================================================
test_section("PHASE 7: Bridge Module Tests")

try:
    from qubitcoin.bridge import BridgeManager, ChainType, BridgeStatus
    test_result("Bridge imports", True)
    
    bridge_manager = BridgeManager(db)
    test_result("BridgeManager initialization", True)
    
    # Test enum values
    test_result("ChainType.ETHEREUM exists", hasattr(ChainType, 'ETHEREUM'))
    test_result("ChainType.SOLANA exists", hasattr(ChainType, 'SOLANA'))
    test_result("BridgeStatus.COMPLETED exists", hasattr(BridgeStatus, 'COMPLETED'))
    
except Exception as e:
    test_result("Bridge module", False, f"Error: {e}")

# ============================================================================
# PHASE 8: QUANTUM FUNCTIONALITY
# ============================================================================
test_section("PHASE 8: Quantum Engine Functionality")

try:
    import numpy as np
    import time
    
    # Generate Hamiltonian
    hamiltonian = qe.generate_hamiltonian(num_qubits=4)
    test_result("Generate Hamiltonian", len(hamiltonian) > 0)
    
    # VQE optimization
    start = time.time()
    params, energy = qe.optimize_vqe(hamiltonian)
    duration = time.time() - start
    
    test_result("VQE optimization", isinstance(energy, float))
    test_result(
        "VQE performance",
        duration < 5.0,
        f"Completed in {duration:.3f}s"
    )
    
    # Proof validation
    valid, reason = qe.validate_proof(
        params=params,
        hamiltonian=hamiltonian,
        claimed_energy=energy,
        difficulty=0.5
    )
    test_result("Proof validation", valid, reason)

except Exception as e:
    test_result("Quantum tests", False, f"Error: {e}")

# ============================================================================
# PHASE 9: ECONOMICS VALIDATION
# ============================================================================
test_section("PHASE 9: Economics & Consensus Tests")

try:
    # Test reward calculation
    reward_0 = ce.calculate_reward(0, Decimal(0))
    test_result(
        "Genesis reward",
        reward_0 == Decimal('15.27'),
        f"Block 0: {reward_0} QBC"
    )
    
    # Test halving
    reward_halving = ce.calculate_reward(15474020, Decimal(0))
    expected_halving = Decimal('15.27') / Decimal('1.618')  # Golden ratio halving
    test_result(
        "First halving reward",
        abs(reward_halving - expected_halving) < Decimal('0.01'),
        f"Block 15,474,020: {reward_halving} QBC (expected ~{expected_halving})"
    )
    
    # Test difficulty calculation
    difficulty = ce.calculate_difficulty(0, db)
    test_result(
        "Initial difficulty",
        difficulty == Config.INITIAL_DIFFICULTY,
        f"Difficulty: {difficulty}"
    )

except Exception as e:
    test_result("Economics tests", False, f"Error: {e}")

# ============================================================================
# PHASE 10: STABLECOIN VERIFICATION
# ============================================================================
test_section("PHASE 10: Stablecoin System Tests")

try:
    # Check QUSD token
    with db.get_session() as session:
        from sqlalchemy import text
        result = session.execute(
            text("SELECT * FROM stablecoin_tokens WHERE symbol = 'QUSD'")
        ).fetchone()
    
    test_result("QUSD token exists", result is not None)
    
    if result:
        test_result("QUSD is active", result[5] == True)  # active column
    
    # Check collateral types
    with db.get_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM collateral_types")
        )
        count = result.scalar()
    
    test_result("Collateral types configured", count >= 5, f"Found {count} types")
    
    # Check oracle sources
    with db.get_session() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM oracle_sources WHERE active = true")
        )
        count = result.scalar()
    
    test_result("Active oracles", count >= 3, f"Found {count} oracles")

except Exception as e:
    test_result("Stablecoin tests", False, f"Error: {e}")

# ============================================================================
# PHASE 11: BRIDGE DATABASE
# ============================================================================
test_section("PHASE 11: Bridge Database Tests")

try:
    # Check bridge config
    with db.get_session() as session:
        from sqlalchemy import text
        result = session.execute(
            text("SELECT COUNT(*) FROM bridge_config")
        )
        count = result.scalar()
    
    test_result("Bridge configs", count >= 2, f"Found {count} chains configured")
    
    # Check views
    with db.get_session() as session:
        result = session.execute(text("SELECT * FROM pending_deposits"))
        test_result("View: pending_deposits", True)
        
        result = session.execute(text("SELECT * FROM bridge_tvl"))
        test_result("View: bridge_tvl", True)

except Exception as e:
    test_result("Bridge database tests", False, f"Error: {e}")

# ============================================================================
# PHASE 12: DEPENDENCIES CHECK
# ============================================================================
test_section("PHASE 12: Python Dependencies")

required_packages = [
    'fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2',
    'qiskit', 'qiskit_aer', 'scipy', 'numpy',
    'dotenv', 'rich', 'requests',
    'ipfshttpclient', 'prometheus_client', 'pydantic',
    'web3', 'eth_account', 'solana', 'solders',
]

for package in required_packages:
    try:
        __import__(package.replace('-', '_'))
        test_result(f"Package: {package}", True)
    except ImportError:
        test_result(f"Package: {package}", False, "Not installed")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
test_section("TEST SUMMARY")

total_tests = len(test_results)
passed_tests = sum(1 for _, passed in test_results if passed)
failed_tests = total_tests - passed_tests

print(f"\nTotal Tests: {total_tests}")
print(f"✅ Passed: {passed_tests}")
print(f"❌ Failed: {failed_tests}")
print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

if failed_tests > 0:
    print("\n⚠️  FAILED TESTS:")
    for name, passed in test_results:
        if not passed:
            print(f"  ❌ {name}")

print("\n" + "=" * 70)
if failed_tests == 0:
    print("🎉 ALL SYSTEMS OPERATIONAL - READY FOR GENESIS!")
else:
    print("⚠️  PLEASE FIX FAILED TESTS BEFORE GENESIS")
print("=" * 70)

sys.exit(0 if failed_tests == 0 else 1)
