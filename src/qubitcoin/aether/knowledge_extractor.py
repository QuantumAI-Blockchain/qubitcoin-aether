"""
Knowledge Extractor — Block-to-Knowledge Pipeline for Aether Tree

Extracts structured knowledge from every block mined/received and feeds
it into the KnowledgeGraph as KeterNodes. This is the sensory input
pipeline of the AGI — how the Aether Tree perceives the blockchain.

Extraction categories:
  - Block metadata (height, difficulty, timing)
  - Transaction patterns (volume, fee trends, contract activity)
  - Mining statistics (energy, VQE convergence)
  - Network health (peer counts, propagation time)
  - Temporal patterns (block time drift, difficulty trends)
"""
import hashlib
import math
import time
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeExtractor:
    """
    Extracts knowledge from blocks and adds structured KeterNodes
    to the Aether Tree knowledge graph.

    Tracks running statistics for pattern detection (inductive reasoning
    feeds). Maintains sliding windows for trend analysis.
    """

    def __init__(self, knowledge_graph: object) -> None:
        self.kg = knowledge_graph
        # Sliding window stats for pattern detection
        self._block_times: List[float] = []
        self._difficulties: List[float] = []
        self._tx_counts: List[int] = []
        self._energies: List[float] = []
        self._window_size = 144  # Match difficulty adjustment window
        self._blocks_processed = 0
        logger.info("Knowledge Extractor initialized")

    def extract_from_block(self, block: object, block_height: int) -> int:
        """
        Extract all knowledge from a block and add to the knowledge graph.

        Returns the number of KeterNodes created.
        """
        if not self.kg:
            return 0

        nodes_created = 0

        try:
            # 1. Core block observation
            block_node_id = self._extract_block_metadata(block, block_height)
            if block_node_id:
                nodes_created += 1

            # 2. Transaction patterns
            tx_nodes = self._extract_transaction_patterns(block, block_height, block_node_id)
            nodes_created += tx_nodes

            # 3. Mining / quantum observations
            mining_nodes = self._extract_mining_data(block, block_height, block_node_id)
            nodes_created += mining_nodes

            # 4. Temporal pattern detection (every 10 blocks)
            if block_height > 0 and block_height % 10 == 0:
                pattern_nodes = self._detect_temporal_patterns(block_height, block_node_id)
                nodes_created += pattern_nodes

            # 5. Difficulty trend analysis (every 144 blocks)
            if block_height > 0 and block_height % 144 == 0:
                trend_nodes = self._analyze_difficulty_trends(block_height, block_node_id)
                nodes_created += trend_nodes

            self._blocks_processed += 1

        except Exception as e:
            logger.debug(f"Knowledge extraction error at block {block_height}: {e}")

        return nodes_created

    def _extract_block_metadata(self, block: object, block_height: int) -> Optional[int]:
        """Extract core block metadata as an observation node."""
        difficulty = getattr(block, 'difficulty', 0.0)
        timestamp = getattr(block, 'timestamp', time.time())
        tx_count = len(getattr(block, 'transactions', []))

        content = {
            'type': 'block_observation',
            'height': block_height,
            'difficulty': difficulty,
            'tx_count': tx_count,
            'timestamp': timestamp,
        }

        node = self.kg.add_node(
            node_type='observation',
            content=content,
            confidence=0.95,
            source_block=block_height,
        )
        node.grounding_source = 'block_oracle'

        # Update sliding windows
        self._difficulties.append(difficulty)
        self._tx_counts.append(tx_count)
        if len(self._difficulties) > self._window_size:
            self._difficulties = self._difficulties[-self._window_size:]
        if len(self._tx_counts) > self._window_size:
            self._tx_counts = self._tx_counts[-self._window_size:]

        # Track block times
        if hasattr(block, 'timestamp') and self._block_times:
            block_time = timestamp - self._block_times[-1]
            self._block_times.append(timestamp)
            content['block_time'] = round(block_time, 3)
        else:
            self._block_times.append(timestamp)

        if len(self._block_times) > self._window_size:
            self._block_times = self._block_times[-self._window_size:]

        # Link to previous block observation
        if block_height > 0:
            self._link_to_previous_block(node.node_id, block_height)

        return node.node_id

    def _extract_transaction_patterns(self, block: object, block_height: int,
                                       parent_node_id: Optional[int]) -> int:
        """Extract transaction pattern knowledge."""
        transactions = getattr(block, 'transactions', [])
        if not transactions:
            return 0

        nodes_created = 0

        # Aggregate tx statistics
        total_fees = 0.0
        contract_txs = 0
        regular_txs = 0

        for tx in transactions:
            fee = getattr(tx, 'fee', 0.0)
            total_fees += fee
            tx_type = getattr(tx, 'tx_type', 'transfer')
            if tx_type in ('contract_deploy', 'contract_call'):
                contract_txs += 1
            else:
                regular_txs += 1

        # Create aggregated transaction observation
        if len(transactions) > 0:
            tx_content = {
                'type': 'transaction_pattern',
                'block_height': block_height,
                'tx_count': len(transactions),
                'regular_txs': regular_txs,
                'contract_txs': contract_txs,
                'total_fees': round(total_fees, 8),
                'avg_fee': round(total_fees / len(transactions), 8) if transactions else 0,
            }

            tx_node = self.kg.add_node(
                node_type='observation',
                content=tx_content,
                confidence=0.9,
                source_block=block_height,
            )
            tx_node.grounding_source = 'block_oracle'
            nodes_created += 1

            if parent_node_id:
                self.kg.add_edge(tx_node.node_id, parent_node_id, 'supports')

            # High contract activity generates an inference
            if contract_txs > 3:
                inference_content = {
                    'type': 'activity_inference',
                    'pattern': 'high_contract_activity',
                    'block_height': block_height,
                    'contract_tx_count': contract_txs,
                }
                inf_node = self.kg.add_node(
                    node_type='inference',
                    content=inference_content,
                    confidence=0.7,
                    source_block=block_height,
                )
                self.kg.add_edge(tx_node.node_id, inf_node.node_id, 'derives')
                nodes_created += 1

        return nodes_created

    def _extract_mining_data(self, block: object, block_height: int,
                              parent_node_id: Optional[int]) -> int:
        """Extract mining and quantum observation data."""
        proof_data = getattr(block, 'proof_data', None)
        if not proof_data or not isinstance(proof_data, dict):
            return 0

        nodes_created = 0
        energy = proof_data.get('energy', 0)

        if energy:
            quantum_content = {
                'type': 'quantum_observation',
                'energy': energy,
                'difficulty': getattr(block, 'difficulty', 0),
                'block_height': block_height,
                'n_qubits': proof_data.get('n_qubits', 4),
                'optimizer_iterations': proof_data.get('iterations', 0),
            }

            q_node = self.kg.add_node(
                node_type='observation',
                content=quantum_content,
                confidence=0.9,
                source_block=block_height,
            )
            q_node.grounding_source = 'block_oracle'
            nodes_created += 1

            if parent_node_id:
                self.kg.add_edge(q_node.node_id, parent_node_id, 'supports')

            # Track energies for trend detection
            self._energies.append(energy)
            if len(self._energies) > self._window_size:
                self._energies = self._energies[-self._window_size:]

        return nodes_created

    def _detect_temporal_patterns(self, block_height: int,
                                   parent_node_id: Optional[int]) -> int:
        """Detect temporal patterns in recent blocks (run every 10 blocks)."""
        if len(self._block_times) < 10:
            return 0

        nodes_created = 0

        # Calculate block time statistics
        recent_times = self._block_times[-10:]
        intervals = [recent_times[i+1] - recent_times[i]
                     for i in range(len(recent_times) - 1)]

        if not intervals:
            return 0

        avg_interval = sum(intervals) / len(intervals)
        target = 3.3  # TARGET_BLOCK_TIME

        drift = abs(avg_interval - target) / target

        # If block time drifts >20% from target, create an inference
        if drift > 0.20:
            direction = "fast" if avg_interval < target else "slow"
            pattern_content = {
                'type': 'temporal_pattern',
                'pattern': f'block_time_{direction}',
                'avg_block_time': round(avg_interval, 3),
                'target_block_time': target,
                'drift_percent': round(drift * 100, 1),
                'block_height': block_height,
                'window': 10,
            }

            p_node = self.kg.add_node(
                node_type='inference',
                content=pattern_content,
                confidence=0.75,
                source_block=block_height,
            )
            nodes_created += 1

            if parent_node_id:
                self.kg.add_edge(parent_node_id, p_node.node_id, 'derives')

        return nodes_created

    def _analyze_difficulty_trends(self, block_height: int,
                                    parent_node_id: Optional[int]) -> int:
        """Analyze difficulty adjustment trends (run every 144 blocks)."""
        if len(self._difficulties) < 20:
            return 0

        nodes_created = 0

        # Compute trend: linear regression slope over recent window
        recent = self._difficulties[-144:] if len(self._difficulties) >= 144 else self._difficulties
        n = len(recent)
        if n < 2:
            return 0

        x_mean = (n - 1) / 2.0
        y_mean = sum(recent) / n
        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0

        slope = numerator / denominator

        # Normalize slope relative to mean difficulty
        if y_mean > 0:
            normalized_slope = slope / y_mean
        else:
            normalized_slope = 0

        trend = "rising" if normalized_slope > 0.01 else "falling" if normalized_slope < -0.01 else "stable"

        trend_content = {
            'type': 'difficulty_trend',
            'trend': trend,
            'normalized_slope': round(normalized_slope, 6),
            'mean_difficulty': round(y_mean, 6),
            'window_size': n,
            'block_height': block_height,
        }

        t_node = self.kg.add_node(
            node_type='inference',
            content=trend_content,
            confidence=0.8,
            source_block=block_height,
        )
        nodes_created += 1

        if parent_node_id:
            self.kg.add_edge(parent_node_id, t_node.node_id, 'derives')

        # If tx volume is also trending, create a cross-inference
        if len(self._tx_counts) >= 20:
            recent_tx = self._tx_counts[-20:]
            tx_avg = sum(recent_tx) / len(recent_tx)
            early_avg = sum(recent_tx[:10]) / 10
            late_avg = sum(recent_tx[10:]) / 10

            if early_avg > 0 and (late_avg / early_avg) > 1.5:
                growth_content = {
                    'type': 'network_growth_inference',
                    'pattern': 'tx_volume_growth',
                    'early_avg': round(early_avg, 2),
                    'late_avg': round(late_avg, 2),
                    'growth_ratio': round(late_avg / early_avg, 2),
                    'block_height': block_height,
                }
                g_node = self.kg.add_node(
                    node_type='inference',
                    content=growth_content,
                    confidence=0.65,
                    source_block=block_height,
                )
                self.kg.add_edge(t_node.node_id, g_node.node_id, 'supports')
                nodes_created += 1

        return nodes_created

    def _link_to_previous_block(self, node_id: int, block_height: int) -> None:
        """Link current block observation to the previous block's observation."""
        prev_height = block_height - 1
        for nid, node in self.kg.nodes.items():
            if (node.content.get('type') == 'block_observation'
                    and node.content.get('height') == prev_height):
                self.kg.add_edge(nid, node_id, 'derives')
                break

    def get_stats(self) -> dict:
        """Get knowledge extraction statistics."""
        avg_difficulty = (sum(self._difficulties) / len(self._difficulties)
                          if self._difficulties else 0)
        avg_tx_count = (sum(self._tx_counts) / len(self._tx_counts)
                        if self._tx_counts else 0)

        return {
            'blocks_processed': self._blocks_processed,
            'window_size': self._window_size,
            'avg_difficulty': round(avg_difficulty, 6),
            'avg_tx_count': round(avg_tx_count, 2),
            'difficulty_samples': len(self._difficulties),
            'energy_samples': len(self._energies),
        }
