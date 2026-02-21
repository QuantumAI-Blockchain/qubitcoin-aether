"""
RPC API endpoints for Qubitcoin node v2.0
FastAPI-based HTTP interface with smart contract support
NOW WITH P2P ENDPOINTS!
"""

from typing import Optional
from decimal import Decimal

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response

from ..config import Config
from ..database.models import Transaction
from ..utils.logger import get_logger
from ..utils.metrics import generate_latest, CONTENT_TYPE_LATEST

logger = get_logger(__name__)


def create_rpc_app(db_manager, consensus_engine, mining_engine,
                   quantum_engine, ipfs_manager, contract_engine=None,
                   state_manager=None, aether_engine=None,
                   llm_manager=None) -> FastAPI:
    """
    Create FastAPI application with all endpoints including smart contracts, QVM, and Aether

    Args:
        db_manager: Database manager instance
        consensus_engine: Consensus engine instance
        mining_engine: Mining engine instance
        quantum_engine: Quantum engine instance
        ipfs_manager: IPFS manager instance
        contract_engine: Smart contract engine instance (optional for v1 compatibility)
        state_manager: QVM state manager instance (optional)
        aether_engine: Aether Tree AGI engine instance (optional)
        llm_manager: LLMAdapterManager instance (optional)

    Returns:
        Configured FastAPI app
    """

    app = FastAPI(
        title="Qubitcoin Node RPC v2.0",
        version="2.0.0",
        description="Quantum-secured L1 blockchain with smart contracts and P2P networking"
    )

    # CORS middleware (restrict in production via QBC_CORS_ORIGINS env)
    import os
    cors_origins = os.getenv('QBC_CORS_ORIGINS', '').split(',')
    cors_origins = [o.strip() for o in cors_origins if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=bool(cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========================================================================
    # RATE LIMITING MIDDLEWARE
    # ========================================================================
    import collections

    _rate_limit_store: dict = {
        'requests': collections.defaultdict(list),  # ip -> [timestamps]
        'max_per_minute': int(os.getenv('RPC_RATE_LIMIT', '120')),
    }

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Simple in-memory rate limiter — per IP, per minute."""
        import time as _time
        client_ip = request.client.host if request.client else 'unknown'
        now = _time.time()
        window = 60.0  # 1 minute window
        max_requests = _rate_limit_store['max_per_minute']

        # Clean old entries
        timestamps = _rate_limit_store['requests'][client_ip]
        _rate_limit_store['requests'][client_ip] = [
            t for t in timestamps if now - t < window
        ]

        if len(_rate_limit_store['requests'][client_ip]) >= max_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": 60},
            )

        _rate_limit_store['requests'][client_ip].append(now)
        response = await call_next(request)
        return response

    # ========================================================================
    # JSON-RPC (eth_* compatible) - Web3 / MetaMask / Hardhat support
    # ========================================================================
    from .jsonrpc import create_jsonrpc_router
    jsonrpc_router = create_jsonrpc_router(
        db_manager, consensus_engine, mining_engine, quantum_engine,
        qvm=state_manager
    )
    app.include_router(jsonrpc_router, tags=["JSON-RPC"])

    # ========================================================================
    # NODE INFO ENDPOINTS
    # ========================================================================

    @app.get("/")
    async def root():
        """Get node information"""
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except Exception as e:
            logger.debug(f"Could not get emission stats: {e}")
            emission_stats = {}

        # Get P2P info if available (handles both Rust and Python P2P)
        p2p_info = {}
        if hasattr(app, 'node'):
            node = app.node
            if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
                p2p_info = {
                    'type': 'rust_libp2p',
                    'peers': node.rust_p2p.get_peer_count(),
                }
            elif hasattr(node, 'p2p') and node.p2p:
                p2p_info = {
                    'type': 'python',
                    'peers': len(node.p2p.connections),
                    'port': node.p2p.port,
                }
        
        return {
            "node": "Qubitcoin Full Node v2.0",
            "version": "2.0.0",
            "network": "mainnet",
            "height": db_manager.get_current_height(),
            "difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "address": Config.ADDRESS,
            "p2p": p2p_info,
            "economics": {
                "model": "Golden Ratio (φ = 1.618...)",
                "current_reward": emission_stats.get('current_reward', 50.0),
                "era": emission_stats.get('current_era', 0),
                "supply": emission_stats.get('total_supply', 0),
                "supply_cap": emission_stats.get('supply_cap', float(Config.MAX_SUPPLY)),
                "percent_emitted": f"{emission_stats.get('percent_emitted', 0):.2f}%"
            },
            "features": {
                "smart_contracts": contract_engine is not None,
                "qvm": state_manager is not None,
                "aether_tree": aether_engine is not None,
                "quantum_proofs": True,
                "post_quantum_crypto": "Dilithium2",
                "consensus": "Proof-of-SUSY-Alignment + Proof-of-Thought",
                "p2p_networking": True,
                "chain_id": Config.CHAIN_ID
            }
        }

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        p2p_status = False
        if hasattr(app, 'node'):
            node = app.node
            if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
                p2p_status = True
            elif hasattr(node, 'p2p') and node.p2p:
                p2p_status = node.p2p.running
        
        return {
            "status": "healthy",
            "mining": mining_engine.is_mining,
            "database": True,
            "quantum": quantum_engine.estimator is not None,
            "ipfs": ipfs_manager.client is not None,
            "contracts": contract_engine is not None,
            "qvm": state_manager is not None,
            "aether_tree": aether_engine is not None,
            "p2p": p2p_status
        }

    @app.get("/info")
    async def node_info():
        """Detailed node information"""
        height = db_manager.get_current_height()
        supply = db_manager.get_total_supply()
        
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except Exception as e:
            logger.debug(f"Could not get emission stats: {e}")
            emission_stats = {
                'current_height': height,
                'total_supply': float(supply),
                'supply_cap': float(Config.MAX_SUPPLY)
            }
        
        # Get P2P stats if available (handles both Rust and Python P2P)
        p2p_stats = {}
        if hasattr(app, 'node'):
            node = app.node
            if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
                p2p_stats = {'type': 'rust_libp2p', 'peers': node.rust_p2p.get_peer_count()}
            elif hasattr(node, 'p2p') and node.p2p:
                p2p_stats = node.p2p.get_stats()

        return {
            "node": {
                "version": "2.0.0",
                "address": Config.ADDRESS,
                "uptime": mining_engine.stats.get('uptime', 0)
            },
            "blockchain": {
                "height": height,
                "total_supply": str(supply),
                "max_supply": str(Config.MAX_SUPPLY),
                "difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
                "target_block_time": Config.TARGET_BLOCK_TIME,
                "emission": emission_stats
            },
            "mining": {
                "is_mining": mining_engine.is_mining,
                "blocks_found": mining_engine.stats['blocks_found'],
                "total_attempts": mining_engine.stats['total_attempts'],
                "success_rate": mining_engine.stats['blocks_found'] / max(1, mining_engine.stats['total_attempts'])
            },
            "quantum": {
                "mode": "local" if Config.USE_LOCAL_ESTIMATOR else "ibm",
                "backend": quantum_engine.backend.name if quantum_engine.backend else "StatevectorEstimator"
            },
            "qvm": {
                "active": state_manager is not None,
                "chain_id": Config.CHAIN_ID,
                "opcodes": 155,
            },
            "aether": {
                "active": aether_engine is not None,
            },
            "p2p": p2p_stats
        }

    # ========================================================================
    # BLOCKCHAIN QUERY ENDPOINTS
    # ========================================================================

    @app.get("/block/{height}")
    async def get_block(height: int):
        """Get block by height"""
        block = db_manager.get_block(height)
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
        return block.to_dict()

    @app.get("/chain/info")
    async def chain_info():
        """Get blockchain information"""
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except Exception as e:
            logger.debug(f"Could not get emission stats for chain_info: {e}")
            height = db_manager.get_current_height()
            supply = db_manager.get_total_supply()
            emission_stats = {
                'current_height': height,
                'total_supply': float(supply),
                'supply_cap': float(Config.MAX_SUPPLY),
                'current_reward': 50.0,
                'current_era': 0,
                'percent_emitted': float(supply / Config.MAX_SUPPLY * 100) if Config.MAX_SUPPLY > 0 else 0,
                'blocks_until_halving': Config.HALVING_INTERVAL,
                'hours_until_halving': (Config.HALVING_INTERVAL * Config.TARGET_BLOCK_TIME) / 3600
            }

        # Peer count
        peers = 0
        if hasattr(app, 'node'):
            node = app.node
            if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
                peers = node.rust_p2p.get_peer_count()
            elif hasattr(node, 'p2p') and node.p2p:
                peers = len(node.p2p.connections)

        # Mempool size
        try:
            pending = db_manager.get_pending_transactions()
            mempool_size = len(pending)
        except Exception:
            mempool_size = 0

        return {
            "chain_id": Config.CHAIN_ID,
            "height": emission_stats['current_height'],
            "total_supply": float(emission_stats['total_supply']),
            "max_supply": float(Config.MAX_SUPPLY),
            "percent_emitted": f"{emission_stats['percent_emitted']:.4f}%",
            "current_era": emission_stats.get('current_era', 0),
            "current_reward": float(emission_stats.get('current_reward', 50.0)),
            "difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "target_block_time": Config.TARGET_BLOCK_TIME,
            "peers": peers,
            "mempool_size": mempool_size,
        }

    @app.get("/chain/tip")
    async def chain_tip():
        """Get latest block"""
        height = db_manager.get_current_height()
        if height < 0:
            raise HTTPException(status_code=404, detail="No blocks yet")
        block = db_manager.get_block(height)
        return block.to_dict()

    # ========================================================================
    # ECONOMICS ENDPOINTS
    # ========================================================================

    @app.get("/economics/emission")
    async def emission_schedule():
        """Get emission schedule statistics"""
        try:
            return consensus_engine.get_emission_stats(db_manager)
        except Exception as e:
            logger.error(f"Error getting emission stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/economics/simulate")
    async def simulate_emission(years: int = 50):
        """Simulate emission schedule for N years"""
        if years < 1 or years > 100:
            raise HTTPException(status_code=400, detail="Years must be between 1 and 100")

        try:
            PHI = Decimal('1.618033988749895')
            blocks_per_year = int(365.25 * 24 * 3600 / Config.TARGET_BLOCK_TIME)
            schedule = []
            total_supply = Decimal(0)

            for year in range(1, years + 1):
                year_emission = Decimal(0)
                start_height = blocks_per_year * (year - 1)
                end_height = blocks_per_year * year
                for h in range(start_height, end_height, 1000):
                    era = h // Config.HALVING_INTERVAL
                    reward = Config.INITIAL_REWARD / (PHI ** era)
                    remaining = Config.MAX_SUPPLY - total_supply - year_emission
                    block_reward = min(reward, remaining)
                    if block_reward <= 0:
                        break
                    chunk = min(1000, end_height - h)
                    year_emission += block_reward * chunk

                total_supply += year_emission
                schedule.append({
                    'year': year,
                    'emission': float(year_emission),
                    'total_supply': float(total_supply),
                    'percent_emitted': float(total_supply / Config.MAX_SUPPLY * 100),
                    'era': start_height // Config.HALVING_INTERVAL
                })
                if total_supply >= Config.MAX_SUPPLY:
                    break

            return {
                'schedule': schedule,
                'max_supply': float(Config.MAX_SUPPLY),
                'halving_interval': Config.HALVING_INTERVAL,
                'blocks_per_year': blocks_per_year,
                'phi': float(PHI)
            }
        except Exception as e:
            logger.error(f"Error simulating emission: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # BALANCE & UTXO ENDPOINTS
    # ========================================================================

    @app.get("/balance/{address}")
    async def get_balance(address: str):
        """Get address balance"""
        balance = db_manager.get_balance(address)
        utxos = db_manager.get_utxos(address)
        return {
            "address": address,
            "balance": str(balance),
            "utxo_count": len(utxos)
        }

    @app.get("/utxos/{address}")
    async def get_utxos(address: str):
        """Get UTXOs for address"""
        utxos = db_manager.get_utxos(address)
        return {
            "address": address,
            "utxos": [utxo.to_dict() for utxo in utxos],
            "total": str(sum(utxo.amount for utxo in utxos))
        }

    @app.get("/mempool")
    async def get_mempool():
        """Get mempool transactions"""
        pending = db_manager.get_pending_transactions()
        total_fees = sum(tx.fee for tx in pending)
        return {
            "size": len(pending),
            "total_fees": str(total_fees),
            "transactions": [tx.to_dict() for tx in pending[:20]]
        }

    # ========================================================================
    # MINING ENDPOINTS
    # ========================================================================

    @app.get("/mining/stats")
    async def mining_stats():
        """Get mining statistics"""
        return {
            "is_mining": mining_engine.is_mining,
            "blocks_found": mining_engine.stats['blocks_found'],
            "total_attempts": mining_engine.stats['total_attempts'],
            "current_difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "success_rate": mining_engine.stats['blocks_found'] / max(1, mining_engine.stats['total_attempts']),
            "best_energy": mining_engine.stats.get('best_energy', None),
            "alignment_score": mining_engine.stats.get('alignment_score', None),
        }

    @app.post("/mining/start")
    async def start_mining():
        """Start mining"""
        mining_engine.start()
        return {"status": "Mining started"}

    @app.post("/mining/stop")
    async def stop_mining():
        """Stop mining"""
        mining_engine.stop()
        return {"status": "Mining stopped"}

    # ========================================================================
    # P2P NETWORK ENDPOINTS (NEW!)
    # ========================================================================

    @app.get("/p2p/peers")
    async def get_p2p_peers():
        """Get list of connected P2P peers"""
        if not hasattr(app, 'node'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        node = app.node
        # Rust P2P mode
        if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
            peer_count = node.rust_p2p.get_peer_count()
            return {
                "type": "rust_libp2p",
                "peer_count": peer_count,
                "peers": []
            }
        # Python P2P mode
        if hasattr(node, 'p2p') and node.p2p:
            peers = node.p2p.get_peer_list()
            return {
                "type": "python",
                "peer_count": len(peers),
                "max_peers": node.p2p.max_peers,
                "port": node.p2p.port,
                "peer_id": node.p2p.peer_id,
                "peers": peers
            }
        raise HTTPException(status_code=503, detail="P2P network not available")

    @app.get("/p2p/stats")
    async def get_p2p_stats():
        """Get P2P network statistics"""
        if not hasattr(app, 'node'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        node = app.node
        # Rust P2P mode
        if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
            peer_count = node.rust_p2p.get_peer_count()
            return {
                "network": {
                    "type": "rust_libp2p",
                    "connected_peers": peer_count,
                },
                "messages": {},
                "connections": {"active": peer_count}
            }
        # Python P2P mode
        if hasattr(node, 'p2p') and node.p2p:
            stats = node.p2p.get_stats()
            return {
                "network": {
                    "type": "python",
                    "connected_peers": stats['connected_peers'],
                    "max_peers": stats['max_peers'],
                    "port": stats['port'],
                    "peer_id": stats['peer_id']
                },
                "messages": {
                    "sent": stats['messages_sent'],
                    "received": stats['messages_received'],
                    "blocks_propagated": stats['blocks_propagated'],
                    "txs_propagated": stats['txs_propagated']
                },
                "connections": {
                    "made": stats['connections_made'],
                    "dropped": stats['connections_dropped'],
                    "active": stats['connected_peers']
                }
            }
        raise HTTPException(status_code=503, detail="P2P network not available")

    @app.post("/p2p/connect")
    async def connect_to_peer(address: str):
        """Connect to a peer manually"""
        if not hasattr(app, 'node'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        node = app.node
        if hasattr(node, 'p2p') and node.p2p:
            try:
                await node.p2p.connect_to_peer(address)
                return {"status": "success", "message": f"Connecting to {address}"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")
        raise HTTPException(status_code=503, detail="Manual peer connection only available in Python P2P mode")

    # ========================================================================
    # QVM CONTRACT ENDPOINTS
    # ========================================================================

    @app.get("/qvm/info")
    async def qvm_info():
        """Get QVM engine info"""
        if not state_manager:
            raise HTTPException(status_code=503, detail="QVM not available")
        return {
            "status": "active",
            "opcodes": 155,
            "quantum_opcodes": 10,
            "chain_id": Config.CHAIN_ID,
            "block_gas_limit": Config.BLOCK_GAS_LIMIT,
        }

    @app.get("/qvm/contract/{address}")
    async def get_contract_info(address: str):
        """Get contract info by address"""
        account = db_manager.get_account(address)
        if not account or not account.is_contract():
            raise HTTPException(status_code=404, detail="Contract not found")
        bytecode = db_manager.get_contract_bytecode(address)
        return {
            "address": address,
            "code_hash": account.code_hash,
            "nonce": account.nonce,
            "bytecode_size": len(bytecode) // 2 if bytecode else 0,
        }

    @app.get("/qvm/account/{address}")
    async def get_qvm_account(address: str):
        """Get QVM account state"""
        account = db_manager.get_account(address)
        if not account:
            return {"address": address, "nonce": 0, "balance": "0", "is_contract": False}
        return {
            "address": account.address,
            "nonce": account.nonce,
            "balance": str(account.balance),
            "is_contract": account.is_contract(),
            "code_hash": account.code_hash,
        }

    @app.get("/qvm/storage/{address}/{key}")
    async def get_qvm_storage(address: str, key: str):
        """Get contract storage slot"""
        value = db_manager.get_storage(address, key)
        return {"address": address, "key": key, "value": value}

    @app.get("/qvm/deploy/estimate")
    async def estimate_deploy_fee(bytecode_size: int = 0, is_template: bool = False):
        """Estimate contract deployment fee."""
        from ..contracts.fee_calculator import ContractFeeCalculator
        calc = ContractFeeCalculator()
        fee = calc.calculate_deploy_fee(bytecode_size, is_template)
        return {
            'bytecode_size_bytes': bytecode_size,
            'is_template': is_template,
            'fee_qbc': str(fee),
            'pricing_mode': Config.CONTRACT_FEE_PRICING_MODE,
        }

    class DeployRequest(BaseModel):
        contract_type: str
        contract_code: dict
        deployer: str

    @app.post("/contracts/deploy")
    async def deploy_contract(req: DeployRequest):
        """Deploy a smart contract via ContractExecutor (template contracts)."""
        if not contract_engine:
            raise HTTPException(status_code=503, detail="Contract engine not available")

        height = db_manager.get_current_height()
        success, message, contract_id = contract_engine.deploy_contract(
            contract_type=req.contract_type,
            contract_code=req.contract_code,
            deployer_address=req.deployer,
            block_height=height,
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {
            "success": True,
            "message": message,
            "contract_id": contract_id,
            "deployer": req.deployer,
            "contract_type": req.contract_type,
            "block_height": height,
        }

    class ExecuteRequest(BaseModel):
        contract_id: str
        function: str
        args: dict
        caller: str

    @app.post("/contracts/execute")
    async def execute_contract(req: ExecuteRequest):
        """Execute a smart contract function."""
        if not contract_engine:
            raise HTTPException(status_code=503, detail="Contract engine not available")

        height = db_manager.get_current_height()
        success, message, result = contract_engine.execute(
            contract_id=req.contract_id,
            function=req.function,
            args=req.args,
            caller=req.caller,
            block_height=height,
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {
            "success": True,
            "message": message,
            "result": result,
        }

    @app.get("/contracts")
    async def list_contracts(limit: int = 50, offset: int = 0):
        """List deployed contracts."""
        from sqlalchemy import text as sa_text
        limit = max(1, min(limit, 200))
        with db_manager.get_session() as session:
            rows = session.execute(
                sa_text("""
                    SELECT contract_id, deployer_address, contract_type,
                           gas_paid, block_height, is_active, deployed_at
                    FROM contracts
                    ORDER BY deployed_at DESC
                    LIMIT :lim OFFSET :off
                """),
                {'lim': limit, 'off': offset}
            ).fetchall()
            count = session.execute(
                sa_text("SELECT COUNT(*) FROM contracts")
            ).scalar()
        contracts = []
        for r in rows:
            contracts.append({
                "contract_id": r[0],
                "deployer": r[1],
                "type": r[2],
                "gas_paid": str(r[3]),
                "block_height": r[4],
                "is_active": r[5],
                "deployed_at": str(r[6]) if r[6] else None,
            })
        return {"contracts": contracts, "total": count}

    @app.get("/contracts/{contract_id}")
    async def get_contract(contract_id: str):
        """Get contract details by ID."""
        from sqlalchemy import text as sa_text
        with db_manager.get_session() as session:
            row = session.execute(
                sa_text("""
                    SELECT contract_id, deployer_address, contract_type,
                           contract_code, contract_state, gas_paid,
                           block_height, is_active, deployed_at, execution_count
                    FROM contracts WHERE contract_id = :cid
                """),
                {'cid': contract_id}
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contract not found")
        import json
        return {
            "contract_id": row[0],
            "deployer": row[1],
            "type": row[2],
            "code": json.loads(row[3]) if isinstance(row[3], str) else row[3],
            "state": json.loads(row[4]) if isinstance(row[4], str) else row[4],
            "gas_paid": str(row[5]),
            "block_height": row[6],
            "is_active": row[7],
            "deployed_at": str(row[8]) if row[8] else None,
            "execution_count": row[9],
        }

    # ========================================================================
    # AETHER TREE ENDPOINTS
    # ========================================================================

    @app.get("/aether/info")
    async def aether_info():
        """Get Aether Tree engine status"""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        return aether_engine.get_stats()

    @app.get("/aether/phi")
    async def aether_phi():
        """Compute current Phi (consciousness metric)"""
        if not aether_engine or not aether_engine.phi:
            raise HTTPException(status_code=503, detail="Phi calculator not available")
        height = db_manager.get_current_height()
        return aether_engine.phi.compute_phi(height)

    @app.get("/aether/phi/history")
    async def aether_phi_history(limit: int = 50):
        """Get Phi measurement history"""
        if not aether_engine or not aether_engine.phi:
            raise HTTPException(status_code=503, detail="Phi calculator not available")
        return aether_engine.phi.get_history(limit)

    @app.get("/aether/knowledge")
    async def aether_knowledge_stats():
        """Get knowledge graph statistics"""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        return aether_engine.kg.get_stats()

    @app.get("/aether/knowledge/node/{node_id}")
    async def aether_knowledge_node(node_id: int):
        """Get a specific KeterNode"""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        node = aether_engine.kg.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Knowledge node not found")
        return node.to_dict()

    @app.get("/aether/knowledge/subgraph/{root_id}")
    async def aether_subgraph(root_id: int, depth: int = 3):
        """Get subgraph from a root node"""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if depth > 5:
            depth = 5
        subgraph = aether_engine.kg.get_subgraph(root_id, depth)
        return {
            "root_id": root_id,
            "depth": depth,
            "nodes": {nid: n.to_dict() for nid, n in subgraph.items()},
            "count": len(subgraph),
        }

    @app.get("/aether/reasoning/stats")
    async def aether_reasoning_stats():
        """Get reasoning engine statistics"""
        if not aether_engine or not aether_engine.reasoning:
            raise HTTPException(status_code=503, detail="Reasoning engine not available")
        return aether_engine.reasoning.get_stats()

    @app.get("/aether/consciousness")
    async def aether_consciousness():
        """Get full consciousness status (Phi, knowledge, events)."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        phi_data = {}
        if aether_engine.phi:
            height = db_manager.get_current_height()
            phi_data = aether_engine.phi.compute_phi(height)
        kg_stats = aether_engine.kg.get_stats() if aether_engine.kg else {}
        result = {
            'phi': phi_data.get('phi_value', 0.0),
            'threshold': phi_data.get('phi_threshold', 3.0),
            'above_threshold': phi_data.get('above_threshold', False),
            'integration': phi_data.get('integration_score', 0.0),
            'differentiation': phi_data.get('differentiation_score', 0.0),
            'knowledge_nodes': kg_stats.get('total_nodes', 0),
            'knowledge_edges': kg_stats.get('total_edges', 0),
            'blocks_processed': kg_stats.get('blocks_processed', 0),
        }
        # v2 gate data (post-fork)
        if phi_data.get('phi_version') == 2:
            result['phi_raw'] = phi_data.get('phi_raw', 0.0)
            result['phi_version'] = 2
            result['gates_passed'] = phi_data.get('gates_passed', 0)
            result['gates_total'] = phi_data.get('gates_total', 6)
            result['gate_ceiling'] = phi_data.get('gate_ceiling', 0.0)
            result['gates'] = phi_data.get('gates', [])
        return result

    @app.get("/aether/consciousness/gates")
    async def aether_consciousness_gates():
        """Get milestone gate status for Phi v2."""
        if not aether_engine or not aether_engine.phi:
            raise HTTPException(status_code=503, detail="Phi calculator not available")
        height = db_manager.get_current_height()
        phi_data = aether_engine.phi.compute_phi(height)
        gates = phi_data.get('gates', [])
        return {
            'block_height': height,
            'phi_version': phi_data.get('phi_version', 1),
            'fork_height': Config.PHI_FORK_HEIGHT,
            'gates_passed': phi_data.get('gates_passed', 0),
            'gates_total': phi_data.get('gates_total', len(gates)),
            'gate_ceiling': phi_data.get('gate_ceiling', 0.0),
            'phi_raw': phi_data.get('phi_raw', phi_data.get('phi_value', 0.0)),
            'phi_capped': phi_data.get('phi_value', 0.0),
            'gates': gates,
        }

    @app.get("/aether/mind")
    async def aether_mind():
        """Get Aether's current cognitive state — the 'window into AGI consciousness'.

        Returns active goals, contradictions, knowledge gaps, domain balance,
        sephirot states, and phi.
        """
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        height = db_manager.get_current_height()
        return aether_engine.get_mind_state(height)

    @app.get("/aether/knowledge/domains")
    async def aether_knowledge_domains():
        """Get knowledge graph domain breakdown."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        return aether_engine.kg.get_domain_stats()

    # ========================================================================
    # KNOWLEDGE GRAPH QUERY ENDPOINTS
    # ========================================================================

    @app.get("/aether/knowledge/graph")
    async def aether_knowledge_graph(limit: int = 3300, include_sephirot: bool = True):
        """Get knowledge graph nodes and edges for 3D visualization."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if limit < 1:
            limit = 1
        if limit > 5000:
            limit = 5000
        kg = aether_engine.kg
        stats = kg.get_stats()
        # Get most recent nodes up to limit
        recent = kg.find_recent(limit)
        node_ids = {n.node_id for n in recent}
        nodes_out = []
        for n in recent:
            content_str = ''
            is_contract = False
            if isinstance(n.content, dict):
                content_str = n.content.get('description', n.content.get('content', str(n.content)))
                if n.content.get('type') == 'contract_activity':
                    is_contract = True
            else:
                content_str = str(n.content)
            node_data: dict = {
                'id': n.node_id,
                'content': content_str[:120],
                'node_type': n.node_type,
                'confidence': n.confidence,
                'source_block': getattr(n, 'source_block', None),
            }
            if is_contract:
                node_data['is_contract'] = True
            nodes_out.append(node_data)
        # Inject synthetic Sephirot nodes (negative IDs to avoid collisions)
        if include_sephirot:
            for s in SEPHIROT_NODES:
                nodes_out.append({
                    'id': -(s['id'] + 1),  # -1 to -10
                    'content': f"{s['name']} ({s['title']}): {s['function']}",
                    'node_type': 'sephirot',
                    'confidence': 1.0,
                    'sephirot_name': s['name'],
                    'sephirot_title': s['title'],
                    'sephirot_function': s['function'],
                    'brain_analog': s['brain_analog'],
                })
        # Filter edges to only those connecting visible nodes
        edges_out = []
        for edge in kg.edges:
            if edge.from_node_id in node_ids and edge.to_node_id in node_ids:
                edges_out.append({
                    'source': edge.from_node_id,
                    'target': edge.to_node_id,
                    'edge_type': edge.edge_type,
                    'weight': edge.weight,
                })
        return {
            'nodes': nodes_out,
            'edges': edges_out,
            'total_nodes': stats.get('total_nodes', 0),
            'total_edges': stats.get('total_edges', 0),
        }

    @app.get("/aether/knowledge/search")
    async def knowledge_search(type: Optional[str] = None, key: Optional[str] = None,
                               value: Optional[str] = None, limit: int = 50):
        """Search knowledge graph nodes by type or content."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if limit > 200:
            limit = 200
        if type:
            nodes = aether_engine.kg.find_by_type(type, limit)
        elif key and value:
            nodes = aether_engine.kg.find_by_content(key, value, limit)
        else:
            nodes = aether_engine.kg.find_recent(limit)
        return {"nodes": [n.to_dict() for n in nodes], "count": len(nodes)}

    @app.get("/aether/knowledge/recent")
    async def knowledge_recent(count: int = 20):
        """Get most recently added knowledge nodes."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if count > 200:
            count = 200
        nodes = aether_engine.kg.find_recent(count)
        return {"nodes": [n.to_dict() for n in nodes], "count": len(nodes)}

    @app.get("/aether/knowledge/paths/{from_id}/{to_id}")
    async def knowledge_paths(from_id: int, to_id: int, max_depth: int = 5):
        """Find paths between two knowledge nodes."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if max_depth > 8:
            max_depth = 8
        paths = aether_engine.kg.find_paths(from_id, to_id, max_depth)
        return {"paths": paths, "count": len(paths)}

    @app.post("/aether/knowledge/prune")
    async def knowledge_prune(threshold: float = 0.1):
        """Prune low-confidence nodes from knowledge graph (admin)."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if threshold < 0.0 or threshold > 0.5:
            raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 0.5")
        removed = aether_engine.kg.prune_low_confidence(threshold)
        return {"removed": removed, "remaining_nodes": len(aether_engine.kg.nodes)}

    @app.get("/aether/knowledge/export")
    async def knowledge_export(limit: int = 0, format: str = "json-ld"):
        """Export knowledge graph in JSON-LD format."""
        if not aether_engine or not aether_engine.kg:
            raise HTTPException(status_code=503, detail="Knowledge graph not available")
        if limit < 0:
            limit = 0
        if limit > 10000:
            limit = 10000
        return aether_engine.kg.export_json_ld(limit=limit)

    @app.get("/aether/phi/timeseries")
    async def phi_timeseries(limit: int = 100):
        """Get Phi value time series for visualization (charts/graphs)."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        dashboard = _get_dashboard()
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        history = dashboard.get_phi_history(limit=limit)
        # Extract arrays for easy chart consumption
        blocks = [h.get("block_height", 0) for h in history]
        phi_values = [h.get("phi", 0.0) for h in history]
        conscious = [h.get("is_conscious", False) for h in history]
        return {
            "blocks": blocks,
            "phi_values": phi_values,
            "is_conscious": conscious,
            "count": len(history),
            "threshold": 3.0,
        }

    # ========================================================================
    # CONSCIOUSNESS DASHBOARD ENDPOINTS
    # ========================================================================

    # Lazy-initialized consciousness dashboard (shared across requests)
    _dashboard_state: dict = {'dashboard': None}

    def _get_dashboard():
        """Get or create the ConsciousnessDashboard instance."""
        if _dashboard_state['dashboard'] is None:
            from ..aether.consciousness import ConsciousnessDashboard
            _dashboard_state['dashboard'] = ConsciousnessDashboard()
        return _dashboard_state['dashboard']

    @app.get("/aether/consciousness/dashboard")
    async def consciousness_dashboard():
        """Get full consciousness dashboard data (status, history, events, trend)."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        dashboard = _get_dashboard()
        return dashboard.get_dashboard_data()

    @app.get("/aether/consciousness/trend")
    async def consciousness_trend(window: int = 20):
        """Get Phi trend analysis (rising, falling, stable)."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        dashboard = _get_dashboard()
        if window < 2:
            window = 2
        if window > 500:
            window = 500
        return dashboard.get_trend(window=window)

    @app.get("/aether/consciousness/events")
    async def consciousness_events(limit: int = 50):
        """Get consciousness emergence/loss events."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        dashboard = _get_dashboard()
        events = dashboard.get_events()
        if limit and limit < len(events):
            events = events[-limit:]
        return {"events": events, "total": dashboard.event_count}

    @app.get("/aether/sephirot")
    async def sephirot_status():
        """Get Tree of Life Sephirot node status."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        try:
            from ..aether.sephirot_nodes import create_all_nodes
            # If nodes are already created on the engine, use them
            if hasattr(aether_engine, 'sephirot_nodes') and aether_engine.sephirot_nodes:
                return {
                    role.value: node.get_status()
                    for role, node in aether_engine.sephirot_nodes.items()
                }
            # Fallback: return static status from SephirotManager
            from ..aether.sephirot import SephirotManager
            mgr = SephirotManager(db_manager)
            return mgr.get_status()
        except Exception as e:
            logger.debug(f"Sephirot status error: {e}")
            raise HTTPException(status_code=500, detail="Failed to get Sephirot status")

    # ========================================================================
    # AETHER CHAT ENDPOINTS
    # ========================================================================

    from pydantic import BaseModel as _PydanticBaseModel

    class _ChatMessageRequest(_PydanticBaseModel):
        message: str
        session_id: str
        is_deep_query: bool = False

    # Lazy-initialized chat components (created on first use)
    _chat_state: dict = {'chat': None, 'fee_mgr': None}

    def _get_chat():
        """Get or create the AetherChat instance."""
        if _chat_state['chat'] is None:
            from ..aether.chat import AetherChat
            from ..aether.fee_manager import AetherFeeManager
            fee_mgr = AetherFeeManager()
            _chat_state['fee_mgr'] = fee_mgr
            _chat_state['chat'] = AetherChat(
                aether_engine, db_manager, fee_mgr,
                llm_manager=llm_manager,
            )
        return _chat_state['chat'], _chat_state['fee_mgr']

    @app.post("/aether/chat/session")
    async def create_chat_session(user_address: str = ''):
        """Create a new Aether chat session."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        chat, _ = _get_chat()
        session = chat.create_session(user_address)
        return {
            'session_id': session.session_id,
            'created_at': session.created_at,
            'free_messages': Config.AETHER_FREE_TIER_MESSAGES,
        }

    @app.post("/aether/chat/message")
    async def send_chat_message(request: _ChatMessageRequest):
        """Send a message to Aether Tree and get a response."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        chat, _ = _get_chat()
        result = chat.process_message(
            request.session_id, request.message, request.is_deep_query
        )
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        # Convert reasoning_trace dicts to human-readable strings for frontend
        raw_trace = result.get('reasoning_trace', [])
        readable_trace: list[str] = []
        for step in raw_trace:
            if isinstance(step, dict):
                expl = step.get('explanation', '')
                op = step.get('operation_type', 'reasoning')
                conf = step.get('confidence', 0)
                chain = step.get('chain', [])
                if expl:
                    readable_trace.append(expl)
                elif chain:
                    for cs in chain:
                        cs_content = cs.get('content', {})
                        desc = cs_content.get('description', '')
                        cs_type = cs.get('step_type', '')
                        if desc:
                            readable_trace.append(f"[{cs_type}] {desc}")
                else:
                    readable_trace.append(f"{op} (confidence: {conf:.0%})")
            else:
                readable_trace.append(str(step))
        result['reasoning_trace'] = readable_trace
        return result

    @app.get("/aether/chat/fee")
    async def get_chat_fee(session_id: str, is_deep_query: bool = False):
        """Get the fee for the next chat message."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        chat, fee_mgr = _get_chat()
        session = chat.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        height = db_manager.get_current_height()
        return fee_mgr.get_fee_info(
            session_messages_sent=session.messages_sent,
            is_deep_query=is_deep_query,
            current_block=height,
        )

    @app.get("/aether/chat/history/{session_id}")
    async def get_chat_history(session_id: str):
        """Get chat message history for a session."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        chat, _ = _get_chat()
        session = chat.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_dict()

    # ========================================================================
    # LLM / KNOWLEDGE SEEDER STATS
    # ========================================================================

    @app.get("/aether/llm/stats")
    async def get_llm_stats():
        """Get LLM adapter and knowledge seeder statistics."""
        stats: dict = {"llm_enabled": Config.LLM_ENABLED}
        if llm_manager:
            stats["adapters"] = llm_manager.get_stats()
        # Seeder stats are on the node object (attached by node.py)
        node = getattr(app, 'node', None)
        if node and getattr(node, 'knowledge_seeder', None):
            stats["seeder"] = node.knowledge_seeder.get_stats()
        return stats

    # ========================================================================
    # WALLET ENDPOINTS — UTXO-to-Account Bridge & Native Wallet
    # ========================================================================

    class TransferRequest(BaseModel):
        to: str
        amount: str

    @app.post("/transfer")
    async def transfer_to_account(req: TransferRequest):
        """Bridge UTXO funds to an account-model address (for MetaMask).

        Selects UTXOs from the mining wallet, marks them spent, and credits
        the recipient in the accounts table.
        """
        import hashlib
        import time as _time

        to_addr = req.to.replace('0x', '')
        amount = Decimal(req.amount)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        miner_addr = Config.ADDRESS
        utxos = db_manager.get_utxos(miner_addr)
        if not utxos:
            raise HTTPException(status_code=400, detail="No UTXOs available")

        # Greedy largest-first selection
        utxos.sort(key=lambda u: u.amount, reverse=True)
        selected = []
        total = Decimal(0)
        for u in utxos:
            selected.append(u)
            total += u.amount
            if total >= amount:
                break
        if total < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient UTXO balance: have {total}, need {amount}")

        change = total - amount
        tx_hash = hashlib.sha256(
            f"{miner_addr}:{to_addr}:{amount}:{_time.time()}".encode()
        ).hexdigest()

        with db_manager.get_session() as session:
            from sqlalchemy import text as sa_text
            # Mark selected UTXOs as spent
            for u in selected:
                session.execute(
                    sa_text("UPDATE utxos SET spent = true, spent_by = :txid WHERE txid = :utxid AND vout = :vout AND spent = false"),
                    {'txid': tx_hash, 'utxid': u.txid, 'vout': u.vout}
                )
            # Create change UTXO if needed
            if change > 0:
                session.execute(
                    sa_text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, 0, :amt, :addr, '{}', :h, false)
                    """),
                    {'txid': tx_hash, 'amt': str(change), 'addr': miner_addr, 'h': db_manager.get_current_height()}
                )
            # Credit recipient in accounts table
            session.execute(
                sa_text("""
                    INSERT INTO accounts (address, nonce, balance, code_hash, storage_root)
                    VALUES (:addr, 0, :amt, '', '')
                    ON CONFLICT (address) DO UPDATE SET balance = accounts.balance + :amt
                """),
                {'addr': to_addr, 'amt': str(amount)}
            )
            # Store transaction record
            outputs = [{'address': to_addr, 'amount': str(amount)}]
            if change > 0:
                outputs.append({'address': miner_addr, 'amount': str(change)})
            import json as _json
            session.execute(
                sa_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                              timestamp, status, tx_type, to_address, data,
                                              gas_limit, gas_price, nonce)
                    VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb), 0, '', '',
                            :ts, 'confirmed', 'transfer', :to_addr, '', 0, 0, 0)
                """),
                {
                    'txid': tx_hash,
                    'inputs': _json.dumps([{'txid': u.txid, 'vout': u.vout} for u in selected]),
                    'outputs': _json.dumps(outputs),
                    'ts': _time.time(), 'to_addr': to_addr,
                }
            )
            session.commit()

        logger.info(f"Transfer: {miner_addr[:8]}→{to_addr[:8]} {amount} QBC (tx={tx_hash[:12]})")
        return {
            'tx_hash': tx_hash,
            'from': miner_addr,
            'to': to_addr,
            'amount': str(amount),
            'change': str(change),
        }

    # ========================================================================
    # NATIVE WALLET — Dilithium2 quantum-secure wallet
    # ========================================================================

    @app.post("/wallet/create")
    async def wallet_create():
        """Generate a new Dilithium2 quantum-secure wallet."""
        from ..quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        address = Dilithium2.derive_address(pk)
        logger.info(f"Native wallet created: {address[:12]}...")
        return {
            'address': address,
            'public_key_hex': pk.hex(),
            'private_key_hex': sk.hex(),  # Returned ONCE — client stores securely
        }

    class WalletSendRequest(BaseModel):
        from_address: str
        to_address: str
        amount: str
        signature_hex: str
        public_key_hex: str

    @app.post("/wallet/send")
    async def wallet_send(req: WalletSendRequest):
        """Send QBC from a native Dilithium wallet."""
        import hashlib
        import time as _time
        from ..quantum.crypto import Dilithium2

        amount = Decimal(req.amount)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Verify Dilithium signature
        pk = bytes.fromhex(req.public_key_hex)
        derived_addr = Dilithium2.derive_address(pk)
        if derived_addr != req.from_address:
            raise HTTPException(status_code=400, detail="Public key does not match from_address")

        tx_data = {'from': req.from_address, 'to': req.to_address, 'amount': req.amount}
        import json as _json
        msg = _json.dumps(tx_data, sort_keys=True).encode()
        sig = bytes.fromhex(req.signature_hex)
        if not Dilithium2.verify(pk, msg, sig):
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Select UTXOs
        utxos = db_manager.get_utxos(req.from_address)
        utxos.sort(key=lambda u: u.amount, reverse=True)
        selected = []
        total = Decimal(0)
        for u in utxos:
            selected.append(u)
            total += u.amount
            if total >= amount:
                break
        if total < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient balance: have {total}, need {amount}")

        change = total - amount
        tx_hash = hashlib.sha256(
            f"{req.from_address}:{req.to_address}:{amount}:{_time.time()}".encode()
        ).hexdigest()

        to_addr = req.to_address.replace('0x', '')

        with db_manager.get_session() as session:
            from sqlalchemy import text as sa_text
            # Spend inputs
            for u in selected:
                session.execute(
                    sa_text("UPDATE utxos SET spent = true, spent_by = :txid WHERE txid = :utxid AND vout = :vout AND spent = false"),
                    {'txid': tx_hash, 'utxid': u.txid, 'vout': u.vout}
                )
            # Create outputs
            outputs = []
            vout = 0
            if req.to_address.startswith('0x'):
                # Cross-model: credit accounts table
                session.execute(
                    sa_text("""
                        INSERT INTO accounts (address, nonce, balance, code_hash, storage_root)
                        VALUES (:addr, 0, :amt, '', '')
                        ON CONFLICT (address) DO UPDATE SET balance = accounts.balance + :amt
                    """),
                    {'addr': to_addr, 'amt': str(amount)}
                )
                outputs.append({'address': to_addr, 'amount': str(amount)})
            else:
                # Same model: create UTXO
                session.execute(
                    sa_text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, :vout, :amt, :addr, '{}', :h, false)
                    """),
                    {'txid': tx_hash, 'vout': vout, 'amt': str(amount), 'addr': to_addr, 'h': db_manager.get_current_height()}
                )
                outputs.append({'address': to_addr, 'amount': str(amount)})
                vout += 1
            # Change UTXO
            if change > 0:
                session.execute(
                    sa_text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, :vout, :amt, :addr, '{}', :h, false)
                    """),
                    {'txid': tx_hash, 'vout': vout, 'amt': str(change), 'addr': req.from_address, 'h': db_manager.get_current_height()}
                )
                outputs.append({'address': req.from_address, 'amount': str(change)})
            # Transaction record
            session.execute(
                sa_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                              timestamp, status, tx_type, to_address, data,
                                              gas_limit, gas_price, nonce)
                    VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb), 0, :sig, :pk,
                            :ts, 'confirmed', 'transfer', :to_addr, '', 0, 0, 0)
                """),
                {
                    'txid': tx_hash,
                    'inputs': _json.dumps([{'txid': u.txid, 'vout': u.vout} for u in selected]),
                    'outputs': _json.dumps(outputs),
                    'sig': req.signature_hex[:128], 'pk': req.public_key_hex[:128],
                    'ts': _time.time(), 'to_addr': to_addr,
                }
            )
            session.commit()

        logger.info(f"Native send: {req.from_address[:8]}→{to_addr[:8]} {amount} QBC")
        return {'tx_hash': tx_hash, 'status': 'confirmed'}

    class WalletSignRequest(BaseModel):
        message_hash: str
        private_key_hex: str

    @app.post("/wallet/sign")
    async def wallet_sign(req: WalletSignRequest):
        """Sign a message hash with a Dilithium2 private key.

        The private key is used only for this signing operation and not stored.
        """
        from ..quantum.crypto import Dilithium2
        try:
            sk = bytes.fromhex(req.private_key_hex)
            msg = bytes.fromhex(req.message_hash)
            signature = Dilithium2.sign(sk, msg)
            return {'signature_hex': signature.hex()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Signing failed: {e}")

    # ========================================================================
    # SEPHIROT NODE STAKING
    # ========================================================================

    SEPHIROT_NODES = [
        {'id': 0, 'name': 'Keter', 'title': 'Crown', 'function': 'Meta-learning, goal formation', 'brain_analog': 'Prefrontal cortex', 'min_stake': 100},
        {'id': 1, 'name': 'Chochmah', 'title': 'Wisdom', 'function': 'Intuition, pattern discovery', 'brain_analog': 'Right hemisphere', 'min_stake': 100},
        {'id': 2, 'name': 'Binah', 'title': 'Understanding', 'function': 'Logic, causal inference', 'brain_analog': 'Left hemisphere', 'min_stake': 100},
        {'id': 3, 'name': 'Chesed', 'title': 'Mercy', 'function': 'Exploration, divergent thinking', 'brain_analog': 'Default mode network', 'min_stake': 100},
        {'id': 4, 'name': 'Gevurah', 'title': 'Severity', 'function': 'Constraint, safety validation', 'brain_analog': 'Amygdala', 'min_stake': 100},
        {'id': 5, 'name': 'Tiferet', 'title': 'Beauty', 'function': 'Integration, conflict resolution', 'brain_analog': 'Thalamocortical loops', 'min_stake': 100},
        {'id': 6, 'name': 'Netzach', 'title': 'Victory', 'function': 'Reinforcement learning, habits', 'brain_analog': 'Basal ganglia', 'min_stake': 100},
        {'id': 7, 'name': 'Hod', 'title': 'Splendor', 'function': 'Language, semantic encoding', 'brain_analog': "Broca/Wernicke", 'min_stake': 100},
        {'id': 8, 'name': 'Yesod', 'title': 'Foundation', 'function': 'Memory, multimodal fusion', 'brain_analog': 'Hippocampus', 'min_stake': 100},
        {'id': 9, 'name': 'Malkuth', 'title': 'Kingdom', 'function': 'Action, world interaction', 'brain_analog': 'Motor cortex', 'min_stake': 100},
    ]

    @app.get("/sephirot/nodes")
    async def get_sephirot_nodes():
        """Get all 10 Sephirot node definitions with staking stats."""
        summary = db_manager.get_sephirot_summary()
        nodes = []
        for n in SEPHIROT_NODES:
            stats = summary.get(n['id'], {'staker_count': 0, 'total_staked': '0'})
            nodes.append({
                **n,
                'current_stakers': stats['staker_count'],
                'total_staked': stats['total_staked'],
                'apy_estimate': 5.0,  # ~5% from Proof-of-Thought bounties
            })
        return {'nodes': nodes}

    class StakeRequest(BaseModel):
        address: str
        node_id: int
        amount: str
        signature_hex: str
        public_key_hex: str

    @app.post("/sephirot/stake")
    async def sephirot_stake(req: StakeRequest):
        """Stake QBC on a Sephirot node."""
        from ..quantum.crypto import Dilithium2
        import json as _json

        amount = Decimal(req.amount)
        if req.node_id < 0 or req.node_id > 9:
            raise HTTPException(status_code=400, detail="node_id must be 0-9")
        min_stake = SEPHIROT_NODES[req.node_id]['min_stake']
        if amount < min_stake:
            raise HTTPException(status_code=400, detail=f"Minimum stake is {min_stake} QBC")

        # Verify signature
        pk = bytes.fromhex(req.public_key_hex)
        derived_addr = Dilithium2.derive_address(pk)
        if derived_addr != req.address:
            raise HTTPException(status_code=400, detail="Public key does not match address")
        tx_data = {'address': req.address, 'node_id': req.node_id, 'amount': req.amount, 'action': 'stake'}
        msg = _json.dumps(tx_data, sort_keys=True).encode()
        sig = bytes.fromhex(req.signature_hex)
        if not Dilithium2.verify(pk, msg, sig):
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Check balance
        balance = db_manager.get_balance(req.address)
        if balance < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient balance: have {balance}, need {amount}")

        # Deduct UTXOs
        import hashlib
        import time as _time
        utxos = db_manager.get_utxos(req.address)
        utxos.sort(key=lambda u: u.amount, reverse=True)
        selected = []
        total = Decimal(0)
        for u in utxos:
            selected.append(u)
            total += u.amount
            if total >= amount:
                break
        change = total - amount
        tx_hash = hashlib.sha256(f"stake:{req.address}:{req.node_id}:{amount}:{_time.time()}".encode()).hexdigest()

        with db_manager.get_session() as session:
            from sqlalchemy import text as sa_text
            for u in selected:
                session.execute(
                    sa_text("UPDATE utxos SET spent = true, spent_by = :txid WHERE txid = :utxid AND vout = :vout AND spent = false"),
                    {'txid': tx_hash, 'utxid': u.txid, 'vout': u.vout}
                )
            if change > 0:
                session.execute(
                    sa_text("INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent) VALUES (:txid, 0, :amt, :addr, '{}', :h, false)"),
                    {'txid': tx_hash, 'amt': str(change), 'addr': req.address, 'h': db_manager.get_current_height()}
                )
            session.commit()

        stake_id = db_manager.create_stake(req.address, req.node_id, amount)
        logger.info(f"Sephirot stake: {req.address[:8]} → node {req.node_id} ({SEPHIROT_NODES[req.node_id]['name']}) {amount} QBC")
        return {'stake_id': stake_id, 'node_id': req.node_id, 'amount': str(amount), 'status': 'active'}

    class UnstakeRequest(BaseModel):
        address: str
        stake_id: str
        signature_hex: str
        public_key_hex: str

    @app.post("/sephirot/unstake")
    async def sephirot_unstake(req: UnstakeRequest):
        """Request unstaking (7-day delay)."""
        from ..quantum.crypto import Dilithium2
        import json as _json

        pk = bytes.fromhex(req.public_key_hex)
        derived_addr = Dilithium2.derive_address(pk)
        if derived_addr != req.address:
            raise HTTPException(status_code=400, detail="Public key does not match address")
        tx_data = {'address': req.address, 'stake_id': req.stake_id, 'action': 'unstake'}
        msg = _json.dumps(tx_data, sort_keys=True).encode()
        sig = bytes.fromhex(req.signature_hex)
        if not Dilithium2.verify(pk, msg, sig):
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Verify stake belongs to address
        stake = db_manager.get_stake(req.stake_id)
        if not stake:
            raise HTTPException(status_code=404, detail="Stake not found")
        if stake['address'] != req.address:
            raise HTTPException(status_code=403, detail="Stake does not belong to this address")
        if stake['status'] != 'active':
            raise HTTPException(status_code=400, detail=f"Stake is already {stake['status']}")

        success = db_manager.request_unstake(req.stake_id, req.address)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to unstake")

        import datetime
        available_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        return {'stake_id': req.stake_id, 'status': 'unstaking', 'available_at': available_at.isoformat()}

    @app.get("/sephirot/stakes/{address}")
    async def get_sephirot_stakes(address: str):
        """Get all stakes for an address."""
        stakes = db_manager.get_stakes_by_address(address)
        # Attach node name
        for s in stakes:
            nid = s['node_id']
            if 0 <= nid <= 9:
                s['node_name'] = SEPHIROT_NODES[nid]['name']
        return {'stakes': stakes}

    @app.get("/sephirot/rewards/{address}")
    async def get_sephirot_rewards(address: str):
        """Get accumulated rewards for an address."""
        stakes = db_manager.get_stakes_by_address(address)
        total_earned = sum(Decimal(s['rewards_earned']) for s in stakes)
        total_claimed = sum(Decimal(s['rewards_claimed']) for s in stakes)
        pending = total_earned - total_claimed
        return {
            'total_earned': str(total_earned),
            'pending_claim': str(pending),
            'claimed': str(total_claimed),
            'stakes': stakes,
        }

    class ClaimRewardsRequest(BaseModel):
        address: str
        signature_hex: str
        public_key_hex: str

    @app.post("/sephirot/claim-rewards")
    async def sephirot_claim_rewards(req: ClaimRewardsRequest):
        """Claim all pending staking rewards."""
        from ..quantum.crypto import Dilithium2
        import json as _json
        import hashlib
        import time as _time

        pk = bytes.fromhex(req.public_key_hex)
        derived_addr = Dilithium2.derive_address(pk)
        if derived_addr != req.address:
            raise HTTPException(status_code=400, detail="Public key does not match address")
        tx_data = {'address': req.address, 'action': 'claim_rewards'}
        msg = _json.dumps(tx_data, sort_keys=True).encode()
        sig = bytes.fromhex(req.signature_hex)
        if not Dilithium2.verify(pk, msg, sig):
            raise HTTPException(status_code=400, detail="Invalid signature")

        claimed = db_manager.claim_rewards(req.address)
        if claimed <= 0:
            return {'claimed_amount': '0', 'tx_hash': None}

        # Create UTXO for claimed rewards
        tx_hash = hashlib.sha256(f"claim:{req.address}:{claimed}:{_time.time()}".encode()).hexdigest()
        with db_manager.get_session() as session:
            from sqlalchemy import text as sa_text
            session.execute(
                sa_text("INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent) VALUES (:txid, 0, :amt, :addr, '{}', :h, false)"),
                {'txid': tx_hash, 'amt': str(claimed), 'addr': req.address, 'h': db_manager.get_current_height()}
            )
            session.commit()

        logger.info(f"Rewards claimed: {req.address[:8]} → {claimed} QBC")
        return {'claimed_amount': str(claimed), 'tx_hash': tx_hash}

    # ========================================================================
    # SUSY SOLUTION DATABASE (Scientific Research API)
    # ========================================================================

    @app.get("/susy-database")
    async def susy_database(
        min_height: Optional[int] = None,
        max_height: Optional[int] = None,
        max_energy: Optional[float] = None,
        limit: int = 50,
    ):
        """Query the public Hamiltonian solution database.

        Every mined block contributes a solved SUSY Hamiltonian to this
        public scientific database.
        """
        from sqlalchemy import text as sa_text
        conditions = []
        params: dict = {"limit": min(limit, 500)}
        if min_height is not None:
            conditions.append("block_height >= :min_h")
            params["min_h"] = min_height
        if max_height is not None:
            conditions.append("block_height <= :max_h")
            params["max_h"] = max_height
        if max_energy is not None:
            conditions.append("energy <= :max_e")
            params["max_e"] = max_energy

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
            SELECT id, hamiltonian, params, energy, miner_address, block_height
            FROM solved_hamiltonians
            {where}
            ORDER BY block_height DESC
            LIMIT :limit
        """
        with db_manager.get_session() as session:
            rows = session.execute(sa_text(query), params).fetchall()
            solutions = []
            for r in rows:
                solutions.append({
                    "id": r[0],
                    "hamiltonian": r[1],
                    "params": r[2],
                    "energy": r[3],
                    "miner_address": r[4],
                    "block_height": r[5],
                })
        return {
            "solutions": solutions,
            "count": len(solutions),
            "description": "Solved SUSY Hamiltonians from Proof-of-SUSY-Alignment mining",
        }

    @app.get("/susy-database/export")
    async def susy_database_export(
        format: str = "json",
        min_height: Optional[int] = None,
        max_height: Optional[int] = None,
        limit: int = 100,
    ):
        """Export SUSY solution data in JSON or CSV format for researchers.

        Args:
            format: Export format — 'json' or 'csv'.
            min_height: Minimum block height filter.
            max_height: Maximum block height filter.
            limit: Maximum number of records (capped at 1000).
        """
        from sqlalchemy import text as sa_text
        conditions: list = []
        params: dict = {"limit": min(limit, 1000)}
        if min_height is not None:
            conditions.append("block_height >= :min_h")
            params["min_h"] = min_height
        if max_height is not None:
            conditions.append("block_height <= :max_h")
            params["max_h"] = max_height

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
            SELECT id, hamiltonian, params, energy, miner_address, block_height
            FROM solved_hamiltonians
            {where}
            ORDER BY block_height ASC
            LIMIT :limit
        """
        with db_manager.get_session() as session:
            rows = session.execute(sa_text(query), params).fetchall()
            solutions = []
            for r in rows:
                solutions.append({
                    "id": r[0],
                    "hamiltonian": r[1],
                    "params": r[2],
                    "energy": r[3],
                    "miner_address": r[4],
                    "block_height": r[5],
                })

        if format == "csv":
            header = "id,hamiltonian,params,energy,miner_address,block_height\n"
            rows_csv = []
            for s in solutions:
                h = str(s['hamiltonian']).replace('"', '""') if s['hamiltonian'] else ''
                p = str(s['params']).replace('"', '""') if s['params'] else ''
                rows_csv.append(
                    f"{s['id']},\"{h}\",\"{p}\",{s['energy']},{s['miner_address']},{s['block_height']}"
                )
            csv_content = header + "\n".join(rows_csv)
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=susy_solutions.csv"},
            )

        # Default: JSON
        return {
            "format": "json",
            "solutions": solutions,
            "count": len(solutions),
            "metadata": {
                "description": "SUSY Hamiltonian solutions from Proof-of-SUSY-Alignment mining",
                "chain": "Qubitcoin",
                "chain_id": Config.CHAIN_ID,
                "scientific_applications": [
                    "particle_physics", "materials_science",
                    "quantum_chemistry", "algorithm_benchmarking",
                ],
            },
        }

    # ========================================================================
    # UTXO STATS ENDPOINT
    # ========================================================================

    @app.get("/utxo/stats")
    async def utxo_stats():
        """Get UTXO set statistics."""
        stats = db_manager.get_utxo_stats()
        commitment = db_manager.compute_utxo_commitment()
        return {**stats, "utxo_commitment": commitment}

    # ========================================================================
    # WEBSOCKET — Real-time block & Phi updates
    # ========================================================================

    from fastapi import WebSocket, WebSocketDisconnect

    _ws_clients: list = []

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket for real-time chain events (blocks, txs, Phi updates)."""
        await websocket.accept()
        _ws_clients.append(websocket)
        try:
            while True:
                # Keep-alive: clients can send pings, we just read and discard
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)

    async def broadcast_ws(event_type: str, data: dict) -> None:
        """Broadcast an event to all connected WebSocket clients."""
        import json as _json
        message = _json.dumps({"type": event_type, "data": data})
        disconnected = []
        for ws in _ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in _ws_clients:
                _ws_clients.remove(ws)

    # Attach broadcast helper to the app so node.py can call it
    app.broadcast_ws = broadcast_ws  # type: ignore[attr-defined]

    # ========================================================================
    # AETHER WEBSOCKET STREAMING (/ws/aether)
    # ========================================================================

    from ..aether.ws_streaming import AetherWSManager
    _aether_ws = AetherWSManager()
    app.aether_ws = _aether_ws  # type: ignore[attr-defined]

    @app.websocket("/ws/aether")
    async def aether_websocket_endpoint(websocket: WebSocket):
        """WebSocket for Aether Tree real-time events.

        Connect with optional query params:
          ?session_id=<uuid>  — bind to a chat session for response streaming
          ?subscribe=phi_update,consciousness_event  — comma-separated events

        Events: aether_response, phi_update, knowledge_node,
                consciousness_event, circulation_update, token_transfer
        """
        await websocket.accept()

        # Parse query parameters
        session_id = websocket.query_params.get('session_id')
        subscribe_param = websocket.query_params.get('subscribe', '')
        subscriptions = None
        if subscribe_param:
            subscriptions = set(subscribe_param.split(','))

        _aether_ws.register(websocket, session_id, subscriptions)
        try:
            while True:
                # Keep-alive: read pings/subscriptions updates
                data = await websocket.receive_text()
                # Clients can update subscriptions dynamically
                try:
                    import json as _ws_json
                    msg = _ws_json.loads(data)
                    if msg.get('type') == 'subscribe' and 'events' in msg:
                        client_id = id(websocket)
                        if client_id in _aether_ws._clients:
                            new_subs = set(msg['events']) & _aether_ws.VALID_EVENTS
                            _aether_ws._clients[client_id].subscriptions = new_subs
                except Exception:
                    pass  # Not JSON or malformed — treat as ping
        except WebSocketDisconnect:
            pass
        finally:
            _aether_ws.unregister(websocket)

    @app.get("/ws/aether/stats")
    async def aether_ws_stats():
        """Get Aether WebSocket streaming statistics."""
        return _aether_ws.get_stats()

    # ========================================================================
    # QBC CIRCULATION TRACKING
    # ========================================================================

    from ..aether.circulation import CirculationTracker
    _circulation_tracker = CirculationTracker()
    app.circulation_tracker = _circulation_tracker  # type: ignore[attr-defined]

    @app.get("/circulation/stats")
    async def circulation_stats():
        """Get current QBC circulation statistics."""
        return _circulation_tracker.get_stats()

    @app.get("/circulation/current")
    async def circulation_current():
        """Get the latest circulation snapshot."""
        current = _circulation_tracker.get_current()
        if not current:
            return {"error": "No circulation data yet. Mine some blocks first."}
        return current.to_dict()

    @app.get("/circulation/history")
    async def circulation_history(limit: int = 100):
        """Get recent circulation snapshots."""
        limit = max(1, min(limit, 1000))
        return {"history": _circulation_tracker.get_history(limit)}

    @app.get("/circulation/halvings")
    async def circulation_halvings():
        """Get all recorded phi-halving events."""
        return {"halvings": _circulation_tracker.get_halving_events()}

    @app.get("/circulation/emission-schedule")
    async def circulation_emission_schedule(num_eras: int = 10):
        """Get projected emission schedule for upcoming eras."""
        num_eras = max(1, min(num_eras, 50))
        return {"schedule": _circulation_tracker.get_emission_schedule(num_eras)}

    # ========================================================================
    # TOKEN INDEXER (QBC-20 / QBC-721)
    # ========================================================================

    from ..qvm.token_indexer import TokenIndexer
    _token_indexer = TokenIndexer()
    app.token_indexer = _token_indexer  # type: ignore[attr-defined]

    @app.get("/tokens")
    async def list_tokens():
        """List all tracked token contracts."""
        return {"tokens": _token_indexer.get_all_tokens()}

    @app.get("/tokens/stats")
    async def token_stats():
        """Get token indexer statistics."""
        return _token_indexer.get_stats()

    @app.get("/tokens/{contract_address}")
    async def get_token_info(contract_address: str):
        """Get metadata about a specific token contract."""
        info = _token_indexer.get_token_info(contract_address)
        if not info:
            raise HTTPException(status_code=404, detail="Token not found")
        return info

    @app.get("/tokens/{contract_address}/holders")
    async def get_token_holders(contract_address: str, limit: int = 100):
        """Get top holders for a token, sorted by balance."""
        limit = max(1, min(limit, 1000))
        return {"holders": _token_indexer.get_token_holders(contract_address, limit)}

    @app.get("/tokens/{contract_address}/transfers")
    async def get_token_transfers(contract_address: str, limit: int = 100):
        """Get recent transfers for a specific token."""
        limit = max(1, min(limit, 1000))
        return {"transfers": _token_indexer.get_transfers(contract_address=contract_address, limit=limit)}

    @app.get("/tokens/{contract_address}/balance/{holder_address}")
    async def get_token_balance(contract_address: str, holder_address: str):
        """Get a specific holder's balance for a token."""
        balance = _token_indexer.get_token_balance(contract_address, holder_address)
        return {"balance": str(balance), "token": contract_address, "holder": holder_address}

    @app.get("/address/{address}/tokens")
    async def get_address_token_transfers(address: str, limit: int = 100):
        """Get all token transfers for a specific address (sent or received)."""
        limit = max(1, min(limit, 1000))
        return {"transfers": _token_indexer.get_transfers(address=address, limit=limit)}

    # ========================================================================
    # PROOF-OF-THOUGHT EXPLORER
    # ========================================================================

    from ..aether.pot_explorer import ProofOfThoughtExplorer
    _pot_explorer = ProofOfThoughtExplorer(aether_engine)
    app.pot_explorer = _pot_explorer  # type: ignore[attr-defined]

    @app.get("/aether/pot/{block_height}")
    async def get_block_thought(block_height: int):
        """Get Proof-of-Thought data for a specific block."""
        data = _pot_explorer.get_block_thought(block_height)
        if not data:
            raise HTTPException(status_code=404, detail="No PoT data for this block")
        return data

    @app.get("/aether/pot/range/{start}/{end}")
    async def get_pot_range(start: int, end: int):
        """Get PoT data for a range of blocks."""
        if end - start > 1000:
            raise HTTPException(status_code=400, detail="Range too large (max 1000)")
        return {"blocks": _pot_explorer.get_block_range(start, end)}

    @app.get("/aether/pot/phi-progression")
    async def get_phi_progression(limit: int = 100):
        """Get Phi value progression over recent blocks."""
        limit = max(1, min(limit, 1000))
        return {"progression": _pot_explorer.get_phi_progression(limit)}

    @app.get("/aether/pot/consciousness-events")
    async def get_pot_consciousness_events(limit: int = 50):
        """Get blocks where consciousness events occurred."""
        return {"events": _pot_explorer.get_consciousness_events(limit)}

    @app.get("/aether/pot/summary/{block_height}")
    async def get_reasoning_summary(block_height: int):
        """Get human-readable reasoning summary for a block."""
        return _pot_explorer.get_reasoning_summary(block_height)

    @app.get("/aether/pot/stats")
    async def get_pot_stats():
        """Get Proof-of-Thought explorer statistics."""
        return _pot_explorer.get_stats()

    # ========================================================================
    # COMPLIANCE PROOFS
    # ========================================================================

    from ..qvm.compliance_proofs import ComplianceProofStore
    _proof_store = ComplianceProofStore()
    app.proof_store = _proof_store  # type: ignore[attr-defined]

    @app.get("/qvm/compliance/proofs/stats")
    async def compliance_proof_stats():
        """Get compliance proof store statistics."""
        return _proof_store.get_stats()

    @app.get("/qvm/compliance/proofs/{proof_id}")
    async def get_compliance_proof(proof_id: str):
        """Get a specific compliance proof by ID."""
        proof = _proof_store.get_proof(proof_id)
        if not proof:
            raise HTTPException(status_code=404, detail="Proof not found")
        return proof

    @app.get("/qvm/compliance/proofs/address/{address}")
    async def get_address_compliance_proofs(address: str, limit: int = 100):
        """Get all compliance proofs for an address."""
        limit = max(1, min(limit, 500))
        return {"proofs": _proof_store.get_address_proofs(address, limit=limit)}

    @app.get("/qvm/compliance/proofs/verify/{address}")
    async def verify_proof_chain(address: str):
        """Verify the integrity of an address's compliance proof chain."""
        return _proof_store.verify_proof_chain(address)

    # ========================================================================
    # REGULATORY REPORTS (initialized after compliance engine below)
    # ========================================================================

    @app.post("/qvm/compliance/reports/generate")
    async def generate_regulatory_report(request: Request):
        """Generate a regulatory compliance report."""
        body = await request.json()
        report_type = body.get('report_type', 'general')
        period = body.get('period', 'monthly')
        report = _report_gen.generate_report(
            report_type=report_type,
            period=period,
            period_start=body.get('period_start', 0.0),
            period_end=body.get('period_end', 0.0),
            block_start=body.get('block_start', 0),
            block_end=body.get('block_end', 0),
            additional_data=body.get('additional_data'),
        )
        return report.to_dict()

    @app.get("/qvm/compliance/reports")
    async def list_regulatory_reports(report_type: Optional[str] = None, limit: int = 50):
        """List generated regulatory reports."""
        limit = max(1, min(limit, 200))
        return {"reports": _report_gen.list_reports(report_type, limit)}

    @app.get("/qvm/compliance/reports/{report_id}")
    async def get_regulatory_report(report_id: str):
        """Get a specific regulatory report by ID."""
        report = _report_gen.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    @app.get("/qvm/compliance/reports/stats")
    async def regulatory_report_stats():
        """Get report generator statistics."""
        return _report_gen.get_stats()

    # ========================================================================
    # METRICS ENDPOINT
    # ========================================================================

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    # ========================================================================
    # QUSD ORACLE ENDPOINTS
    # ========================================================================

    @app.get("/qusd/price")
    async def qusd_price():
        """Get current QBC/USD price from oracle."""
        from ..utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle(state_manager)
        return oracle.get_status()

    @app.get("/qusd/reserves")
    async def qusd_reserves():
        """Get QUSD reserve status."""
        try:
            from sqlalchemy import text as sql_text
            with db_manager.get_session() as session:
                result = session.execute(sql_text(
                    "SELECT total_minted, total_backed, backing_percentage "
                    "FROM qusd_debt_ledger ORDER BY recorded_at DESC LIMIT 1"
                )).fetchone()
                if result:
                    return {
                        'total_minted': str(result[0]),
                        'total_backed': str(result[1]),
                        'backing_percentage': float(result[2]),
                    }
        except Exception:
            pass
        return {'total_minted': '3300000000', 'total_backed': '0', 'backing_percentage': 0.0}

    @app.get("/qusd/debt")
    async def qusd_debt():
        """Get QUSD debt status."""
        return await qusd_reserves()

    # ========================================================================
    # COMPLIANCE POLICY ENDPOINTS (PCP — Programmable Compliance Policies)
    # ========================================================================
    from ..qvm.compliance import ComplianceEngine, KYCLevel
    _compliance_engine = ComplianceEngine(db_manager)

    from ..qvm.regulatory_reports import RegulatoryReportGenerator
    _report_gen = RegulatoryReportGenerator(_compliance_engine, _proof_store)
    app.report_generator = _report_gen  # type: ignore[attr-defined]

    @app.get("/qvm/compliance/policies")
    async def list_compliance_policies():
        """List all registered compliance policies."""
        return {"policies": [p.to_dict() for p in _compliance_engine.list_policies()]}

    @app.post("/qvm/compliance/policies")
    async def create_compliance_policy(request: Request):
        """Create a new compliance policy for an address."""
        body = await request.json()
        address = body.get('address', '')
        if not address:
            raise HTTPException(status_code=400, detail="address is required")
        policy = _compliance_engine.create_policy(
            address=address,
            kyc_level=body.get('kyc_level', KYCLevel.BASIC),
            aml_status=body.get('aml_status', 0),
            sanctions_checked=body.get('sanctions_checked', False),
            daily_limit=body.get('daily_limit', 10_000.0),
            tier=body.get('tier', 0),
            jurisdiction=body.get('jurisdiction', ''),
        )
        return {"policy": policy.to_dict()}

    @app.get("/qvm/compliance/policies/{policy_id}")
    async def get_compliance_policy(policy_id: str):
        """Get a specific compliance policy by ID."""
        policy = _compliance_engine.get_policy(policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"policy": policy.to_dict()}

    @app.put("/qvm/compliance/policies/{policy_id}")
    async def update_compliance_policy(policy_id: str, request: Request):
        """Update fields on an existing compliance policy."""
        body = await request.json()
        updated = _compliance_engine.update_policy(policy_id, **body)
        if not updated:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"policy": updated.to_dict()}

    @app.delete("/qvm/compliance/policies/{policy_id}")
    async def delete_compliance_policy(policy_id: str):
        """Delete a compliance policy."""
        if not _compliance_engine.delete_policy(policy_id):
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"deleted": True}

    @app.get("/qvm/compliance/check/{address}")
    async def check_compliance(address: str):
        """Check compliance level for an address."""
        level = _compliance_engine.check_compliance(address)
        blocked = _compliance_engine.is_address_blocked(address)
        return {"address": address, "kyc_level": level, "is_blocked": blocked}

    @app.get("/qvm/compliance/circuit-breaker")
    async def get_circuit_breaker():
        """Get circuit breaker status."""
        return _compliance_engine.circuit_breaker.to_dict()

    @app.post("/qvm/compliance/circuit-breaker/reset")
    async def reset_circuit_breaker():
        """Manually reset the circuit breaker."""
        _compliance_engine.reset_circuit_breaker()
        return {"reset": True}

    # ========================================================================
    # DATABASE POOL HEALTH MONITORING
    # ========================================================================

    from ..database.pool_monitor import PoolHealthMonitor
    _pool_monitor = PoolHealthMonitor(engine=getattr(db_manager, 'engine', None))
    app.state.pool_monitor = _pool_monitor

    @app.get("/db/pool/health")
    async def db_pool_health():
        """Get current connection pool health snapshot."""
        snap = _pool_monitor.get_snapshot()
        return snap.to_dict()

    @app.get("/db/pool/stats")
    async def db_pool_stats():
        """Get aggregate pool statistics."""
        return _pool_monitor.get_stats()

    @app.get("/db/pool/history")
    async def db_pool_history(limit: int = 20):
        """Get recent pool health snapshots."""
        return {"history": _pool_monitor.get_history(limit=min(limit, 100))}

    # ========================================================================
    # SUSY SOLUTION VERIFICATION TRACKING
    # ========================================================================

    from ..mining.solution_tracker import SolutionVerificationTracker
    _solution_tracker = SolutionVerificationTracker()
    app.state.solution_tracker = _solution_tracker

    @app.get("/susy-database/verifications/stats")
    async def solution_verification_stats():
        """Get aggregate solution verification statistics."""
        return _solution_tracker.get_stats()

    @app.get("/susy-database/verifications/{solution_id}")
    async def get_solution_verifications(solution_id: int):
        """Get verification record for a specific solution."""
        record = _solution_tracker.get_solution(solution_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Solution not found")
        return record.to_dict()

    @app.get("/susy-database/verifications/block/{block_height}")
    async def get_solution_by_block(block_height: int):
        """Get solution verification record by block height."""
        record = _solution_tracker.get_by_block(block_height)
        if record is None:
            raise HTTPException(status_code=404, detail="No solution for block")
        return record.to_dict()

    @app.get("/susy-database/verifications/top")
    async def get_top_verified(limit: int = 10):
        """Get solutions with the most verifications."""
        top = _solution_tracker.get_top_verified(limit=min(limit, 50))
        return {"solutions": [r.to_dict() for r in top]}

    @app.get("/susy-database/verifications/unverified")
    async def get_unverified_solutions(limit: int = 20):
        """Get solutions that have zero verifications."""
        unv = _solution_tracker.get_unverified(limit=min(limit, 100))
        return {"solutions": [r.to_dict() for r in unv]}

    @app.post("/susy-database/verifications/{solution_id}/verify")
    async def submit_verification(solution_id: int, request: Request):
        """Submit a verification for a solution."""
        body = await request.json()
        verifier = body.get('verifier_address', '')
        energy = body.get('verified_energy', 0.0)
        tolerance = body.get('energy_tolerance', 0.01)
        if not verifier:
            raise HTTPException(status_code=400, detail="verifier_address required")
        v = _solution_tracker.record_verification(
            solution_id=solution_id,
            verifier_address=verifier,
            verified_energy=float(energy),
            energy_tolerance=float(tolerance),
        )
        if v is None:
            raise HTTPException(status_code=404, detail="Solution not found")
        return v.to_dict()

    # ========================================================================
    # MINING NODE VQE CAPABILITY DETECTION
    # ========================================================================

    from ..mining.capability_detector import VQECapabilityDetector
    _capability_detector = VQECapabilityDetector()
    app.state.capability_detector = _capability_detector

    # Auto-detect capabilities on startup
    try:
        _capability_detector.detect(quantum_engine)
    except Exception as _e:
        logger.warning(f"Auto-detect VQE capability failed: {_e}")

    @app.get("/mining/capability")
    async def mining_capability():
        """Get this node's VQE mining capabilities."""
        cap = _capability_detector.get_cached()
        if cap is None:
            cap = _capability_detector.detect_from_config()
        return cap.to_dict()

    @app.get("/mining/capability/advertisement")
    async def mining_capability_advertisement():
        """Get P2P capability advertisement message."""
        return _capability_detector.get_p2p_advertisement()

    # ========================================================================
    # P2P CAPABILITY ADVERTISEMENT REGISTRY
    # ========================================================================

    from .capability_advertisement import CapabilityAdvertiser
    _node_peer_id = getattr(Config, 'ADDRESS', 'unknown')[:16]
    _cap_advertiser = CapabilityAdvertiser(node_peer_id=_node_peer_id)
    app.state.capability_advertiser = _cap_advertiser

    # Seed local capability from detector
    _local_ad = _capability_detector.get_p2p_advertisement()
    if _local_ad:
        _cap_advertiser.set_local_capability(_local_ad)

    @app.get("/p2p/capabilities")
    async def p2p_capabilities():
        """Get all known peer capabilities."""
        peers = _cap_advertiser.get_all_peers()
        return {"peers": [p.to_dict() for p in peers]}

    @app.get("/p2p/capabilities/ranked")
    async def p2p_capabilities_ranked(limit: int = 20):
        """Get peers ranked by mining power."""
        ranked = _cap_advertiser.get_peers_by_power(limit=min(limit, 50))
        return {"peers": [p.to_dict() for p in ranked]}

    @app.get("/p2p/capabilities/summary")
    async def p2p_capabilities_summary():
        """Get network-wide capability summary."""
        return _cap_advertiser.get_network_summary()

    @app.get("/p2p/capabilities/local")
    async def p2p_capabilities_local():
        """Get this node's capability advertisement."""
        ad = _cap_advertiser.get_local_advertisement()
        if ad is None:
            return {"error": "No local capability set"}
        return ad

    @app.post("/p2p/capabilities/report")
    async def p2p_capabilities_report(request: Request):
        """Receive a capability advertisement from a peer."""
        body = await request.json()
        peer_id = body.get('peer_id', '')
        if not peer_id:
            raise HTTPException(status_code=400, detail="peer_id required")
        cap = _cap_advertiser.receive_advertisement(peer_id, body)
        return cap.to_dict()

    # ========================================================================
    # BLOCKCHAIN SNAPSHOT SCHEDULER
    # ========================================================================

    from ..storage.snapshot_scheduler import SnapshotScheduler
    _snapshot_scheduler = SnapshotScheduler()
    app.state.snapshot_scheduler = _snapshot_scheduler

    @app.get("/snapshots/stats")
    async def snapshot_stats():
        """Get snapshot scheduler statistics."""
        return _snapshot_scheduler.get_stats()

    @app.get("/snapshots/history")
    async def snapshot_history(limit: int = 20):
        """Get recent snapshot history."""
        return {"history": _snapshot_scheduler.get_history(limit=min(limit, 100))}

    @app.get("/snapshots/latest")
    async def snapshot_latest():
        """Get the most recent snapshot."""
        latest = _snapshot_scheduler.get_latest()
        if latest is None:
            return {"error": "No snapshots taken yet"}
        return latest.to_dict()

    @app.post("/snapshots/trigger")
    async def snapshot_trigger():
        """Manually trigger a blockchain snapshot."""
        height = db_manager.get_current_height()
        record = _snapshot_scheduler.take_snapshot(
            height=height, db_manager=db_manager, ipfs_manager=ipfs_manager,
        )
        return record.to_dict()

    # ========================================================================
    # SUSY SOLUTION ARCHIVER
    # ========================================================================

    from ..storage.solution_archiver import SolutionArchiver
    _solution_archiver = SolutionArchiver()
    app.state.solution_archiver = _solution_archiver

    @app.get("/susy-database/archives/stats")
    async def solution_archive_stats():
        """Get solution archive statistics."""
        return _solution_archiver.get_stats()

    @app.get("/susy-database/archives/history")
    async def solution_archive_history(limit: int = 20):
        """Get recent archive history."""
        return {"history": _solution_archiver.get_history(limit=min(limit, 100))}

    @app.get("/susy-database/archives/cids")
    async def solution_archive_cids():
        """Get all IPFS CIDs from solution archives."""
        return {"cids": _solution_archiver.get_all_cids()}

    @app.post("/susy-database/archives/trigger")
    async def solution_archive_trigger(
        from_height: int = 0, to_height: Optional[int] = None,
    ):
        """Manually trigger a solution archive for a block range."""
        if to_height is None:
            to_height = db_manager.get_current_height()
        record = _solution_archiver.archive_range(
            from_height=from_height, to_height=to_height,
            db_manager=db_manager, ipfs_manager=ipfs_manager,
        )
        return record.to_dict()

    # ========================================================================
    # ADMIN API (Economics hot-reload)
    # ========================================================================

    from .admin_api import router as admin_router
    app.include_router(admin_router)

    logger.info("RPC endpoints configured (v2.0 with P2P + QVM + Aether + WebSocket + Admin)")

    return app
