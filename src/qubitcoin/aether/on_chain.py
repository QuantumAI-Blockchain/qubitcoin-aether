"""
On-Chain AGI Integration — Phase 6

Bridges the Python AGI engine with deployed Solidity contracts via QVM.
Provides write operations (record Phi, submit proofs, veto operations)
and read operations (query on-chain state, governance parameters) using
the QVM ABI encoding layer.

Contract suite:
  - ConsciousnessDashboard: On-chain Phi measurements and events
  - ProofOfThought: PoT hash submission and validation
  - ConstitutionalAI: Safety principle enforcement and veto recording
  - TreasuryDAO: Community governance for fund allocation
  - UpgradeGovernor: Protocol upgrade governance
"""
import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..qvm.abi import (
    decode_bool,
    decode_uint256,
    encode_function_call,
    function_selector,
    encode_uint256,
    encode_address,
    encode_bytes32,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi precision multiplier (contract stores uint256 = phi_float * 1000)
PHI_PRECISION = 1000


class OnChainAGI:
    """
    Bridge between Python AGI engine and on-chain Solidity contracts.

    Uses QVM static_call() for reads and builds contract_call transactions
    for writes.  All writes go through the StateManager transaction pipeline
    to ensure proper gas accounting and state root updates.

    Requires:
      - state_manager: QVM StateManager with .qvm.static_call() and
        .process_transaction() methods.
      - Contract addresses configured in Config (set after deployment).
    """

    def __init__(self, state_manager: object) -> None:
        self._sm = state_manager
        self._qvm = getattr(state_manager, 'qvm', None)

        # Contract addresses (empty until deployed)
        self._dashboard_addr = Config.CONSCIOUSNESS_DASHBOARD_ADDRESS
        self._pot_addr = Config.PROOF_OF_THOUGHT_ADDRESS
        self._constitution_addr = Config.CONSTITUTIONAL_AI_ADDRESS
        self._treasury_addr = Config.TREASURY_DAO_ADDRESS
        self._governor_addr = Config.UPGRADE_GOVERNOR_ADDRESS
        self._kernel_addr = Config.AETHER_KERNEL_ADDRESS
        self._higgs_addr = getattr(Config, 'HIGGS_FIELD_ADDRESS', '')
        self._emergency_addr = getattr(Config, 'EMERGENCY_SHUTDOWN_ADDRESS', '')

        # Stats
        self._phi_writes: int = 0
        self._pot_submissions: int = 0
        self._veto_checks: int = 0
        self._governance_reads: int = 0
        self._errors: int = 0
        self._total_calls: int = 0

        # Read cache: key -> (result_bytes, block_height_cached)
        self._read_cache: OrderedDict = OrderedDict()
        self._cache_ttl_blocks: int = 10  # Cache static_call results for N blocks
        self._cache_max_entries: int = 256
        self._current_block: int = 0

        # Health tracking
        self._health_window_size: int = 100
        self._recent_results: list = []  # List of (timestamp, success_bool)

        addrs = sum(1 for a in [
            self._dashboard_addr, self._pot_addr, self._constitution_addr,
            self._treasury_addr, self._governor_addr,
        ] if a)
        logger.info(
            f"OnChainAGI initialized ({addrs}/5 contract addresses configured)"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _static_call(self, contract_addr: str, calldata: bytes,
                     use_cache: bool = True) -> Optional[bytes]:
        """Execute a read-only static call to a contract.

        Results are cached for ``_cache_ttl_blocks`` blocks to reduce
        QVM overhead on repeated reads of the same data.

        Returns raw return data bytes, or None on failure.
        """
        if not self._qvm or not contract_addr:
            return None

        self._total_calls += 1
        cache_key = f"{contract_addr}:{calldata.hex()}"

        # Check cache
        if use_cache and cache_key in self._read_cache:
            cached_result, cached_block = self._read_cache[cache_key]
            if self._current_block - cached_block <= self._cache_ttl_blocks:
                # Move to end (LRU)
                self._read_cache.move_to_end(cache_key)
                return cached_result

        try:
            caller = self._kernel_addr or '0' * 40
            result = self._qvm.static_call(caller, contract_addr, calldata)
            if result:
                # Store in cache
                self._read_cache[cache_key] = (result, self._current_block)
                if len(self._read_cache) > self._cache_max_entries:
                    self._read_cache.popitem(last=False)
                self._recent_results.append((time.time(), True))
                self._trim_health_window()
            return result if result else None
        except Exception as e:
            logger.debug(f"Static call failed ({contract_addr[:8]}...): {e}")
            self._errors += 1
            self._recent_results.append((time.time(), False))
            self._trim_health_window()
            return None

    def _write_call(self, contract_addr: str, calldata: bytes,
                    block_height: int = 0, _retry: int = 0) -> bool:
        """Execute a state-changing call to a contract.

        Builds a minimal contract_call transaction and processes it
        through the StateManager pipeline.  On transient failure,
        retries once after a short backoff.

        Returns True if the call succeeded.
        """
        if not self._sm or not contract_addr:
            return False
        self._total_calls += 1
        try:
            from decimal import Decimal
            from ..database.models import Transaction
            caller = self._kernel_addr or '0' * 40
            nonce_salt = f":{_retry}" if _retry else ""
            tx = Transaction(
                txid=hashlib.sha256(
                    f"{caller}:{contract_addr}:{block_height}:{calldata.hex()}{nonce_salt}"
                    .encode()
                ).hexdigest(),
                inputs=[],
                outputs=[],
                fee=Decimal(0),
                signature='',
                public_key='',
                timestamp=time.time(),
                tx_type='contract_call',
                to_address=contract_addr,
                data=calldata.hex(),
                gas_limit=1_000_000,
                gas_price=Decimal(0),
            )
            receipt = self._sm.process_transaction(tx, block_height, '0' * 64, 0)
            if receipt and getattr(receipt, 'status', 0) == 1:
                self._recent_results.append((time.time(), True))
                self._trim_health_window()
                return True
            # Transient failure — retry once with backoff
            if _retry < 1:
                backoff = 0.5 * (2 ** _retry)
                logger.debug(
                    f"Write call returned non-success ({contract_addr[:8]}...), "
                    f"retrying in {backoff:.1f}s (attempt {_retry + 2}/2)"
                )
                time.sleep(backoff)
                return self._write_call(contract_addr, calldata, block_height, _retry + 1)
            self._recent_results.append((time.time(), False))
            self._trim_health_window()
            return False
        except Exception as e:
            if _retry < 1:
                backoff = 0.5 * (2 ** _retry)
                logger.debug(
                    f"Write call exception ({contract_addr[:8]}...): {e}, "
                    f"retrying in {backoff:.1f}s"
                )
                time.sleep(backoff)
                return self._write_call(contract_addr, calldata, block_height, _retry + 1)
            logger.debug(f"Write call failed after retry ({contract_addr[:8]}...): {e}")
            self._errors += 1
            self._recent_results.append((time.time(), False))
            self._trim_health_window()
            return False

    # ------------------------------------------------------------------
    # 6.1 ConsciousnessDashboard
    # ------------------------------------------------------------------

    def record_phi_onchain(self, block_height: int, phi_value: float,
                           integration: float = 0.0,
                           differentiation: float = 0.0,
                           coherence: float = 0.0,
                           knowledge_nodes: int = 0,
                           knowledge_edges: int = 0) -> bool:
        """Write a Phi measurement to the ConsciousnessDashboard contract.

        Called every ONCHAIN_PHI_INTERVAL blocks from AetherEngine.

        Args:
            block_height: Current block height.
            phi_value: Phi value (float, e.g. 2.5).
            integration: Integration score (0.0-1.0).
            differentiation: Differentiation score (0.0-1.0).
            coherence: Phase coherence (0.0-1.0).
            knowledge_nodes: Total KG nodes.
            knowledge_edges: Total KG edges.

        Returns:
            True if successfully written on-chain.
        """
        if not self._dashboard_addr:
            return False

        calldata = encode_function_call(
            'recordPhi(uint256,uint256,uint256,uint256,uint256,uint256)',
            [
                int(phi_value * PHI_PRECISION),
                int(integration * PHI_PRECISION),
                int(differentiation * PHI_PRECISION),
                int(coherence * PHI_PRECISION),
                knowledge_nodes,
                knowledge_edges,
            ],
            ['uint256'] * 6,
        )

        success = self._write_call(self._dashboard_addr, calldata, block_height)
        if success:
            self._phi_writes += 1
            logger.debug(
                f"Phi {phi_value:.4f} written on-chain at block {block_height}"
            )
        return success

    def get_onchain_phi(self) -> Optional[float]:
        """Read the current Phi value from the on-chain dashboard.

        Returns:
            Phi value as float, or None if unavailable.
        """
        if not self._dashboard_addr:
            return None

        calldata = function_selector('getCurrentPhi()')
        result = self._static_call(self._dashboard_addr, calldata)
        if result and len(result) >= 32:
            raw = decode_uint256(result[:32])
            return raw / PHI_PRECISION
        return None

    def get_onchain_consciousness_status(self) -> Optional[dict]:
        """Read full consciousness status from the on-chain dashboard.

        Returns:
            Dict with phi, threshold, above_threshold, highest, measurements,
            events, ever_conscious, genesis_block. Or None if unavailable.
        """
        if not self._dashboard_addr:
            return None

        calldata = function_selector('getConsciousnessStatus()')
        result = self._static_call(self._dashboard_addr, calldata)
        if not result or len(result) < 256:  # 8 * 32 bytes
            return None

        try:
            return {
                'phi': decode_uint256(result[0:32]) / PHI_PRECISION,
                'threshold': decode_uint256(result[32:64]) / PHI_PRECISION,
                'above_threshold': decode_bool(result[64:96]),
                'highest_phi': decode_uint256(result[96:128]) / PHI_PRECISION,
                'total_measurements': decode_uint256(result[128:160]),
                'total_events': decode_uint256(result[160:192]),
                'ever_conscious': decode_bool(result[192:224]),
                'genesis_block': decode_uint256(result[224:256]),
            }
        except Exception as e:
            logger.debug(f"Failed to decode consciousness status: {e}")
            return None

    def record_genesis(self) -> bool:
        """Call recordGenesis() on the ConsciousnessDashboard contract.

        Should be called once at genesis block to initialize the dashboard.

        Returns:
            True if successfully called.
        """
        if not self._dashboard_addr:
            return False

        calldata = function_selector('recordGenesis()')
        return self._write_call(self._dashboard_addr, calldata, 0)

    # ------------------------------------------------------------------
    # 6.2 Proof-of-Thought On-Chain Verification
    # ------------------------------------------------------------------

    def submit_proof_onchain(self, block_height: int, thought_hash: str,
                             knowledge_root: str, submitter: str = '',
                             task_id: int = 0) -> bool:
        """Submit a Proof-of-Thought hash to the on-chain contract.

        Called after each block is mined, records the thought proof
        hash for consensus verification.

        Args:
            block_height: Block height this proof is for.
            thought_hash: SHA3-256 hash of the thought proof content.
            knowledge_root: Merkle root of the knowledge graph.
            submitter: Address of the validator/miner.
            task_id: PoT task ID (0 for auto-generated proofs).

        Returns:
            True if successfully submitted.
        """
        if not self._pot_addr:
            return False

        # Convert hashes to bytes32
        solution_hash = bytes.fromhex(thought_hash[:64].ljust(64, '0'))
        quantum_hash = bytes.fromhex(knowledge_root[:64].ljust(64, '0'))
        submitter_addr = submitter or self._kernel_addr or '0' * 40

        calldata = encode_function_call(
            'submitProof(uint256,address,bytes32,bytes32,uint256)',
            [task_id, submitter_addr, solution_hash, quantum_hash, block_height],
            ['uint256', 'address', 'bytes32', 'bytes32', 'uint256'],
        )

        success = self._write_call(self._pot_addr, calldata, block_height)
        if success:
            self._pot_submissions += 1
            logger.debug(
                f"PoT proof submitted on-chain at block {block_height}"
            )
        return success

    def get_proof_by_block(self, block_height: int) -> Optional[int]:
        """Check if a block already has an on-chain proof.

        Returns:
            Proof ID if exists, None otherwise.
        """
        if not self._pot_addr:
            return None

        calldata = encode_function_call(
            'getProofByBlock(uint256)',
            [block_height],
            ['uint256'],
        )
        result = self._static_call(self._pot_addr, calldata)
        if result and len(result) >= 32:
            proof_id = decode_uint256(result[:32])
            return proof_id if proof_id > 0 else None
        return None

    # ------------------------------------------------------------------
    # 6.3 Constitutional AI Safety Enforcement
    # ------------------------------------------------------------------

    def check_operation_vetoed(self, operation_description: str) -> bool:
        """Check if an operation has been vetoed by the ConstitutionalAI contract.

        Computes a hash of the operation description and checks on-chain
        whether it has been vetoed by the Gevurah safety node.

        Args:
            operation_description: Human-readable description of the operation.

        Returns:
            True if the operation is vetoed (should NOT proceed).
        """
        if not self._constitution_addr:
            return False  # No constitution → no veto

        self._veto_checks += 1

        # Hash the operation description
        op_hash = hashlib.sha256(operation_description.encode()).digest()

        calldata = encode_function_call(
            'isOperationVetoed(bytes32)',
            [op_hash],
            ['bytes32'],
        )

        result = self._static_call(self._constitution_addr, calldata)
        if result and len(result) >= 32:
            return decode_bool(result[:32])
        return False

    def record_veto_onchain(self, principle_id: int,
                            operation_description: str,
                            reason: str,
                            block_height: int = 0) -> bool:
        """Record a veto on-chain via the ConstitutionalAI contract.

        Called by the Gevurah safety node when it vetoes an operation.

        Args:
            principle_id: ID of the constitutional principle violated.
            operation_description: Description of the vetoed operation.
            reason: Why it was vetoed.
            block_height: Current block height.

        Returns:
            True if successfully recorded on-chain.
        """
        if not self._constitution_addr:
            return False

        op_hash = hashlib.sha256(operation_description.encode()).digest()

        # vetoOperation uses dynamic string for reason — we encode as bytes32
        # since our ABI encoder doesn't support dynamic strings in calls.
        # Use first 32 bytes of sha256(reason) as a reason identifier.
        reason_hash = hashlib.sha256(reason.encode()).digest()

        # Build calldata manually: selector + principleId + opHash + reason offset
        # For simplicity, encode reason as bytes32 (reason hash)
        sel = function_selector(
            'vetoOperation(uint256,bytes32,string)'
        )
        # Manual encoding with dynamic string
        # offset for string param = 3 * 32 = 96
        reason_bytes = reason.encode('utf-8')
        reason_len = len(reason_bytes)
        reason_padded = reason_bytes + b'\x00' * ((32 - reason_len % 32) % 32)

        calldata = (
            sel
            + encode_uint256(principle_id)
            + encode_bytes32(op_hash)
            + encode_uint256(96)  # offset to string data
            + encode_uint256(reason_len)
            + reason_padded
        )

        return self._write_call(self._constitution_addr, calldata, block_height)

    def get_principle_count(self) -> Tuple[int, int]:
        """Get the total and active principle count from ConstitutionalAI.

        Returns:
            (total, active) tuple. (0, 0) if unavailable.
        """
        if not self._constitution_addr:
            return (0, 0)

        calldata = function_selector('getPrincipleCount()')
        result = self._static_call(self._constitution_addr, calldata)
        if result and len(result) >= 64:
            total = decode_uint256(result[0:32])
            active = decode_uint256(result[32:64])
            return (total, active)
        return (0, 0)

    # ------------------------------------------------------------------
    # 6.4 On-Chain Governance
    # ------------------------------------------------------------------

    def get_treasury_balance(self) -> Optional[int]:
        """Read the TreasuryDAO balance.

        Returns:
            Balance in QBC units, or None if unavailable.
        """
        if not self._treasury_addr:
            return None

        calldata = function_selector('getBalance()')
        result = self._static_call(self._treasury_addr, calldata)
        if result and len(result) >= 32:
            self._governance_reads += 1
            return decode_uint256(result[:32])
        return None

    def get_proposal_count(self) -> Optional[int]:
        """Read the number of governance proposals.

        Returns:
            Proposal count, or None if unavailable.
        """
        if not self._treasury_addr:
            return None

        calldata = function_selector('proposalCount()')
        result = self._static_call(self._treasury_addr, calldata)
        if result and len(result) >= 32:
            self._governance_reads += 1
            return decode_uint256(result[:32])
        return None

    def get_upgrade_proposal_count(self) -> Optional[int]:
        """Read the number of upgrade governance proposals.

        Returns:
            Proposal count, or None if unavailable.
        """
        if not self._governor_addr:
            return None

        calldata = function_selector('proposalCount()')
        result = self._static_call(self._governor_addr, calldata)
        if result and len(result) >= 32:
            self._governance_reads += 1
            return decode_uint256(result[:32])
        return None

    # ------------------------------------------------------------------
    # 6.5 Higgs Cognitive Field
    # ------------------------------------------------------------------

    def update_higgs_field_onchain(self, block_height: int,
                                    field_value: float,
                                    avg_mass: float = 0.0) -> bool:
        """Update the Higgs field value on-chain.

        Called per-block from AetherEngine to track field evolution.

        Args:
            block_height: Current block height.
            field_value: Current Higgs field value (float, e.g. 245.17).
            avg_mass: Average cognitive mass across all nodes.

        Returns:
            True if successfully written on-chain.
        """
        if not self._higgs_addr:
            return False

        calldata = encode_function_call(
            'updateFieldValue(uint256)',
            [int(field_value * PHI_PRECISION)],
            ['uint256'],
        )

        return self._write_call(self._higgs_addr, calldata, block_height)

    def get_higgs_field_state(self) -> Optional[dict]:
        """Read the Higgs field state from on-chain contract.

        Returns:
            Dict with vev, currentField, mu, lambda, tanBeta, avgMass,
            totalMass, massGap, totalExcitations. Or None if unavailable.
        """
        if not self._higgs_addr:
            return None

        calldata = function_selector('getFieldState()')
        result = self._static_call(self._higgs_addr, calldata)
        if not result or len(result) < 288:  # 9 * 32 bytes
            return None

        try:
            return {
                'vev': decode_uint256(result[0:32]) / PHI_PRECISION,
                'current_field': decode_uint256(result[32:64]) / PHI_PRECISION,
                'mu': decode_uint256(result[64:96]) / PHI_PRECISION,
                'lambda': decode_uint256(result[96:128]) / (PHI_PRECISION * PHI_PRECISION),
                'tan_beta': decode_uint256(result[128:160]) / PHI_PRECISION,
                'avg_mass': decode_uint256(result[160:192]) / PHI_PRECISION,
                'total_mass': decode_uint256(result[192:224]) / PHI_PRECISION,
                'mass_gap': decode_uint256(result[224:256]) / PHI_PRECISION,
                'total_excitations': decode_uint256(result[256:288]),
            }
        except Exception as e:
            logger.debug(f"Failed to decode Higgs field state: {e}")
            return None

    def get_node_mass_onchain(self, node_id: int) -> Optional[dict]:
        """Read a node's cognitive mass from the on-chain Higgs contract.

        Returns:
            Dict with yukawa, mass, is_expansion. Or None if unavailable.
        """
        if not self._higgs_addr:
            return None

        calldata = encode_function_call(
            'getNodeMass(uint8)',
            [node_id],
            ['uint8'],
        )
        result = self._static_call(self._higgs_addr, calldata)
        if not result or len(result) < 96:
            return None

        try:
            return {
                'yukawa': decode_uint256(result[0:32]) / PHI_PRECISION,
                'mass': decode_uint256(result[32:64]) / PHI_PRECISION,
                'is_expansion': decode_bool(result[64:96]),
            }
        except Exception as e:
            logger.debug(f"Failed to decode node mass: {e}")
            return None

    # ------------------------------------------------------------------
    # 6.5 Emergency Shutdown Integration
    # ------------------------------------------------------------------

    def is_shutdown_onchain(self) -> bool:
        """Check if emergency shutdown has been triggered on-chain.

        Queries the EmergencyShutdown contract's getStatus() function.

        Returns:
            True if the system is currently shut down on-chain.
        """
        if not self._emergency_addr:
            return False

        calldata = function_selector('getStatus()')
        result = self._static_call(self._emergency_addr, calldata)
        if result and len(result) >= 32:
            return decode_bool(result[:32])
        return False

    def trigger_shutdown_onchain(self, block_height: int = 0) -> bool:
        """Propose emergency shutdown on-chain.

        Calls initiateShutdown() on the EmergencyShutdown contract.
        Requires multi-sig governance consensus to actually execute.

        Args:
            block_height: Current block height for transaction ordering.

        Returns:
            True if the call was submitted successfully.
        """
        if not self._emergency_addr:
            return False

        calldata = function_selector('initiateShutdown()')
        return self._write_call(self._emergency_addr, calldata, block_height)

    def get_emergency_status(self) -> dict:
        """Get full emergency shutdown status from on-chain contract.

        Returns:
            Dict with 'shutdown' (bool), 'timestamp', 'signers' count.
        """
        if not self._emergency_addr:
            return {'shutdown': False, 'on_chain': False}

        calldata = function_selector('getStatus()')
        result = self._static_call(self._emergency_addr, calldata)
        if result and len(result) >= 96:
            return {
                'shutdown': decode_bool(result[0:32]),
                'timestamp': decode_uint256(result[32:64]),
                'signers': decode_uint256(result[64:96]),
                'on_chain': True,
            }
        return {'shutdown': False, 'on_chain': bool(self._emergency_addr)}

    # ------------------------------------------------------------------
    # Combined integration hook
    # ------------------------------------------------------------------

    def process_block(self, block_height: int, phi_result: dict,
                      thought_hash: str = '', knowledge_root: str = '',
                      validator_address: str = '',
                      higgs_field_value: float = 0.0,
                      avg_cognitive_mass: float = 0.0) -> dict:
        """Per-block on-chain integration hook.

        Called from AetherEngine after block processing. Writes Phi
        and PoT data to on-chain contracts at configured intervals.

        Args:
            block_height: Current block height.
            phi_result: Dict from PhiCalculator.compute_phi().
            thought_hash: Proof-of-Thought hash.
            knowledge_root: Knowledge graph Merkle root.
            validator_address: Miner/validator address.
            higgs_field_value: Current Higgs field value (float).
            avg_cognitive_mass: Average cognitive mass across all nodes.

        Returns:
            Dict with write results.
        """
        self._current_block = block_height
        results: dict = {
            'phi_written': False,
            'pot_submitted': False,
            'higgs_updated': False,
            'block_height': block_height,
        }

        # Write Phi to ConsciousnessDashboard every N blocks
        phi_interval = Config.ONCHAIN_PHI_INTERVAL
        if block_height % phi_interval == 0 and phi_result:
            results['phi_written'] = self.record_phi_onchain(
                block_height=block_height,
                phi_value=phi_result.get('phi_value', 0.0),
                integration=phi_result.get('integration', 0.0),
                differentiation=phi_result.get('differentiation', 0.0),
                coherence=phi_result.get('coherence', 0.0),
                knowledge_nodes=phi_result.get('num_nodes', 0),
                knowledge_edges=phi_result.get('num_edges', 0),
            )

        # Submit PoT proof on-chain for every block
        if thought_hash and knowledge_root:
            results['pot_submitted'] = self.submit_proof_onchain(
                block_height=block_height,
                thought_hash=thought_hash,
                knowledge_root=knowledge_root,
                submitter=validator_address,
            )

        # Update Higgs field value on-chain
        if higgs_field_value > 0 and self._higgs_addr:
            results['higgs_updated'] = self.update_higgs_field_onchain(
                block_height=block_height,
                field_value=higgs_field_value,
                avg_mass=avg_cognitive_mass,
            )

        return results

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    def batch_process_blocks(self, start_block: int, end_block: int,
                             block_data_fn: object) -> dict:
        """Catch up multiple blocks of on-chain data efficiently.

        Useful when the node restarts and needs to replay on-chain
        writes for blocks that were mined while the bridge was down.

        Args:
            start_block: First block height to process (inclusive).
            end_block: Last block height to process (inclusive).
            block_data_fn: Callable(block_height) -> dict with keys
                matching ``process_block()`` kwargs (phi_result,
                thought_hash, knowledge_root, etc.).  Return None to
                skip a block.

        Returns:
            Dict with 'blocks_processed', 'blocks_skipped',
            'phi_writes', 'pot_submissions', 'errors'.
        """
        stats = {
            'blocks_processed': 0,
            'blocks_skipped': 0,
            'phi_writes': 0,
            'pot_submissions': 0,
            'higgs_updates': 0,
            'errors': 0,
            'start_block': start_block,
            'end_block': end_block,
        }

        for height in range(start_block, end_block + 1):
            self._current_block = height
            try:
                data = block_data_fn(height)
            except Exception as e:
                logger.debug(f"batch_process_blocks: block_data_fn({height}) error: {e}")
                stats['errors'] += 1
                continue

            if data is None:
                stats['blocks_skipped'] += 1
                continue

            result = self.process_block(
                block_height=height,
                phi_result=data.get('phi_result', {}),
                thought_hash=data.get('thought_hash', ''),
                knowledge_root=data.get('knowledge_root', ''),
                validator_address=data.get('validator_address', ''),
                higgs_field_value=data.get('higgs_field_value', 0.0),
                avg_cognitive_mass=data.get('avg_cognitive_mass', 0.0),
            )

            stats['blocks_processed'] += 1
            if result.get('phi_written'):
                stats['phi_writes'] += 1
            if result.get('pot_submitted'):
                stats['pot_submissions'] += 1
            if result.get('higgs_updated'):
                stats['higgs_updates'] += 1

        logger.info(
            f"Batch on-chain catchup: blocks {start_block}-{end_block}, "
            f"{stats['blocks_processed']} processed, {stats['blocks_skipped']} skipped, "
            f"{stats['errors']} errors"
        )
        return stats

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def _trim_health_window(self) -> None:
        """Keep only the most recent entries in the health window."""
        if len(self._recent_results) > self._health_window_size:
            self._recent_results = self._recent_results[-self._health_window_size:]

    def is_healthy(self) -> dict:
        """Check on-chain integration health.

        Evaluates:
          1. At least one contract address is configured
          2. QVM is accessible (static_call doesn't crash)
          3. Error rate in recent window is below 50%

        Returns:
            Dict with 'healthy' (bool), 'contracts_configured' (int),
            'qvm_accessible' (bool), 'error_rate' (float 0.0-1.0),
            'total_calls' (int), 'details' (str).
        """
        contracts_configured = sum(1 for a in [
            self._dashboard_addr, self._pot_addr, self._constitution_addr,
            self._treasury_addr, self._governor_addr, self._higgs_addr,
            self._emergency_addr,
        ] if a)

        qvm_accessible = self._qvm is not None

        # Compute error rate from recent results
        if self._recent_results:
            successes = sum(1 for _, ok in self._recent_results if ok)
            error_rate = 1.0 - (successes / len(self._recent_results))
        else:
            error_rate = 0.0

        healthy = (
            contracts_configured > 0
            and qvm_accessible
            and error_rate < 0.5
        )

        if not healthy:
            issues = []
            if contracts_configured == 0:
                issues.append('no contracts configured')
            if not qvm_accessible:
                issues.append('QVM not accessible')
            if error_rate >= 0.5:
                issues.append(f'error rate {error_rate:.0%} >= 50%')
            detail = '; '.join(issues)
        else:
            detail = 'all checks passed'

        return {
            'healthy': healthy,
            'contracts_configured': contracts_configured,
            'qvm_accessible': qvm_accessible,
            'error_rate': round(error_rate, 4),
            'total_calls': self._total_calls,
            'recent_window_size': len(self._recent_results),
            'details': detail,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get on-chain integration statistics."""
        return {
            'phi_writes': self._phi_writes,
            'pot_submissions': self._pot_submissions,
            'veto_checks': self._veto_checks,
            'governance_reads': self._governance_reads,
            'errors': self._errors,
            'contracts_configured': {
                'consciousness_dashboard': bool(self._dashboard_addr),
                'proof_of_thought': bool(self._pot_addr),
                'constitutional_ai': bool(self._constitution_addr),
                'treasury_dao': bool(self._treasury_addr),
                'upgrade_governor': bool(self._governor_addr),
                'higgs_field': bool(self._higgs_addr),
                'emergency_shutdown': bool(self._emergency_addr),
            },
        }


class OnChainAGILogOnly:
    """Log-only fallback for on-chain AGI integration.

    When no QVM StateManager is available (no deployed contracts), this
    class records phi writes and PoT submissions as database entries and
    increments counters so that the stats dashboard shows activity.

    Drop-in replacement for OnChainAGI — same public API surface.
    """

    def __init__(self, db_manager: object = None) -> None:
        self._db = db_manager
        self._phi_writes: int = 0
        self._pot_submissions: int = 0
        self._veto_checks: int = 0
        self._governance_reads: int = 0
        self._errors: int = 0
        self._total_calls: int = 0
        self._current_block: int = 0
        self._recent_results: list = []
        logger.info("OnChainAGI running in LOG-ONLY mode (no contracts deployed)")

    def record_phi_onchain(self, block_height: int, phi_value: float,
                           integration: float = 0.0,
                           differentiation: float = 0.0,
                           coherence: float = 0.0,
                           knowledge_nodes: int = 0,
                           knowledge_edges: int = 0) -> bool:
        """Record a Phi measurement to the database (log-only mode)."""
        self._phi_writes += 1
        self._total_calls += 1
        logger.debug(
            f"[log-only] Phi {phi_value:.4f} recorded at block {block_height} "
            f"(integration={integration:.3f}, coherence={coherence:.3f}, "
            f"nodes={knowledge_nodes}, edges={knowledge_edges})"
        )
        # Persist to DB if available
        if self._db:
            try:
                self._db.record_phi_measurement(
                    block_height=block_height,
                    phi_value=phi_value,
                    integration=integration,
                    differentiation=differentiation,
                    coherence=coherence,
                )
            except Exception as e:
                logger.debug(f"[log-only] DB phi write failed: {e}")
        return True

    def submit_proof_onchain(self, block_height: int, thought_hash: str,
                             knowledge_root: str, submitter: str = '',
                             task_id: int = 0) -> bool:
        """Record a PoT submission to the database (log-only mode)."""
        self._pot_submissions += 1
        self._total_calls += 1
        logger.debug(
            f"[log-only] PoT proof recorded at block {block_height} "
            f"(hash={thought_hash[:16]}..., submitter={submitter[:16]})"
        )
        return True

    def process_block(self, block_height: int, phi_result: dict,
                      thought_hash: str = '', knowledge_root: str = '',
                      validator_address: str = '',
                      higgs_field_value: float = 0.0,
                      avg_cognitive_mass: float = 0.0) -> dict:
        """Per-block log-only integration hook."""
        self._current_block = block_height
        results: dict = {
            'phi_written': False,
            'pot_submitted': False,
            'higgs_updated': False,
            'block_height': block_height,
            'mode': 'log_only',
        }

        # Record phi every ONCHAIN_PHI_INTERVAL blocks
        phi_interval = Config.ONCHAIN_PHI_INTERVAL
        if block_height % phi_interval == 0 and phi_result:
            results['phi_written'] = self.record_phi_onchain(
                block_height=block_height,
                phi_value=phi_result.get('phi_value', 0.0),
                integration=phi_result.get('integration', 0.0),
                differentiation=phi_result.get('differentiation', 0.0),
                coherence=phi_result.get('coherence', 0.0),
                knowledge_nodes=phi_result.get('num_nodes', 0),
                knowledge_edges=phi_result.get('num_edges', 0),
            )

        # Record PoT proof
        if thought_hash and knowledge_root:
            results['pot_submitted'] = self.submit_proof_onchain(
                block_height=block_height,
                thought_hash=thought_hash,
                knowledge_root=knowledge_root,
                submitter=validator_address,
            )

        return results

    def check_operation_vetoed(self, operation_description: str) -> bool:
        """No veto in log-only mode."""
        self._veto_checks += 1
        return False

    def is_healthy(self) -> dict:
        """Health check for log-only mode."""
        return {
            'healthy': True,
            'mode': 'log_only',
            'contracts_configured': 0,
            'qvm_accessible': False,
            'error_rate': 0.0,
            'total_calls': self._total_calls,
            'recent_window_size': 0,
            'details': 'running in log-only mode (no contracts deployed)',
        }

    def get_stats(self) -> dict:
        """Get log-only integration statistics."""
        return {
            'phi_writes': self._phi_writes,
            'pot_submissions': self._pot_submissions,
            'veto_checks': self._veto_checks,
            'governance_reads': self._governance_reads,
            'errors': self._errors,
            'mode': 'log_only',
            'contracts_configured': {
                'consciousness_dashboard': False,
                'proof_of_thought': False,
                'constitutional_ai': False,
                'treasury_dao': False,
                'upgrade_governor': False,
                'higgs_field': False,
                'emergency_shutdown': False,
            },
        }

    def get_onchain_phi(self) -> Optional[float]:
        return None

    def get_onchain_consciousness_status(self) -> Optional[dict]:
        return None

    def record_genesis(self) -> bool:
        return True

    def get_proof_by_block(self, block_height: int) -> Optional[int]:
        return None

    def record_veto_onchain(self, principle_id: int,
                            operation_description: str,
                            reason: str,
                            block_height: int = 0) -> bool:
        return True

    def get_principle_count(self) -> tuple:
        return (0, 0)

    def get_treasury_balance(self) -> Optional[int]:
        return None

    def get_proposal_count(self) -> Optional[int]:
        return None

    def get_upgrade_proposal_count(self) -> Optional[int]:
        return None

    def update_higgs_field_onchain(self, block_height: int,
                                    field_value: float,
                                    avg_mass: float = 0.0) -> bool:
        return True

    def get_higgs_field_state(self) -> Optional[dict]:
        return None

    def get_node_mass_onchain(self, node_id: int) -> Optional[dict]:
        return None

    def is_shutdown_onchain(self) -> bool:
        return False

    def trigger_shutdown_onchain(self, block_height: int = 0) -> bool:
        return False

    def get_emergency_status(self) -> dict:
        return {'shutdown': False, 'on_chain': False, 'mode': 'log_only'}
