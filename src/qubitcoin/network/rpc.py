"""
RPC API endpoints for Qubitcoin node v2.0
FastAPI-based HTTP interface with smart contract support
NOW WITH P2P ENDPOINTS!
"""

from typing import Optional
from decimal import Decimal

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from ..config import Config
from ..database.models import Transaction
from ..utils.logger import get_logger
from ..utils.metrics import generate_latest, CONTENT_TYPE_LATEST

logger = get_logger(__name__)


def create_rpc_app(db_manager, consensus_engine, mining_engine,
                   quantum_engine, ipfs_manager, contract_engine=None,
                   state_manager=None, aether_engine=None) -> FastAPI:
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

        return {
            "height": emission_stats['current_height'],
            "total_supply": str(emission_stats['total_supply']),
            "max_supply": str(Config.MAX_SUPPLY),
            "percent_emitted": f"{emission_stats['percent_emitted']:.4f}%",
            "current_era": emission_stats.get('current_era', 0),
            "current_reward": str(emission_stats.get('current_reward', 50.0)),
            "difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "target_block_time": Config.TARGET_BLOCK_TIME
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
            "success_rate": mining_engine.stats['blocks_found'] / max(1, mining_engine.stats['total_attempts'])
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
        return {
            'phi': phi_data.get('phi_value', 0.0),
            'threshold': phi_data.get('phi_threshold', 3.0),
            'above_threshold': phi_data.get('above_threshold', False),
            'integration': phi_data.get('integration_score', 0.0),
            'differentiation': phi_data.get('differentiation_score', 0.0),
            'knowledge_nodes': kg_stats.get('total_nodes', 0),
            'knowledge_edges': kg_stats.get('total_edges', 0),
            'blocks_processed': kg_stats.get('blocks_processed', 0),
        }

    # ========================================================================
    # KNOWLEDGE GRAPH QUERY ENDPOINTS
    # ========================================================================

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
            _chat_state['chat'] = AetherChat(aether_engine, db_manager, fee_mgr)
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
    # ADMIN API (Economics hot-reload)
    # ========================================================================

    from .admin_api import router as admin_router
    app.include_router(admin_router)

    logger.info("RPC endpoints configured (v2.0 with P2P + QVM + Aether + WebSocket + Admin)")

    return app
