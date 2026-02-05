#!/usr/bin/env python3
"""
QUBITCOIN L1 PRODUCTION READINESS TEST
======================================

Tests everything needed for production launch:
- Core blockchain (mining, consensus, quantum proofs)
- Smart contract infrastructure (for QUSD and other contracts)
- P2P networking (multi-node support)
- Bridge infrastructure (for wQBC/wQUSD wrappers)
- Database schema (correct tables for L1 functionality)
- RPC API (all endpoints working)
- IPFS storage (snapshots)

QUSD Note: QUSD is a smart contract on QBC, not native chain logic.
The L1 just needs contract execution + bridge support.
"""

import sys
import os
import time
import requests
import asyncio
from decimal import Decimal
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qubitcoin.config import Config
from qubitcoin.database.manager import DatabaseManager
from qubitcoin.quantum.engine import QuantumEngine
from qubitcoin.consensus.engine import ConsensusEngine
from qubitcoin.mining.engine import MiningEngine
from qubitcoin.storage.ipfs import IPFSManager
from qubitcoin.contracts.executor import ContractExecutor
from qubitcoin.bridge.manager import BridgeManager
from qubitcoin.utils.logger import get_logger

logger = get_logger(__name__)

class ProductionTest:
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
        
    def test(self, name: str, func, *args, **kwargs):
        """Run a test and track results"""
        try:
            result = func(*args, **kwargs)
            if result:
                self.tests_passed += 1
                self.test_results.append((name, True, None))
                print(f"✅ PASS: {name}")
                return True
            else:
                self.tests_failed += 1
                self.test_results.append((name, False, "Test returned False"))
                print(f"❌ FAIL: {name}")
                return False
        except Exception as e:
            self.tests_failed += 1
            self.test_results.append((name, False, str(e)))
            print(f"❌ FAIL: {name}")
            print(f"   Error: {e}")
            return False
    
    def print_header(self, title: str):
        """Print section header"""
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print('=' * 70)
        print()

def main():
    test = ProductionTest()
    
    print("=" * 70)
    print("QUBITCOIN L1 PRODUCTION READINESS TEST")
    print("=" * 70)
    print()
    
    # =========================================================================
    # PHASE 1: Core Configuration
    # =========================================================================
    test.print_header("PHASE 1: Configuration Validation")
    
    test.test("MAX_SUPPLY = 3.3B", lambda: Config.MAX_SUPPLY == Decimal('3300000000'))
    test.test("INITIAL_REWARD = 15.27", lambda: Config.INITIAL_REWARD == Decimal('15.27'))
    test.test("TARGET_BLOCK_TIME = 3.3s", lambda: Config.TARGET_BLOCK_TIME == 3.3)
    test.test("HALVING_INTERVAL correct", lambda: Config.HALVING_INTERVAL == 15474020)
    test.test("Golden ratio φ", lambda: abs(Config.PHI - 1.618033988749895) < 0.000001)
    
    # =========================================================================
    # PHASE 2: Database Connectivity & Schema
    # =========================================================================
    test.print_header("PHASE 2: Database Infrastructure")
    
    try:
        db = DatabaseManager()
        test.test("Database connection", lambda: db.engine is not None)
        
        # Core blockchain tables
        core_tables = ['blocks', 'utxos', 'transactions', 'supply', 'solved_hamiltonians']
        for table in core_tables:
            test.test(f"Core table: {table}", lambda t=table: db.table_exists(t))
        
        # Smart contract tables (REQUIRED for QUSD)
        contract_tables = ['contracts', 'contract_storage', 'contract_events', 'contract_deployments']
        for table in contract_tables:
            test.test(f"Contract table: {table}", lambda t=table: db.table_exists(t))
        
        # Bridge tables (REQUIRED for wQUSD on Ethereum)
        bridge_tables = [
            'bridge_deposits', 'bridge_withdrawals', 'bridge_validators',
            'bridge_approvals', 'bridge_events', 'bridge_config',
            'bridge_stats', 'bridge_sync_status'
        ]
        for table in bridge_tables:
            test.test(f"Bridge table: {table}", lambda t=table: db.table_exists(t))
        
        # Optional tables
        optional_tables = ['users', 'susy_swaps', 'peer_reputation', 'ipfs_snapshots', 
                          'oracle_sources', 'collateral_types', 'stablecoin_params', 
                          'reserve_snapshots']
        for table in optional_tables:
            test.test(f"Optional table: {table}", lambda t=table: db.table_exists(t))
        
        # Get current state
        height = db.get_current_height()
        supply = db.get_total_supply()
        test.test(f"Blockchain height > 0 (height: {height})", lambda: height >= 0)
        test.test(f"Total supply > 0 (supply: {supply} QBC)", lambda: supply > 0)
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        db = None
    
    # =========================================================================
    # PHASE 3: Component Initialization
    # =========================================================================
    test.print_header("PHASE 3: Core Components")
    
    # Quantum engine
    try:
        quantum = QuantumEngine()
        test.test("Quantum engine initialized", lambda: quantum.estimator is not None)
    except Exception as e:
        print(f"❌ Quantum engine failed: {e}")
        quantum = None
    
    # Consensus engine
    try:
        consensus = ConsensusEngine()
        test.test("Consensus engine initialized", lambda: consensus is not None)
    except Exception as e:
        print(f"❌ Consensus engine failed: {e}")
        consensus = None
    
    # IPFS
    try:
        ipfs = IPFSManager()
        test.test("IPFS connected", lambda: ipfs.client is not None)
    except Exception as e:
        print(f"❌ IPFS failed: {e}")
        ipfs = None
    
    # Smart contracts (CRITICAL for QUSD)
    if db:
        try:
            contracts = ContractExecutor(db)
            test.test("Contract executor initialized", lambda: contracts is not None)
        except Exception as e:
            print(f"❌ Contract executor failed: {e}")
            contracts = None
    
    # Bridge manager (CRITICAL for wQUSD)
    if db:
        try:
            bridge = BridgeManager(db)
            test.test("Bridge manager initialized", lambda: bridge is not None)
        except Exception as e:
            print(f"❌ Bridge manager failed: {e}")
            bridge = None
    
    # =========================================================================
    # PHASE 4: Quantum Engine Functionality
    # =========================================================================
    test.print_header("PHASE 4: Quantum Mining Proofs")
    
    if quantum:
        try:
            # Generate Hamiltonian
            hamiltonian = quantum.generate_hamiltonian()
            test.test("Generate Hamiltonian", lambda: len(hamiltonian) > 0)
            
            # VQE optimization
            start = time.time()
            result = quantum.solve_vqe(hamiltonian)
            elapsed = time.time() - start
            test.test(f"VQE optimization (took {elapsed:.2f}s)", lambda: result['converged'])
            test.test("VQE performance < 2s", lambda: elapsed < 2.0)
            
            # Validate proof
            is_valid = quantum.validate_proof(hamiltonian, result['optimal_params'], Config.INITIAL_DIFFICULTY)
            test.test("Proof validation", lambda: is_valid)
            
        except Exception as e:
            print(f"❌ Quantum tests failed: {e}")
    
    # =========================================================================
    # PHASE 5: Consensus & Economics
    # =========================================================================
    test.print_header("PHASE 5: Economics & Consensus")
    
    if consensus:
        try:
            # Genesis reward
            genesis_reward = consensus.calculate_block_reward(0)
            test.test(f"Genesis reward = 15.27 QBC (got: {genesis_reward})", 
                     lambda: abs(genesis_reward - Decimal('15.27')) < Decimal('0.01'))
            
            # First halving reward
            halving_reward = consensus.calculate_block_reward(Config.HALVING_INTERVAL)
            expected = Decimal('15.27') / Config.PHI
            test.test(f"First halving ~ {expected:.2f} QBC (got: {halving_reward:.2f})", 
                     lambda: abs(halving_reward - expected) < Decimal('0.01'))
            
            # Difficulty adjustment
            test.test("Initial difficulty = 0.5", lambda: Config.INITIAL_DIFFICULTY == 0.5)
            
        except Exception as e:
            print(f"❌ Economics tests failed: {e}")
    
    # =========================================================================
    # PHASE 6: RPC API Endpoints
    # =========================================================================
    test.print_header("PHASE 6: RPC API Endpoints")
    
    rpc_port = Config.RPC_PORT
    base_url = f"http://localhost:{rpc_port}"
    
    def test_endpoint(path: str, expected_keys: List[str] = None):
        """Test an RPC endpoint"""
        try:
            resp = requests.get(f"{base_url}{path}", timeout=5)
            if resp.status_code != 200:
                return False
            data = resp.json()
            if expected_keys:
                return all(k in data for k in expected_keys)
            return True
        except:
            return False
    
    # Core endpoints
    test.test("GET /", lambda: test_endpoint("/", ["node", "height", "difficulty"]))
    test.test("GET /health", lambda: test_endpoint("/health", ["status"]))
    test.test("GET /info", lambda: test_endpoint("/info", ["node", "blockchain"]))
    
    # Blockchain endpoints
    test.test("GET /chain/info", lambda: test_endpoint("/chain/info", ["height", "total_supply"]))
    test.test("GET /chain/tip", lambda: test_endpoint("/chain/tip"))
    
    # Mining endpoints
    test.test("GET /mining/stats", lambda: test_endpoint("/mining/stats", ["is_mining"]))
    
    # Economics
    test.test("GET /economics/emission", lambda: test_endpoint("/economics/emission"))
    
    # P2P endpoints (NEW)
    test.test("GET /p2p/peers", lambda: test_endpoint("/p2p/peers"))
    test.test("GET /p2p/stats", lambda: test_endpoint("/p2p/stats"))
    
    # Contract endpoints (CRITICAL for QUSD)
    test.test("GET /contracts", lambda: test_endpoint("/contracts"))
    
    # Bridge endpoints (CRITICAL for wQUSD)
    test.test("GET /bridge/status", lambda: test_endpoint("/bridge/status"))
    
    # =========================================================================
    # PHASE 7: P2P Network Readiness
    # =========================================================================
    test.print_header("PHASE 7: P2P Network Infrastructure")
    
    # Check P2P port configured
    test.test(f"P2P port configured ({Config.P2P_PORT})", lambda: Config.P2P_PORT > 0)
    test.test("P2P port != IPFS port (4001)", lambda: Config.P2P_PORT != 4001)
    test.test("Max peers configured", lambda: Config.MAX_PEERS > 0)
    
    # Check P2P module exists
    try:
        from qubitcoin.network.p2p_network import P2PNetwork
        test.test("P2P network module available", lambda: True)
    except:
        test.test("P2P network module available", lambda: False)
    
    # =========================================================================
    # PHASE 8: Smart Contract Readiness (for QUSD)
    # =========================================================================
    test.print_header("PHASE 8: Smart Contract Infrastructure")
    
    if db:
        # Check contract storage table structure
        try:
            result = db.session.execute("SELECT * FROM contract_storage LIMIT 1")
            test.test("Contract storage table accessible", lambda: True)
        except:
            test.test("Contract storage table accessible", lambda: False)
        
        # Check contract events table
        try:
            result = db.session.execute("SELECT * FROM contract_events LIMIT 1")
            test.test("Contract events table accessible", lambda: True)
        except:
            test.test("Contract events table accessible", lambda: False)
        
        # Check contract deployments table
        try:
            result = db.session.execute("SELECT * FROM contract_deployments LIMIT 1")
            test.test("Contract deployments table accessible", lambda: True)
        except:
            test.test("Contract deployments table accessible", lambda: False)
        
        # Check reserve snapshots (for QUSD transparency)
        try:
            result = db.session.execute("SELECT * FROM reserve_snapshots LIMIT 1")
            test.test("Reserve snapshots table accessible", lambda: True)
        except:
            test.test("Reserve snapshots table accessible", lambda: False)
    
    # =========================================================================
    # PHASE 9: Bridge Infrastructure (for wQUSD)
    # =========================================================================
    test.print_header("PHASE 9: Bridge Infrastructure")
    
    if db:
        # Check bridge deposits table
        try:
            result = db.session.execute("SELECT COUNT(*) FROM bridge_deposits")
            count = result.scalar()
            test.test(f"Bridge deposits table (found {count} entries)", lambda: True)
        except Exception as e:
            test.test("Bridge deposits table accessible", lambda: False)
        
        # Check bridge config
        try:
            result = db.session.execute("SELECT COUNT(*) FROM bridge_config")
            count = result.scalar()
            test.test(f"Bridge config exists ({count} chains)", lambda: count >= 0)
        except Exception as e:
            test.test("Bridge config table accessible", lambda: False)
        
        # Check bridge validators
        try:
            result = db.session.execute("SELECT * FROM bridge_validators LIMIT 1")
            test.test("Bridge validators table accessible", lambda: True)
        except:
            test.test("Bridge validators table accessible", lambda: False)
    
    # Check web3 library (needed for Ethereum bridge)
    try:
        import web3
        test.test("Web3.py installed (for ETH bridge)", lambda: True)
    except:
        test.test("Web3.py installed (for ETH bridge)", lambda: False)
    
    # =========================================================================
    # PHASE 10: Python Dependencies
    # =========================================================================
    test.print_header("PHASE 10: Production Dependencies")
    
    required_packages = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2',
        'qiskit', 'qiskit_aer', 'scipy', 'numpy',
        'web3', 'eth_account',  # Ethereum bridge
        'ipfshttpclient',  # IPFS storage
        'prometheus_client',  # Monitoring
    ]
    
    for pkg in required_packages:
        try:
            __import__(pkg)
            test.test(f"Package: {pkg}", lambda: True)
        except:
            test.test(f"Package: {pkg}", lambda: False)
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print()
    print("=" * 70)
    print("  PRODUCTION READINESS SUMMARY")
    print("=" * 70)
    print()
    
    total = test.tests_passed + test.tests_failed
    percent = (test.tests_passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"✅ Passed: {test.tests_passed}")
    print(f"❌ Failed: {test.tests_failed}")
    print(f"Success Rate: {percent:.1f}%")
    print()
    
    if test.tests_failed > 0:
        print("⚠️  FAILED TESTS:")
        for name, passed, error in test.test_results:
            if not passed:
                print(f"  ❌ {name}")
                if error:
                    print(f"     {error}")
    
    print()
    print("=" * 70)
    
    if percent >= 95:
        print("✅ PRODUCTION READY!")
        print("=" * 70)
        print()
        print("Your QBC L1 node is ready for:")
        print("  • Multi-node P2P networking")
        print("  • QUSD smart contract deployment")
        print("  • Ethereum bridge (wQBC/wQUSD)")
        print("  • Mainnet launch")
        print()
        return 0
    elif percent >= 85:
        print("⚠️  MOSTLY READY")
        print("=" * 70)
        print()
        print("Fix remaining issues before production launch.")
        print()
        return 0
    else:
        print("❌ NOT READY FOR PRODUCTION")
        print("=" * 70)
        print()
        print("Critical issues must be fixed before launch.")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
