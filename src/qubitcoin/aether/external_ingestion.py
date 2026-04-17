"""
External Data Ingestion — Feed Real-World Knowledge into KG

AI Roadmap Item #49: Ingest data from external sources to ground the
Aether Tree's knowledge in real-world information:
  - Blockchain metrics (from the local node's own chain data)
  - Crypto market data (CoinGecko free API)
  - Network status indicators

All data ingested becomes grounded knowledge nodes with
`grounding_source = 'external'` to distinguish from derived knowledge.

Uses only stdlib + aiohttp/requests for HTTP. No API keys required
for the free-tier endpoints used here.
"""
import time
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExternalDataIngestion:
    """Ingest external data into the Aether Tree knowledge graph.

    Designed to run periodically (every N blocks) as part of the
    AetherEngine block processing loop. Each source has its own
    cooldown to prevent excessive API calls.
    """

    def __init__(self, knowledge_graph: object = None) -> None:
        self.kg = knowledge_graph
        # Cooldown tracking: source_name -> last_fetch_timestamp
        self._last_fetch: Dict[str, float] = {}
        # Stats
        self._nodes_ingested: int = 0
        self._fetch_errors: int = 0
        self._fetch_successes: int = 0
        # Minimum seconds between fetches per source
        self._cooldowns: Dict[str, int] = {
            'chain_metrics': 30,    # Every ~10 blocks
            'market_data': 300,     # Every 5 minutes
            'network_status': 60,   # Every minute
        }

    def _should_fetch(self, source: str) -> bool:
        """Check if enough time has passed since last fetch."""
        cooldown = self._cooldowns.get(source, 60)
        last = self._last_fetch.get(source, 0)
        return (time.time() - last) >= cooldown

    def ingest_chain_metrics(self, block_data: dict, block_height: int) -> int:
        """Ingest on-chain metrics from the current block.

        This is the primary grounding source — real blockchain data
        from the local node. Creates observation nodes with
        grounding_source='chain_data'.

        Args:
            block_data: Dict with block metadata (difficulty, tx_count, etc.)
            block_height: Current block height.

        Returns:
            Number of nodes created.
        """
        if not self.kg or not self._should_fetch('chain_metrics'):
            return 0

        self._last_fetch['chain_metrics'] = time.time()
        created = 0

        # Extract meaningful metrics
        metrics = {
            'difficulty': block_data.get('difficulty'),
            'tx_count': block_data.get('tx_count', 0),
            'block_reward': block_data.get('reward'),
            'energy': block_data.get('energy'),
            'total_supply': block_data.get('total_supply'),
        }

        for metric_name, value in metrics.items():
            if value is None:
                continue
            try:
                node = self.kg.add_node(
                    node_type='observation',
                    content={
                        'type': 'chain_metric',
                        'metric': metric_name,
                        'value': float(value),
                        'block_height': block_height,
                        'text': f"{metric_name}={value} at block {block_height}",
                        'domain': 'chain_data',
                    },
                    confidence=0.95,  # High confidence — this is ground truth
                    source_block=block_height,
                )
                if node:
                    node.grounding_source = 'chain_data'
                    created += 1
            except Exception as e:
                logger.debug(f"Chain metric ingestion error ({metric_name}): {e}")

        self._nodes_ingested += created
        self._fetch_successes += 1
        return created

    def ingest_network_status(self, health_data: dict, block_height: int) -> int:
        """Ingest network health data as grounded observations.

        Args:
            health_data: Dict from /health endpoint (component statuses).
            block_height: Current block height.

        Returns:
            Number of nodes created.
        """
        if not self.kg or not self._should_fetch('network_status'):
            return 0

        self._last_fetch['network_status'] = time.time()
        created = 0

        # Extract component health
        components = health_data.get('components', {})
        healthy_count = sum(1 for v in components.values()
                           if v in (True, 'healthy', 'running'))
        total_count = len(components)

        if total_count > 0:
            health_pct = healthy_count / total_count
            try:
                node = self.kg.add_node(
                    node_type='observation',
                    content={
                        'type': 'network_health',
                        'healthy_components': healthy_count,
                        'total_components': total_count,
                        'health_pct': round(health_pct, 3),
                        'text': (f"Network health: {healthy_count}/{total_count} "
                                 f"components healthy ({health_pct:.0%})"),
                        'domain': 'network',
                    },
                    confidence=0.9,
                    source_block=block_height,
                )
                if node:
                    node.grounding_source = 'network_status'
                    created += 1
            except Exception as e:
                logger.debug(f"Network status ingestion error: {e}")

        self._nodes_ingested += created
        return created

    def ingest_market_data_sync(self, block_height: int) -> int:
        """Ingest crypto market data from CoinGecko free API (synchronous).

        Uses the free /simple/price endpoint — no API key needed.
        Creates market observation nodes for BTC, ETH prices.

        Args:
            block_height: Current block height.

        Returns:
            Number of nodes created.
        """
        if not self.kg or not self._should_fetch('market_data'):
            return 0

        self._last_fetch['market_data'] = time.time()

        try:
            import urllib.request
            import json

            url = (
                "https://api.coingecko.com/api/v3/simple/price"
                "?ids=bitcoin,ethereum&vs_currencies=usd"
                "&include_24hr_change=true"
            )
            req = urllib.request.Request(url, headers={
                'User-Agent': 'QBC-Aether/1.0',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

        except Exception as e:
            self._fetch_errors += 1
            logger.debug(f"Market data fetch failed: {e}")
            return 0

        created = 0
        for coin_id, prices in data.items():
            usd_price = prices.get('usd')
            change_24h = prices.get('usd_24h_change')
            if usd_price is None:
                continue

            try:
                node = self.kg.add_node(
                    node_type='observation',
                    content={
                        'type': 'market_data',
                        'coin': coin_id,
                        'price_usd': float(usd_price),
                        'change_24h': float(change_24h) if change_24h else 0.0,
                        'text': (f"{coin_id.upper()} price: ${usd_price:,.2f} "
                                 f"({change_24h:+.2f}% 24h)" if change_24h
                                 else f"{coin_id.upper()} price: ${usd_price:,.2f}"),
                        'domain': 'market',
                    },
                    confidence=0.85,
                    source_block=block_height,
                )
                if node:
                    node.grounding_source = 'coingecko'
                    created += 1
            except Exception as e:
                logger.debug(f"Market node creation error ({coin_id}): {e}")

        self._nodes_ingested += created
        if created > 0:
            self._fetch_successes += 1
        return created

    def process_block(self, block_height: int, block_data: dict,
                      health_data: Optional[dict] = None) -> Dict[str, int]:
        """Run all ingestion sources for a block.

        Args:
            block_height: Current block height.
            block_data: Block metadata dict.
            health_data: Optional health endpoint data.

        Returns:
            Dict of nodes created per source.
        """
        results: Dict[str, int] = {}

        # Always ingest chain metrics (every ~10 blocks)
        results['chain_metrics'] = self.ingest_chain_metrics(block_data, block_height)

        # Network status (every ~20 blocks)
        if health_data:
            results['network_status'] = self.ingest_network_status(
                health_data, block_height
            )

        # Market data (every ~90 blocks = ~5 minutes)
        if block_height % 90 == 0:
            results['market_data'] = self.ingest_market_data_sync(block_height)

        return results

    def get_stats(self) -> dict:
        return {
            'nodes_ingested': self._nodes_ingested,
            'fetch_successes': self._fetch_successes,
            'fetch_errors': self._fetch_errors,
            'last_fetch': {k: round(v, 1) for k, v in self._last_fetch.items()},
        }
