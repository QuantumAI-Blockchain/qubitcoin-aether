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
                   state_manager=None) -> FastAPI:
    """
    Create FastAPI application with all endpoints including smart contracts and QVM

    Args:
        db_manager: Database manager instance
        consensus_engine: Consensus engine instance
        mining_engine: Mining engine instance
        quantum_engine: Quantum engine instance
        ipfs_manager: IPFS manager instance
        contract_engine: Smart contract engine instance (optional for v1 compatibility)
        state_manager: QVM state manager instance (optional)

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

        # Get P2P info if available
        p2p_info = {}
        if hasattr(app, 'node') and hasattr(app.node, 'p2p'):
            p2p_info = {
                'peers': len(app.node.p2p.connections),
                'port': app.node.p2p.port
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
                "quantum_proofs": True,
                "post_quantum_crypto": "Dilithium2",
                "consensus": "Proof-of-SUSY-Alignment",
                "p2p_networking": True
            }
        }

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        p2p_status = False
        if hasattr(app, 'node') and hasattr(app.node, 'p2p'):
            p2p_status = app.node.p2p.running
        
        return {
            "status": "healthy",
            "mining": mining_engine.is_mining,
            "database": True,
            "quantum": quantum_engine.estimator is not None,
            "ipfs": ipfs_manager.client is not None,
            "contracts": contract_engine is not None,
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
        
        # Get P2P stats if available
        p2p_stats = {}
        if hasattr(app, 'node') and hasattr(app.node, 'p2p'):
            p2p_stats = app.node.p2p.get_stats()

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
        if not hasattr(app, 'node') or not hasattr(app.node, 'p2p'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        
        peers = app.node.p2p.get_peer_list()
        
        return {
            "peer_count": len(peers),
            "max_peers": app.node.p2p.max_peers,
            "port": app.node.p2p.port,
            "peer_id": app.node.p2p.peer_id,
            "peers": peers
        }

    @app.get("/p2p/stats")
    async def get_p2p_stats():
        """Get P2P network statistics"""
        if not hasattr(app, 'node') or not hasattr(app.node, 'p2p'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        
        stats = app.node.p2p.get_stats()
        
        return {
            "network": {
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

    @app.post("/p2p/connect")
    async def connect_to_peer(address: str):
        """Connect to a peer manually"""
        if not hasattr(app, 'node') or not hasattr(app.node, 'p2p'):
            raise HTTPException(status_code=503, detail="P2P network not available")
        
        try:
            await app.node.p2p.connect_to_peer(address)
            return {"status": "success", "message": f"Connecting to {address}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")

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

    logger.info("RPC endpoints configured (v2.0 with P2P + QVM)")

    return app
