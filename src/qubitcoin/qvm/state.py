"""
QVM State Manager
Handles transaction routing, state root computation, and QVM integration with QBC chain
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from .vm import QVM, ExecutionResult
from ..database.models import Transaction, TransactionReceipt, Account, Block
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── EIP-2930 Access List Support ─────────────────────────────────────────
# Gas costs per EIP-2930 specification
ACCESS_LIST_ADDRESS_COST: int = 2400   # Gas per address in access list
ACCESS_LIST_STORAGE_KEY_COST: int = 1900  # Gas per storage key in access list


@dataclass
class AccessListEntry:
    """A single entry in an EIP-2930 access list.

    Each entry pre-declares an account address and a set of storage keys
    that the transaction intends to access, allowing them to be loaded into
    the "warm" cache before execution begins.

    Attributes:
        address: The hex account address (40 chars, no 0x prefix).
        storage_keys: List of storage slot keys (hex strings) to pre-warm.
    """
    address: str
    storage_keys: List[str] = field(default_factory=list)


def calculate_base_fee(parent_gas_used: int, parent_gas_limit: int,
                       parent_base_fee: int) -> int:
    """Calculate the EIP-1559 base fee for the next block.

    The gas target is ``parent_gas_limit // EIP1559_ELASTICITY_MULTIPLIER``.
    If the parent block used more gas than the target, the base fee increases;
    if less, it decreases.  The maximum change per block is bounded by
    ``1 / EIP1559_BASE_FEE_CHANGE_DENOMINATOR`` of the parent base fee.

    The base fee has a floor of 1 (never reaches zero).

    Args:
        parent_gas_used: Gas consumed by the parent block.
        parent_gas_limit: Gas limit of the parent block.
        parent_base_fee: Base fee of the parent block (wei).

    Returns:
        The base fee for the next block (wei).
    """
    elasticity = Config.EIP1559_ELASTICITY_MULTIPLIER
    denominator = Config.EIP1559_BASE_FEE_CHANGE_DENOMINATOR
    gas_target = parent_gas_limit // elasticity

    if gas_target == 0:
        return parent_base_fee

    if parent_gas_used == gas_target:
        # Exactly at target -- no change
        return parent_base_fee

    if parent_gas_used > gas_target:
        # Above target -- increase base fee
        gas_used_delta = parent_gas_used - gas_target
        fee_delta = max(
            parent_base_fee * gas_used_delta // gas_target // denominator,
            1,  # Ensure at least +1 when rounding would give 0
        )
        return parent_base_fee + fee_delta

    # Below target -- decrease base fee
    gas_used_delta = gas_target - parent_gas_used
    fee_delta = parent_base_fee * gas_used_delta // gas_target // denominator
    return max(parent_base_fee - fee_delta, 1)  # Floor at 1


class StateManager:
    """
    Manages world state and routes transactions between UTXO and QVM
    Computes state root after block execution
    """

    def __init__(self, db_manager, quantum_engine=None, compliance_engine=None):
        self.db = db_manager
        self.quantum = quantum_engine
        self.compliance = compliance_engine
        self.qvm = QVM(db_manager, quantum_engine, compliance_engine=compliance_engine)
        self.event_index = None  # Injected by node after EventIndex init
        self.current_base_fee: int = Config.EIP1559_INITIAL_BASE_FEE

        # EIP-2930 warm caches — reset per transaction via clear_access_list()
        self.warm_addresses: Set[str] = set()
        self.warm_storage_keys: Set[Tuple[str, str]] = set()

    def set_block_context(self, block_height: int, timestamp: float, coinbase: str, difficulty: float) -> None:
        """Update QVM block context before executing transactions"""
        self.qvm.block = {
            'number': block_height,
            'timestamp': int(timestamp),
            'coinbase': coinbase,
            'prevrandao': int(hashlib.sha256(str(block_height).encode()).hexdigest()[:16], 16),
            'basefee': self.current_base_fee,
        }

    def update_base_fee(self, parent_gas_used: int, parent_gas_limit: int) -> int:
        """Recalculate the base fee after a parent block and update internal state.

        This should be called once per block, passing the parent block's gas
        usage and limit.  The new base fee is stored in ``self.current_base_fee``
        and will be used by subsequent ``set_block_context`` calls.

        Args:
            parent_gas_used: Total gas consumed by the parent block.
            parent_gas_limit: Gas limit of the parent block.

        Returns:
            The updated base fee for the current block.
        """
        self.current_base_fee = calculate_base_fee(
            parent_gas_used, parent_gas_limit, self.current_base_fee
        )
        logger.debug(
            f"EIP-1559 base fee updated: {self.current_base_fee} "
            f"(parent used {parent_gas_used}/{parent_gas_limit})"
        )
        return self.current_base_fee

    # ── EIP-2930 Access List Methods ────────────────────────────────────

    def apply_access_list(self, access_list: List[AccessListEntry]) -> int:
        """Pre-warm addresses and storage keys from an EIP-2930 access list.

        Marks each address and storage key as "warm" so that subsequent
        SLOAD / SSTORE / BALANCE / EXTCODE* opcodes use the cheaper warm
        gas cost instead of the cold cost.

        Gas charges per EIP-2930:
          - 2400 gas per address entry
          - 1900 gas per storage key entry

        Args:
            access_list: List of AccessListEntry items declaring addresses
                         and storage keys to pre-warm.

        Returns:
            Total gas cost for the access list pre-warming.
        """
        total_gas: int = 0
        for entry in access_list:
            addr = entry.address.lower()
            self.warm_addresses.add(addr)
            total_gas += ACCESS_LIST_ADDRESS_COST

            for key in entry.storage_keys:
                self.warm_storage_keys.add((addr, key.lower()))
                total_gas += ACCESS_LIST_STORAGE_KEY_COST

        logger.debug(
            f"EIP-2930 access list applied: {len(access_list)} addresses, "
            f"{sum(len(e.storage_keys) for e in access_list)} storage keys, "
            f"{total_gas} gas"
        )
        return total_gas

    def clear_access_list(self) -> None:
        """Reset warm caches between transactions."""
        self.warm_addresses.clear()
        self.warm_storage_keys.clear()

    def is_address_warm(self, address: str) -> bool:
        """Check if an address has been pre-warmed by an access list.

        Args:
            address: The hex account address to check.

        Returns:
            True if the address is in the warm cache.
        """
        return address.lower() in self.warm_addresses

    def is_storage_key_warm(self, address: str, key: str) -> bool:
        """Check if a specific storage slot has been pre-warmed.

        Args:
            address: The hex account address.
            key: The storage slot key.

        Returns:
            True if the (address, key) pair is in the warm cache.
        """
        return (address.lower(), key.lower()) in self.warm_storage_keys

    def process_transaction(self, tx: Transaction, block_height: int, block_hash: str, tx_index: int) -> Optional[TransactionReceipt]:
        """
        Route transaction to appropriate execution path

        Args:
            tx: Transaction to process
            block_height: Current block height
            block_hash: Current block hash
            tx_index: Index of transaction in block

        Returns:
            TransactionReceipt for QVM transactions, None for UTXO-only
        """
        if tx.tx_type == 'transfer':
            # Pure UTXO transfer — handled by existing consensus/mining pipeline
            return None

        if tx.tx_type == 'contract_deploy':
            return self._deploy_contract(tx, block_height, block_hash, tx_index)

        if tx.tx_type == 'contract_call':
            return self._call_contract(tx, block_height, block_hash, tx_index)

        return None

    def _check_compliance(self, from_addr: str, tx: Transaction,
                          block_height: int, block_hash: str,
                          tx_index: int) -> Optional[TransactionReceipt]:
        """Pre-execution compliance check.

        If the sender is blocked (sanctions, AML, or policy), returns a
        failed receipt immediately so the caller can short-circuit before
        executing any QVM code.  Returns None if the address passes.
        """
        if not self.compliance:
            return None

        try:
            if not self.compliance.is_address_blocked(from_addr):
                return None

            # Also check circuit breaker — if tripped, block all executions
            reason = f"Compliance: address {from_addr[:12]}... is blocked"

            # Check sanctions for a more specific reason
            screening = self.compliance.screen_sanctions(from_addr)
            if screening.get('sanctioned'):
                sources = ', '.join(screening.get('sources', []))
                reason = f"Compliance: address sanctioned ({sources})"

            logger.warning(reason)

            receipt = TransactionReceipt(
                txid=tx.txid,
                block_height=block_height,
                block_hash=block_hash,
                tx_index=tx_index,
                from_address=from_addr,
                to_address=tx.to_address or None,
                contract_address=None,
                gas_used=21000,  # Base gas charged even on compliance rejection
                gas_limit=tx.gas_limit or Config.BLOCK_GAS_LIMIT,
                status=0,
                revert_reason=reason,
            )
            self.db.store_receipt(receipt)
            return receipt

        except Exception as e:
            logger.debug(f"Compliance check error (allowing tx): {e}")
            return None

    def _deploy_contract(self, tx: Transaction, block_height: int, block_hash: str, tx_index: int) -> TransactionReceipt:
        """Deploy a new contract via QVM"""
        from_addr = self._get_sender_address(tx)

        # Pre-execution compliance gate
        blocked_receipt = self._check_compliance(from_addr, tx, block_height, block_hash, tx_index)
        if blocked_receipt is not None:
            return blocked_receipt

        hex_data = tx.data.removeprefix('0x') if tx.data else ''
        try:
            bytecode = bytes.fromhex(hex_data) if hex_data else b''
        except ValueError:
            bytecode = b''

        # Derive contract address: keccak256(RLP([sender, nonce]))[:20]
        # Matches the EVM CREATE opcode specification in vm.py
        account = self.db.get_or_create_account(from_addr)
        from .vm import rlp_encode_create_address
        addr_hash = rlp_encode_create_address(from_addr, account.nonce).hex()

        # Execute init code
        result = self.qvm.execute(
            caller=from_addr,
            address=addr_hash,
            code=bytecode,
            data=b'',
            value=0,
            gas=tx.gas_limit or Config.BLOCK_GAS_LIMIT,
            origin=from_addr,
        )

        # Create contract account and store bytecode
        if result.success and result.return_data:
            contract_code_hash = hashlib.sha256(result.return_data).hexdigest()
            contract_account = Account(
                address=addr_hash,
                nonce=0,
                balance=Decimal(0),
                code_hash=contract_code_hash,
            )
            with self.db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text("""
                        INSERT INTO accounts (address, nonce, balance, code_hash, storage_root, bytecode)
                        VALUES (:addr, 0, 0, :code_hash, '', :bytecode)
                        ON CONFLICT (address) DO UPDATE SET
                            code_hash = :code_hash, bytecode = :bytecode
                    """),
                    {
                        'addr': addr_hash,
                        'code_hash': contract_code_hash,
                        'bytecode': result.return_data.hex()
                    }
                )
                session.commit()

            # Flush storage changes
            self._flush_storage(result, block_height)

        # Increment sender nonce
        account.nonce += 1
        self.db.update_account(account)

        receipt = TransactionReceipt(
            txid=tx.txid,
            block_height=block_height,
            block_hash=block_hash,
            tx_index=tx_index,
            from_address=from_addr,
            to_address=None,
            contract_address=addr_hash if result.success else None,
            gas_used=result.gas_used,
            gas_limit=tx.gas_limit or Config.BLOCK_GAS_LIMIT,
            status=1 if result.success else 0,
            logs=result.logs,
            return_data=result.return_data.hex(),
            revert_reason=result.revert_reason,
        )

        self.db.store_receipt(receipt)
        self._index_receipt_events(receipt, block_hash)
        logger.info(f"Contract deployed: {addr_hash} (gas: {result.gas_used})")
        return receipt

    def _call_contract(self, tx: Transaction, block_height: int, block_hash: str, tx_index: int) -> TransactionReceipt:
        """Call an existing contract via QVM"""
        from_addr = self._get_sender_address(tx)

        # Pre-execution compliance gate
        blocked_receipt = self._check_compliance(from_addr, tx, block_height, block_hash, tx_index)
        if blocked_receipt is not None:
            return blocked_receipt

        to_addr = tx.to_address or ''
        hex_data = tx.data.removeprefix('0x') if tx.data else ''
        try:
            calldata = bytes.fromhex(hex_data) if hex_data else b''
        except ValueError:
            calldata = b''

        # Load contract bytecode
        code = b''
        if self.db:
            bytecode_hex = self.db.get_contract_bytecode(to_addr)
            if bytecode_hex:
                code = bytes.fromhex(bytecode_hex)

        if not code:
            receipt = TransactionReceipt(
                txid=tx.txid, block_height=block_height, block_hash=block_hash,
                tx_index=tx_index, from_address=from_addr, to_address=to_addr,
                contract_address=None, gas_used=21000, gas_limit=tx.gas_limit or 21000,
                status=0, revert_reason="Contract not found"
            )
            self.db.store_receipt(receipt)
            return receipt

        value_wei = int(tx.outputs[0]['amount'] * 10**8) if tx.outputs else 0

        result = self.qvm.execute(
            caller=from_addr,
            address=to_addr,
            code=code,
            data=calldata,
            value=value_wei,
            gas=tx.gas_limit or Config.BLOCK_GAS_LIMIT,
            origin=from_addr,
        )

        # Flush storage changes
        if result.success:
            self._flush_storage(result, block_height)

        # Increment sender nonce
        account = self.db.get_or_create_account(from_addr)
        account.nonce += 1
        self.db.update_account(account)

        receipt = TransactionReceipt(
            txid=tx.txid,
            block_height=block_height,
            block_hash=block_hash,
            tx_index=tx_index,
            from_address=from_addr,
            to_address=to_addr,
            contract_address=None,
            gas_used=result.gas_used,
            gas_limit=tx.gas_limit or Config.BLOCK_GAS_LIMIT,
            status=1 if result.success else 0,
            logs=result.logs,
            return_data=result.return_data.hex(),
            revert_reason=result.revert_reason,
        )

        self.db.store_receipt(receipt)
        self._index_receipt_events(receipt, block_hash)
        return receipt

    def _flush_storage(self, result: ExecutionResult, block_height: int):
        """Write QVM storage changes to database"""
        for addr, changes in result.storage_changes.items():
            for key, value in changes.items():
                self.db.set_storage(addr, key, value, block_height)

    def _index_receipt_events(
        self, receipt: TransactionReceipt, block_hash: str
    ) -> None:
        """Feed receipt logs into the EventIndex if available."""
        if not self.event_index or not receipt.logs:
            return
        try:
            for i, log in enumerate(receipt.logs):
                self.event_index.add_from_log_dict(
                    log,
                    block_height=receipt.block_height,
                    block_hash=block_hash,
                    tx_hash=receipt.txid,
                    tx_index=receipt.tx_index,
                    log_index=i,
                )
        except Exception as e:
            logger.debug(f"Event indexing skipped: {e}")

    def _get_sender_address(self, tx: Transaction) -> str:
        """Derive sender address from transaction (consistent with crypto.derive_address)"""
        if tx.public_key:
            return hashlib.sha256(bytes.fromhex(tx.public_key)).hexdigest()[:40]
        return '0' * 40

    def compute_state_root(self, block_height: int) -> str:
        """
        Compute state root hash from all accounts at given height.
        Simple Merkle root over sorted account states.
        """
        with self.db.get_session() as session:
            from sqlalchemy import text
            rows = session.execute(
                text("SELECT address, nonce, balance, code_hash, storage_root FROM accounts ORDER BY address")
            )
            leaves = []
            for row in rows:
                leaf = hashlib.sha256(
                    f"{row[0]}:{row[1]}:{row[2]}:{row[3]}:{row[4]}".encode()
                ).hexdigest()
                leaves.append(leaf)

        if not leaves:
            return hashlib.sha256(b'empty_state').hexdigest()

        # Simple Merkle tree
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = hashlib.sha256(
                    (leaves[i] + leaves[i + 1]).encode()
                ).hexdigest()
                new_leaves.append(combined)
            leaves = new_leaves

        return leaves[0]

    def compute_receipts_root(self, receipts: List[TransactionReceipt]) -> str:
        """Compute Merkle root of transaction receipts"""
        if not receipts:
            return hashlib.sha256(b'empty_receipts').hexdigest()

        leaves = []
        for r in receipts:
            leaf = hashlib.sha256(
                json.dumps(r.to_dict(), sort_keys=True).encode()
            ).hexdigest()
            leaves.append(leaf)

        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = hashlib.sha256(
                    (leaves[i] + leaves[i + 1]).encode()
                ).hexdigest()
                new_leaves.append(combined)
            leaves = new_leaves

        return leaves[0]

    def execute_block_transactions(self, block: Block) -> Tuple[str, str]:
        """
        Execute all QVM transactions in a block, compute state and receipts roots.

        Args:
            block: Block with transactions to execute

        Returns:
            (state_root, receipts_root) tuple
        """
        self.set_block_context(
            block.height, block.timestamp,
            block.proof_data.get('miner_address', '0' * 40),
            block.difficulty
        )

        receipts = []
        for i, tx in enumerate(block.transactions):
            receipt = self.process_transaction(
                tx, block.height,
                block.block_hash or block.calculate_hash(),
                i
            )
            if receipt:
                receipts.append(receipt)

        state_root = self.compute_state_root(block.height)
        receipts_root = self.compute_receipts_root(receipts)

        return state_root, receipts_root


class QuantumStateStore:
    """In-memory + DB-backed store for quantum state density matrices.

    Each quantum state is keyed by a ``state_id`` (uint256 from QCREATE).
    The store records the number of qubits, the creating contract address,
    the block height, and whether the state has been measured (collapsed).

    This is the implementation behind the QSP (Quantum State Persistence)
    patent feature described in the QVM whitepaper.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager
        # Fast in-memory index: state_id → state dict
        self._states: Dict[int, dict] = {}

    def create(self, state_id: int, n_qubits: int, contract_address: str,
               block_height: int) -> dict:
        """Register a new quantum state.

        Args:
            state_id: Unique identifier (hash from QCREATE).
            n_qubits: Number of qubits in the density matrix.
            contract_address: Contract that created the state.
            block_height: Block in which the state was created.

        Returns:
            The stored state record.
        """
        record = {
            'state_id': state_id,
            'n_qubits': n_qubits,
            'contract_address': contract_address,
            'block_height': block_height,
            'measured': False,
            'entangled_with': None,
        }
        self._states[state_id] = record
        self._persist(record)
        return record

    def get(self, state_id: int) -> Optional[dict]:
        """Retrieve a quantum state by ID."""
        if state_id in self._states:
            return self._states[state_id]
        return self._load(state_id)

    def measure(self, state_id: int) -> bool:
        """Mark a state as measured (collapsed). Returns False if not found."""
        state = self.get(state_id)
        if state is None:
            return False
        state['measured'] = True
        self._states[state_id] = state
        self._persist(state)
        return True

    def entangle(self, state_a: int, state_b: int) -> bool:
        """Record an entanglement link between two states."""
        a = self.get(state_a)
        b = self.get(state_b)
        if a is None or b is None:
            return False
        a['entangled_with'] = state_b
        b['entangled_with'] = state_a
        self._states[state_a] = a
        self._states[state_b] = b
        self._persist(a)
        self._persist(b)
        return True

    def delete(self, state_id: int) -> bool:
        """Remove a quantum state (e.g. after measurement and consumption)."""
        if state_id in self._states:
            del self._states[state_id]
            return True
        return False

    def list_states(self, contract_address: Optional[str] = None) -> list:
        """Return all states, optionally filtered by contract address."""
        states = list(self._states.values())
        if contract_address:
            states = [s for s in states if s['contract_address'] == contract_address]
        return states

    def compute_state_root(self) -> str:
        """Compute Merkle root over all quantum states.

        Returns a 64-char hex digest.  Empty set → hash of 'empty_quantum'.
        """
        if not self._states:
            return hashlib.sha256(b'empty_quantum').hexdigest()

        leaves = []
        for sid in sorted(self._states.keys()):
            s = self._states[sid]
            leaf_data = (
                f"{s['state_id']}:{s['n_qubits']}:{s['contract_address']}:"
                f"{s['block_height']}:{s['measured']}:{s['entangled_with']}"
            )
            leaves.append(hashlib.sha256(leaf_data.encode()).hexdigest())

        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = hashlib.sha256(
                    (leaves[i] + leaves[i + 1]).encode()
                ).hexdigest()
                new_leaves.append(combined)
            leaves = new_leaves

        return leaves[0]

    # ── Persistence helpers ──────────────────────────────────────────
    def _persist(self, record: dict) -> None:
        """Write state record to CockroachDB if available."""
        if not self.db:
            return
        try:
            with self.db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text("""
                        UPSERT INTO quantum_states
                            (state_id, n_qubits, contract_address,
                             block_height, measured, entangled_with)
                        VALUES (:sid, :nq, :ca, :bh, :m, :ew)
                    """),
                    {
                        'sid': str(record['state_id']),
                        'nq': record['n_qubits'],
                        'ca': record['contract_address'],
                        'bh': record['block_height'],
                        'm': record['measured'],
                        'ew': str(record['entangled_with']) if record['entangled_with'] else None,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Quantum state persist skipped: {e}")

    def _load(self, state_id: int) -> Optional[dict]:
        """Load a state from the DB (fallback when not in memory)."""
        if not self.db:
            return None
        try:
            with self.db.get_session() as session:
                from sqlalchemy import text
                row = session.execute(
                    text("SELECT state_id, n_qubits, contract_address, "
                         "block_height, measured, entangled_with "
                         "FROM quantum_states WHERE state_id = :sid"),
                    {'sid': str(state_id)},
                ).fetchone()
                if row:
                    record = {
                        'state_id': int(row[0]),
                        'n_qubits': row[1],
                        'contract_address': row[2],
                        'block_height': row[3],
                        'measured': row[4],
                        'entangled_with': int(row[5]) if row[5] else None,
                    }
                    self._states[state_id] = record
                    return record
        except Exception as e:
            logger.debug(f"Quantum state load skipped: {e}")
        return None
