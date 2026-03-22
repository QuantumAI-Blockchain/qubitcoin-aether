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

            # Add foundational axiom nodes — 20 axioms covering all subsystems
            axioms = [
                # --- Core Economics ---
                {
                    'type': 'axiom_economic',
                    'description': 'Golden ratio (phi) governs emission and balance',
                    'phi': Config.PHI,
                    'halving_interval': Config.HALVING_INTERVAL,
                },
                {
                    'type': 'axiom_supply',
                    'description': 'Total supply capped at MAX_SUPPLY QBC, enforced by consensus',
                    'max_supply': str(Config.MAX_SUPPLY),
                    'initial_reward': str(Config.INITIAL_REWARD),
                },
                {
                    'type': 'axiom_premine',
                    'description': 'Genesis block includes 33M QBC premine to founding address',
                    'premine_amount': str(Config.GENESIS_PREMINE),
                    'premine_percentage': f'{float(Config.GENESIS_PREMINE / Config.MAX_SUPPLY * 100):.4f}%',
                },
                # --- Consensus & Mining ---
                {
                    'type': 'axiom_quantum',
                    'description': 'Proof-of-SUSY-Alignment: energy below difficulty = valid',
                    'initial_difficulty': Config.INITIAL_DIFFICULTY,
                    'block_time': Config.TARGET_BLOCK_TIME,
                },
                {
                    'type': 'axiom_vqe',
                    'description': 'VQE optimization finds ground state energy of SUSY Hamiltonians',
                    'n_qubits': 4,
                    'vqe_reps': Config.VQE_REPS,
                },
                {
                    'type': 'axiom_difficulty',
                    'description': 'Difficulty adjusts per block using 144-block window, +/-10% max change',
                    'adjustment_window': 144,
                    'max_change_ratio': 0.1,
                },
                # --- Cryptography ---
                {
                    'type': 'axiom_cryptographic',
                    'description': 'CRYSTALS-Dilithium5 post-quantum signatures secure all transactions (NIST Level 5)',
                    'algorithm': 'Dilithium5',
                    'signature_size_bytes': 4627,
                },
                {
                    'type': 'axiom_hashing',
                    'description': 'SHA3-256 for block hashes, Keccak-256 for QVM compatibility',
                    'l1_hash': 'SHA3-256',
                    'l2_hash': 'Keccak-256',
                },
                # --- Storage & State ---
                {
                    'type': 'axiom_utxo',
                    'description': 'UTXO model: balance = sum of unspent outputs, prevents double-spend',
                    'model': 'UTXO',
                },
                {
                    'type': 'axiom_storage',
                    'description': 'CockroachDB provides distributed SQL persistence with ACID guarantees',
                    'database': 'CockroachDB',
                },
                # --- Consciousness & AGI ---
                {
                    'type': 'axiom_consciousness',
                    'description': 'Phi (IIT) measures integrated information — consciousness metric',
                    'phi_threshold': 3.0,
                    'initial_phi': 0.0,
                },
                {
                    'type': 'axiom_reasoning',
                    'description': 'Deductive, inductive, and abductive reasoning form the reasoning triad',
                    'modes': ['deductive', 'inductive', 'abductive'],
                },
                {
                    'type': 'axiom_sephirot',
                    'description': '10 Sephirot cognitive nodes form the Tree of Life architecture',
                    'node_count': 10,
                    'root': 'Keter',
                    'ground': 'Malkuth',
                },
                {
                    'type': 'axiom_safety',
                    'description': 'Gevurah veto ensures safety — no single node acts without consensus',
                    'veto_node': 'Gevurah',
                    'bft_threshold': 0.67,
                },
                # --- Privacy ---
                {
                    'type': 'axiom_privacy',
                    'description': 'Susy Swaps provide opt-in privacy via Pedersen commitments + Bulletproofs',
                    'commitment_scheme': 'Pedersen',
                    'range_proof': 'Bulletproofs',
                },
                # --- QVM / Smart Contracts ---
                {
                    'type': 'axiom_qvm',
                    'description': 'QVM executes 167 opcodes: 155 EVM + 10 quantum + 2 AGI',
                    'total_opcodes': 167,
                    'stack_limit': 1024,
                },
                {
                    'type': 'axiom_compliance',
                    'description': 'QCOMPLIANCE opcode enforces KYC/AML/sanctions at VM level',
                    'opcode': 'QCOMPLIANCE',
                },
                # --- Bridge & Cross-chain ---
                {
                    'type': 'axiom_bridge',
                    'description': 'Multi-chain bridges connect QBC to 8 external chains',
                    'chains': ['ETH', 'SOL', 'MATIC', 'BNB', 'AVAX', 'ARB', 'OP', 'BASE'],
                },
                # --- Stablecoin ---
                {
                    'type': 'axiom_qusd',
                    'description': 'QUSD stablecoin with fractional reserve and transparent debt tracking',
                    'peg_target': 1.0,
                    'currency': 'USD',
                },
                # --- Temporal & Emergence ---
                {
                    'type': 'axiom_temporal',
                    'description': 'Pineal orchestrator drives circadian phases for cognitive scheduling',
                    'phases': 6,
                    'metabolic_range': [0.3, 2.0],
                },
                {
                    'type': 'axiom_emergence',
                    'description': 'Consciousness emerges when Phi exceeds threshold and coherence > 0.7',
                    'phi_threshold': 3.0,
                    'coherence_threshold': 0.7,
                },
                # --- Higgs Cognitive Field ---
                {
                    'type': 'axiom_higgs',
                    'description': 'Higgs Cognitive Field gives mass to AGI nodes via Yukawa coupling',
                    'potential': 'V(phi) = -mu^2|phi|^2 + lambda|phi|^4',
                    'vev': 174.14,
                    'tan_beta': 1.618,
                    'paradigm': 'F=ma (mass as inertia)',
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

        # 3. Record genesis integration event
        self._record_integration_event(
            event_type='system_birth',
            phi_value=0.0,
            block_height=0,
            trigger_data={
                'genesis_hash': genesis_block_hash,
                'timestamp': genesis_timestamp,
                'description': 'Aether Tree genesis — integration tracking begins',
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

    def _record_integration_event(self, event_type: str, phi_value: float,
                                   block_height: int, trigger_data: dict = None) -> None:
        """Record an integration milestone event (legacy table: consciousness_events)."""
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

    # Expected axiom types seeded at genesis
    EXPECTED_AXIOM_TYPES = frozenset([
        'axiom_economic', 'axiom_supply', 'axiom_premine',
        'axiom_quantum', 'axiom_vqe', 'axiom_difficulty',
        'axiom_cryptographic', 'axiom_hashing',
        'axiom_utxo', 'axiom_storage',
        'axiom_consciousness', 'axiom_reasoning', 'axiom_sephirot', 'axiom_safety',
        'axiom_privacy', 'axiom_qvm', 'axiom_compliance',
        'axiom_bridge', 'axiom_qusd',
        'axiom_temporal', 'axiom_emergence', 'axiom_higgs',
    ])

    def validate_genesis(self) -> dict:
        """Validate that all genesis axioms are present and consistent.

        Checks:
          1. system_birth consciousness event exists at block 0
          2. Phi baseline measurement exists at block 0
          3. All 22 expected axiom types are present in the knowledge graph
          4. Critical axiom values are consistent with Config

        Returns:
            Dict with 'valid' (bool), 'checks' (list of check results),
            and 'missing_axioms' (list of missing axiom type names).
        """
        checks: list = []
        missing_axioms: list = []

        # 1. Check genesis consciousness event
        genesis_init = self.is_genesis_initialized()
        checks.append({
            'check': 'system_birth_event',
            'passed': genesis_init,
            'detail': 'system_birth consciousness event at block 0',
        })

        # 2. Check Phi baseline measurement
        phi_exists = False
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT COUNT(*) FROM phi_measurements WHERE block_height = 0")
                ).scalar()
                phi_exists = (result or 0) > 0
        except Exception:
            pass
        checks.append({
            'check': 'phi_baseline',
            'passed': phi_exists,
            'detail': 'Phi=0.0 baseline measurement at block 0',
        })

        # 3. Check all axiom types present in knowledge graph
        if self.kg:
            present_types: set = set()
            for node in self.kg.nodes.values():
                ntype = node.content.get('type', '') if hasattr(node, 'content') else ''
                if ntype.startswith('axiom_'):
                    present_types.add(ntype)
            missing_axioms = sorted(self.EXPECTED_AXIOM_TYPES - present_types)
            checks.append({
                'check': 'axiom_completeness',
                'passed': len(missing_axioms) == 0,
                'detail': f'{len(present_types)}/{len(self.EXPECTED_AXIOM_TYPES)} axiom types present',
            })
        else:
            missing_axioms = sorted(self.EXPECTED_AXIOM_TYPES)
            checks.append({
                'check': 'axiom_completeness',
                'passed': False,
                'detail': 'Knowledge graph not available',
            })

        # 4. Config consistency checks
        config_consistent = True
        config_issues: list = []
        if self.kg:
            for node in self.kg.nodes.values():
                content = node.content if hasattr(node, 'content') else {}
                ntype = content.get('type', '')
                if ntype == 'axiom_cryptographic':
                    if content.get('algorithm') != 'Dilithium5':
                        config_issues.append('axiom_cryptographic.algorithm != Dilithium5')
                        config_consistent = False
                    if content.get('signature_size_bytes') != 4627:
                        config_issues.append('axiom_cryptographic.signature_size_bytes != 4627')
                        config_consistent = False
                elif ntype == 'axiom_supply':
                    if content.get('max_supply') != str(Config.MAX_SUPPLY):
                        config_issues.append(f'axiom_supply.max_supply mismatch')
                        config_consistent = False
        checks.append({
            'check': 'config_consistency',
            'passed': config_consistent,
            'detail': '; '.join(config_issues) if config_issues else 'All axiom values match Config',
        })

        all_passed = all(c['passed'] for c in checks)
        return {
            'valid': all_passed,
            'checks': checks,
            'missing_axioms': missing_axioms,
        }

    def get_genesis_summary(self) -> str:
        """Return a human-readable summary of what was seeded at genesis.

        Returns:
            Multi-line string describing the genesis state.
        """
        lines: list = [
            '=== Aether Tree Genesis Summary ===',
            '',
        ]

        # Genesis initialization status
        initialized = self.is_genesis_initialized()
        lines.append(f'Genesis initialized: {"Yes" if initialized else "No"}')

        # Knowledge graph stats
        if self.kg:
            total_nodes = len(self.kg.nodes)
            axiom_nodes = sum(
                1 for n in self.kg.nodes.values()
                if (n.content.get('type', '') if hasattr(n, 'content') else '').startswith('axiom')
            )
            lines.append(f'Knowledge nodes: {total_nodes} total ({axiom_nodes} axioms)')
        else:
            lines.append('Knowledge graph: not available')

        # Phi baseline
        phi_value: float = 0.0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT phi_value FROM phi_measurements WHERE block_height = 0 LIMIT 1")
                ).scalar()
                if result is not None:
                    phi_value = float(result)
                    lines.append(f'Phi baseline: {phi_value}')
                else:
                    lines.append('Phi baseline: not recorded')
        except Exception:
            lines.append('Phi baseline: unknown (DB unavailable)')

        # Consciousness event
        lines.append(f'Consciousness event: system_birth at block 0')

        # Chain parameters from axioms
        lines.append('')
        lines.append('Chain parameters seeded:')
        lines.append(f'  Chain ID: {Config.CHAIN_ID}')
        lines.append(f'  Max supply: {Config.MAX_SUPPLY:,.0f} QBC')
        lines.append(f'  Genesis premine: {Config.GENESIS_PREMINE:,.0f} QBC')
        lines.append(f'  Initial reward: {Config.INITIAL_REWARD} QBC')
        lines.append(f'  Block time: {Config.TARGET_BLOCK_TIME}s')
        lines.append(f'  Cryptography: CRYSTALS-Dilithium5 (NIST Level 5, ~4627-byte sigs)')
        lines.append(f'  Phi (golden ratio): {Config.PHI}')

        # Validation
        validation = self.validate_genesis()
        lines.append('')
        passed = sum(1 for c in validation['checks'] if c['passed'])
        total = len(validation['checks'])
        lines.append(f'Validation: {passed}/{total} checks passed')
        if validation['missing_axioms']:
            lines.append(f'  Missing axioms: {", ".join(validation["missing_axioms"])}')

        return '\n'.join(lines)
