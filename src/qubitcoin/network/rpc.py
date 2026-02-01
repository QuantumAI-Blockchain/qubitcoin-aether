"""
RPC API endpoints for Qubitcoin node v2.0
FastAPI-based HTTP interface with smart contract support
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
                   quantum_engine, ipfs_manager, contract_engine=None) -> FastAPI:
    """
    Create FastAPI application with all endpoints including smart contracts

    Args:
        db_manager: Database manager instance
        consensus_engine: Consensus engine instance
        mining_engine: Mining engine instance
        quantum_engine: Quantum engine instance
        ipfs_manager: IPFS manager instance
        contract_engine: Smart contract engine instance (optional for v1 compatibility)

    Returns:
        Configured FastAPI app
    """

    app = FastAPI(
        title="Qubitcoin Node RPC v2.0",
        version="2.0.0",
        description="Quantum-secured L1 blockchain with smart contracts"
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
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except:
            emission_stats = {}
        
        return {
            "node": "Qubitcoin Full Node v2.0",
            "version": "2.0.0",
            "network": "mainnet",
            "height": db_manager.get_current_height(),
            "difficulty": mining_engine.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "address": Config.ADDRESS,
            "economics": {
                "model": "Golden Ratio (φ = 1.618...)",
                "current_reward": emission_stats.get('current_reward', 50.0),
                "era": emission_stats.get('current_era', 0),
                "supply": emission_stats.get('total_supply', 0),
                "supply_cap": emission_stats.get('supply_cap', float(Config.TOTAL_SUPPLY)),
                "percent_emitted": f"{emission_stats.get('percent_emitted', 0):.2f}%"
            },
            "features": {
                "smart_contracts": contract_engine is not None,
                "quantum_proofs": True,
                "post_quantum_crypto": "Dilithium2",
                "consensus": "Proof-of-SUSY-Alignment"
            }
        }

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "mining": mining_engine.is_mining,
            "database": True,
            "quantum": quantum_engine.estimator is not None,
            "ipfs": ipfs_manager.client is not None,
            "contracts": contract_engine is not None
        }

    @app.get("/info")
    async def node_info():
        """Detailed node information"""
        height = db_manager.get_current_height()
        supply = db_manager.get_total_supply()
        
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except:
            emission_stats = {
                'current_height': height,
                'total_supply': float(supply),
                'supply_cap': float(Config.TOTAL_SUPPLY)
            }

        return {
            "node": {
                "version": "2.0.0",
                "address": Config.ADDRESS,
                "uptime": mining_engine.stats.get('uptime', 0)
            },
            "blockchain": {
                "height": height,
                "total_supply": str(supply),
                "max_supply": str(Config.TOTAL_SUPPLY),
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

    @app.get("/chain/info")
    async def chain_info():
        """Get blockchain information"""
        try:
            emission_stats = consensus_engine.get_emission_stats(db_manager)
        except:
            height = db_manager.get_current_height()
            supply = db_manager.get_total_supply()
            emission_stats = {
                'current_height': height,
                'total_supply': float(supply),
                'supply_cap': float(Config.TOTAL_SUPPLY),
                'current_reward': 50.0,
                'current_era': 0,
                'percent_emitted': float(supply / Config.TOTAL_SUPPLY * 100) if Config.TOTAL_SUPPLY > 0 else 0,
                'blocks_until_halving': Config.HALVING_INTERVAL,
                'hours_until_halving': (Config.HALVING_INTERVAL * Config.TARGET_BLOCK_TIME) / 3600
            }

        return {
            "height": emission_stats['current_height'],
            "total_supply": str(emission_stats['total_supply']),
            "max_supply": str(Config.TOTAL_SUPPLY),
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
            return Config.estimate_emission_schedule(years)
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
    # METRICS ENDPOINT
    # ========================================================================

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    logger.info("✓ RPC endpoints configured (v2.0)")

    return app
