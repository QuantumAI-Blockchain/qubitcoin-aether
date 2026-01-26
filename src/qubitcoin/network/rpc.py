"""
RPC API endpoints for Qubitcoin node
FastAPI-based HTTP interface for wallets and clients
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
                   quantum_engine, ipfs_manager) -> FastAPI:
    """
    Create FastAPI application with all endpoints
    
    Args:
        db_manager: Database manager instance
        consensus_engine: Consensus engine instance
        mining_engine: Mining engine instance
        quantum_engine: Quantum engine instance
        ipfs_manager: IPFS manager instance
        
    Returns:
        Configured FastAPI app
    """
    
    app = FastAPI(
        title="Qubitcoin Node RPC",
        version="1.0.0",
        description="Quantum-secured cryptocurrency node"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ========================================================================
    # NODE INFO ENDPOINTS
    # ========================================================================
    
    @app.get("/")
    async def root():
        """Get node information"""
        return {
            "node": "Qubitcoin Full Node",
            "version": "1.0.0",
            "network": "mainnet",
            "height": db_manager.get_current_height(),
            "difficulty": mining_engine.stats['current_difficulty'],
            "address": Config.ADDRESS
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "mining": mining_engine.is_mining,
            "database": True,
            "quantum": quantum_engine.estimator is not None,
            "ipfs": ipfs_manager.client is not None
        }
    
    @app.get("/info")
    async def node_info():
        """Detailed node information"""
        height = db_manager.get_current_height()
        supply = db_manager.get_total_supply()
        
        return {
            "node": {
                "version": "1.0.0",
                "address": Config.ADDRESS,
                "uptime": mining_engine.stats.get('uptime', 0)
            },
            "blockchain": {
                "height": height,
                "total_supply": str(supply),
                "max_supply": str(Config.MAX_SUPPLY),
                "difficulty": mining_engine.stats['current_difficulty']
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
            }
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
    
    @app.get("/block/hash/{block_hash}")
    async def get_block_by_hash(block_hash: str):
        """Get block by hash"""
        # Note: Requires index on block_hash in database
        with db_manager.get_session() as session:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT height FROM blocks WHERE block_hash = :bh"),
                {'bh': block_hash}
            ).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Block not found")
            
            block = db_manager.get_block(result[0])
            return block.to_dict()
    
    @app.get("/chain/info")
    async def chain_info():
        """Get blockchain information"""
        height = db_manager.get_current_height()
        supply = db_manager.get_total_supply()
        
        return {
            "height": height,
            "total_supply": str(supply),
            "max_supply": str(Config.MAX_SUPPLY),
            "current_reward": str(consensus_engine.calculate_reward(height + 1, supply)),
            "next_halving": Config.HALVING_INTERVAL - (height % Config.HALVING_INTERVAL) if height >= 0 else Config.HALVING_INTERVAL,
            "difficulty": mining_engine.stats['current_difficulty'],
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
    
    # ========================================================================
    # TRANSACTION ENDPOINTS
    # ========================================================================
    
    @app.get("/tx/{txid}")
    async def get_transaction(txid: str):
        """Get transaction by ID"""
        with db_manager.get_session() as session:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT * FROM transactions WHERE txid = :txid"),
                {'txid': txid}
            ).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            import json
            return {
                "txid": result[0],
                "inputs": json.loads(result[1]) if isinstance(result[1], str) else result[1],
                "outputs": json.loads(result[2]) if isinstance(result[2], str) else result[2],
                "fee": str(result[3]),
                "signature": result[4],
                "public_key": result[5],
                "timestamp": result[6],
                "status": result[7],
                "block_height": result[8] if len(result) > 8 else None
            }
    
    @app.get("/mempool")
    async def get_mempool():
        """Get mempool transactions"""
        pending = db_manager.get_pending_transactions()
        
        total_fees = sum(tx.fee for tx in pending)
        
        return {
            "size": len(pending),
            "total_fees": str(total_fees),
            "transactions": [tx.to_dict() for tx in pending[:20]]  # First 20
        }
    
    @app.post("/tx/broadcast")
    async def broadcast_transaction(request: Request):
        """Broadcast transaction to network"""
        data = await request.json()
        
        # TODO: Implement transaction creation and validation
        # This requires UTXO selection and signature creation
        
        raise HTTPException(
            status_code=501,
            detail="Transaction broadcasting not yet implemented. Use /tx/create first."
        )
    
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
            "current_difficulty": mining_engine.stats['current_difficulty'],
            "success_rate": mining_engine.stats['blocks_found'] / max(1, mining_engine.stats['total_attempts']),
            "hashrate_equivalent": mining_engine.stats['total_attempts'] / max(1, time.time())  # Simplified
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
    # QUANTUM ENDPOINTS
    # ========================================================================
    
    @app.get("/quantum/info")
    async def quantum_info():
        """Get quantum backend information"""
        return {
            "mode": "local" if Config.USE_LOCAL_ESTIMATOR else "ibm",
            "backend": quantum_engine.backend.name if quantum_engine.backend else "StatevectorEstimator",
            "vqe_maxiter": Config.VQE_MAXITER,
            "circuit_depth": quantum_engine.estimate_circuit_depth()
        }
    
    @app.post("/quantum/verify_proof")
    async def verify_proof(request: Request):
        """Verify a quantum proof"""
        data = await request.json()
        
        import numpy as np
        
        valid, reason = quantum_engine.validate_proof(
            params=np.array(data['params']),
            hamiltonian=data['hamiltonian'],
            claimed_energy=data['energy'],
            difficulty=data.get('difficulty', Config.INITIAL_DIFFICULTY)
        )
        
        return {
            "valid": valid,
            "reason": reason
        }
    
    # ========================================================================
    # RESEARCH ENDPOINTS
    # ========================================================================
    
    @app.get("/research/hamiltonians")
    async def get_hamiltonians(limit: int = 10):
        """Get solved Hamiltonians for research"""
        with db_manager.get_session() as session:
            from sqlalchemy import text
            results = session.execute(
                text("""
                    SELECT hamiltonian, params, energy, block_height, created_at
                    FROM solved_hamiltonians
                    ORDER BY block_height DESC
                    LIMIT :limit
                """),
                {'limit': limit}
            )
            
            import json
            hamiltonians = []
            for row in results:
                hamiltonians.append({
                    "hamiltonian": json.loads(row[0]) if isinstance(row[0], str) else row[0],
                    "params": json.loads(row[1]) if isinstance(row[1], str) else row[1],
                    "energy": row[2],
                    "block_height": row[3],
                    "timestamp": row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]
                })
            
            return {
                "count": len(hamiltonians),
                "hamiltonians": hamiltonians
            }
    
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
    # STORAGE ENDPOINTS
    # ========================================================================
    
    @app.get("/ipfs/snapshots")
    async def list_snapshots():
        """List IPFS snapshots"""
        with db_manager.get_session() as session:
            from sqlalchemy import text
            results = session.execute(
                text("""
                    SELECT cid, block_height, chain_hash, created_at
                    FROM ipfs_snapshots
                    ORDER BY block_height DESC
                    LIMIT 10
                """)
            )
            
            snapshots = []
            for row in results:
                snapshots.append({
                    "cid": row[0],
                    "block_height": row[1],
                    "chain_hash": row[2],
                    "created_at": row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3]
                })
            
            return {
                "count": len(snapshots),
                "snapshots": snapshots
            }
    
    logger.info("✓ RPC endpoints configured")
    
    return app
