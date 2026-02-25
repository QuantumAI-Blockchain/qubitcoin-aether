"""
RPC API endpoints for Qubitcoin node v2.0
FastAPI-based HTTP interface with smart contract support
NOW WITH P2P ENDPOINTS!
"""

import json
from typing import Dict, Optional
from decimal import Decimal

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response

from ..config import Config
from ..utils.logger import get_logger
from ..utils.metrics import generate_latest, CONTENT_TYPE_LATEST, setup_metrics

logger = get_logger(__name__)


def create_rpc_app(db_manager, consensus_engine, mining_engine,
                   quantum_engine, ipfs_manager, contract_engine=None,
                   state_manager=None, aether_engine=None,
                   llm_manager=None, pot_protocol=None,
                   # New subsystem instances (all optional, backward-compatible)
                   fee_collector=None, qusd_oracle=None,
                   compliance_engine=None, aml_monitor=None,
                   compliance_proof_store=None, tlac_manager=None,
                   risk_normalizer=None, plugin_manager=None,
                   decoherence_manager=None, transaction_batcher=None,
                   state_channel_manager=None, qvm_debugger=None,
                   qsol_compiler=None, systemic_risk_model=None,
                   tx_graph=None,
                   stablecoin_engine=None, reserve_fee_router=None,
                   reserve_verifier=None, bridge_manager=None,
                   sephirot_manager=None, csf_transport=None,
                   pineal_orchestrator=None, safety_manager=None,
                   spv_verifier=None, ipfs_memory=None,
                   capability_advertiser=None,
                   on_chain_agi=None,
                   event_index=None,
                   abi_registry=None,
                   bridge_lp=None,
                   neural_reasoner=None) -> FastAPI:
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
        pot_protocol: ProofOfThoughtProtocol instance (optional)
        fee_collector: FeeCollector instance (optional)
        qusd_oracle: QUSDOracle instance (optional)
        compliance_engine: ComplianceEngine instance (optional)
        aml_monitor: AMLMonitor instance (optional)
        compliance_proof_store: ComplianceProofStore instance (optional)
        tlac_manager: TLACManager instance (optional)
        risk_normalizer: RiskNormalizer instance (optional)
        plugin_manager: PluginManager instance (optional)
        decoherence_manager: DecoherenceManager instance (optional)
        transaction_batcher: TransactionBatcher instance (optional)
        state_channel_manager: StateChannelManager instance (optional)
        qvm_debugger: QVMDebugger instance (optional)
        qsol_compiler: QSolCompiler instance (optional)
        systemic_risk_model: SystemicRiskModel instance (optional)
        tx_graph: TransactionGraph instance (optional)
        stablecoin_engine: StablecoinEngine instance (optional)
        reserve_fee_router: ReserveFeeRouter instance (optional)
        reserve_verifier: ReserveVerifier instance (optional)
        bridge_manager: BridgeManager instance (optional)
        sephirot_manager: SephirotManager instance (optional)
        csf_transport: CSFTransport instance (optional)
        pineal_orchestrator: PinealOrchestrator instance (optional)
        safety_manager: SafetyManager instance (optional)
        spv_verifier: SPVVerifier instance (optional)
        ipfs_memory: IPFSMemoryStore instance (optional)
        capability_advertiser: CapabilityAdvertiser instance (optional)

    Returns:
        Configured FastAPI app
    """

    app = FastAPI(
        title="Qubitcoin Node RPC v2.0",
        version="2.0.0",
        description="Quantum-secured L1 blockchain with smart contracts and P2P networking"
    )

    # Prometheus HTTP request instrumentation (latency, count, error rate)
    setup_metrics(app)

    # CORS middleware (restrict in production via QBC_CORS_ORIGINS env)
    import os
    _default_origins = 'http://localhost:3000,https://qbc.network,https://www.qbc.network'
    cors_origins = os.getenv('QBC_CORS_ORIGINS', _default_origins).split(',')
    cors_origins = [o.strip() for o in cors_origins if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
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
        qvm=state_manager, event_index=event_index
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
                "chain_id": Config.CHAIN_ID,
                "bridge": bridge_manager is not None,
                "stablecoin": stablecoin_engine is not None,
                "compliance": compliance_engine is not None or _compliance_engine is not None,
                "plugins": plugin_manager is not None,
                "cognitive_architecture": sephirot_manager is not None,
                "privacy": True,
                "fee_collector": fee_collector is not None,
                "spv_verifier": spv_verifier is not None,
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
            "p2p": p2p_status,
            "bridge": bridge_manager is not None,
            "stablecoin": stablecoin_engine is not None,
            "compliance": _compliance_engine is not None,
            "plugins": plugin_manager is not None,
            "cognitive": sephirot_manager is not None,
            "privacy": True,
            "fee_collector": fee_collector is not None,
            "spv_verifier": spv_verifier is not None,
        }

    @app.get("/health/subsystems")
    async def health_subsystems():
        """Detailed subsystem health with version and diagnostics."""
        subsystems = {}
        # Mining
        if mining_engine:
            stats = mining_engine.get_stats_snapshot()
            subsystems['mining'] = {
                'active': mining_engine.is_mining,
                'blocks_found': stats.get('blocks_found', 0),
                'uptime': stats.get('uptime', 0),
            }
        # Database
        try:
            height = db_manager.get_current_height()
            subsystems['database'] = {'active': True, 'height': height}
        except Exception:
            subsystems['database'] = {'active': False}
        # Quantum
        subsystems['quantum'] = {
            'active': quantum_engine.estimator is not None,
            'backend': getattr(quantum_engine, 'backend_type', 'unknown'),
        }
        # Aether Tree
        if aether_engine:
            subsystems['aether_tree'] = {
                'active': True,
                'phi': getattr(aether_engine, 'phi', 0.0),
                'knowledge_nodes': len(aether_engine.kg.nodes) if hasattr(aether_engine, 'kg') and aether_engine.kg else 0,
            }
        else:
            subsystems['aether_tree'] = {'active': False}
        # Bridge
        if bridge_manager:
            try:
                bridge_stats = await bridge_manager.get_all_stats()
                subsystems['bridge'] = {'active': True, 'chains': len(bridge_stats.get('chains', {}))}
            except Exception:
                subsystems['bridge'] = {'active': True, 'chains': 0}
        else:
            subsystems['bridge'] = {'active': False}
        # Stablecoin
        if stablecoin_engine:
            try:
                shealth = stablecoin_engine.get_system_health()
                subsystems['stablecoin'] = {
                    'active': True,
                    'total_qusd': float(shealth.get('total_qusd', 0)),
                }
            except Exception:
                subsystems['stablecoin'] = {'active': True}
        else:
            subsystems['stablecoin'] = {'active': False}
        # Compliance
        subsystems['compliance'] = {'active': _compliance_engine is not None}
        # Plugins
        if plugin_manager:
            subsystems['plugins'] = {
                'active': True,
                'count': len(plugin_manager.list_plugins()),
            }
        else:
            subsystems['plugins'] = {'active': False}
        # Cognitive
        subsystems['cognitive'] = {'active': sephirot_manager is not None}
        # QVM
        subsystems['qvm'] = {'active': state_manager is not None}
        # P2P
        p2p_active = False
        if hasattr(app, 'node'):
            node = app.node
            if hasattr(node, 'rust_p2p') and node.rust_p2p and node.rust_p2p.connected:
                p2p_active = True
            elif hasattr(node, 'p2p') and node.p2p:
                p2p_active = getattr(node.p2p, 'running', False)
        subsystems['p2p'] = {'active': p2p_active}

        active_count = sum(1 for s in subsystems.values() if s.get('active'))
        return {
            'subsystems': subsystems,
            'total': len(subsystems),
            'active': active_count,
            'healthy': active_count >= 3,  # mining + database + quantum = minimum viable
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
                "blocks_found": mining_engine.stats.get('blocks_found', 0),
                "total_attempts": mining_engine.stats.get('total_attempts', 0),
                "success_rate": mining_engine.stats.get('blocks_found', 0) / max(1, mining_engine.stats.get('total_attempts', 1))
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

    @app.get("/fee-estimate")
    async def fee_estimate():
        """Estimate transaction fee based on recent mempool and block data."""
        try:
            pending = db_manager.get_pending_transactions(limit=100)
            height = db_manager.get_current_height()

            # Average fee from pending transactions (or minimum fee as fallback)
            if pending:
                avg_fee = sum(float(tx.fee) for tx in pending) / len(pending)
                max_fee = max(float(tx.fee) for tx in pending)
                min_fee = min(float(tx.fee) for tx in pending)
            else:
                avg_fee = float(Config.MIN_FEE)
                max_fee = float(Config.MIN_FEE)
                min_fee = float(Config.MIN_FEE)

            return {
                'low': max(float(Config.MIN_FEE), min_fee),
                'medium': max(float(Config.MIN_FEE), avg_fee),
                'high': max(float(Config.MIN_FEE), max_fee * 1.5),
                'mempool_size': len(pending),
                'block_height': height,
                'min_fee': float(Config.MIN_FEE),
                'unit': 'QBC',
            }
        except Exception as e:
            logger.error(f"Error estimating fee: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/inflation")
    async def inflation_stats():
        """Get current inflation rate and supply metrics."""
        try:
            height = db_manager.get_current_height()
            supply = db_manager.get_total_supply()
            reward = consensus_engine.calculate_reward(max(0, height), supply)
            blocks_per_year = int(365.25 * 24 * 3600 / Config.TARGET_BLOCK_TIME)
            annual_emission = float(reward) * blocks_per_year
            inflation_rate = (annual_emission / float(supply) * 100) if float(supply) > 0 else float('inf')

            return {
                'current_height': height,
                'total_supply': float(supply),
                'max_supply': float(Config.MAX_SUPPLY),
                'current_block_reward': float(reward),
                'annual_emission_estimate': annual_emission,
                'inflation_rate_percent': round(inflation_rate, 4),
                'percent_emitted': round(float(supply) / float(Config.MAX_SUPPLY) * 100, 4) if Config.MAX_SUPPLY > 0 else 0,
                'blocks_per_year': blocks_per_year,
            }
        except Exception as e:
            logger.error(f"Error getting inflation stats: {e}")
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
        s = mining_engine.get_stats_snapshot()
        return {
            "is_mining": mining_engine.is_mining,
            "blocks_found": s.get('blocks_found', 0),
            "total_attempts": s.get('total_attempts', 0),
            "current_difficulty": s.get('current_difficulty', Config.INITIAL_DIFFICULTY),
            "success_rate": s.get('blocks_found', 0) / max(1, s.get('total_attempts', 1)),
            "best_energy": s.get('best_energy', None),
            "alignment_score": s.get('alignment_score', None),
            "total_fees_burned": s.get('total_burned', 0.0),
            "fee_burn_percentage": Config.FEE_BURN_PERCENTAGE,
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

        # Count contracts from BOTH tables (accounts = EVM bytecode, contracts = template)
        total_contracts = 0
        active_contracts = 0
        try:
            from sqlalchemy import text as sa_text
            with db_manager.get_session() as session:
                evm_count = session.execute(
                    sa_text("SELECT COUNT(*) FROM accounts WHERE code_hash != '' AND code_hash IS NOT NULL")
                ).scalar() or 0
                template_count = session.execute(
                    sa_text("SELECT COUNT(*) FROM contracts")
                ).scalar() or 0
                template_active = session.execute(
                    sa_text("SELECT COUNT(*) FROM contracts WHERE is_active = true")
                ).scalar() or 0
                total_contracts = evm_count + template_count
                active_contracts = evm_count + template_active
        except Exception as e:
            logger.debug(f"Could not count contracts: {e}")

        return {
            "status": "active",
            "total_opcodes": 155,
            "quantum_opcodes": 10,
            "total_contracts": total_contracts,
            "active_contracts": active_contracts,
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

    # ────────────────────────────────────────────────────────────────────
    # QVM TOKEN / NFT / EVENT / CALL ENDPOINTS
    # ────────────────────────────────────────────────────────────────────

    @app.get("/qvm/tokens/{address}")
    async def get_tokens_for_address(address: str):
        """Return list of QBC-20 tokens held by an address."""
        tokens: list = []
        try:
            from sqlalchemy import text as sa_text
            with db_manager.get_session() as session:
                # Try the token_balances table (populated by token indexer)
                rows = session.execute(
                    sa_text("""
                        SELECT tb.contract_address, tb.balance,
                               tc.token_name, tc.token_symbol, tc.decimals
                        FROM token_balances tb
                        LEFT JOIN token_contracts tc
                            ON tb.contract_address = tc.contract_address
                        WHERE tb.holder_address = :addr AND tb.balance > 0
                        ORDER BY tb.balance DESC
                    """),
                    {'addr': address}
                ).fetchall()
                for r in rows:
                    tokens.append({
                        "contract_address": r[0].hex() if isinstance(r[0], (bytes, memoryview)) else str(r[0]),
                        "balance": str(r[1]),
                        "name": r[2] or "Unknown",
                        "symbol": r[3] or "???",
                        "decimals": r[4] if r[4] is not None else 18,
                    })
        except Exception as e:
            logger.debug(f"Token balance query not available: {e}")
            # Table may not exist yet — return empty list gracefully
        return {
            "address": address,
            "tokens": tokens,
            "note": "Token indexer not active — list may be incomplete" if not tokens else None,
        }

    @app.get("/qvm/token/{address}")
    async def get_token_info(address: str):
        """Return token contract info (name, symbol, total_supply, decimals)."""
        try:
            from sqlalchemy import text as sa_text
            with db_manager.get_session() as session:
                row = session.execute(
                    sa_text("""
                        SELECT token_name, token_symbol, total_supply, decimals,
                               token_standard, total_holders, total_transfers,
                               is_mintable, is_burnable, is_pausable
                        FROM token_contracts
                        WHERE contract_address = :addr
                    """),
                    {'addr': address}
                ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Token contract not found")
            return {
                "address": address,
                "name": row[0],
                "symbol": row[1],
                "total_supply": str(row[2]),
                "decimals": row[3],
                "standard": row[4],
                "total_holders": row[5],
                "total_transfers": row[6],
                "is_mintable": row[7],
                "is_burnable": row[8],
                "is_pausable": row[9],
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Token info query failed: {e}")
            raise HTTPException(status_code=404, detail="Token contract not found or token indexer not available")

    class TokenTransferRequest(BaseModel):
        token_address: str
        to_address: str
        amount: str
        from_address: str

    @app.post("/qvm/token/transfer")
    async def transfer_token(req: TokenTransferRequest):
        """Transfer QBC-20 tokens between addresses."""
        if not state_manager:
            raise HTTPException(status_code=503, detail="QVM not available")

        # Build ERC-20 transfer(address,uint256) calldata
        # Function selector: keccak256("transfer(address,uint256)")[:4] = 0xa9059cbb
        import hashlib as _hl
        try:
            to_padded = req.to_address.replace('0x', '').lower().zfill(64)
            amount_int = int(req.amount)
            amount_padded = hex(amount_int)[2:].zfill(64)
            calldata_hex = "a9059cbb" + to_padded + amount_padded
            calldata = bytes.fromhex(calldata_hex)
        except (ValueError, OverflowError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid transfer parameters: {e}")

        # Execute the call via QVM
        try:
            code_hex = db_manager.get_contract_bytecode(req.token_address)
            if not code_hex:
                raise HTTPException(status_code=404, detail="Token contract not found")
            code = bytes.fromhex(code_hex)

            result = state_manager.qvm.execute(
                caller=req.from_address,
                address=req.token_address,
                code=code,
                data=calldata,
                value=0,
                gas=Config.BLOCK_GAS_LIMIT,
                origin=req.from_address,
            )
            if not result.success:
                raise HTTPException(status_code=400, detail=f"Transfer failed: {result.revert_reason or 'execution reverted'}")

            # Generate a pseudo tx hash from the call
            tx_hash = _hl.sha256(
                f"{req.from_address}:{req.token_address}:{req.to_address}:{req.amount}:{id(result)}".encode()
            ).hexdigest()

            return {
                "success": True,
                "tx_hash": tx_hash,
                "from": req.from_address,
                "to": req.to_address,
                "token": req.token_address,
                "amount": req.amount,
                "gas_used": result.gas_used,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token transfer error: {e}")
            raise HTTPException(status_code=500, detail=f"Transfer execution error: {str(e)}")

    @app.get("/qvm/nfts/{address}")
    async def get_nfts_for_address(address: str):
        """Return NFTs (QBC-721) owned by an address."""
        nfts: list = []
        try:
            from sqlalchemy import text as sa_text
            with db_manager.get_session() as session:
                rows = session.execute(
                    sa_text("""
                        SELECT tb.contract_address, tb.token_id, tb.metadata,
                               tc.token_name, tc.token_symbol
                        FROM token_balances tb
                        LEFT JOIN token_contracts tc
                            ON tb.contract_address = tc.contract_address
                        WHERE tb.holder_address = :addr
                          AND tc.token_standard = 'QRC721'
                        ORDER BY tb.contract_address, tb.token_id
                    """),
                    {'addr': address}
                ).fetchall()
                for r in rows:
                    nfts.append({
                        "token_address": r[0].hex() if isinstance(r[0], (bytes, memoryview)) else str(r[0]),
                        "token_id": str(r[1]),
                        "metadata": r[2] if r[2] else {},
                        "collection_name": r[3] or "Unknown",
                        "collection_symbol": r[4] or "???",
                    })
        except Exception as e:
            logger.debug(f"NFT query not available: {e}")
            # Table may not exist yet — return empty list gracefully
        return {
            "address": address,
            "nfts": nfts,
            "total": len(nfts),
            "note": "NFT indexer not active — list may be incomplete" if not nfts else None,
        }

    @app.get("/qvm/events/{address}")
    async def get_contract_events(address: str, limit: int = 50, offset: int = 0):
        """Return event logs emitted by a contract."""
        limit = max(1, min(limit, 200))
        events: list = []
        total = 0
        try:
            from sqlalchemy import text as sa_text
            with db_manager.get_session() as session:
                total = session.execute(
                    sa_text("SELECT COUNT(*) FROM contract_logs WHERE contract_address = :addr"),
                    {'addr': address}
                ).scalar() or 0
                rows = session.execute(
                    sa_text("""
                        SELECT log_id, execution_id, tx_hash, block_height,
                               log_index, topic0, topic1, topic2, topic3,
                               data, event_name, decoded_data, timestamp
                        FROM contract_logs
                        WHERE contract_address = :addr
                        ORDER BY block_height DESC, log_index DESC
                        LIMIT :lim OFFSET :off
                    """),
                    {'addr': address, 'lim': limit, 'off': offset}
                ).fetchall()
                for r in rows:
                    events.append({
                        "log_id": str(r[0]),
                        "execution_id": str(r[1]),
                        "tx_hash": r[2].hex() if isinstance(r[2], (bytes, memoryview)) else str(r[2]),
                        "block_height": r[3],
                        "log_index": r[4],
                        "topic0": r[5].hex() if isinstance(r[5], (bytes, memoryview)) else str(r[5]) if r[5] else None,
                        "topic1": r[6].hex() if isinstance(r[6], (bytes, memoryview)) else str(r[6]) if r[6] else None,
                        "topic2": r[7].hex() if isinstance(r[7], (bytes, memoryview)) else str(r[7]) if r[7] else None,
                        "topic3": r[8].hex() if isinstance(r[8], (bytes, memoryview)) else str(r[8]) if r[8] else None,
                        "data": r[9].hex() if isinstance(r[9], (bytes, memoryview)) else str(r[9]) if r[9] else "",
                        "event_name": r[10],
                        "decoded_data": r[11],
                        "timestamp": str(r[12]) if r[12] else None,
                    })
        except Exception as e:
            logger.debug(f"Event log query not available: {e}")
            # Table may not exist yet — return empty list gracefully
        return {
            "address": address,
            "events": events,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    class ContractCallRequest(BaseModel):
        contract_address: str
        calldata: str
        from_address: Optional[str] = None

    @app.post("/qvm/call")
    async def qvm_static_call(req: ContractCallRequest):
        """Execute a read-only (static) contract call."""
        if not state_manager:
            raise HTTPException(status_code=503, detail="QVM not available")

        try:
            calldata_hex = req.calldata.replace('0x', '')
            calldata_bytes = bytes.fromhex(calldata_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid calldata hex")

        caller = req.from_address or ('0' * 40)
        try:
            result_bytes = state_manager.qvm.static_call(
                caller=caller,
                address=req.contract_address,
                data=calldata_bytes,
            )
            return {
                "success": True,
                "result": '0x' + result_bytes.hex() if result_bytes else '0x',
                "contract_address": req.contract_address,
            }
        except Exception as e:
            logger.error(f"Static call error: {e}")
            raise HTTPException(status_code=500, detail=f"Call execution error: {str(e)}")

    # ────────────────────────────────────────────────────────────────────

    class DeployRequest(BaseModel):
        contract_type: str
        contract_code: dict
        deployer: str

    @app.post("/contracts/deploy")
    async def deploy_contract(req: DeployRequest):
        """Deploy a smart contract via ContractExecutor (template contracts)."""
        if not contract_engine:
            raise HTTPException(status_code=503, detail="Contract engine not available")

        # Deduct deployment fee before deploying
        fee_record = None
        if fee_collector and req.deployer:
            from ..contracts.fee_calculator import ContractFeeCalculator
            import json as _json
            calc = ContractFeeCalculator()
            code_size = len(_json.dumps(req.contract_code).encode())
            deploy_fee = calc.calculate_deploy_fee(code_size, is_template=False)
            if deploy_fee > 0:
                success, fee_msg, fee_record = fee_collector.collect_fee(
                    payer_address=req.deployer,
                    fee_amount=deploy_fee,
                    fee_type='contract_deploy',
                )
                if not success:
                    raise HTTPException(status_code=402, detail=f"Deployment fee failed: {fee_msg}")

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
            "fee_paid": str(fee_record.fee_amount) if fee_record else "0",
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
        raw = aether_engine.phi.get_history(limit)
        # Wrap in envelope and include frontend-expected field names
        return {
            'history': [
                {
                    'block': entry.get('block_height', 0),
                    'phi': entry.get('phi_value', 0),
                    'phi_value': entry.get('phi_value', 0),
                    'phi_threshold': entry.get('phi_threshold', 3.0),
                    'integration_score': entry.get('integration_score', 0),
                    'differentiation_score': entry.get('differentiation_score', 0),
                    'block_height': entry.get('block_height', 0),
                }
                for entry in raw
            ]
        }

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
        # v2+ gate data (post-fork)
        if phi_data.get('phi_version', 0) >= 2:
            result['phi_raw'] = phi_data.get('phi_raw', 0.0)
            result['phi_version'] = phi_data.get('phi_version', 3)
            result['gates_passed'] = phi_data.get('gates_passed', 0)
            result['gates_total'] = phi_data.get('gates_total', 10)
            result['gate_ceiling'] = phi_data.get('gate_ceiling', 0.0)
            result['gates'] = phi_data.get('gates', [])
            result['connectivity'] = phi_data.get('connectivity', 0.0)
            result['maturity'] = phi_data.get('maturity', 0.0)
            result['redundancy_factor'] = phi_data.get('redundancy_factor', 1.0)
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
            'phi_version': phi_data.get('phi_version', 3),
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

    @app.get("/aether/circadian")
    async def aether_circadian():
        """Get current circadian phase and metabolic status."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        status = aether_engine.get_circadian_status()
        if status is None:
            return {"phase": "waking", "metabolic_rate": 1.0, "note": "Pineal not active"}
        return status

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
        if limit > Config.RPC_GRAPH_MAX_NODES:
            limit = Config.RPC_GRAPH_MAX_NODES
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
        if limit > Config.RPC_SEARCH_MAX_RESULTS:
            limit = Config.RPC_SEARCH_MAX_RESULTS
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
        if limit > Config.RPC_JSONLD_MAX_NODES:
            limit = Config.RPC_JSONLD_MAX_NODES
        return aether_engine.kg.export_json_ld(limit=limit)

    @app.get("/aether/phi/timeseries")
    async def phi_timeseries(limit: int = 100):
        """Get Phi value time series for visualization (charts/graphs)."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        dashboard = _get_dashboard()
        if limit < 1:
            limit = 1
        if limit > Config.RPC_PHI_HISTORY_MAX:
            limit = Config.RPC_PHI_HISTORY_MAX
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

    # Eagerly initialized consciousness dashboard (shared across requests)
    from ..aether.consciousness import ConsciousnessDashboard
    _consciousness_dashboard = ConsciousnessDashboard()
    app.consciousness_dashboard = _consciousness_dashboard  # type: ignore[attr-defined]

    def _get_dashboard():
        """Get the ConsciousnessDashboard instance."""
        return _consciousness_dashboard

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
            result = {}
            if hasattr(aether_engine, 'sephirot') and aether_engine.sephirot:
                for role, node in aether_engine.sephirot.items():
                    result[role.value] = node.get_status()
            else:
                # Fallback: return static status from SephirotManager
                from ..aether.sephirot import SephirotManager
                mgr = SephirotManager(db_manager)
                result = mgr.get_status()
            # Ensure frontend-expected fields are always present
            result.setdefault('susy_pairs', [
                {'expansion': 'chesed', 'constraint': 'gevurah', 'ratio': 1.618, 'target_ratio': 1.618},
                {'expansion': 'chochmah', 'constraint': 'binah', 'ratio': 1.618, 'target_ratio': 1.618},
                {'expansion': 'netzach', 'constraint': 'hod', 'ratio': 1.618, 'target_ratio': 1.618},
            ])
            result.setdefault('coherence', 0.0)
            result.setdefault('total_violations', 0)
            return result
        except Exception as e:
            logger.debug(f"Sephirot status error: {e}")
            raise HTTPException(status_code=500, detail="Failed to get Sephirot status")

    # ========================================================================
    # ON-CHAIN AGI ENDPOINTS (Phase 6)
    # ========================================================================

    @app.get("/aether/on-chain/phi")
    async def onchain_phi():
        """Read the current Phi value from the on-chain ConsciousnessDashboard."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        phi = on_chain_agi.get_onchain_phi()
        return {"phi": phi, "source": "on-chain"}

    @app.get("/aether/on-chain/consciousness")
    async def onchain_consciousness():
        """Read full consciousness status from the on-chain dashboard."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        status = on_chain_agi.get_onchain_consciousness_status()
        if status is None:
            return {"status": None, "reason": "Contract not deployed or no data"}
        return status

    @app.get("/aether/on-chain/proof/{block_height}")
    async def onchain_proof(block_height: int):
        """Check if a block has an on-chain Proof-of-Thought."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        proof_id = on_chain_agi.get_proof_by_block(block_height)
        return {"block_height": block_height, "proof_id": proof_id, "exists": proof_id is not None}

    @app.get("/aether/on-chain/constitution")
    async def onchain_constitution():
        """Get constitutional AI principle counts."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        total, active = on_chain_agi.get_principle_count()
        return {"total_principles": total, "active_principles": active}

    @app.get("/aether/on-chain/stats")
    async def onchain_stats():
        """Get on-chain AGI integration statistics."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        return on_chain_agi.get_stats()

    @app.get("/governance/treasury/balance")
    async def governance_treasury_balance():
        """Get TreasuryDAO balance from on-chain contract."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        balance = on_chain_agi.get_treasury_balance()
        return {"balance": balance, "source": "on-chain"}

    @app.get("/governance/proposals/count")
    async def governance_proposal_count():
        """Get governance proposal counts from on-chain contracts."""
        if not on_chain_agi:
            raise HTTPException(status_code=503, detail="On-chain AGI not available")
        treasury_count = on_chain_agi.get_proposal_count()
        upgrade_count = on_chain_agi.get_upgrade_proposal_count()
        return {
            "treasury_proposals": treasury_count,
            "upgrade_proposals": upgrade_count,
        }

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
            fee_mgr = AetherFeeManager(oracle_provider=qusd_oracle)
            _chat_state['fee_mgr'] = fee_mgr
            _chat_state['chat'] = AetherChat(
                aether_engine, db_manager, fee_mgr,
                llm_manager=llm_manager,
                fee_collector=fee_collector,
            )
        return _chat_state['chat'], _chat_state['fee_mgr']

    @app.post("/aether/chat/session")
    async def create_chat_session(request: Request):
        """Create a new Aether chat session."""
        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether Tree not available")
        # Accept user_address from JSON body or query param
        user_address = ''
        try:
            body = await request.json()
            user_address = body.get('user_address', '')
        except Exception:
            pass
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

    @app.post("/aether/llm/seed")
    async def trigger_seed(domain: Optional[str] = None):
        """Trigger a manual knowledge seed. Optionally specify a domain."""
        node = getattr(app, 'node', None)
        if not node or not getattr(node, 'knowledge_seeder', None):
            raise HTTPException(status_code=503, detail="Knowledge seeder not available")
        result = node.knowledge_seeder.seed_once(domain)
        if result:
            return {"status": "ok", **result}
        return {"status": "skipped", "reason": "rate limited or no prompt available"}

    @app.post("/aether/llm/seed-batch")
    async def trigger_seed_batch(count: int = 10):
        """Trigger multiple seeds in sequence. Max 50."""
        import asyncio
        node = getattr(app, 'node', None)
        if not node or not getattr(node, 'knowledge_seeder', None):
            raise HTTPException(status_code=503, detail="Knowledge seeder not available")
        count = min(count, 50)
        results = []
        for i in range(count):
            result = node.knowledge_seeder.seed_once()
            if result:
                results.append(result)
            await asyncio.sleep(0.1)  # yield to event loop
        return {"seeded": len(results), "total_requested": count, "results": results}

    # ---- User-driven LLM knowledge seeding (user provides their own API key) ----

    class UserSeedRequest(BaseModel):
        wallet_address: str
        api_key: str
        prompt: str
        model: str = "gpt-4"
        max_tokens: int = 1024

    @app.post("/aether/llm/seed-user")
    async def seed_user_knowledge(req: UserSeedRequest):
        """Seed knowledge graph using the caller's own OpenAI API key.

        The API key is used for a single request and immediately discarded.
        It is never logged or persisted server-side.
        """
        import time as _time

        if not aether_engine:
            raise HTTPException(status_code=503, detail="Aether engine not available")

        # Validate inputs
        if not req.api_key.startswith("sk-"):
            raise HTTPException(status_code=400, detail="Invalid API key format")
        if len(req.prompt.strip()) < 10:
            raise HTTPException(status_code=400, detail="Prompt must be at least 10 characters")
        if req.max_tokens < 64 or req.max_tokens > 4096:
            raise HTTPException(status_code=400, detail="max_tokens must be between 64 and 4096")

        try:
            from ..aether.llm_adapter import OpenAIAdapter, KnowledgeDistiller

            # Create a temporary adapter — key lives only in this scope
            adapter = OpenAIAdapter(
                api_key=req.api_key,
                model=req.model,
                max_tokens=req.max_tokens,
            )

            t0 = _time.monotonic()
            llm_response = adapter.generate(prompt=req.prompt)
            latency_ms = (_time.monotonic() - t0) * 1000

            if not llm_response.content:
                raise HTTPException(status_code=502, detail="LLM returned empty response")

            # Distill into knowledge graph
            distiller = KnowledgeDistiller(knowledge_graph=aether_engine.kg)
            current_height = db_manager.get_current_height()
            node_ids = distiller.distill(
                llm_response=llm_response,
                query=req.prompt,
                block_height=current_height,
            )

            # Recalculate Phi after new nodes
            phi_after = aether_engine.phi

            return {
                "status": "ok",
                "nodes_created": len(node_ids),
                "node_ids": node_ids,
                "tokens_used": llm_response.tokens_used,
                "model": llm_response.model,
                "latency_ms": round(latency_ms, 1),
                "knowledge_nodes": len(aether_engine.kg.nodes),
                "phi_after": phi_after,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("User seed failed: %s", str(e))
            raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")

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
        utxo_strategy: str = 'largest_first'  # largest_first | smallest_first | exact_match

    @app.post("/wallet/send")
    async def wallet_send(req: WalletSendRequest):
        """Send QBC from a native Dilithium wallet."""
        import hashlib
        import time as _time
        from ..quantum.crypto import Dilithium2

        amount = Decimal(req.amount)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        strategy = req.utxo_strategy
        if strategy not in ('largest_first', 'smallest_first', 'exact_match'):
            raise HTTPException(status_code=400, detail="Invalid utxo_strategy. Must be: largest_first, smallest_first, exact_match")

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

        # Select UTXOs using requested strategy
        utxos = db_manager.get_utxos(req.from_address)

        if strategy == 'exact_match':
            # Try to find a single UTXO that exactly covers the amount
            exact = [u for u in utxos if u.amount == amount]
            if exact:
                selected = [exact[0]]
                total = exact[0].amount
            else:
                # Fall back to smallest_first
                strategy = 'smallest_first'

        if strategy == 'smallest_first':
            utxos.sort(key=lambda u: u.amount)
        elif strategy == 'largest_first':
            utxos.sort(key=lambda u: u.amount, reverse=True)

        if strategy != 'exact_match':
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

    def _sync_stake_energy(node_id: int) -> None:
        """Sync a Sephirot node's qbc_stake and energy from DB stake totals.

        Reads the total stake for the node, updates the in-memory SephirahState,
        recomputes energy using log-diminishing returns, and enforces SUSY balance.
        """
        import math
        if not aether_engine or not aether_engine._sephirot:
            return
        try:
            from ..aether.sephirot import SephirahRole
            role_map = {i: role for i, role in enumerate(SephirahRole)}
            role = role_map.get(node_id)
            if not role:
                return
            node = aether_engine._sephirot.get(role)
            if not node:
                return
            total_stake = float(db_manager.get_node_total_stake(node_id))
            node.state.qbc_stake = total_stake
            factor = Config.SEPHIROT_STAKE_ENERGY_FACTOR
            node.state.energy = 1.0 + factor * math.log2(1.0 + total_stake / 100.0)
            # TODO: Wire SephirotManager.enforce_susy_balance() properly
            # Currently skipped — SephirotManager operates on SephirahState objects
            # while AetherEngine._sephirot contains BaseSephirah objects (different types)
        except Exception as e:
            logger.debug(f"Stake energy sync for node {node_id}: {e}")

    @app.get("/sephirot/nodes")
    async def get_sephirot_nodes():
        """Get all 10 Sephirot node definitions with staking and performance stats."""
        summary = db_manager.get_sephirot_summary()

        # Collect live performance metrics from AetherEngine sephirot
        perf_data: dict = {}
        if aether_engine and aether_engine._sephirot:
            total_weight = 0.0
            weights: dict = {}
            for role, node in aether_engine._sephirot.items():
                role_name = role.value if hasattr(role, 'value') else str(role)
                w = node.get_performance_weight()
                weights[role_name] = w
                total_weight += w
                perf_data[role_name] = {
                    'tasks_solved': node._tasks_solved,
                    'knowledge_contributed': node._knowledge_contributed,
                    'reasoning_ops': node.state.reasoning_ops,
                    'messages_processed': node.state.messages_processed,
                    'performance_weight': round(w, 2),
                }
            # Compute weighted APY per node
            if total_weight > 0:
                for role_name in perf_data:
                    share = weights[role_name] / total_weight
                    perf_data[role_name]['apy_weighted'] = round(5.0 * share * 10, 2)

        nodes = []
        for n in SEPHIROT_NODES:
            stats = summary.get(n['id'], {'staker_count': 0, 'total_staked': '0'})
            node_perf = perf_data.get(n['name'].lower(), {})
            nodes.append({
                **n,
                'current_stakers': stats['staker_count'],
                'total_staked': stats['total_staked'],
                'apy_estimate': node_perf.get('apy_weighted', 5.0),
                'performance': node_perf,
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

        # Stake cap A2: max stake per address on this node
        current_addr_stake = db_manager.get_address_stake_on_node(req.address, req.node_id)
        max_per_addr = Decimal(str(Config.SEPHIROT_MAX_STAKE_PER_ADDRESS))
        if current_addr_stake + amount > max_per_addr:
            remaining = max_per_addr - current_addr_stake
            raise HTTPException(
                status_code=400,
                detail=f"Exceeds per-address cap ({max_per_addr} QBC). "
                       f"Current: {current_addr_stake}, remaining capacity: {max(Decimal(0), remaining)}"
            )

        # Stake cap A1: max stake per node (absolute cap or share cap)
        node_total = db_manager.get_node_total_stake(req.node_id)
        total_all = db_manager.get_total_staked_all_nodes()
        absolute_cap = Decimal(str(Config.SEPHIROT_MAX_STAKE_PER_NODE))
        share_cap = total_all * Decimal(str(Config.SEPHIROT_NODE_MAX_SHARE)) if total_all > 0 else absolute_cap
        effective_cap = min(absolute_cap, share_cap) if share_cap > 0 else absolute_cap
        if node_total + amount > effective_cap:
            remaining = effective_cap - node_total
            raise HTTPException(
                status_code=400,
                detail=f"Exceeds node stake cap ({effective_cap:.0f} QBC). "
                       f"Current: {node_total}, remaining capacity: {max(Decimal(0), remaining)}"
            )

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
        _sync_stake_energy(req.node_id)
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

        _sync_stake_energy(stake['node_id'])

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
    # PROOF-OF-THOUGHT PROTOCOL
    # ========================================================================

    @app.get("/pot/stats")
    async def pot_stats():
        """Get Proof-of-Thought protocol statistics."""
        if not pot_protocol:
            return {"error": "PoT protocol not initialized", "task_market": {}, "validators": {}}
        return pot_protocol.get_stats()

    @app.get("/pot/tasks")
    async def pot_tasks(limit: int = 20):
        """Get open reasoning tasks."""
        if not pot_protocol:
            return {"tasks": []}
        tasks = pot_protocol.task_market.get_open_tasks(limit=limit)
        return {"tasks": [
            {
                "task_id": t.task_id,
                "submitter": t.submitter,
                "description": t.description,
                "query_type": t.query_type,
                "bounty_qbc": t.bounty_qbc,
                "status": t.status.value,
                "created_block": t.created_block,
            }
            for t in tasks
        ]}

    @app.get("/pot/task/{task_id}")
    async def pot_task_detail(task_id: str):
        """Get details of a specific reasoning task."""
        if not pot_protocol:
            raise HTTPException(status_code=503, detail="PoT protocol not initialized")
        task = pot_protocol.task_market.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "task_id": task.task_id,
            "submitter": task.submitter,
            "description": task.description,
            "query_type": task.query_type,
            "bounty_qbc": task.bounty_qbc,
            "status": task.status.value,
            "created_block": task.created_block,
            "claimed_by": task.claimed_by,
            "solution_hash": task.solution_hash,
            "votes": len(task.validation_votes),
            "reward_distributed": task.reward_distributed,
        }

    class SubmitTaskRequest(BaseModel):
        submitter: str
        description: str
        bounty_qbc: float
        query_type: str = "general"

    @app.post("/pot/submit-task")
    async def pot_submit_task(req: SubmitTaskRequest):
        """Submit a reasoning task with QBC bounty."""
        if not pot_protocol:
            raise HTTPException(status_code=503, detail="PoT protocol not initialized")
        block_height = db_manager.get_current_height()
        task = pot_protocol.task_market.submit_task(
            submitter=req.submitter,
            description=req.description,
            bounty_qbc=req.bounty_qbc,
            query_type=req.query_type,
            block_height=block_height,
        )
        if not task:
            raise HTTPException(status_code=400, detail="Task submission failed (check bounty minimum)")
        return {
            "task_id": task.task_id,
            "bounty_qbc": task.bounty_qbc,
            "status": task.status.value,
        }

    class ValidateRequest(BaseModel):
        task_id: str
        validator_address: str
        approve: bool

    @app.post("/pot/validate")
    async def pot_validate(req: ValidateRequest):
        """Submit a validation vote on a proposed solution."""
        if not pot_protocol:
            raise HTTPException(status_code=503, detail="PoT protocol not initialized")
        success = pot_protocol.validate_solution(
            req.task_id, req.validator_address, req.approve
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Validation failed (task not in validating state or validator not active)"
            )
        return {"task_id": req.task_id, "validator": req.validator_address, "approve": req.approve}

    @app.get("/pot/validators")
    async def pot_validators():
        """Get validator registry statistics."""
        if not pot_protocol:
            return {"validators": {}}
        return pot_protocol.validator_registry.get_stats()

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
        # Also notify eth_subscribe subscribers
        sub_type_map = {"new_block": "newHeads", "new_transaction": "pendingTransactions"}
        if event_type in sub_type_map:
            try:
                await notify_subscribers(sub_type_map[event_type], data)
            except Exception:
                pass

    # Attach broadcast helper to the app so node.py can call it
    app.broadcast_ws = broadcast_ws  # type: ignore[attr-defined]

    # ========================================================================
    # ETH SUBSCRIBE — JSON-RPC WebSocket subscriptions (newHeads, logs, pendingTransactions)
    # ========================================================================

    import uuid as _ws_uuid
    _eth_subscribers: Dict[str, Dict] = {}  # sub_id -> {ws, type, params}

    @app.websocket("/ws/jsonrpc")
    async def jsonrpc_ws_endpoint(websocket: WebSocket) -> None:
        """JSON-RPC over WebSocket with eth_subscribe/eth_unsubscribe support."""
        await websocket.accept()
        client_subs: list[str] = []
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except Exception:
                    await websocket.send_text(json.dumps({
                        "jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}
                    }))
                    continue

                method = msg.get("method", "")
                params = msg.get("params", [])
                req_id = msg.get("id", 1)

                if method == "eth_subscribe":
                    sub_type = params[0] if params else "newHeads"
                    sub_params = params[1] if len(params) > 1 else {}
                    sub_id = _ws_uuid.uuid4().hex[:16]
                    _eth_subscribers[sub_id] = {
                        "ws": websocket, "type": sub_type, "params": sub_params,
                    }
                    client_subs.append(sub_id)
                    await websocket.send_text(json.dumps({
                        "jsonrpc": "2.0", "id": req_id, "result": "0x" + sub_id,
                    }))
                elif method == "eth_unsubscribe":
                    sub_id = params[0].replace("0x", "") if params else ""
                    removed = sub_id in _eth_subscribers
                    if removed:
                        del _eth_subscribers[sub_id]
                        if sub_id in client_subs:
                            client_subs.remove(sub_id)
                    await websocket.send_text(json.dumps({
                        "jsonrpc": "2.0", "id": req_id, "result": removed,
                    }))
                else:
                    # Forward to regular JSON-RPC handler
                    from .jsonrpc import JsonRpcRequest
                    rpc_req = JsonRpcRequest(
                        jsonrpc="2.0", method=method, params=params, id=req_id,
                    )
                    rpc_resp = await jsonrpc_handler.handle(rpc_req)
                    await websocket.send_text(json.dumps({
                        "jsonrpc": "2.0", "id": req_id,
                        "result": rpc_resp.result, "error": rpc_resp.error,
                    }))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("jsonrpc WS client disconnected")
        finally:
            for sid in client_subs:
                _eth_subscribers.pop(sid, None)

    async def notify_subscribers(event_type: str, data: dict) -> None:
        """Send subscription notifications to matching subscribers."""
        dead: list[str] = []
        for sub_id, sub in _eth_subscribers.items():
            if sub["type"] != event_type:
                continue
            notification = json.dumps({
                "jsonrpc": "2.0", "method": "eth_subscription",
                "params": {"subscription": "0x" + sub_id, "result": data},
            })
            try:
                await sub["ws"].send_text(notification)
            except Exception:
                dead.append(sub_id)
        for sid in dead:
            _eth_subscribers.pop(sid, None)

    app.notify_subscribers = notify_subscribers  # type: ignore[attr-defined]

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

    # NOTE: Literal routes MUST be defined before parameterized routes
    # to avoid FastAPI matching "stats" as a {block_height} parameter.

    @app.get("/aether/pot/stats")
    async def get_pot_stats():
        """Get Proof-of-Thought explorer statistics."""
        return _pot_explorer.get_stats()

    @app.get("/aether/pot/phi-progression")
    async def get_phi_progression(limit: int = 100):
        """Get Phi value progression over recent blocks."""
        limit = max(1, min(limit, 1000))
        return {"progression": _pot_explorer.get_phi_progression(limit)}

    @app.get("/aether/pot/consciousness-events")
    async def get_pot_consciousness_events(limit: int = 50):
        """Get blocks where consciousness events occurred."""
        return {"events": _pot_explorer.get_consciousness_events(limit)}

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
        if end - start > Config.RPC_BLOCK_RANGE_MAX:
            raise HTTPException(status_code=400, detail=f"Range too large (max {Config.RPC_BLOCK_RANGE_MAX})")
        return {"blocks": _pot_explorer.get_block_range(start, end)}

    @app.get("/aether/pot/summary/{block_height}")
    async def get_reasoning_summary(block_height: int):
        """Get human-readable reasoning summary for a block."""
        return _pot_explorer.get_reasoning_summary(block_height)

    # ========================================================================
    # COMPLIANCE PROOFS
    # ========================================================================

    from ..qvm.compliance_proofs import ComplianceProofStore
    _proof_store = compliance_proof_store if compliance_proof_store is not None else ComplianceProofStore()
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

    # NOTE: Literal route MUST be before parameterized route to avoid
    # FastAPI matching "stats" as a {report_id} parameter.
    @app.get("/qvm/compliance/reports/stats")
    async def regulatory_report_stats():
        """Get report generator statistics."""
        return _report_gen.get_stats()

    @app.get("/qvm/compliance/reports/{report_id}")
    async def get_regulatory_report(report_id: str):
        """Get a specific regulatory report by ID."""
        report = _report_gen.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

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
    _compliance_engine = compliance_engine if compliance_engine is not None else ComplianceEngine(db_manager)

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
    _cap_advertiser = capability_advertiser if capability_advertiser is not None else CapabilityAdvertiser(node_peer_id=_node_peer_id)
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
    # BRIDGE ENDPOINTS
    # ========================================================================

    @app.get("/bridge/stats")
    async def bridge_stats():
        """Get bridge statistics across all chains."""
        if not bridge_manager:
            return {"error": "Bridge not available", "chains": [], "totals": {}}
        return await bridge_manager.get_all_stats()

    @app.get("/bridge/chains")
    async def bridge_chains():
        """Get list of supported bridge chains."""
        if not bridge_manager:
            return {"chains": []}
        return {"chains": await bridge_manager.get_supported_chains()}

    class BridgeDepositRequest(BaseModel):
        chain: str
        qbc_txid: str
        qbc_address: str
        target_address: str
        amount: str

    @app.post("/bridge/deposit")
    async def bridge_deposit(req: BridgeDepositRequest):
        """Initiate a bridge deposit (QBC → target chain)."""
        if not bridge_manager:
            raise HTTPException(status_code=503, detail="Bridge not available")
        from ..bridge.base import ChainType
        try:
            chain_type = ChainType(req.chain.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported chain: {req.chain}")

        # Deduct bridge fee before processing deposit
        fee_record = None
        amount = Decimal(req.amount)
        if fee_collector and req.qbc_address:
            bridge_fee_rate = Decimal('0.001')  # 0.1% bridge fee
            bridge_fee = amount * bridge_fee_rate
            if bridge_fee > 0:
                success, fee_msg, fee_record = fee_collector.collect_fee(
                    payer_address=req.qbc_address,
                    fee_amount=bridge_fee,
                    fee_type='bridge_deposit',
                )
                if not success:
                    raise HTTPException(status_code=402, detail=f"Bridge fee failed: {fee_msg}")

        tx_hash = await bridge_manager.process_deposit(
            chain_type, req.qbc_txid, req.qbc_address,
            req.target_address, amount,
        )
        if not tx_hash:
            raise HTTPException(status_code=500, detail="Deposit failed")
        return {
            "tx_hash": tx_hash,
            "chain": req.chain,
            "amount": req.amount,
            "fee_paid": str(fee_record.fee_amount) if fee_record else "0",
        }

    @app.get("/bridge/balance/{chain}/{address}")
    async def bridge_balance(chain: str, address: str):
        """Get wQBC balance on a target chain."""
        if not bridge_manager:
            raise HTTPException(status_code=503, detail="Bridge not available")
        from ..bridge.base import ChainType
        try:
            chain_type = ChainType(chain.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported chain: {chain}")
        balance = await bridge_manager.get_balance(chain_type, address)
        return {"chain": chain, "address": address, "balance": str(balance)}

    @app.get("/bridge/fees/{chain}/{amount}")
    async def bridge_fees(chain: str, amount: str):
        """Estimate bridge fees for a transfer."""
        if not bridge_manager:
            raise HTTPException(status_code=503, detail="Bridge not available")
        from ..bridge.base import ChainType
        try:
            chain_type = ChainType(chain.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported chain: {chain}")
        fees = await bridge_manager.estimate_fees(chain_type, Decimal(amount))
        return fees

    @app.post("/bridge/pause/{chain}")
    async def bridge_pause(chain: str):
        """Pause a specific bridge chain (admin)."""
        if not bridge_manager:
            raise HTTPException(status_code=503, detail="Bridge not available")
        from ..bridge.base import ChainType
        try:
            chain_type = ChainType(chain.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported chain: {chain}")
        await bridge_manager.pause_bridge(chain_type)
        return {"paused": True, "chain": chain}

    @app.post("/bridge/resume/{chain}")
    async def bridge_resume(chain: str):
        """Resume a paused bridge chain (admin)."""
        if not bridge_manager:
            raise HTTPException(status_code=503, detail="Bridge not available")
        from ..bridge.base import ChainType
        try:
            chain_type = ChainType(chain.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported chain: {chain}")
        await bridge_manager.resume_bridge(chain_type)
        return {"resumed": True, "chain": chain}

    @app.get("/bridge/validators/stats")
    async def bridge_validator_stats():
        """Get overall bridge validator reward statistics."""
        if not bridge_manager or not bridge_manager.validator_rewards:
            return {"total_validators": 0, "total_verifications": 0, "total_rewards_qbc": 0}
        return bridge_manager.validator_rewards.get_stats()

    @app.get("/bridge/validators/top")
    async def bridge_top_validators(limit: int = 10):
        """Get top bridge validators by verification count."""
        if not bridge_manager or not bridge_manager.validator_rewards:
            return {"validators": [], "total": 0}
        top = bridge_manager.validator_rewards.get_top_validators(limit=limit)
        return {"validators": top, "total": len(top)}

    @app.get("/bridge/validators/{validator}")
    async def bridge_validator_detail(validator: str):
        """Get verification stats for a specific bridge validator."""
        if not bridge_manager or not bridge_manager.validator_rewards:
            raise HTTPException(status_code=503, detail="Validator rewards not available")
        stats = bridge_manager.validator_rewards.get_validator_stats(validator)
        return stats

    @app.get("/bridge/validators/rewards/{bridge_name}")
    async def bridge_validator_rewards(bridge_name: str):
        """Get reward distribution for a specific bridge chain."""
        if not bridge_manager or not bridge_manager.validator_rewards:
            raise HTTPException(status_code=503, detail="Validator rewards not available")
        rewards = bridge_manager.validator_rewards.calculate_rewards(bridge_name=bridge_name)
        return {"bridge": bridge_name, "rewards": rewards, "total_validators": len(rewards)}

    # ========================================================================
    # PRIVACY ENDPOINTS
    # ========================================================================

    @app.post("/privacy/commitment/create")
    async def privacy_commitment_create(request: Request):
        """Create a Pedersen commitment for a value."""
        body = await request.json()
        value = int(body.get('value', 0))
        from ..privacy.commitments import PedersenCommitment
        commitment = PedersenCommitment.commit(value)
        return {"commitment": commitment.commitment.hex(), "blinding": commitment.blinding.hex()}

    @app.post("/privacy/commitment/verify")
    async def privacy_commitment_verify(request: Request):
        """Verify a Pedersen commitment."""
        body = await request.json()
        from ..privacy.commitments import PedersenCommitment
        valid = PedersenCommitment.verify(
            bytes.fromhex(body['commitment']),
            int(body['value']),
            bytes.fromhex(body['blinding']),
        )
        return {"valid": valid}

    @app.post("/privacy/range-proof/generate")
    async def privacy_range_proof_generate(request: Request):
        """Generate a Bulletproof range proof."""
        body = await request.json()
        value = int(body.get('value', 0))
        from ..privacy.range_proofs import RangeProofGenerator
        gen = RangeProofGenerator()
        proof = gen.generate(value)
        return {"proof": proof.to_dict() if hasattr(proof, 'to_dict') else str(proof)}

    @app.post("/privacy/range-proof/verify")
    async def privacy_range_proof_verify(request: Request):
        """Verify a Bulletproof range proof."""
        body = await request.json()
        from ..privacy.range_proofs import RangeProofGenerator
        gen = RangeProofGenerator()
        valid = gen.verify(body['proof'])
        return {"valid": valid}

    @app.post("/privacy/stealth/generate-keypair")
    async def privacy_stealth_keygen():
        """Generate a stealth address keypair (spend + view)."""
        from ..privacy.stealth import StealthAddressManager
        mgr = StealthAddressManager()
        keypair = mgr.generate_keypair()
        return keypair

    @app.post("/privacy/stealth/create-output")
    async def privacy_stealth_output(request: Request):
        """Create a stealth output for a recipient."""
        body = await request.json()
        from ..privacy.stealth import StealthAddressManager
        mgr = StealthAddressManager()
        output = mgr.create_output(
            recipient_spend_pub=body['recipient_spend_pub'],
            recipient_view_pub=body['recipient_view_pub'],
        )
        return output

    @app.post("/privacy/tx/build")
    async def privacy_tx_build(request: Request):
        """Build a confidential (Susy Swap) transaction."""
        body = await request.json()
        from ..privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        tx = builder.build(
            inputs=body.get('inputs', []),
            outputs=body.get('outputs', []),
            sender_address=body.get('sender_address', ''),
        )
        return tx

    # ========================================================================
    # PLUGIN ENDPOINTS
    # ========================================================================

    @app.get("/qvm/plugins")
    async def list_qvm_plugins():
        """List all registered QVM plugins."""
        if not plugin_manager:
            return {"plugins": []}
        return {"plugins": plugin_manager.list_plugins()}

    @app.get("/qvm/plugins/{name}")
    async def get_qvm_plugin(name: str):
        """Get details of a specific QVM plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not available")
        plugins = plugin_manager.list_plugins()
        match = [p for p in plugins if p.get('name') == name]
        if not match:
            raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
        return match[0]

    @app.post("/qvm/plugins/{name}/start")
    async def start_qvm_plugin(name: str):
        """Start a registered QVM plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not available")
        success = plugin_manager.start(name)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to start plugin '{name}'")
        return {"started": True, "name": name}

    @app.post("/qvm/plugins/{name}/stop")
    async def stop_qvm_plugin(name: str):
        """Stop a running QVM plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not available")
        success = plugin_manager.stop(name)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to stop plugin '{name}'")
        return {"stopped": True, "name": name}

    @app.get("/qvm/plugins/defi/stats")
    async def defi_plugin_stats():
        """Get DeFi plugin statistics (lending, DEX, staking)."""
        if not plugin_manager:
            return {"error": "Plugin manager not available"}
        plugins = plugin_manager.list_plugins()
        defi = [p for p in plugins if p.get('name') == 'DeFiPlugin']
        if not defi:
            return {"error": "DeFi plugin not registered"}
        return defi[0]

    @app.get("/qvm/plugins/governance/proposals")
    async def governance_proposals():
        """Get governance plugin proposals."""
        if not plugin_manager:
            return {"proposals": []}
        try:
            meta = plugin_manager.registry.get('GovernancePlugin')
            if meta and meta.instance:
                return {"proposals": [p.to_dict() for p in meta.instance.list_proposals()]}
        except Exception as e:
            logger.debug(f"Governance proposals: {e}")
        return {"proposals": []}

    @app.post("/qvm/plugins/governance/propose")
    async def governance_propose(request: Request):
        """Submit a governance proposal."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not available")
        body = await request.json()
        try:
            meta = plugin_manager.registry.get('GovernancePlugin')
            if not meta or not meta.instance:
                raise HTTPException(status_code=503, detail="Governance plugin not active")
            proposal = meta.instance.create_proposal(
                proposer=body.get('proposer', ''),
                description=body.get('description', ''),
                proposal_type=body.get('type', 'general'),
            )
            return proposal.to_dict() if hasattr(proposal, 'to_dict') else {"id": str(proposal)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/qvm/plugins/governance/vote")
    async def governance_vote(request: Request):
        """Vote on a governance proposal."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not available")
        body = await request.json()
        try:
            gov_plugin = plugin_manager.registry.get('governance')
            if not gov_plugin:
                raise HTTPException(status_code=503, detail="Governance plugin not active")
            # choice: 0=AGAINST, 1=FOR, 2=ABSTAIN
            approve = body.get('approve', True)
            choice = 1 if approve else 0
            vote_obj = gov_plugin.cast_vote(
                proposal_id=body.get('proposal_id', ''),
                voter=body.get('voter', ''),
                choice=choice,
                weight=body.get('weight', 1.0),
            )
            return {
                "voted": vote_obj is not None,
                "result": vote_obj.to_dict() if vote_obj else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ========================================================================
    # COMPLIANCE EXTENDED ENDPOINTS
    # ========================================================================

    @app.get("/qvm/compliance/aml/alerts")
    async def compliance_aml_alerts():
        """Get recent AML alerts."""
        if not aml_monitor:
            return {"alerts": []}
        try:
            alerts = aml_monitor.get_alerts()
            return {"alerts": [a.to_dict() if hasattr(a, 'to_dict') else a for a in alerts]}
        except Exception:
            return {"alerts": []}

    @app.get("/qvm/compliance/risk/{address}")
    async def compliance_risk_score(address: str):
        """Get normalized risk score for an address."""
        if not risk_normalizer:
            return {"address": address, "risk_score": 0.0, "error": "Risk normalizer not available"}
        try:
            score = risk_normalizer.normalize(address)
            return {"address": address, "risk_score": score}
        except Exception as e:
            return {"address": address, "risk_score": 0.0, "error": str(e)}

    @app.get("/qvm/compliance/tlac/transactions")
    async def compliance_tlac_transactions():
        """Get pending TLAC (Time-Locked Atomic Compliance) transactions."""
        if not tlac_manager:
            return {"transactions": []}
        try:
            pending = [
                t.to_dict() for t in tlac_manager._transactions.values()
                if not t.expired and not t.executed
            ]
            return {"transactions": pending}
        except Exception:
            return {"transactions": []}

    @app.post("/qvm/compliance/tlac/create")
    async def compliance_tlac_create(request: Request):
        """Create a new TLAC transaction."""
        if not tlac_manager:
            raise HTTPException(status_code=503, detail="TLAC manager not available")
        body = await request.json()
        try:
            result = tlac_manager.create(
                initiator=body.get('sender', ''),
                tx_data={
                    "recipient": body.get('recipient', ''),
                    "amount": body.get('amount', 0),
                },
                jurisdictions=body.get('jurisdictions', []),
                time_lock_blocks=body.get('timeout_blocks', 100),
                block_height=body.get('block_height', 0),
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/qvm/compliance/graph/{address}")
    async def compliance_tx_graph(address: str):
        """Get transaction graph analysis for an address."""
        if not tx_graph:
            return {"address": address, "graph": {}, "error": "Transaction graph not available"}
        try:
            subgraph = tx_graph.build_subgraph(address)
            result = {k: v.to_dict() for k, v in subgraph.items()} if subgraph else {}
            return {"address": address, "graph": result}
        except Exception as e:
            return {"address": address, "graph": {}, "error": str(e)}

    @app.get("/qvm/compliance/systemic-risk/{address}")
    async def compliance_systemic_risk(address: str):
        """Get systemic risk assessment for an address."""
        if not systemic_risk_model:
            return {"address": address, "risk": {}, "error": "Systemic risk model not available"}
        try:
            connections = systemic_risk_model.detect_high_risk_connections(address)
            return {
                "address": address,
                "high_risk_connections": connections,
                "count": len(connections),
            }
        except Exception as e:
            return {"address": address, "risk": {}, "error": str(e)}

    # ========================================================================
    # QVM EXTENSION ENDPOINTS
    # ========================================================================

    @app.get("/qvm/decoherence/states")
    async def qvm_decoherence_states():
        """Get active decoherence-tracked quantum states."""
        if not decoherence_manager:
            return {"states": [], "error": "Decoherence manager not available"}
        return decoherence_manager.get_stats()

    @app.get("/qvm/tokens/list")
    async def qvm_tokens_list_all():
        """List all tracked tokens (from token indexer)."""
        if hasattr(app, 'token_indexer'):
            return {"tokens": app.token_indexer.get_all_tokens()}
        return {"tokens": []}

    @app.get("/qvm/tokens/balances/{address}")
    async def qvm_token_balances(address: str):
        """Get all token balances for an address."""
        if hasattr(app, 'token_indexer'):
            tokens = app.token_indexer.get_address_tokens(address)
            return {"address": address, "tokens": tokens}
        return {"address": address, "tokens": []}

    @app.get("/qvm/batcher/stats")
    async def qvm_batcher_stats():
        """Get transaction batcher statistics."""
        if not transaction_batcher:
            return {"error": "Transaction batcher not available"}
        return transaction_batcher.get_stats()

    @app.get("/qvm/channels")
    async def qvm_state_channels():
        """Get all state channels."""
        if not state_channel_manager:
            return {"channels": [], "error": "State channel manager not available"}
        return state_channel_manager.get_stats()

    @app.get("/qvm/channels/{channel_id}")
    async def qvm_state_channel_detail(channel_id: str):
        """Get details of a specific state channel."""
        if not state_channel_manager:
            raise HTTPException(status_code=503, detail="State channel manager not available")
        channel = state_channel_manager.get_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        return channel.to_dict() if hasattr(channel, 'to_dict') else channel

    @app.post("/qvm/debug/load")
    async def qvm_debug_load(request: Request):
        """Load bytecode into the QVM debugger."""
        if not qvm_debugger:
            raise HTTPException(status_code=503, detail="QVM debugger not available")
        body = await request.json()
        bytecode = bytes.fromhex(body.get('bytecode', ''))
        qvm_debugger.load(bytecode)
        return {"loaded": True, "bytecode_size": len(bytecode)}

    @app.post("/qvm/debug/step")
    async def qvm_debug_step():
        """Step one instruction in the QVM debugger."""
        if not qvm_debugger:
            raise HTTPException(status_code=503, detail="QVM debugger not available")
        result = qvm_debugger.step()
        return result

    @app.get("/qvm/debug/state")
    async def qvm_debug_state():
        """Get current QVM debugger state (stack, memory, PC)."""
        if not qvm_debugger:
            raise HTTPException(status_code=503, detail="QVM debugger not available")
        return qvm_debugger.get_state()

    @app.post("/qvm/compile")
    async def qvm_compile(request: Request):
        """Compile QSol (Quantum Solidity) source to bytecode."""
        if not qsol_compiler:
            raise HTTPException(status_code=503, detail="QSol compiler not available")
        body = await request.json()
        source = body.get('source', '')
        try:
            result = qsol_compiler.compile(source)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Compilation error: {e}")

    # ========================================================================
    # ABI REGISTRY ENDPOINTS
    # ========================================================================

    @app.get("/qvm/abi/{address}")
    async def get_contract_abi(address: str):
        """Get the ABI for a deployed contract."""
        if not abi_registry:
            raise HTTPException(status_code=503, detail="ABI registry not available")
        record = abi_registry.get_record(address)
        if not record:
            raise HTTPException(status_code=404, detail="No ABI registered for this contract")
        return record.to_dict()

    @app.post("/qvm/abi/{address}")
    async def register_contract_abi(address: str, request: Request):
        """Register an ABI for a deployed contract."""
        if not abi_registry:
            raise HTTPException(status_code=503, detail="ABI registry not available")
        body = await request.json()
        abi = body.get("abi")
        if not abi or not isinstance(abi, list):
            raise HTTPException(status_code=400, detail="Missing or invalid 'abi' field (must be a list)")
        abi_registry.register_abi(address, abi)

        # Optionally verify if source_code and compiler_version are provided
        source_code = body.get("source_code")
        compiler_version = body.get("compiler_version")
        verified = False
        if source_code and compiler_version:
            verified = abi_registry.verify_contract(address, source_code, compiler_version)

        return {
            "address": address.lower().strip(),
            "abi_entries": len(abi),
            "verified": verified,
        }

    @app.get("/qvm/verified")
    async def list_verified_contracts():
        """List all verified contracts."""
        if not abi_registry:
            raise HTTPException(status_code=503, detail="ABI registry not available")
        contracts = abi_registry.get_verified_contracts()
        return {
            "verified_contracts": contracts,
            "total": len(contracts),
        }

    @app.get("/qvm/abi-registry/stats")
    async def abi_registry_stats():
        """Get ABI registry statistics."""
        if not abi_registry:
            return {"total_registered": 0, "total_verified": 0, "total_unverified": 0}
        return abi_registry.get_stats()

    # ========================================================================
    # STABLECOIN ENDPOINTS
    # ========================================================================

    @app.get("/qusd/health")
    async def qusd_health():
        """Get QUSD stablecoin system health."""
        if not stablecoin_engine:
            return {"error": "Stablecoin engine not available", "total_qusd": 0}
        return stablecoin_engine.get_system_health()

    @app.get("/qusd/vaults/at-risk")
    async def qusd_vaults_at_risk():
        """Get vaults at risk of liquidation."""
        if not stablecoin_engine:
            return {"vaults": []}
        return {"vaults": stablecoin_engine.check_vault_health()}

    class QUSDMintRequest(BaseModel):
        user_address: str
        collateral_amount: str
        collateral_type: str = "QBC"

    @app.post("/qusd/mint")
    async def qusd_mint(req: QUSDMintRequest):
        """Mint QUSD by depositing collateral."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        height = db_manager.get_current_height()
        success, msg, vault_id = stablecoin_engine.mint_qusd(
            req.user_address, Decimal(req.collateral_amount),
            req.collateral_type, height,
        )
        if not success:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg, "vault_id": vault_id}

    class QUSDBurnRequest(BaseModel):
        user_address: str
        amount: str
        vault_id: str

    @app.post("/qusd/burn")
    async def qusd_burn(req: QUSDBurnRequest):
        """Burn QUSD to redeem collateral."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        height = db_manager.get_current_height()
        success, msg = stablecoin_engine.burn_qusd(
            req.user_address, Decimal(req.amount), req.vault_id, height,
        )
        if not success:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.get("/qusd/reserves/inflows")
    async def qusd_reserve_inflows():
        """Get reserve fee inflows."""
        if not reserve_fee_router:
            return {"inflows": []}
        try:
            return reserve_fee_router.get_stats()
        except Exception:
            return {"inflows": []}

    @app.get("/qusd/reserves/milestones")
    async def qusd_reserve_milestones():
        """Get reserve backing milestones."""
        if not reserve_verifier:
            return {"milestones": []}
        try:
            return reserve_verifier.get_stats()
        except Exception:
            return {"milestones": []}

    @app.get("/qusd/reserves/verification")
    async def qusd_reserve_verification():
        """Get reserve verification status."""
        if not reserve_verifier:
            return {"verified": False, "error": "Reserve verifier not available"}
        try:
            return reserve_verifier.get_stats()
        except Exception as e:
            return {"verified": False, "error": str(e)}

    @app.get("/qusd/peg/history")
    async def qusd_peg_history():
        """Get historical QUSD peg deviation from price feeds."""
        try:
            from sqlalchemy import text as sql_text
            limit = min(int(request.query_params.get('limit', '100')), 500)
            with db_manager.get_session() as session:
                rows = session.execute(sql_text(
                    "SELECT price, block_height, timestamp, source "
                    "FROM price_feeds WHERE asset_pair = 'QUSD/USD' "
                    "ORDER BY block_height DESC LIMIT :lim"
                ), {'lim': limit}).fetchall()
                history = []
                for row in rows:
                    price = float(row[0])
                    history.append({
                        'price': price,
                        'deviation': round(price - 1.0, 6),
                        'block_height': row[1],
                        'timestamp': float(row[2]) if row[2] else 0,
                        'source': row[3],
                    })
                return {
                    'asset_pair': 'QUSD/USD',
                    'target_peg': 1.0,
                    'entries': len(history),
                    'history': history,
                }
        except Exception:
            return {
                'asset_pair': 'QUSD/USD',
                'target_peg': 1.0,
                'entries': 0,
                'history': [],
                'note': 'No price feed data available yet',
            }

    @app.get("/qusd/cross-chain")
    async def qusd_cross_chain():
        """Get cross-chain QUSD (wQUSD) status."""
        return {
            "wrapped_token": "wQUSD",
            "supported_chains": ["ETH", "SOL", "MATIC", "BNB", "AVAX", "ARB", "OP", "ATOM"],
            "bridge_available": bridge_manager is not None,
        }

    # ========================================================================
    # COGNITIVE ARCHITECTURE ENDPOINTS
    # ========================================================================

    @app.get("/aether/cognitive/sephirot/nodes")
    async def cognitive_sephirot_nodes():
        """Get all Sephirot node states from the cognitive architecture."""
        if not sephirot_manager:
            return {"nodes": {}, "error": "Sephirot manager not available"}
        return sephirot_manager.get_status()

    @app.get("/aether/cognitive/sephirot/{role}")
    async def cognitive_sephirot_role(role: str):
        """Get a specific Sephirot node by role name."""
        if not sephirot_manager:
            raise HTTPException(status_code=503, detail="Sephirot manager not available")
        try:
            status = sephirot_manager.get_status()
            if role in status:
                return status[role]
            # Try matching by name
            for key, val in status.items():
                if isinstance(val, dict) and val.get('name', '').lower() == role.lower():
                    return val
            raise HTTPException(status_code=404, detail=f"Sephirot node '{role}' not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/aether/cognitive/csf/stats")
    async def cognitive_csf_stats():
        """Get CSF (Cerebrospinal Fluid) transport statistics."""
        if not csf_transport:
            return {"error": "CSF transport not available", "queue_size": 0}
        return csf_transport.get_stats()

    @app.get("/aether/cognitive/pineal/status")
    async def cognitive_pineal_status():
        """Get Pineal Orchestrator status (circadian phase, metabolic rate, consciousness)."""
        if not pineal_orchestrator:
            return {"phase": "waking", "metabolic_rate": 1.0, "is_conscious": False,
                    "error": "Pineal orchestrator not available"}
        return pineal_orchestrator.get_status()

    @app.post("/aether/cognitive/pineal/tick")
    async def cognitive_pineal_tick(request: Request):
        """Manually advance the Pineal Orchestrator by one tick."""
        if not pineal_orchestrator:
            raise HTTPException(status_code=503, detail="Pineal orchestrator not available")
        body = await request.json()
        block_height = body.get('block_height', db_manager.get_current_height())
        phi_value = body.get('phi_value', 0.0)
        result = pineal_orchestrator.tick(block_height, phi_value)
        return result

    @app.get("/aether/cognitive/safety/stats")
    async def cognitive_safety_stats():
        """Get safety manager statistics (vetoes, evaluations, shutdown status)."""
        if not safety_manager:
            return {"error": "Safety manager not available"}
        return safety_manager.get_stats()

    @app.post("/aether/cognitive/safety/evaluate")
    async def cognitive_safety_evaluate(request: Request):
        """Evaluate an action through the safety pipeline."""
        if not safety_manager:
            raise HTTPException(status_code=503, detail="Safety manager not available")
        body = await request.json()
        allowed, veto = safety_manager.evaluate_and_decide(
            action_description=body.get('action', ''),
            source_node=body.get('source_node', ''),
            target_node=body.get('target_node', ''),
            block_height=body.get('block_height', 0),
        )
        result = {"allowed": allowed}
        if veto:
            result["veto"] = veto.to_dict() if hasattr(veto, 'to_dict') else str(veto)
        return result

    # ========================================================================
    # LIGHT NODE / SPV ENDPOINTS
    # ========================================================================

    @app.post("/light/verify-tx")
    async def light_verify_tx(request: Request):
        """Verify a transaction via SPV (Merkle proof)."""
        if not spv_verifier:
            raise HTTPException(status_code=503, detail="SPV verifier not available")
        body = await request.json()
        from ..network.light_node import MerkleProof
        proof = MerkleProof(
            tx_hash=body.get('tx_hash', ''),
            merkle_root=body.get('merkle_root', ''),
            siblings=body.get('siblings', []),
            index=body.get('index', 0),
            block_height=body.get('block_height', 0),
        )
        result = spv_verifier.verify_merkle_proof(proof)
        return {"valid": result, "tx_hash": body.get('tx_hash', '')}

    @app.get("/light/headers/{start}/{end}")
    async def light_headers(start: int, end: int):
        """Get block headers for light node sync."""
        if end - start > Config.RPC_BLOCK_RANGE_MAX:
            raise HTTPException(status_code=400, detail=f"Range too large (max {Config.RPC_BLOCK_RANGE_MAX})")
        headers = []
        for h in range(start, min(end, start + 1000)):
            block = db_manager.get_block(h)
            if block:
                headers.append({
                    "height": block.height,
                    "hash": block.hash,
                    "prev_hash": block.prev_hash,
                    "merkle_root": getattr(block, 'merkle_root', ''),
                    "timestamp": block.timestamp,
                    "difficulty": getattr(block, 'difficulty_target', 0),
                })
        return {"headers": headers, "count": len(headers)}

    # ========================================================================
    # FEE ENDPOINTS
    # ========================================================================

    @app.get("/fees/audit")
    async def fees_audit():
        """Get fee collection audit trail."""
        if not fee_collector:
            return {"audit": [], "error": "Fee collector not available"}
        try:
            return {"audit": fee_collector.get_audit_log()}
        except Exception:
            return {"audit": []}

    @app.get("/fees/total")
    async def fees_total():
        """Get total fees collected."""
        if not fee_collector:
            return {"total_qbc": "0", "error": "Fee collector not available"}
        try:
            return {"total_qbc": str(fee_collector.get_total_fees_collected())}
        except Exception:
            return {"total_qbc": "0"}

    @app.get("/fees/stats")
    async def fees_stats():
        """Get fee collector statistics."""
        if not fee_collector:
            return {"error": "Fee collector not available"}
        return fee_collector.get_stats()

    @app.get("/treasury")
    async def treasury_dashboard():
        """Treasury overview: balances, collected fees, and configuration."""
        aether_addr = Config.AETHER_FEE_TREASURY_ADDRESS
        contract_addr = Config.CONTRACT_FEE_TREASURY_ADDRESS
        aether_balance = str(db_manager.get_balance(aether_addr)) if aether_addr else "0"
        contract_balance = str(db_manager.get_balance(contract_addr)) if contract_addr else "0"
        fee_stats = fee_collector.get_stats() if fee_collector else {}
        return {
            "aether_treasury": {
                "address": aether_addr or "(not configured)",
                "balance_qbc": aether_balance,
            },
            "contract_treasury": {
                "address": contract_addr or "(not configured)",
                "balance_qbc": contract_balance,
            },
            "fee_stats": fee_stats,
            "config": {
                "aether_chat_fee_qbc": str(Config.AETHER_CHAT_FEE_QBC),
                "contract_deploy_base_fee_qbc": str(Config.CONTRACT_DEPLOY_BASE_FEE_QBC),
                "pricing_mode": Config.AETHER_FEE_PRICING_MODE,
            },
        }

    # ========================================================================
    # ORACLE ENDPOINTS
    # ========================================================================

    @app.get("/oracle/qbc-usd")
    async def oracle_qbc_usd():
        """Get current QBC/USD price from oracle."""
        if not qusd_oracle:
            from ..utils.qusd_oracle import QUSDOracle
            fallback = QUSDOracle(state_manager)
            return fallback.get_status()
        return qusd_oracle.get_status()

    @app.get("/oracle/status")
    async def oracle_status():
        """Get oracle health status."""
        if not qusd_oracle:
            return {"active": False, "error": "QUSD oracle not available"}
        status = qusd_oracle.get_status()
        status['active'] = True
        return status

    # ========================================================================
    # IPFS MEMORY ENDPOINTS
    # ========================================================================

    @app.get("/aether/memory/stats")
    async def aether_memory_stats():
        """Get IPFS memory store statistics."""
        if not ipfs_memory:
            return {"error": "IPFS memory store not available"}
        return ipfs_memory.get_stats()

    @app.post("/aether/memory/store")
    async def aether_memory_store(request: Request):
        """Store a memory to IPFS."""
        if not ipfs_memory:
            raise HTTPException(status_code=503, detail="IPFS memory store not available")
        body = await request.json()
        cid = ipfs_memory.store_memory(
            memory_id=body.get('memory_id', ''),
            memory_type=body.get('memory_type', 'episodic'),
            content=body.get('content', {}),
            source_block=body.get('source_block', 0),
            confidence=body.get('confidence', 1.0),
            metadata=body.get('metadata'),
        )
        return {"cid": cid}

    @app.get("/aether/memory/{cid}")
    async def aether_memory_retrieve(cid: str):
        """Retrieve a memory from IPFS by CID."""
        if not ipfs_memory:
            raise HTTPException(status_code=503, detail="IPFS memory store not available")
        memory = ipfs_memory.retrieve_memory(cid)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory

    # ========================================================================
    # QVM TRACE / DEBUG
    # ========================================================================

    @app.get("/qvm/trace/{tx_hash}")
    async def trace_transaction(tx_hash: str):
        """Re-execute a transaction and return an opcode-by-opcode execution trace.

        Returns a Geth-compatible ``debug_traceTransaction`` response with
        ``structLogs`` containing pc, op, gas, gasCost, stack, and memory
        for each executed opcode.
        """
        if not state_manager:
            raise HTTPException(status_code=503, detail="QVM not available")

        tx_hash_clean = tx_hash.replace("0x", "")

        # Look up the transaction to get its parameters
        from sqlalchemy import text as sa_text
        with db_manager.get_session() as session:
            row = session.execute(
                sa_text("""
                    SELECT txid, to_address, data, gas_limit, nonce, block_height
                    FROM transactions WHERE txid = :txid
                """),
                {"txid": tx_hash_clean},
            ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")

        to_address = row[1] or ""
        data_hex = row[2] or ""
        gas_limit = row[3] or 30_000_000
        block_height = row[5] or 0

        # Get the sender from the receipt
        receipt = db_manager.get_receipt(tx_hash_clean)
        from_address = receipt.from_address if receipt else "0" * 40

        # Get contract bytecode for re-execution
        bytecode_hex = ""
        if to_address:
            bytecode_hex = db_manager.get_contract_bytecode(to_address) or ""

        if not bytecode_hex and not to_address:
            # Contract deploy: the data IS the init code
            bytecode_hex = data_hex

        if not bytecode_hex:
            raise HTTPException(
                status_code=400,
                detail="No bytecode found for transaction target"
            )

        # Re-execute with tracing
        try:
            code = bytes.fromhex(bytecode_hex)
            calldata = bytes.fromhex(data_hex) if data_hex else b""

            trace = state_manager.qvm.execute_with_trace(
                caller=from_address,
                address=to_address or "0" * 40,
                code=code,
                data=calldata,
                gas=gas_limit,
                origin=from_address,
                is_static=True,  # read-only re-execution
            )
            return trace
        except Exception as e:
            logger.error(f"Trace execution error: {e}")
            raise HTTPException(status_code=500, detail=f"Trace failed: {str(e)}")

    # ========================================================================
    # BRIDGE LIQUIDITY POOL ENDPOINTS
    # ========================================================================

    @app.get("/bridge/lp/stats")
    async def bridge_lp_stats():
        """Get bridge liquidity pool statistics."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        return bridge_lp.get_pool_stats()

    @app.post("/bridge/lp/add")
    async def bridge_lp_add(request: Request):
        """Add liquidity to a chain pool."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        body = await request.json()
        provider = body.get('provider', '')
        chain = body.get('chain', '')
        amount = float(body.get('amount', 0))
        if not provider or not chain:
            raise HTTPException(status_code=400, detail="provider and chain required")
        try:
            position = bridge_lp.add_liquidity(provider, chain, amount)
            return {
                "status": "ok",
                "provider": position.provider,
                "chain": position.chain,
                "amount": position.amount,
                "accumulated_rewards": position.accumulated_rewards,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/bridge/lp/remove")
    async def bridge_lp_remove(request: Request):
        """Remove liquidity from a chain pool."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        body = await request.json()
        provider = body.get('provider', '')
        chain = body.get('chain', '')
        amount = float(body.get('amount', 0))
        if not provider or not chain:
            raise HTTPException(status_code=400, detail="provider and chain required")
        try:
            withdrawn, rewards = bridge_lp.remove_liquidity(provider, chain, amount)
            return {
                "status": "ok",
                "withdrawn": withdrawn,
                "rewards_collected": rewards,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/bridge/lp/rewards/{provider}")
    async def bridge_lp_rewards(provider: str):
        """Get pending + accumulated rewards for a provider."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        rewards = bridge_lp.calculate_rewards(provider)
        return {"provider": provider, "rewards_by_chain": rewards}

    @app.get("/bridge/lp/positions/{provider}")
    async def bridge_lp_positions(provider: str):
        """Get all LP positions for a provider."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        positions = bridge_lp.get_provider_positions(provider)
        return {"provider": provider, "positions": positions}

    @app.post("/bridge/lp/distribute")
    async def bridge_lp_distribute():
        """Trigger reward distribution for all LP positions."""
        if not bridge_lp:
            raise HTTPException(status_code=503, detail="Bridge LP not available")
        count = bridge_lp.distribute_rewards()
        return {"distributed_to": count}

    # ========================================================================
    # FLASH LOAN ENDPOINTS
    # ========================================================================

    @app.post("/qusd/flash-loan/initiate")
    async def flash_loan_initiate(request: Request):
        """Initiate a QUSD flash loan."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        body = await request.json()
        borrower = body.get('borrower', '')
        amount_str = body.get('amount', '0')
        if not borrower:
            raise HTTPException(status_code=400, detail="borrower address required")
        try:
            from decimal import Decimal
            loan = stablecoin_engine.initiate_flash_loan(borrower, Decimal(amount_str))
            return {
                "status": "ok",
                "loan_id": loan.id,
                "borrower": loan.borrower,
                "amount": str(loan.amount),
                "fee": str(loan.fee),
                "required_repayment": str(loan.amount + loan.fee),
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/qusd/flash-loan/repay")
    async def flash_loan_repay(request: Request):
        """Repay a flash loan."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        body = await request.json()
        loan_id = body.get('loan_id', '')
        repay_amount_str = body.get('repay_amount', '0')
        if not loan_id:
            raise HTTPException(status_code=400, detail="loan_id required")
        try:
            from decimal import Decimal
            success = stablecoin_engine.complete_flash_loan(loan_id, Decimal(repay_amount_str))
            return {"status": "ok" if success else "insufficient", "repaid": success}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/qusd/flash-loan/stats")
    async def flash_loan_stats():
        """Get flash loan statistics."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        return stablecoin_engine.get_flash_loan_stats()

    @app.get("/qusd/flash-loan/{loan_id}")
    async def flash_loan_get(loan_id: str):
        """Get an active flash loan by ID."""
        if not stablecoin_engine:
            raise HTTPException(status_code=503, detail="Stablecoin engine not available")
        loan = stablecoin_engine.get_active_flash_loan(loan_id)
        if not loan:
            raise HTTPException(status_code=404, detail="Flash loan not found or already repaid")
        return {
            "loan_id": loan.id,
            "borrower": loan.borrower,
            "amount": str(loan.amount),
            "fee": str(loan.fee),
            "repaid": loan.repaid,
            "timestamp": loan.timestamp,
        }

    # ========================================================================
    # NEURAL REASONER ENDPOINTS
    # ========================================================================

    @app.get("/aether/neural/stats")
    async def neural_reasoner_stats():
        """Get neural reasoning engine statistics."""
        if not neural_reasoner:
            raise HTTPException(status_code=503, detail="Neural reasoner not available")
        return neural_reasoner.get_stats()

    @app.get("/aether/neural/accuracy")
    async def neural_reasoner_accuracy():
        """Get neural reasoner prediction accuracy."""
        if not neural_reasoner:
            raise HTTPException(status_code=503, detail="Neural reasoner not available")
        return {
            "accuracy": neural_reasoner.get_accuracy(),
            "training_mode": neural_reasoner.training_mode,
            "has_pytorch": neural_reasoner.has_pytorch,
        }

    # ========================================================================
    # CONTRACT VALIDATION ENDPOINT
    # ========================================================================

    @app.get("/contracts/validate")
    async def contracts_validate():
        """Validate all Solidity contracts in the suite."""
        try:
            from pathlib import Path
            contracts_root = Path(__file__).parent.parent / "contracts" / "solidity"
            if not contracts_root.exists():
                return {"error": "Contracts directory not found", "path": str(contracts_root)}
            from ..contracts.solidity_validator import validate_all, compute_deploy_order
            results, summary = validate_all(contracts_root)
            deploy_order = compute_deploy_order(results)
            return {
                "summary": summary,
                "deploy_order": deploy_order,
                "results": [r.to_dict() for r in results],
            }
        except ImportError:
            # Fallback: use the standalone script
            try:
                import sys
                scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts" / "deploy"
                sys.path.insert(0, str(scripts_dir))
                from validate_contracts import validate_all, compute_deploy_order
                contracts_root = Path(__file__).parent.parent / "contracts" / "solidity"
                results, summary = validate_all(contracts_root)
                deploy_order = compute_deploy_order(results)
                return {
                    "summary": summary,
                    "deploy_order": deploy_order,
                    "results": [r.to_dict() for r in results],
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Validation failed: {e}")

    # ========================================================================
    # ADMIN API (Economics hot-reload)
    # ========================================================================

    from .admin_api import router as admin_router
    app.include_router(admin_router)

    logger.info("RPC endpoints configured (v2.1 with P2P + QVM + Aether + WebSocket + Admin + Bridge LP + Flash Loans + Neural)")

    return app
