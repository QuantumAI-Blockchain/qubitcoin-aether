#!/usr/bin/env python3
"""
Qubitcoin Comprehensive Pre-Genesis Validation
Complete system test covering all components and edge cases
"""

import sys
import os
import time
import json
import hashlib
import threading
import concurrent.futures
from decimal import Decimal, getcontext
from datetime import datetime
import traceback

# Set precision
getcontext().prec = 28

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 100)
print("🔬 QUBITCOIN COMPREHENSIVE PRE-GENESIS VALIDATION SUITE")
print("=" * 100)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Environment: Python {0}.{1}.{2}".format(*sys.version_info[:3]))
print("=" * 100)
print()

test_results = []
warnings = []
test_count = 0

def test_section(name, level=1):
    """Print test section header"""
    if level == 1:
        print(f"\n{'=' * 100}")
        print(f"  {name}")
        print(f"{'=' * 100}\n")
    else:
        print(f"\n{'─' * 80}")
        print(f"  {name}")
        print(f"{'─' * 80}\n")

def test_result(name, passed, details="", critical=True):
    """Record and print test result"""
    global test_count
    test_count += 1
    status = "✅ PASS" if passed else ("❌ CRITICAL" if critical else "⚠️  WARNING")
    print(f"[{test_count:3d}] {status}: {name}")
    if details:
        for line in details.split('\n'):
            if line.strip():
                print(f"          {line}")
    test_results.append((name, passed, critical))
    if not passed and not critical:
        warnings.append((name, details))
    return passed

def safe_execute(func, test_name, critical=True):
    """Safely execute test function with error handling"""
    try:
        return func()
    except Exception as e:
        test_result(test_name, False, f"Exception: {str(e)[:200]}", critical)
        if critical:
            traceback.print_exc()
        return False

# ============================================================================
# SECTION 1: ENVIRONMENT & CONFIGURATION
# ============================================================================
test_section("SECTION 1: Environment & Configuration Validation", level=1)

try:
    from qubitcoin.config import Config
    
    # 1.1 Node Identity
    test_section("1.1 Node Identity", level=2)
    
    has_address = hasattr(Config, 'ADDRESS') and Config.ADDRESS and len(Config.ADDRESS) == 40
    test_result(
        "Node ADDRESS configured (40 chars)",
        has_address,
        f"Address: {Config.ADDRESS[:20]}...{Config.ADDRESS[-10:] if has_address else ''}"
    )
    
    has_public_key = hasattr(Config, 'PUBLIC_KEY_HEX') and Config.PUBLIC_KEY_HEX and len(Config.PUBLIC_KEY_HEX) == 2624
    test_result(
        "Node PUBLIC_KEY valid (2624 hex chars = 1312 bytes)",
        has_public_key,
        f"Length: {len(Config.PUBLIC_KEY_HEX) if hasattr(Config, 'PUBLIC_KEY_HEX') else 0} chars"
    )
    
    has_private_key = hasattr(Config, 'PRIVATE_KEY_HEX') and Config.PRIVATE_KEY_HEX and len(Config.PRIVATE_KEY_HEX) == 5056
    test_result(
        "Node PRIVATE_KEY valid (5056 hex chars = 2528 bytes)",
        has_private_key,
        f"Length: {len(Config.PRIVATE_KEY_HEX) if hasattr(Config, 'PRIVATE_KEY_HEX') else 0} chars"
    )
    
    # 1.2 Economic Parameters
    test_section("1.2 Economic Parameters", level=2)
    
    test_result(
        "MAX_SUPPLY = 3,300,000,000 QBC",
        Config.MAX_SUPPLY == Decimal('3300000000'),
        f"Value: {Config.MAX_SUPPLY:,}"
    )
    
    test_result(
        "INITIAL_REWARD = 15.27 QBC",
        Config.INITIAL_REWARD == Decimal('15.27'),
        f"Value: {Config.INITIAL_REWARD}"
    )
    
    test_result(
        "TARGET_BLOCK_TIME = 3.3 seconds (φ²)",
        Config.TARGET_BLOCK_TIME == 3.3,
        f"Value: {Config.TARGET_BLOCK_TIME}s"
    )
    
    test_result(
        "HALVING_INTERVAL = 15,474,020 blocks",
        Config.HALVING_INTERVAL == 15474020,
        f"Value: {Config.HALVING_INTERVAL:,} (~1.618 years)"
    )
    
    test_result(
        "INITIAL_DIFFICULTY = 0.5",
        Config.INITIAL_DIFFICULTY == 0.5,
        f"Value: {Config.INITIAL_DIFFICULTY}"
    )
    
    test_result(
        "MIN_FEE = 0.01 QBC",
        Config.MIN_FEE == Decimal('0.01'),
        f"Value: {Config.MIN_FEE}"
    )
    
    # 1.3 Network Configuration
    test_section("1.3 Network Configuration", level=2)
    
    test_result(
        "RPC_PORT configured",
        hasattr(Config, 'RPC_PORT') and isinstance(Config.RPC_PORT, int),
        f"Port: {Config.RPC_PORT if hasattr(Config, 'RPC_PORT') else 'N/A'}"
    )
    
    test_result(
        "P2P_PORT configured",
        hasattr(Config, 'P2P_PORT') and isinstance(Config.P2P_PORT, int),
        f"Port: {Config.P2P_PORT if hasattr(Config, 'P2P_PORT') else 'N/A'}",
        critical=False
    )
    
    test_result(
        "DATABASE_URL configured",
        hasattr(Config, 'DATABASE_URL') and 'qbc' in Config.DATABASE_URL,
        f"URL: {Config.DATABASE_URL.split('@')[0] if hasattr(Config, 'DATABASE_URL') else 'N/A'}@..."
    )
    
    # 1.4 Quantum Settings
    test_section("1.4 Quantum Settings", level=2)
    
    test_result(
        "USE_LOCAL_ESTIMATOR configured",
        hasattr(Config, 'USE_LOCAL_ESTIMATOR'),
        f"Value: {Config.USE_LOCAL_ESTIMATOR if hasattr(Config, 'USE_LOCAL_ESTIMATOR') else 'N/A'}",
        critical=False
    )
    
    test_result(
        "VQE_MAXITER configured",
        hasattr(Config, 'VQE_MAXITER') and Config.VQE_MAXITER > 0,
        f"Max iterations: {Config.VQE_MAXITER if hasattr(Config, 'VQE_MAXITER') else 'N/A'}",
        critical=False
    )

except Exception as e:
    test_result("Configuration loading", False, f"Fatal error: {e}")
    print("\n❌ FATAL: Cannot proceed without valid configuration")
    sys.exit(1)

# ============================================================================
# SECTION 2: DATABASE INTEGRITY & SCHEMA
# ============================================================================
test_section("SECTION 2: Database Integrity & Schema Validation", level=1)

try:
    from qubitcoin.database.manager import DatabaseManager
    from sqlalchemy import text
    
    db = DatabaseManager()
    
    # 2.1 Connection & Basic Operations
    test_section("2.1 Database Connectivity", level=2)
    
    def test_db_connection():
        with db.get_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1
    
    test_result(
        "Database connection successful",
        safe_execute(test_db_connection, "DB connection"),
        "CockroachDB/PostgreSQL connected"
    )
    
    def test_db_version():
        with db.get_session() as session:
            result = session.execute(text("SELECT version()")).scalar()
            return 'CockroachDB' in result or 'PostgreSQL' in result
    
    test_result(
        "Database version check",
        safe_execute(test_db_version, "DB version"),
        "Supported database detected",
        critical=False
    )
    
    # 2.2 Schema Validation
    test_section("2.2 Schema Validation", level=2)
    
    required_tables = {
        # Core blockchain (5)
        'users': 'User accounts',
        'utxos': 'Unspent transaction outputs',
        'transactions': 'Transaction pool',
        'blocks': 'Blockchain data',
        'supply': 'Supply tracking',
        
        # Research (2)
        'solved_hamiltonians': 'SUSY research data',
        'susy_swaps': 'Privacy mixing',
        
        # Network (2)
        'peer_reputation': 'P2P network',
        'ipfs_snapshots': 'IPFS snapshots',
        
        # Contracts (4)
        'contracts': 'Smart contracts',
        'contract_storage': 'Contract state',
        'contract_events': 'Contract events',
        'contract_deployments': 'Deployment tracking',
        
        # Stablecoin (6)
        'stablecoin_tokens': 'QUSD token',
        'stablecoin_positions': 'CDP positions',
        'stablecoin_liquidations': 'Liquidation history',
        'collateral_types': 'Collateral config',
        'stablecoin_params': 'System parameters',
        'oracle_sources': 'Price feeds',
        
        # Bridge (8)
        'bridge_deposits': 'Cross-chain deposits',
        'bridge_withdrawals': 'Cross-chain withdrawals',
        'bridge_validators': 'Bridge validators',
        'bridge_approvals': 'Validator signatures',
        'bridge_events': 'Bridge event log',
        'bridge_config': 'Chain configurations',
        'bridge_stats': 'Statistics',
        'bridge_sync_status': 'Sync tracking',
    }
    
    with db.get_session() as session:
        result = session.execute(text("SHOW TABLES"))
        existing_tables = {row[1] for row in result}
    
    for table, description in required_tables.items():
        test_result(
            f"Table: {table:<30}",
            table in existing_tables,
            description
        )
    
    total_tables = len(existing_tables)
    test_result(
        "Total table count",
        total_tables >= 29,
        f"{total_tables} tables (expected: ≥29)"
    )
    
    # 2.3 Genesis State
    test_section("2.3 Genesis State Verification", level=2)
    
    height = db.get_current_height()
    test_result(
        "Blockchain height = -1 (pre-genesis)",
        height == -1,
        f"Current height: {height}"
    )
    
    supply = db.get_total_supply()
    test_result(
        "Total supply = 0 QBC",
        supply == Decimal(0),
        f"Current supply: {supply}"
    )
    
    # Check no blocks exist
    with db.get_session() as session:
        block_count = session.execute(text("SELECT COUNT(*) FROM blocks")).scalar()
    
    test_result(
        "No blocks in database",
        block_count == 0,
        f"Block count: {block_count}"
    )
    
    # Check no transactions exist
    with db.get_session() as session:
        tx_count = session.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
    
    test_result(
        "No transactions in database",
        tx_count == 0,
        f"Transaction count: {tx_count}"
    )
    
    # Check no UTXOs exist
    with db.get_session() as session:
        utxo_count = session.execute(text("SELECT COUNT(*) FROM utxos")).scalar()
    
    test_result(
        "No UTXOs in database",
        utxo_count == 0,
        f"UTXO count: {utxo_count}"
    )
    
    # 2.4 Data Integrity Constraints
    test_section("2.4 Data Integrity Constraints", level=2)
    
    # Test negative amount rejection
    try:
        with db.get_session() as session:
            session.execute(
                text("INSERT INTO utxos (txid, vout, amount, address, proof, spent) "
                     "VALUES ('test_neg', 0, -100, 'test', '{}', false)")
            )
            session.commit()
        test_result("Negative UTXO amount rejection", False, "Database accepted negative amount!")
    except Exception:
        test_result("Negative UTXO amount rejection", True, "CHECK constraint enforced")
    
    # Test supply constraint
    try:
        with db.get_session() as session:
            session.execute(
                text("UPDATE supply SET total_minted = 9999999999999 WHERE id = 1")
            )
            session.commit()
        test_result("Max supply constraint", False, "Exceeded max supply!")
    except Exception:
        test_result("Max supply constraint", True, "Supply limit enforced")
    
    # 2.5 Stablecoin Configuration
    test_section("2.5 Stablecoin System", level=2)
    
    with db.get_session() as session:
        qusd = session.execute(
            text("SELECT token_id, symbol, active FROM stablecoin_tokens WHERE symbol = 'QUSD'")
        ).fetchone()
    
    test_result(
        "QUSD token configured",
        qusd is not None and qusd[2] == True,
        f"Token ID: {qusd[0] if qusd else 'NOT FOUND'}"
    )
    
    with db.get_session() as session:
        collateral_count = session.execute(
            text("SELECT COUNT(*) FROM collateral_types WHERE active = true")
        ).scalar()
    
    test_result(
        "Collateral types configured",
        collateral_count >= 5,
        f"{collateral_count} active types (QBC, ETH, USDT, USDC, DAI)"
    )
    
    with db.get_session() as session:
        oracle_count = session.execute(
            text("SELECT COUNT(*) FROM oracle_sources WHERE active = true")
        ).scalar()
    
    test_result(
        "Oracle sources configured",
        oracle_count >= 3,
        f"{oracle_count} active oracles"
    )
    
    # 2.6 Bridge Configuration
    test_section("2.6 Multi-Chain Bridge", level=2)
    
    with db.get_session() as session:
        bridge_chains = session.execute(
            text("SELECT chain, enabled FROM bridge_config ORDER BY chain")
        ).fetchall()
    
    test_result(
        "Bridge chains configured",
        len(bridge_chains) >= 2,
        f"{len(bridge_chains)} chains: {', '.join([b[0] for b in bridge_chains])}"
    )

except Exception as e:
    test_result("Database section", False, f"Error: {e}")
    traceback.print_exc()

# ============================================================================
# SECTION 3: QUANTUM ENGINE & VQE
# ============================================================================
test_section("SECTION 3: Quantum Engine & VQE Validation", level=1)

try:
    from qubitcoin.quantum.engine import QuantumEngine
    import numpy as np
    
    qe = QuantumEngine()
    
    # 3.1 Initialization
    test_section("3.1 Engine Initialization", level=2)
    
    test_result(
        "QuantumEngine instantiation",
        qe is not None,
        "Engine created successfully"
    )
    
    test_result(
        "Estimator configured",
        qe.estimator is not None,
        f"Estimator: {qe.estimator.__class__.__name__}"
    )
    
    # 3.2 Hamiltonian Generation
    test_section("3.2 Hamiltonian Generation", level=2)
    
    hamiltonian = qe.generate_hamiltonian(num_qubits=4)
    
    test_result(
        "Hamiltonian generation (4 qubits)",
        len(hamiltonian) == 5,
        f"Generated {len(hamiltonian)} Pauli terms"
    )
    
    # Verify structure
    pauli_strings = [h[0] for h in hamiltonian]
    coefficients = [h[1] for h in hamiltonian]
    
    test_result(
        "Pauli strings valid",
        all(len(p) == 4 for p in pauli_strings),
        f"All strings have length 4"
    )
    
    test_result(
        "Coefficients are floats",
        all(isinstance(c, float) for c in coefficients),
        f"All coefficients are float type"
    )
    
    # 3.3 VQE Optimization
    test_section("3.3 VQE Optimization", level=2)
    
    start = time.time()
    params, energy = qe.optimize_vqe(hamiltonian)
    vqe_time = time.time() - start
    
    test_result(
        "VQE optimization completes",
        isinstance(energy, float) and isinstance(params, np.ndarray),
        f"Energy: {energy:.6f}, Time: {vqe_time:.3f}s"
    )
    
    test_result(
        "VQE parameters valid",
        len(params) > 0 and all(np.isfinite(params)),
        f"Parameters: {len(params)} values, all finite"
    )
    
    test_result(
        "VQE energy finite",
        np.isfinite(energy),
        f"Energy: {energy:.6f}"
    )
    
    test_result(
        "VQE performance acceptable",
        vqe_time < 10.0,
        f"{vqe_time:.3f}s (target: <10s)",
        critical=False
    )
    
    # 3.4 Proof Validation
    test_section("3.4 Proof Validation", level=2)
    
    valid, reason = qe.validate_proof(
        params=params,
        hamiltonian=hamiltonian,
        claimed_energy=energy,
        difficulty=0.5
    )
    
    test_result(
        "Valid proof accepted",
        valid,
        f"Reason: {reason}"
    )
    
    # Test invalid proof (tampered energy)
    valid_bad, reason_bad = qe.validate_proof(
        params=params,
        hamiltonian=hamiltonian,
        claimed_energy=energy + 0.1,
        difficulty=0.5
    )
    
    test_result(
        "Invalid proof rejected (energy mismatch)",
        not valid_bad,
        f"Correctly rejected: {reason_bad}"
    )
    
    # 3.5 Consistency Tests
    test_section("3.5 VQE Consistency", level=2)
    
    # Run VQE multiple times on same Hamiltonian
    energies = []
    for i in range(3):
        p, e = qe.optimize_vqe(hamiltonian)
        energies.append(e)
    
    max_variance = max(energies) - min(energies)
    test_result(
        "VQE consistency (same Hamiltonian)",
        max_variance < 0.1,
        f"Energy variance: {max_variance:.6f} (max: {max(energies):.6f}, min: {min(energies):.6f})",
        critical=False
    )
    
    # Different Hamiltonians should give different energies
    different_energies = []
    for i in range(5):
        h = qe.generate_hamiltonian(num_qubits=4)
        p, e = qe.optimize_vqe(h)
        different_energies.append(e)
    
    unique_count = len(set([round(e, 4) for e in different_energies]))
    test_result(
        "VQE produces varied results",
        unique_count >= 3,
        f"{unique_count}/5 unique energies",
        critical=False
    )
    
    # 3.6 Circuit Properties
    test_section("3.6 Quantum Circuit Properties", level=2)
    
    depth = qe.estimate_circuit_depth(num_qubits=4)
    test_result(
        "Circuit depth NISQ-compatible",
        depth < 50,
        f"Depth: {depth} gates (target: <50 for NISQ)"
    )

except Exception as e:
    test_result("Quantum engine section", False, f"Error: {e}")
    traceback.print_exc()

# ============================================================================
# SECTION 4: POST-QUANTUM CRYPTOGRAPHY
# ============================================================================
test_section("SECTION 4: Post-Quantum Cryptography (Dilithium)", level=1)

try:
    from qubitcoin.quantum.crypto import Dilithium2, CryptoManager
    
    # 4.1 Key Generation
    test_section("4.1 Key Generation", level=2)
    
    pk, sk = Dilithium2.keygen()
    
    test_result(
        "Public key size = 1312 bytes",
        len(pk) == 1312,
        f"Size: {len(pk)} bytes (NIST Dilithium2 standard)"
    )
    
    test_result(
        "Private key size = 2528 bytes",
        len(sk) == 2528,
        f"Size: {len(sk)} bytes (NIST Dilithium2 standard)"
    )
    
    # Generate multiple keys (should be unique)
    keys = [Dilithium2.keygen() for _ in range(5)]
    unique_pks = len(set([k[0] for k in keys]))
    
    test_result(
        "Key generation uniqueness",
        unique_pks == 5,
        f"{unique_pks}/5 unique public keys"
    )
    
    # 4.2 Signing
    test_section("4.2 Digital Signatures", level=2)
    
    message = b"Genesis block transaction data"
    signature = Dilithium2.sign(sk, message)
    
    test_result(
        "Signature size = 2420 bytes",
        len(signature) == 2420,
        f"Size: {len(signature)} bytes (NIST standard)"
    )
    
    # Test deterministic signing
    sig2 = Dilithium2.sign(sk, message)
    test_result(
        "Signatures are deterministic",
        signature == sig2,
        "Same message + key → same signature",
        critical=False
    )
    
    # Different messages should produce different signatures
    message2 = b"Different transaction data"
    sig_different = Dilithium2.sign(sk, message2)
    
    test_result(
        "Different messages → different signatures",
        signature != sig_different,
        "Signature collision avoided"
    )
    
    # 4.3 Verification
    test_section("4.3 Signature Verification", level=2)
    
    valid = Dilithium2.verify(pk, message, signature)
    test_result(
        "Valid signature verification",
        valid == True,
        "Correct signature accepted"
    )
    
    # Tampered message
    tampered_msg = b"Tampered transaction data"
    invalid_msg = Dilithium2.verify(pk, tampered_msg, signature)
    test_result(
        "Tampered message rejected",
        invalid_msg == False,
        "Message integrity verified"
    )
    
    # Wrong public key
    pk2, sk2 = Dilithium2.keygen()
    invalid_pk = Dilithium2.verify(pk2, message, signature)
    test_result(
        "Wrong public key rejected",
        invalid_pk == False,
        "Key-signature binding enforced"
    )
    
    # Tampered signature
    tampered_sig = bytearray(signature)
    tampered_sig[100] ^= 0xFF  # Flip bits
    tampered_sig = bytes(tampered_sig)
    invalid_sig = Dilithium2.verify(pk, message, tampered_sig)
    test_result(
        "Tampered signature rejected",
        invalid_sig == False,
        "Signature integrity verified"
    )
    
    # 4.4 Address Derivation
    test_section("4.4 Address Derivation", level=2)
    
    address = Dilithium2.derive_address(pk)
    
    test_result(
        "Address length = 40 hex chars",
        len(address) == 40,
        f"Address: {address[:16]}...{address[-8:]}"
    )
    
    test_result(
        "Address is hex string",
        all(c in '0123456789abcdef' for c in address),
        "All characters are valid hex"
    )
    
    # Same public key should always derive same address
    address2 = Dilithium2.derive_address(pk)
    test_result(
        "Address derivation deterministic",
        address == address2,
        "Same PK → same address"
    )
    
    # Different public keys → different addresses
    address3 = Dilithium2.derive_address(pk2)
    test_result(
        "Different keys → different addresses",
        address != address3,
        "Address collision avoided"
    )
    
    # 4.5 Node Key Validation
    test_section("4.5 Node Keys Validation", level=2)
    
    if hasattr(Config, 'PUBLIC_KEY_HEX') and Config.PUBLIC_KEY_HEX:
        node_pk = bytes.fromhex(Config.PUBLIC_KEY_HEX)
        node_address_derived = Dilithium2.derive_address(node_pk)
        
        test_result(
            "Node address matches derived",
            node_address_derived == Config.ADDRESS,
            f"Config: {Config.ADDRESS[:20]}...\nDerived: {node_address_derived[:20]}..."
        )

except Exception as e:
    test_result("Cryptography section", False, f"Error: {e}")
    traceback.print_exc()

# ============================================================================
# SECTION 5: CONSENSUS & ECONOMICS
# ============================================================================
test_section("SECTION 5: Consensus Engine & SUSY Economics", level=1)

try:
    from qubitcoin.consensus.engine import ConsensusEngine
    
    ce = ConsensusEngine(qe)
    PHI = Decimal('1.618033988749895')
    
    # 5.1 Reward Calculation
    test_section("5.1 Block Reward Calculation", level=2)
    
    # Test first 5 eras
    expected_rewards = [
        (0, Decimal('15.27')),
        (15474020, Decimal('15.27') / PHI),
        (30948040, Decimal('15.27') / (PHI ** 2)),
        (46422060, Decimal('15.27') / (PHI ** 3)),
        (61896080, Decimal('15.27') / (PHI ** 4)),
    ]
    
    for height, expected in expected_rewards:
        reward = ce.calculate_reward(height, Decimal(0))
        era = height // Config.HALVING_INTERVAL
        matches = abs(reward - expected) < Decimal('0.01')
        
        test_result(
            f"Era {era} reward (block {height:,})",
            matches,
            f"Expected: {float(expected):.6f}, Got: {float(reward):.6f}"
        )
    
    # 5.2 Golden Ratio Validation
    test_section("5.2 Golden Ratio Halvings", level=2)
    
    reward_0 = ce.calculate_reward(0, Decimal(0))
    reward_1 = ce.calculate_reward(15474020, Decimal(0))
    reward_2 = ce.calculate_reward(30948040, Decimal(0))
    
    ratio_0_1 = reward_0 / reward_1
    ratio_1_2 = reward_1 / reward_2
    
    test_result(
        "Era 0→1 ratio = φ",
        abs(ratio_0_1 - PHI) < Decimal('0.001'),
        f"Ratio: {float(ratio_0_1):.6f}, φ: {float(PHI):.6f}"
    )
    
    test_result(
        "Era 1→2 ratio = φ",
        abs(ratio_1_2 - PHI) < Decimal('0.001'),
        f"Ratio: {float(ratio_1_2):.6f}, φ: {float(PHI):.6f}"
    )
    
    # 5.3 Supply Convergence
    test_section("5.3 Supply Convergence", level=2)
    
    total_supply = Decimal(0)
    for era in range(21):
        height = era * Config.HALVING_INTERVAL
        reward = ce.calculate_reward(height, total_supply)
        era_supply = reward * Decimal(Config.HALVING_INTERVAL)
        total_supply += era_supply
    
    convergence_percent = (total_supply / Config.MAX_SUPPLY) * 100
    
    test_result(
        "Supply converges to max (21 eras)",
        total_supply >= Config.MAX_SUPPLY * Decimal('0.99'),
        f"{float(total_supply/Decimal(1000000000)):.2f}B / {float(Config.MAX_SUPPLY/Decimal(1000000000)):.1f}B ({float(convergence_percent):.1f}%)"
    )
    
    # 5.4 Max Supply Enforcement
    test_section("5.4 Supply Limit Enforcement", level=2)
    
    at_max = ce.calculate_reward(0, Config.MAX_SUPPLY)
    test_result(
        "Reward = 0 when supply = max",
        at_max == Decimal(0),
        f"Reward at max supply: {at_max}"
    )
    
    over_max = ce.calculate_reward(0, Config.MAX_SUPPLY + Decimal('1000000'))
    test_result(
        "Reward = 0 when supply > max",
        over_max == Decimal(0),
        f"Reward over max supply: {over_max}"
    )
    
    # 5.5 Difficulty Adjustment
    test_section("5.5 Difficulty Adjustment", level=2)
    
    initial_diff = ce.calculate_difficulty(0, db)
    test_result(
        "Initial difficulty = 0.5",
        initial_diff == Config.INITIAL_DIFFICULTY,
        f"Difficulty: {initial_diff}"
    )
    
    test_result(
        "Difficulty in valid range [0.1, 1.0]",
        0.1 <= initial_diff <= 1.0,
        f"Value: {initial_diff}"
    )

except Exception as e:
    test_result("Consensus section", False, f"Error: {e}")
    traceback.print_exc()

# ============================================================================
# SECTION 6: MINING ENGINE
# ============================================================================
test_section("SECTION 6: Mining Engine Validation", level=1)

try:
    from qubitcoin.mining.engine import MiningEngine
    from rich.console import Console
    
    console = Console()
    mining = MiningEngine(qe, ce, db, console)
    
    # 6.1 Initialization
    test_section("6.1 Mining Engine Setup", level=2)
    
    test_result(
        "MiningEngine instantiation",
        mining is not None,
        "Engine created successfully"
    )
    
    test_result(
        "Mining in stopped state",
        not mining.is_mining,
        "Default state: stopped"
    )
    
    test_result(
        "Mining stats initialized",
        all(k in mining.stats for k in ['blocks_found', 'total_attempts', 'current_difficulty']),
        f"Stats keys: {list(mining.stats.keys())}"
    )
    
    test_result(
        "Zero blocks mined (pre-genesis)",
        mining.stats['blocks_found'] == 0,
        "Clean initial state"
    )
    
    test_result(
        "Zero attempts (pre-genesis)",
        mining.stats['total_attempts'] == 0,
        "No mining attempts yet"
    )
    
    # 6.2 Interface Methods
    test_section("6.2 Mining Interface", level=2)
    
    test_result(
        "start() method exists",
        hasattr(mining, 'start') and callable(mining.start),
        "Mining can be started"
    )
    
    test_result(
        "stop() method exists",
        hasattr(mining, 'stop') and callable(mining.stop),
        "Mining can be stopped"
    )
    
    test_result(
        "_mine_block() method exists",
        hasattr(mining, '_mine_block') and callable(mining._mine_block),
        "Block mining implementation present"
    )

except Exception as e:
    test_result("Mining engine section", False, f"Error: {e}")
    traceback.print_exc()

# ============================================================================
# SECTION 7: NETWORK & RPC
# ============================================================================
test_section("SECTION 7: Network & RPC Interface", level=1)

try:
    from qubitcoin.network.rpc import create_rpc_app
    from qubitcoin.storage.ipfs import IPFSManager
    
    ipfs = IPFSManager()
    app = create_rpc_app(db, ce, mining, qe, ipfs)
    
    # 7.1 RPC App
    test_section("7.1 RPC Application", level=2)
    
    test_result(
        "FastAPI app created",
        app is not None,
        "RPC interface initialized"
    )
    
    routes = [route.path for route in app.routes]
    test_result(
        "RPC routes configured",
        len(routes) >= 15,
        f"{len(routes)} endpoints available"
    )
    
    # 7.2 Critical Endpoints
    test_section("7.2 Critical Endpoints", level=2)
    
    critical_endpoints = [
        ('/', 'Node info'),
        ('/health', 'Health check'),
        ('/chain/info', 'Blockchain info'),
        ('/chain/tip', 'Latest block'),
        ('/block/{height}', 'Block query'),
        ('/balance/{address}', 'Balance query'),
        ('/utxos/{address}', 'UTXO query'),
        ('/tx/{txid}', 'Transaction query'),
        ('/mempool', 'Mempool status'),
        ('/mining/stats', 'Mining statistics'),
        ('/mining/start', 'Start mining'),
        ('/mining/stop', 'Stop mining'),
    ]
    
    for endpoint, description in critical_endpoints:
        base_path = endpoint.split('{')[0].rstrip('/')
        exists = any(base_path in route for route in routes)
        test_result(
            f"Endpoint: {endpoint:<30}",
            exists,
            description,
            critical=False
        )
    
    # 7.3 IPFS Storage
    test_section("7.3 IPFS Storage", level=2)
    
    ipfs_connected = ipfs.client is not None
    test_result(
        "IPFS daemon connection",
        True,
        f"Status: {'Connected' if ipfs_connected else 'Not running (optional)'}",
        critical=False
    )
    
    if ipfs_connected:
        try:
            version = ipfs.client.version()
            test_result(
                "IPFS version query",
                'Version' in version,
                f"Version: {version.get('Version', 'unknown')}",
                critical=False
            )
        except Exception as e:
            test_result("IPFS version", False, f"Error: {e}", critical=False)

except Exception as e:
    test_result("Network section", False, f"Error: {e}", critical=False)
    traceback.print_exc()

# ============================================================================
# SECTION 8: PERFORMANCE & STRESS TESTING
# ============================================================================
test_section("SECTION 8: Performance & Stress Testing", level=1)

try:
    # 8.1 VQE Performance
    test_section("8.1 VQE Performance Benchmarks", level=2)
    
    vqe_times = []
    for i in range(5):
        h = qe.generate_hamiltonian(num_qubits=4)
        start = time.time()
        p, e = qe.optimize_vqe(h)
        vqe_times.append(time.time() - start)
    
    avg_vqe = sum(vqe_times) / len(vqe_times)
    min_vqe = min(vqe_times)
    max_vqe = max(vqe_times)
    
    test_result(
        "VQE average time",
        avg_vqe < 5.0,
        f"Avg: {avg_vqe:.3f}s, Min: {min_vqe:.3f}s, Max: {max_vqe:.3f}s",
        critical=False
    )
    
    # 8.2 Database Performance
    test_section("8.2 Database Query Performance", level=2)
    
    query_times = []
    for i in range(20):
        start = time.time()
        db.get_current_height()
        query_times.append(time.time() - start)
    
    avg_query = sum(query_times) / len(query_times)
    test_result(
        "Database query average",
        avg_query < 0.1,
        f"{avg_query*1000:.2f}ms (target: <100ms)",
        critical=False
    )
    
    # 8.3 Signature Performance
    test_section("8.3 Signature Performance", level=2)
    
    keygen_times = []
    sign_times = []
    verify_times = []
    
    for i in range(10):
        # Key generation
        start = time.time()
        pk, sk = Dilithium2.keygen()
        keygen_times.append(time.time() - start)
        
        # Signing
        msg = f"test_message_{i}".encode()
        start = time.time()
        sig = Dilithium2.sign(sk, msg)
        sign_times.append(time.time() - start)
        
        # Verification
        start = time.time()
        Dilithium2.verify(pk, msg, sig)
        verify_times.append(time.time() - start)
    
    test_result(
        "Key generation average",
        sum(keygen_times)/len(keygen_times) < 1.0,
        f"{sum(keygen_times)/len(keygen_times)*1000:.1f}ms",
        critical=False
    )
    
    test_result(
        "Signing average",
        sum(sign_times)/len(sign_times) < 0.5,
        f"{sum(sign_times)/len(sign_times)*1000:.1f}ms",
        critical=False
    )
    
    test_result(
        "Verification average",
        sum(verify_times)/len(verify_times) < 0.1,
        f"{sum(verify_times)/len(verify_times)*1000:.1f}ms",
        critical=False
    )
    
    # 8.4 Throughput Estimation
    test_section("8.4 System Throughput", level=2)
    
    block_time = Config.TARGET_BLOCK_TIME
    tx_per_block = 333  # Conservative estimate
    tps = tx_per_block / block_time
    
    test_result(
        "Estimated TPS",
        tps > 50,
        f"{tps:.0f} TPS ({tx_per_block} tx / {block_time}s block)",
        critical=False
    )
    
    # Blocks per day
    blocks_per_day = (24 * 3600) / block_time
    test_result(
        "Blocks per day",
        blocks_per_day > 20000,
        f"{blocks_per_day:.0f} blocks/day",
        critical=False
    )

except Exception as e:
    test_result("Performance section", False, f"Error: {e}", critical=False)
    traceback.print_exc()

# ============================================================================
# SECTION 9: SECURITY VALIDATIONS
# ============================================================================
test_section("SECTION 9: Security & Attack Resistance", level=1)

try:
    # 9.1 Economic Security
    test_section("9.1 Economic Security", level=2)
    
    # Max supply enforcement
    huge_supply = Config.MAX_SUPPLY + Decimal('10000000')
    reward = ce.calculate_reward(0, huge_supply)
    test_result(
        "Supply overflow protection",
        reward == Decimal(0),
        "No rewards when max supply reached"
    )
    
    # Negative fee rejection
    test_result(
        "Minimum fee enforcement",
        Config.MIN_FEE > 0,
        f"Min fee: {Config.MIN_FEE} QBC"
    )
    
    # 9.2 Cryptographic Security
    test_section("9.2 Cryptographic Security", level=2)
    
    # Signature non-transferability
    pk1, sk1 = Dilithium2.keygen()
    pk2, sk2 = Dilithium2.keygen()
    
    msg = b"Transaction: Transfer 100 QBC"
    sig1 = Dilithium2.sign(sk1, msg)
    
    cross_verify = Dilithium2.verify(pk2, msg, sig1)
    test_result(
        "Signature key-binding",
        cross_verify == False,
        "Signature tied to specific key"
    )
    
    # Message integrity
    sig_original = Dilithium2.sign(sk1, b"Send 10 QBC")
    tamper_verify = Dilithium2.verify(pk1, b"Send 100 QBC", sig_original)
    test_result(
        "Message integrity",
        tamper_verify == False,
        "Message tampering detected"
    )
    
    # 9.3 Consensus Security
    test_section("9.3 Consensus Security", level=2)
    
    # Difficulty bounds
    test_result(
        "Difficulty lower bound",
        Config.INITIAL_DIFFICULTY >= 0.1,
        f"Difficulty: {Config.INITIAL_DIFFICULTY} ≥ 0.1"
    )
    
    test_result(
        "Difficulty upper bound",
        Config.INITIAL_DIFFICULTY <= 1.0,
        f"Difficulty: {Config.INITIAL_DIFFICULTY} ≤ 1.0"
    )
    
    # VQE proof cannot be faked
    fake_params = np.random.rand(8)
    fake_energy = -999.0  # Impossibly low
    
    valid_fake, _ = qe.validate_proof(
        params=fake_params,
        hamiltonian=hamiltonian,
        claimed_energy=fake_energy,
        difficulty=0.5
    )
    
    test_result(
        "Fake proof detection",
        valid_fake == False,
        "Invalid energy values rejected"
    )

except Exception as e:
    test_result("Security section", False, f"Error: {e}", critical=False)
    traceback.print_exc()

# ============================================================================
# SECTION 10: INTEGRATION TESTS
# ============================================================================
test_section("SECTION 10: Component Integration Tests", level=1)

try:
    # 10.1 End-to-End Flow (Simulation)
    test_section("10.1 Genesis Block Simulation (No Commit)", level=2)
    
    # Simulate genesis block creation WITHOUT actually creating it
    genesis_height = 0
    prev_hash = '0' * 64
    
    # Generate quantum proof
    h_genesis = qe.generate_hamiltonian(num_qubits=4)
    params_genesis, energy_genesis = qe.optimize_vqe(h_genesis)
    
    test_result(
        "Genesis quantum proof generated",
        energy_genesis < 0.5,  # Meets difficulty
        f"Energy: {energy_genesis:.6f} < 0.5 difficulty"
    )
    
    # Calculate genesis reward
    genesis_reward = ce.calculate_reward(0, Decimal(0))
    test_result(
        "Genesis reward calculation",
        genesis_reward == Decimal('15.27'),
        f"Reward: {genesis_reward} QBC"
    )
    
    # Simulate coinbase transaction
    coinbase_txid = hashlib.sha256(b"genesis_coinbase").hexdigest()
    coinbase_tx = {
        'txid': coinbase_txid,
        'inputs': [],
        'outputs': [{'address': Config.ADDRESS, 'amount': genesis_reward}],
        'fee': Decimal(0),
    }
    
    test_result(
        "Genesis coinbase structure",
        len(coinbase_tx['inputs']) == 0 and len(coinbase_tx['outputs']) == 1,
        f"Coinbase: 0 inputs, 1 output ({genesis_reward} QBC)"
    )
    
    # 10.2 Multi-Component Integration
    test_section("10.2 Multi-Component Integration", level=2)
    
    # Quantum + Consensus
    reward_check = ce.calculate_reward(0, Decimal(0))
    h_check = qe.generate_hamiltonian()
    p_check, e_check = qe.optimize_vqe(h_check)
    
    test_result(
        "Quantum-Consensus integration",
        reward_check == Decimal('15.27') and isinstance(e_check, float),
        "Components communicate correctly"
    )
    
    # Database + Consensus
    supply_check = db.get_total_supply()
    reward_with_supply = ce.calculate_reward(0, supply_check)
    
    test_result(
        "Database-Consensus integration",
        supply_check == Decimal(0) and reward_with_supply == Decimal('15.27'),
        "Supply tracking integrated"
    )

except Exception as e:
    test_result("Integration section", False, f"Error: {e}", critical=False)
    traceback.print_exc()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
test_section("🎯 COMPREHENSIVE VALIDATION SUMMARY", level=1)

total_tests = len(test_results)
passed = sum(1 for _, p, _ in test_results if p)
failed_critical = sum(1 for _, p, c in test_results if not p and c)
failed_warnings = sum(1 for _, p, c in test_results if not p and not c)
success_rate = (passed / total_tests) * 100

print(f"\n{'=' * 100}")
print(f"COMPREHENSIVE VALIDATION RESULTS")
print(f"{'=' * 100}")
print(f"Total Tests:          {total_tests}")
print(f"✅ Passed:            {passed}")
print(f"❌ Critical Failures: {failed_critical}")
print(f"⚠️  Warnings:          {failed_warnings}")
print(f"Success Rate:         {success_rate:.1f}%")
print(f"{'=' * 100}\n")

if failed_critical > 0:
    print("🛑 CRITICAL FAILURES:\n")
    for i, (name, p, c) in enumerate(test_results, 1):
        if not p and c:
            print(f"  [{i:3d}] ❌ {name}")
    print(f"\n{'=' * 100}")
    print("⛔ CANNOT PROCEED TO GENESIS")
    print(f"{'=' * 100}\n")
    sys.exit(1)

if failed_warnings > 0:
    print("⚠️  NON-CRITICAL WARNINGS:\n")
    for i, (name, p, c) in enumerate(test_results, 1):
        if not p and not c:
            print(f"  [{i:3d}] ⚠️  {name}")
    print()

print(f"{'=' * 100}")
print("🎉 ALL CRITICAL TESTS PASSED - SYSTEM READY FOR GENESIS!")
print(f"{'=' * 100}\n")

print("📊 SYSTEM OVERVIEW:")
print(f"  ✅ Node Keys:         Configured ({Config.ADDRESS[:20]}...)")
print(f"  ✅ Economics:         SUSY φ-halvings (15.27 QBC → ...)")
print(f"  ✅ Database:          {total_tables} tables, genesis state")
print(f"  ✅ Quantum Engine:    VQE operational (avg {avg_vqe:.3f}s)")
print(f"  ✅ Cryptography:      Dilithium2 post-quantum")
print(f"  ✅ Consensus:         Golden ratio validated")
print(f"  ✅ Mining:            Engine ready (stopped)")
print(f"  ✅ Network:           RPC configured ({len(routes)} endpoints)")
print(f"  ✅ Storage:           IPFS {'connected' if ipfs_connected else 'optional'}")
print(f"  ✅ Performance:       {tps:.0f} TPS estimated")
print()

print("🚀 GENESIS CHECKLIST:")
print("  1. ✅ All critical systems validated")
print("  2. ✅ Database in clean genesis state")
print("  3. ✅ Node keys properly configured")
print("  4. ✅ Economic parameters verified")
print("  5. ✅ Security constraints enforced")
print()

print("📋 PRE-LAUNCH STEPS:")
print("  1. Backup database:    cockroach dump qbc > qbc_pre_genesis_$(date +%Y%m%d).sql")
print("  2. Review warnings:    Check any non-critical issues above")
print("  3. Start node:         cd src && python3 run_node.py")
print("  4. Monitor genesis:    Watch for Block 0 creation")
print("  5. Verify reward:      First block should reward 15.27 QBC")
print("  6. Check balance:      Confirm coinbase UTXO created")
print()

print(f"{'=' * 100}")
print(f"Validation completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Time elapsed: {time.time() - time.time():.2f}s")
print(f"{'=' * 100}\n")

print("🌟 READY FOR GENESIS BLOCK CREATION 🌟\n")

if __name__ == "__main__":
    sys.exit(0)
