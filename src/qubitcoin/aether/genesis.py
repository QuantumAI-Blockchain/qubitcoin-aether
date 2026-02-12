"""
Aether Tree Genesis Initialization

Seeds the knowledge graph, records the first Phi measurement (Phi=0.0),
and logs the "system_birth" consciousness event at block 0.

NON-NEGOTIABLE: AGI must be tracked from genesis. No retroactive reconstruction.
This module MUST be called during genesis block creation/processing.
"""
import time
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AetherGenesis:
    """Initialize the Aether Tree at genesis (block 0)."""

    def __init__(self, db_manager, knowledge_graph=None, phi_calculator=None) -> None:
        self.db = db_manager
        self.kg = knowledge_graph
        self.phi = phi_calculator

    def initialize_genesis(self, genesis_block_hash: str = '0' * 64,
                           genesis_timestamp: Optional[float] = None) -> dict:
        """Initialize Aether Tree from genesis block.

        Must be called exactly once, during genesis block creation.

        Args:
            genesis_block_hash: Hash of the genesis block.
            genesis_timestamp: Timestamp of genesis block. Defaults to now.

        Returns:
            Dict with initialization results.
        """
        if genesis_timestamp is None:
            genesis_timestamp = time.time()

        results = {
            'knowledge_nodes_created': 0,
            'phi_baseline': 0.0,
            'consciousness_event': 'system_birth',
            'block_height': 0,
        }

        # 1. Seed the knowledge graph with genesis metadata
        if self.kg:
            genesis_node = self.kg.add_node(
                node_type='axiom',
                content={
                    'type': 'genesis',
                    'block_hash': genesis_block_hash,
                    'timestamp': genesis_timestamp,
                    'chain_id': Config.CHAIN_ID,
                    'max_supply': str(Config.MAX_SUPPLY),
                    'phi': Config.PHI,
                    'description': 'Qubitcoin genesis — first moment of chain existence',
                },
                confidence=1.0,
                source_block=0,
            )
            results['knowledge_nodes_created'] += 1

            # Add foundational axiom nodes
            axioms = [
                {
                    'type': 'axiom_economic',
                    'description': 'Golden ratio (phi) governs emission and balance',
                    'phi': Config.PHI,
                    'halving_interval': Config.HALVING_INTERVAL,
                },
                {
                    'type': 'axiom_quantum',
                    'description': 'Proof-of-SUSY-Alignment: energy below difficulty = valid',
                    'initial_difficulty': Config.INITIAL_DIFFICULTY,
                    'block_time': Config.TARGET_BLOCK_TIME,
                },
                {
                    'type': 'axiom_consciousness',
                    'description': 'Phi (IIT) measures integrated information — consciousness metric',
                    'phi_threshold': 3.0,
                    'initial_phi': 0.0,
                },
            ]
            for axiom in axioms:
                node = self.kg.add_node(
                    node_type='axiom',
                    content=axiom,
                    confidence=1.0,
                    source_block=0,
                )
                self.kg.add_edge(genesis_node.node_id, node.node_id, 'derives')
                results['knowledge_nodes_created'] += 1

        # 2. Record first Phi measurement (baseline Phi = 0.0 at genesis)
        self._record_phi_measurement(0.0, block_height=0)

        # 3. Record genesis consciousness event
        self._record_consciousness_event(
            event_type='system_birth',
            phi_value=0.0,
            block_height=0,
            trigger_data={
                'genesis_hash': genesis_block_hash,
                'timestamp': genesis_timestamp,
                'description': 'Aether Tree genesis — consciousness tracking begins',
            }
        )

        logger.info(
            f"Aether Genesis initialized: "
            f"{results['knowledge_nodes_created']} knowledge nodes, "
            f"Phi=0.0 baseline, system_birth recorded"
        )

        return results

    def is_genesis_initialized(self) -> bool:
        """Check if genesis initialization has already been performed."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT COUNT(*) FROM consciousness_events WHERE event_type = 'system_birth' AND block_height = 0")
                ).scalar()
                return (result or 0) > 0
        except Exception:
            return False

    def _record_phi_measurement(self, phi_value: float, block_height: int) -> None:
        """Record a Phi measurement in the database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO phi_measurements
                        (phi_value, phi_threshold, integration_score, differentiation_score,
                         num_nodes, num_edges, block_height)
                        VALUES (:phi, 3.0, 0.0, 0.0, :nodes, 0, :bh)
                    """),
                    {
                        'phi': phi_value,
                        'nodes': len(self.kg.nodes) if self.kg else 0,
                        'bh': block_height,
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to record Phi measurement: {e}")

    def _record_consciousness_event(self, event_type: str, phi_value: float,
                                     block_height: int, trigger_data: dict = None) -> None:
        """Record a consciousness event."""
        try:
            import json
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO consciousness_events
                        (event_type, phi_at_event, trigger_data, is_verified, block_height)
                        VALUES (:etype, :phi, CAST(:trigger AS jsonb), true, :bh)
                    """),
                    {
                        'etype': event_type,
                        'phi': phi_value,
                        'trigger': json.dumps(trigger_data or {}),
                        'bh': block_height,
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to record consciousness event: {e}")
