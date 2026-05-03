"""
FastAPI application factory for the Aether service.

Creates the FastAPI app with all Aether endpoints, initializes the
knowledge graph, reasoning engine, phi calculator, and block subscriber.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("qubitcoin.aether-service")

# Global references to Aether components (initialized on startup)
_aether_engine = None
_block_subscriber = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Aether components on startup, clean up on shutdown."""
    global _aether_engine, _block_subscriber

    logger.info("Initializing Aether Tree components...")

    try:
        # Import Aether modules (from the main qubitcoin package)
        from qubitcoin.aether.proof_of_thought import AetherEngine
        from qubitcoin.database.manager import DatabaseManager

        # Initialize database connection
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://root@127.0.0.1:26257/qbc?sslmode=disable",
        )
        db_manager = DatabaseManager(db_url)

        # Initialize the Aether engine
        _aether_engine = AetherEngine(db_manager=db_manager)
        logger.info("Aether engine initialized")

        # Start block subscriber in background
        _block_subscriber = asyncio.create_task(
            subscribe_to_blocks(_aether_engine)
        )
        logger.info("Block subscriber started")

    except Exception as e:
        logger.error(f"Failed to initialize Aether engine: {e}")
        logger.warning("Running in degraded mode (no Aether processing)")

    yield

    # Shutdown
    logger.info("Shutting down Aether service...")
    if _block_subscriber and not _block_subscriber.done():
        _block_subscriber.cancel()
        try:
            await _block_subscriber
        except asyncio.CancelledError:
            pass
    logger.info("Aether service stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application with all routes."""
    app = FastAPI(
        title="Qubitcoin Aether Service",
        description="Standalone AI reasoning engine for the Qubitcoin blockchain",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://qbc.network",
            "https://app.qbc.network",
            "http://localhost:3000",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from routes import register_routes

    register_routes(app)

    return app


async def subscribe_to_blocks(engine) -> None:
    """
    Subscribe to finalized Substrate blocks and process each through Aether.

    Uses substrate-interface to subscribe to finalized heads. For each block:
    1. Extract knowledge from block data (miner, energy, difficulty, etc.)
    2. Add knowledge nodes to the graph
    3. Run auto-reasoning
    4. Compute Phi
    5. Generate Proof-of-Thought
    6. Write phi measurement to CockroachDB
    """
    ws_url = os.getenv("SUBSTRATE_WS_URL", "ws://127.0.0.1:9944")

    while True:
        try:
            from substrateinterface import SubstrateInterface

            substrate = SubstrateInterface(url=ws_url, ss58_format=88)
            logger.info(f"Connected to Substrate node: {ws_url}")

            subscription = substrate.subscribe_block_headers(finalized_only=True)

            for header in subscription:
                block_number = int(header["header"]["number"], 16)

                try:
                    # Process block through Aether engine
                    block_data = {
                        "height": block_number,
                        "hash": header.get("hash", ""),
                        "parent_hash": header["header"]["parentHash"],
                    }

                    # Extract knowledge and compute phi
                    if engine:
                        engine.process_block(block_data)

                    if block_number % 10 == 0:
                        phi = engine.phi if engine else 0.0
                        logger.info(
                            f"Processed block {block_number} | "
                            f"Phi={phi:.4f}"
                        )
                except Exception as e:
                    logger.error(f"Error processing block {block_number}: {e}")

        except Exception as e:
            logger.error(f"Block subscription error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Block subscriber cancelled")
            return
