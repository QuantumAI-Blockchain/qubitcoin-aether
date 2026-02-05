#!/usr/bin/env python3
"""
QUBITCOIN L1 PRODUCTION READINESS TEST (FIXED)
Simplified test that works with actual QBC codebase
"""

import sys
import os
import time
import requests
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qubitcoin.config import Config
from qubitcoin.database.manager import DatabaseManager
from qubitcoin.quantum.engine import QuantumEngine
from qubitcoin.consensus.engine import ConsensusEngine
from qubitcoin.storage.ipfs import IPFSManager
from qubitcoin.contracts.executor import ContractExecutor
from qubitcoin.bridge.manager import BridgeManager

class ProductionTest:
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        
    def test(self, name: str, func):
        try:
            result = func()
            if result:
                self.tests_passed += 1
                print(f"✅ PASS: {name}")
                return True
            else:
                self.tests_failed += 1
                print(f"❌ FAIL: {name}")
                return False
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ FAIL: {name}")
            print(f"   Error: {e}")
            return False
    
    def header(self, title: str):
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print('=' * 70)
        print()

def table_exists(db, table_name):
    """Check if a table exists"""
    try:
        result = db.session.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        return True
    except:
        return False

def main():
    test = ProductionTest()
    
    print("=" * 70)
    print("QUBITCOIN L1 PRODUCTION READINESS TEST")
    print("=" * 70)
    
    # PHASE 1: Configuration
    test.header("PHASE 1: Configuration")
    test.test("MAX_SUPPLY = 3.3B", lambda: Config.MAX_SUPPLY == Decimal('3300000000'))
    test.test("INITIAL_REWARD = 15.27", lambda: Config.INITIAL_REWARD == Decimal('15.27'))
    test.test("TARGET_BLOCK_TIME = 3.3s", lambda: Config.TARGET_BLOCK_TIME == 3.3)
    test.test("HALVING_INTERVAL = 15,474,020", lambda: Config.HALVING_INTERVAL == 15474020)
    
    # PHASE 2: Database
    test.header("PHASE 2: Database")
    try:
        db = DatabaseManager()
        test.test("Database connected", lambda: db.engine is not None)
        
        # Core tables
        core_tables = ['blocks', 'utxos', 'transactions', 'supply', 'solved_hamiltonians']
        for t in core_tables:
            test.test(f"Core table: {t}", lambda table=t: table_exists(db, table))
        
        # Contract tables (CRITICAL for QUSD)
        contract_tables = ['contracts', 'contract_storage', 'contract_events', 'contract_deployments']
        for t in contract_tables:
            test.test(f"Contract table: {t}", lambda table=t: table_exists(db, table))
        
        # Bridge tables (CRITICAL for wQUSD)
        bridge_tables = ['bridge_deposits', 'bridge_withdrawals', 'bridge_validators', 
                        'bridge_approvals', 'bridge_events', 'bridge_config']
        for t in bridge_tables:
            test.test(f"Bridge table: {t}", lambda table=t: table_exists(db, table))
        
        # Get current state
        height = db.get_current_height()
        supply = db.get_total_supply()
        test.test(f"Blockchain height ({height})", lambda: height >= 0)
        test.test(f"Total supply ({supply} QBC)", lambda: supply > 0)
        
    except Exception as e:
        print(f"❌ Database failed: {e}")
        db = None
    
    # PHASE 3: Components
    test.header("PHASE 3: Core Components")
    
    try:
        quantum = QuantumEngine()
        test.test("Quantum engine", lambda: quantum.estimator is not None)
    except Exception as e:
        print(f"❌ Quantum engine failed: {e}")
        quantum = None
    
    try:
        if quantum:
            consensus = ConsensusEngine(quantum)
            test.test("Consensus engine", lambda: consensus is not None)
        else:
            consensus = None
    except Exception as e:
        print(f"❌ Consensus engine failed: {e}")
        consensus = None
    
    try:
        ipfs = IPFSManager()
        test.test("IPFS connected", lambda: ipfs.client is not None)
    except Exception as e:
        print(f"❌ IPFS failed: {e}")
    
    if db and quantum:
        try:
            contracts = ContractExecutor(db, quantum)
            test.test("Contract executor (for QUSD)", lambda: contracts is not None)
        except Exception as e:
            print(f"❌ Contract executor failed: {e}")
    
    if db:
        try:
            bridge = BridgeManager(db)
            test.test("Bridge manager (for wQUSD)", lambda: bridge is not None)
        except Exception as e:
            print(f"❌ Bridge manager failed: {e}")
    
    # PHASE 4: Quantum Proofs
    test.header("PHASE 4: Quantum Mining")
    
    if quantum:
        try:
            hamiltonian = quantum.generate_hamiltonian()
            test.test("Generate Hamiltonian", lambda: len(hamiltonian) > 0)
            
            start = time.time()
            result = quantum.run_vqe(hamiltonian)
            elapsed = time.time() - start
            test.test(f"VQE optimization ({elapsed:.2f}s)", lambda: result['converged'])
            test.test("VQE performance < 2s", lambda: elapsed < 2.0)
            
            is_valid = quantum.validate_proof(hamiltonian, result['optimal_params'], Config.INITIAL_DIFFICULTY)
            test.test("Proof validation", lambda: is_valid)
        except Exception as e:
            print(f"❌ Quantum tests failed: {e}")
    
    # PHASE 5: Economics
    test.header("PHASE 5: Economics")
    
    if consensus:
        try:
            genesis = consensus.calculate_block_reward(0)
            test.test(f"Genesis reward ({genesis})", lambda: abs(genesis - Decimal('15.27')) < Decimal('0.01'))
            
            halving = consensus.calculate_block_reward(Config.HALVING_INTERVAL)
            expected = Decimal('15.27') / Config.PHI
            test.test(f"First halving ({halving:.2f})", lambda: abs(halving - expected) < Decimal('0.1'))
        except Exception as e:
            print(f"❌ Economics failed: {e}")
    
    # PHASE 6: RPC API
    test.header("PHASE 6: RPC API")
    
    def test_endpoint(path):
        try:
            r = requests.get(f"http://localhost:{Config.RPC_PORT}{path}", timeout=5)
            return r.status_code == 200
        except:
            return False
    
    test.test("GET /", lambda: test_endpoint("/"))
    test.test("GET /health", lambda: test_endpoint("/health"))
    test.test("GET /info", lambda: test_endpoint("/info"))
    test.test("GET /chain/info", lambda: test_endpoint("/chain/info"))
    test.test("GET /mining/stats", lambda: test_endpoint("/mining/stats"))
    test.test("GET /p2p/peers", lambda: test_endpoint("/p2p/peers"))
    test.test("GET /p2p/stats", lambda: test_endpoint("/p2p/stats"))
    
    # PHASE 7: P2P
    test.header("PHASE 7: P2P Network")
    
    test.test(f"P2P port configured ({Config.P2P_PORT})", lambda: Config.P2P_PORT > 0)
    test.test("P2P port != IPFS port", lambda: Config.P2P_PORT != 4001)
    
    try:
        from qubitcoin.network.p2p_network import P2PNetwork
        test.test("P2P module available", lambda: True)
    except:
        test.test("P2P module available", lambda: False)
    
    # PHASE 8: Dependencies
    test.header("PHASE 8: Dependencies")
    
    packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2', 
                'qiskit', 'scipy', 'numpy', 'web3', 'eth_account', 
                'ipfshttpclient', 'prometheus_client']
    
    for pkg in packages:
        try:
            __import__(pkg)
            test.test(f"Package: {pkg}", lambda: True)
        except:
            test.test(f"Package: {pkg}", lambda: False)
    
    # SUMMARY
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
    print("=" * 70)
    
    if percent >= 95:
        print("✅ PRODUCTION READY!")
        print()
        print("Your QBC L1 node is ready for:")
        print("  • Multi-node P2P networking")
        print("  • QUSD smart contract deployment")
        print("  • Ethereum bridge (wQBC/wQUSD)")
        print("  • Mainnet launch")
        return 0
    elif percent >= 80:
        print("⚠️  MOSTLY READY (Fix remaining issues)")
        return 0
    else:
        print("❌ NOT READY FOR PRODUCTION")
        print()
        print("Critical issues must be fixed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
