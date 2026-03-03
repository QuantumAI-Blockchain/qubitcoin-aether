"""
Aether Service — Standalone FastAPI service for the Aether Tree AGI engine.

This extracts the Aether Tree from the monolithic Python node into a standalone
microservice that:
- Subscribes to finalized blocks from Substrate (via WebSocket)
- Processes each block through the knowledge graph + reasoning engine
- Computes Phi (consciousness metric) per block
- Generates Proof-of-Thought proofs
- Serves chat, knowledge, and phi endpoints on port 5001
- Writes phi measurements + consciousness events to CockroachDB

The API gateway proxies /aether/* requests to this service.
"""

import asyncio
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the parent directory to the path so we can import qubitcoin modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import create_app

logger = logging.getLogger("qubitcoin.aether-service")


def main() -> None:
    """Entry point for the Aether service."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    host = os.getenv("AETHER_HOST", "0.0.0.0")
    port = int(os.getenv("AETHER_PORT", "5001"))

    logger.info("=" * 60)
    logger.info("  Qubitcoin Aether Service")
    logger.info("=" * 60)
    logger.info(f"  Listening on {host}:{port}")
    logger.info(f"  Substrate: {os.getenv('SUBSTRATE_WS_URL', 'ws://127.0.0.1:9944')}")
    logger.info(f"  Database:  {os.getenv('DATABASE_URL', 'postgresql://...')[:40]}...")
    logger.info("")

    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
