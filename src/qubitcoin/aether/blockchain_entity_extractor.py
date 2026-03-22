"""
Blockchain Entity Extractor — Extract structured entities from blockchain data

Item #43: Extracts entities (addresses, amounts, block refs, tx refs, contract refs,
token names, timestamps) from blocks, transactions, and contract events.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Entity:
    """A structured entity extracted from blockchain data."""
    entity_type: str    # Address, Amount, BlockRef, TxRef, ContractRef, TokenName, Timestamp
    value: Any          # The extracted value (string, number, etc.)
    confidence: float   # 0.0–1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    kg_node_id: Optional[int] = None  # Linked KG node ID (if resolvable)


# Well-known contract names (for entity enrichment)
_KNOWN_CONTRACTS = {
    "qusd", "qbc-20", "qbc-721", "aethertree", "higgsfield",
    "susytoken", "bridgelock", "governance", "timereversalvault",
    "launchpad", "staking", "rewards",
}

# Well-known token names
_KNOWN_TOKENS = {
    "qbc", "qusd", "wqbc", "wqusd", "eth", "btc", "sol",
    "matic", "bnb", "avax", "arb", "op", "base",
}


class BlockchainEntityExtractor:
    """Extract structured entities from blockchain data structures."""

    def __init__(self, knowledge_graph: Optional[Any] = None) -> None:
        self._kg = knowledge_graph
        self._blocks_processed: int = 0
        self._txs_processed: int = 0
        self._events_processed: int = 0
        self._entities_extracted: int = 0
        self._total_time: float = 0.0

    # ------------------------------------------------------------------
    # Block extraction
    # ------------------------------------------------------------------

    def extract_from_block(self, block_data: dict) -> List[Entity]:
        """Extract entities from a block data dict.

        Args:
            block_data: Dict with keys like height, timestamp, difficulty,
                        miner_address, transactions, reward, etc.

        Returns:
            List of Entity objects extracted from the block.
        """
        t0 = time.time()
        entities: List[Entity] = []

        # Block height
        height = block_data.get("height") or block_data.get("block_height")
        if height is not None:
            entities.append(Entity(
                entity_type="BlockRef",
                value=int(height),
                confidence=1.0,
                metadata={"source": "block_header"},
            ))

        # Timestamp
        ts = block_data.get("timestamp")
        if ts is not None:
            entities.append(Entity(
                entity_type="Timestamp",
                value=ts,
                confidence=1.0,
                metadata={"source": "block_header"},
            ))

        # Miner address
        miner = block_data.get("miner_address") or block_data.get("miner")
        if miner and isinstance(miner, str) and len(miner) >= 10:
            entities.append(Entity(
                entity_type="Address",
                value=miner,
                confidence=1.0,
                metadata={"role": "miner", "source": "block_header"},
            ))

        # Difficulty
        diff = block_data.get("difficulty")
        if diff is not None:
            entities.append(Entity(
                entity_type="Amount",
                value=float(diff),
                confidence=0.95,
                metadata={"kind": "difficulty", "source": "block_header"},
            ))

        # Block reward
        reward = block_data.get("reward") or block_data.get("block_reward")
        if reward is not None:
            entities.append(Entity(
                entity_type="Amount",
                value=float(reward),
                confidence=1.0,
                metadata={"kind": "block_reward", "unit": "QBC", "source": "block_header"},
            ))

        # Energy (VQE)
        energy = block_data.get("energy") or block_data.get("ground_state_energy")
        if energy is not None:
            entities.append(Entity(
                entity_type="Amount",
                value=float(energy),
                confidence=0.95,
                metadata={"kind": "vqe_energy", "source": "proof_data"},
            ))

        # Block hash
        bhash = block_data.get("hash") or block_data.get("block_hash")
        if bhash and isinstance(bhash, str):
            entities.append(Entity(
                entity_type="TxRef",
                value=bhash,
                confidence=1.0,
                metadata={"kind": "block_hash", "source": "block_header"},
            ))

        # Previous block hash
        prev_hash = block_data.get("prev_block_hash") or block_data.get("previous_hash")
        if prev_hash and isinstance(prev_hash, str):
            entities.append(Entity(
                entity_type="BlockRef",
                value=prev_hash,
                confidence=1.0,
                metadata={"kind": "prev_block_hash", "source": "block_header"},
            ))

        # Extract from embedded transactions
        txs = block_data.get("transactions", [])
        if isinstance(txs, list):
            for tx in txs:
                if isinstance(tx, dict):
                    entities.extend(self.extract_from_transaction(tx))

        self._blocks_processed += 1
        self._entities_extracted += len(entities)
        self._total_time += time.time() - t0

        # Link to KG nodes
        self._link_to_kg(entities, block_height=height)

        return entities

    # ------------------------------------------------------------------
    # Transaction extraction
    # ------------------------------------------------------------------

    def extract_from_transaction(self, tx_data: dict) -> List[Entity]:
        """Extract entities from a transaction data dict.

        Args:
            tx_data: Dict with keys like tx_hash, sender, recipient, amount,
                     tx_type, contract_address, etc.

        Returns:
            List of Entity objects.
        """
        t0 = time.time()
        entities: List[Entity] = []

        # TX hash
        tx_hash = tx_data.get("tx_hash") or tx_data.get("hash") or tx_data.get("txid")
        if tx_hash and isinstance(tx_hash, str):
            entities.append(Entity(
                entity_type="TxRef",
                value=tx_hash,
                confidence=1.0,
                metadata={"source": "transaction"},
            ))

        # Sender
        sender = tx_data.get("sender") or tx_data.get("from") or tx_data.get("from_address")
        if sender and isinstance(sender, str) and len(sender) >= 10:
            entities.append(Entity(
                entity_type="Address",
                value=sender,
                confidence=1.0,
                metadata={"role": "sender", "source": "transaction"},
            ))

        # Recipient
        recipient = (tx_data.get("recipient") or tx_data.get("to")
                     or tx_data.get("to_address"))
        if recipient and isinstance(recipient, str) and len(recipient) >= 10:
            entities.append(Entity(
                entity_type="Address",
                value=recipient,
                confidence=1.0,
                metadata={"role": "recipient", "source": "transaction"},
            ))

        # Amount
        amount = tx_data.get("amount") or tx_data.get("value")
        if amount is not None:
            try:
                entities.append(Entity(
                    entity_type="Amount",
                    value=float(amount),
                    confidence=1.0,
                    metadata={"unit": "QBC", "source": "transaction"},
                ))
            except (ValueError, TypeError):
                pass

        # Fee
        fee = tx_data.get("fee") or tx_data.get("gas_price")
        if fee is not None:
            try:
                entities.append(Entity(
                    entity_type="Amount",
                    value=float(fee),
                    confidence=0.90,
                    metadata={"kind": "fee", "source": "transaction"},
                ))
            except (ValueError, TypeError):
                pass

        # TX type / contract info
        tx_type = tx_data.get("tx_type") or tx_data.get("type")
        if tx_type and isinstance(tx_type, str):
            if "contract" in tx_type.lower() or "deploy" in tx_type.lower():
                contract_addr = (tx_data.get("contract_address")
                                 or tx_data.get("creates"))
                if contract_addr:
                    entities.append(Entity(
                        entity_type="ContractRef",
                        value=contract_addr,
                        confidence=0.95,
                        metadata={"tx_type": tx_type, "source": "transaction"},
                    ))

        # Timestamp
        ts = tx_data.get("timestamp")
        if ts is not None:
            entities.append(Entity(
                entity_type="Timestamp",
                value=ts,
                confidence=1.0,
                metadata={"source": "transaction"},
            ))

        self._txs_processed += 1
        self._entities_extracted += len(entities)
        self._total_time += time.time() - t0
        return entities

    # ------------------------------------------------------------------
    # Contract event extraction
    # ------------------------------------------------------------------

    def extract_from_contract_event(self, event: dict) -> List[Entity]:
        """Extract entities from a contract event log.

        Args:
            event: Dict with keys like event_name, contract_address,
                   args, block_height, tx_hash, etc.

        Returns:
            List of Entity objects.
        """
        t0 = time.time()
        entities: List[Entity] = []

        # Contract address
        contract_addr = event.get("contract_address") or event.get("address")
        if contract_addr and isinstance(contract_addr, str):
            entities.append(Entity(
                entity_type="ContractRef",
                value=contract_addr,
                confidence=1.0,
                metadata={"source": "event"},
            ))

        # Event name as metadata
        event_name = event.get("event_name") or event.get("event") or event.get("name")

        # Block height
        bh = event.get("block_height") or event.get("blockNumber")
        if bh is not None:
            entities.append(Entity(
                entity_type="BlockRef",
                value=int(bh),
                confidence=1.0,
                metadata={"source": "event", "event_name": event_name},
            ))

        # TX hash
        tx_hash = event.get("tx_hash") or event.get("transactionHash")
        if tx_hash and isinstance(tx_hash, str):
            entities.append(Entity(
                entity_type="TxRef",
                value=tx_hash,
                confidence=1.0,
                metadata={"source": "event"},
            ))

        # Parse event args
        args = event.get("args") or event.get("data") or {}
        if isinstance(args, dict):
            for key, val in args.items():
                if val is None:
                    continue
                val_str = str(val)

                # Address-like args
                if isinstance(val, str) and (
                    (val.startswith("0x") and len(val) == 42)
                    or val.startswith("qbc1")
                ):
                    entities.append(Entity(
                        entity_type="Address",
                        value=val,
                        confidence=0.90,
                        metadata={
                            "arg_name": key, "source": "event_arg",
                            "event_name": event_name,
                        },
                    ))

                # Numeric args (amounts, IDs)
                elif isinstance(val, (int, float)):
                    kind = "amount" if "amount" in key.lower() or "value" in key.lower() else "numeric"
                    etype = "Amount" if kind == "amount" else "Amount"
                    entities.append(Entity(
                        entity_type=etype,
                        value=float(val),
                        confidence=0.85,
                        metadata={
                            "arg_name": key, "kind": kind, "source": "event_arg",
                            "event_name": event_name,
                        },
                    ))

                # Token names in args
                elif isinstance(val, str) and val.lower() in _KNOWN_TOKENS:
                    entities.append(Entity(
                        entity_type="TokenName",
                        value=val,
                        confidence=0.85,
                        metadata={
                            "arg_name": key, "source": "event_arg",
                            "event_name": event_name,
                        },
                    ))

        self._events_processed += 1
        self._entities_extracted += len(entities)
        self._total_time += time.time() - t0
        return entities

    # ------------------------------------------------------------------
    # KG linking
    # ------------------------------------------------------------------

    def _link_to_kg(self, entities: List[Entity],
                    block_height: Optional[int] = None) -> None:
        """Try to link entities to existing KG node IDs."""
        if not self._kg or not hasattr(self._kg, 'nodes'):
            return

        for ent in entities:
            if ent.kg_node_id is not None:
                continue

            # Try to find matching KG node
            if ent.entity_type == "BlockRef" and isinstance(ent.value, int):
                # Match block observation nodes by height
                for nid, node in self._kg.nodes.items():
                    content = getattr(node, 'content', None)
                    if isinstance(content, dict):
                        if content.get('height') == ent.value:
                            ent.kg_node_id = nid
                            break
                        if content.get('block_height') == ent.value:
                            ent.kg_node_id = nid
                            break

            elif ent.entity_type == "Address":
                # Match address nodes
                for nid, node in self._kg.nodes.items():
                    content = getattr(node, 'content', None)
                    if isinstance(content, dict):
                        if content.get('address') == ent.value:
                            ent.kg_node_id = nid
                            break
                        if content.get('miner_address') == ent.value:
                            ent.kg_node_id = nid
                            break

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return extractor statistics."""
        return {
            "blocks_processed": self._blocks_processed,
            "txs_processed": self._txs_processed,
            "events_processed": self._events_processed,
            "entities_extracted": self._entities_extracted,
            "total_time_s": round(self._total_time, 4),
            "avg_entities_per_block": (
                self._entities_extracted / self._blocks_processed
                if self._blocks_processed else 0.0
            ),
        }
