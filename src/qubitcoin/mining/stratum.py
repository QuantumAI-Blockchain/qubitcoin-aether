"""
Stratum Mining Pool Protocol for Qubitcoin.

Implements a simplified Stratum-like protocol adapted for VQE (Proof-of-SUSY-Alignment) mining.
Unlike traditional hash-based Stratum, QBC Stratum distributes Hamiltonian problems and collects
VQE solutions (energy values + parameters).

Protocol:
  - mining.subscribe → session + difficulty
  - mining.authorize → wallet address verification
  - mining.notify → new Hamiltonian work unit
  - mining.submit → VQE solution submission
  - mining.set_difficulty → adjust worker difficulty
"""
import asyncio
import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StratumWorker:
    """Represents a connected mining worker."""
    worker_id: str
    address: str
    session_id: str
    difficulty: float
    connected_at: float = field(default_factory=time.time)
    shares_accepted: int = 0
    shares_rejected: int = 0
    last_share_at: float = 0.0
    hashrate_estimate: float = 0.0  # Solutions per second estimate
    authorized: bool = False


@dataclass
class WorkUnit:
    """A VQE work unit distributed to miners."""
    job_id: str
    block_height: int
    prev_hash: str
    hamiltonian_seed: str
    difficulty_target: float
    timestamp: float = field(default_factory=time.time)
    clean_jobs: bool = True  # If True, workers should drop old work


@dataclass
class ShareSubmission:
    """A VQE solution share submitted by a worker."""
    worker_id: str
    job_id: str
    vqe_params: List[float]
    energy: float
    nonce: int
    timestamp: float = field(default_factory=time.time)


class StratumPool:
    """
    Stratum mining pool server for Qubitcoin VQE mining.

    Manages workers, distributes Hamiltonian work units, validates solutions,
    and tracks shares for reward distribution.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3333,
        reward_address: str = "",
        on_block_found: Optional[Callable] = None,
    ):
        self.host = host
        self.port = port
        self.reward_address = reward_address
        self.on_block_found = on_block_found

        self.workers: Dict[str, StratumWorker] = {}
        self.current_work: Optional[WorkUnit] = None
        self.shares: List[ShareSubmission] = []
        self.blocks_found: int = 0
        self.total_shares: int = 0

        # Reward tracking (proportional share-based)
        self.reward_window: List[ShareSubmission] = []
        self.pool_fee_percent: float = getattr(Config, "STRATUM_POOL_FEE_PERCENT", 2.0)
        self.min_difficulty: float = getattr(Config, "STRATUM_MIN_DIFFICULTY", 0.1)

        self._server: Optional[asyncio.AbstractServer] = None
        self._connections: Dict[str, asyncio.StreamWriter] = {}
        self._running = False
        self._session_counter = 0

        logger.info(f"Stratum pool initialized on {host}:{port}")

    def _generate_session_id(self) -> str:
        """Generate a unique session ID for a worker."""
        self._session_counter += 1
        raw = f"{time.time()}-{self._session_counter}".encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def _generate_job_id(self, block_height: int) -> str:
        """Generate a job ID from block height + timestamp."""
        raw = f"{block_height}-{time.time()}".encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    # ─── Worker Management ──────────────────────────────────────────────

    def register_worker(self, worker_id: str, address: str) -> StratumWorker:
        """Register a new mining worker."""
        session_id = self._generate_session_id()
        worker = StratumWorker(
            worker_id=worker_id,
            address=address,
            session_id=session_id,
            difficulty=self.min_difficulty,
        )
        self.workers[worker_id] = worker
        logger.info(f"Worker registered: {worker_id} (session={session_id})")
        return worker

    def authorize_worker(self, worker_id: str, address: str) -> bool:
        """Authorize a worker with their wallet address."""
        worker = self.workers.get(worker_id)
        if not worker:
            return False
        # Basic validation: address starts with "qbc1" or is a hex address
        if not address or (not address.startswith("qbc1") and len(address) < 20):
            logger.warning(f"Invalid address for worker {worker_id}: {address}")
            return False
        worker.address = address
        worker.authorized = True
        logger.info(f"Worker authorized: {worker_id} → {address[:20]}...")
        return True

    def disconnect_worker(self, worker_id: str) -> None:
        """Remove a disconnected worker."""
        if worker_id in self.workers:
            del self.workers[worker_id]
            logger.info(f"Worker disconnected: {worker_id}")
        if worker_id in self._connections:
            del self._connections[worker_id]

    def get_worker_stats(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific worker."""
        worker = self.workers.get(worker_id)
        if not worker:
            return None
        total = worker.shares_accepted + worker.shares_rejected
        return {
            "worker_id": worker.worker_id,
            "address": worker.address,
            "difficulty": worker.difficulty,
            "shares_accepted": worker.shares_accepted,
            "shares_rejected": worker.shares_rejected,
            "acceptance_rate": worker.shares_accepted / max(total, 1),
            "hashrate_estimate": worker.hashrate_estimate,
            "uptime_seconds": time.time() - worker.connected_at,
            "authorized": worker.authorized,
        }

    # ─── Work Distribution ──────────────────────────────────────────────

    def create_work_unit(
        self,
        block_height: int,
        prev_hash: str,
        hamiltonian_seed: str,
        difficulty_target: float,
    ) -> WorkUnit:
        """Create a new work unit from the current chain state."""
        work = WorkUnit(
            job_id=self._generate_job_id(block_height),
            block_height=block_height,
            prev_hash=prev_hash,
            hamiltonian_seed=hamiltonian_seed,
            difficulty_target=difficulty_target,
        )
        self.current_work = work
        # Clear the reward window for a new block
        self.reward_window = []
        logger.info(f"New work unit: job={work.job_id}, height={block_height}, difficulty={difficulty_target:.4f}")
        return work

    def get_work_notification(self) -> Optional[Dict[str, Any]]:
        """Get the current work unit as a JSON-RPC notification payload."""
        if not self.current_work:
            return None
        return {
            "method": "mining.notify",
            "params": [
                self.current_work.job_id,
                self.current_work.prev_hash,
                self.current_work.hamiltonian_seed,
                self.current_work.difficulty_target,
                self.current_work.clean_jobs,
            ],
        }

    # ─── Share Validation ───────────────────────────────────────────────

    def submit_share(
        self,
        worker_id: str,
        job_id: str,
        vqe_params: List[float],
        energy: float,
        nonce: int,
    ) -> Dict[str, Any]:
        """
        Validate and record a share submission.

        A share is valid if:
          1. Worker is authorized
          2. Job ID matches current work
          3. Energy < worker's difficulty threshold
          4. VQE params are plausible (right count, bounded values)

        A share is a BLOCK SOLUTION if:
          - Energy < block difficulty target
        """
        worker = self.workers.get(worker_id)
        if not worker or not worker.authorized:
            return {"accepted": False, "reason": "unauthorized"}

        if not self.current_work or self.current_work.job_id != job_id:
            worker.shares_rejected += 1
            return {"accepted": False, "reason": "stale_job"}

        # Validate VQE params
        if not vqe_params or len(vqe_params) < 4:
            worker.shares_rejected += 1
            return {"accepted": False, "reason": "invalid_params"}

        # Validate energy is below worker difficulty
        if energy >= worker.difficulty:
            worker.shares_rejected += 1
            return {"accepted": False, "reason": "above_difficulty"}

        # Share is valid
        share = ShareSubmission(
            worker_id=worker_id,
            job_id=job_id,
            vqe_params=vqe_params,
            energy=energy,
            nonce=nonce,
        )
        self.shares.append(share)
        self.reward_window.append(share)
        worker.shares_accepted += 1
        worker.last_share_at = time.time()
        self.total_shares += 1

        # Update hashrate estimate (simple EMA)
        elapsed = time.time() - worker.connected_at
        if elapsed > 0:
            worker.hashrate_estimate = worker.shares_accepted / elapsed

        # Check if this is a block solution
        is_block = energy < self.current_work.difficulty_target
        result: Dict[str, Any] = {
            "accepted": True,
            "is_block": is_block,
            "energy": energy,
        }

        if is_block:
            self.blocks_found += 1
            logger.info(
                f"BLOCK FOUND by {worker_id}! Energy={energy:.6f} < Target={self.current_work.difficulty_target:.6f}"
            )
            if self.on_block_found:
                self.on_block_found(share, self.current_work)
            result["block_height"] = self.current_work.block_height

        return result

    # ─── Difficulty Adjustment ──────────────────────────────────────────

    def adjust_worker_difficulty(self, worker_id: str, target_shares_per_minute: float = 4.0) -> float:
        """
        Adjust a worker's difficulty to target a specific share rate.

        Higher difficulty = lower energy threshold (harder to find solutions).
        """
        worker = self.workers.get(worker_id)
        if not worker:
            return self.min_difficulty

        elapsed = time.time() - worker.connected_at
        if elapsed < 60:  # Wait at least 1 minute before adjusting
            return worker.difficulty

        actual_rate = worker.shares_accepted / (elapsed / 60)
        if actual_rate <= 0:
            return worker.difficulty

        ratio = actual_rate / target_shares_per_minute
        new_difficulty = worker.difficulty * ratio

        # Clamp to reasonable bounds
        new_difficulty = max(self.min_difficulty, min(new_difficulty, 100.0))
        worker.difficulty = new_difficulty

        logger.debug(f"Worker {worker_id} difficulty adjusted: {new_difficulty:.4f} (rate={actual_rate:.1f}/min)")
        return new_difficulty

    # ─── Reward Distribution ────────────────────────────────────────────

    def calculate_rewards(self, block_reward: float) -> Dict[str, float]:
        """
        Calculate per-worker rewards for a found block using proportional share distribution.

        Pool takes pool_fee_percent, rest distributed proportional to accepted shares.
        """
        if not self.reward_window:
            return {}

        pool_fee = block_reward * (self.pool_fee_percent / 100.0)
        distributable = block_reward - pool_fee

        # Count shares per worker in the reward window
        worker_shares: Dict[str, int] = {}
        total = 0
        for share in self.reward_window:
            worker_shares[share.worker_id] = worker_shares.get(share.worker_id, 0) + 1
            total += 1

        if total == 0:
            return {}

        rewards: Dict[str, float] = {}
        for wid, count in worker_shares.items():
            worker = self.workers.get(wid)
            if worker:
                rewards[worker.address] = distributable * (count / total)

        return rewards

    # ─── Pool Statistics ────────────────────────────────────────────────

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get overall pool statistics."""
        active_workers = [w for w in self.workers.values() if w.authorized]
        total_hashrate = sum(w.hashrate_estimate for w in active_workers)

        return {
            "active_workers": len(active_workers),
            "total_workers_connected": len(self.workers),
            "total_hashrate": total_hashrate,
            "blocks_found": self.blocks_found,
            "total_shares": self.total_shares,
            "pool_fee_percent": self.pool_fee_percent,
            "current_job": self.current_work.job_id if self.current_work else None,
            "current_block_height": self.current_work.block_height if self.current_work else None,
            "uptime": time.time() - self._server_start if hasattr(self, "_server_start") else 0,
        }

    # ─── JSON-RPC Protocol ──────────────────────────────────────────────

    def handle_message(self, worker_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a Stratum JSON-RPC message from a worker.

        Supported methods:
          - mining.subscribe → session + work
          - mining.authorize → wallet verification
          - mining.submit → share submission
        """
        method = message.get("method", "")
        params = message.get("params", [])
        msg_id = message.get("id", 0)

        if method == "mining.subscribe":
            worker_name = params[0] if params else f"worker-{worker_id[:8]}"
            worker = self.register_worker(worker_id, "")
            result = {
                "id": msg_id,
                "result": [
                    worker.session_id,
                    worker.difficulty,
                ],
                "error": None,
            }
            return result

        elif method == "mining.authorize":
            address = params[0] if params else ""
            password = params[1] if len(params) > 1 else ""
            success = self.authorize_worker(worker_id, address)
            return {
                "id": msg_id,
                "result": success,
                "error": None if success else "invalid_address",
            }

        elif method == "mining.submit":
            if len(params) < 4:
                return {"id": msg_id, "result": False, "error": "insufficient_params"}

            job_id = params[0]
            nonce = int(params[1])
            energy = float(params[2])
            vqe_params = [float(p) for p in params[3]] if isinstance(params[3], list) else []

            result = self.submit_share(worker_id, job_id, vqe_params, energy, nonce)
            return {
                "id": msg_id,
                "result": result["accepted"],
                "error": None if result["accepted"] else result.get("reason"),
            }

        else:
            return {"id": msg_id, "result": None, "error": f"unknown_method: {method}"}

    # ─── TCP Server ─────────────────────────────────────────────────────

    async def start_server(self) -> None:
        """Start the Stratum TCP server."""
        self._running = True
        self._server_start = time.time()
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        logger.info(f"Stratum pool server listening on {self.host}:{self.port}")

    async def stop_server(self) -> None:
        """Stop the Stratum server and disconnect all workers."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Close all connections
        for writer in self._connections.values():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self._connections.clear()
        self.workers.clear()
        logger.info("Stratum pool server stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new worker connection."""
        peername = writer.get_extra_info("peername")
        worker_id = self._generate_session_id()
        self._connections[worker_id] = writer
        logger.info(f"New connection from {peername}, assigned worker_id={worker_id}")

        try:
            while self._running:
                data = await asyncio.wait_for(reader.readline(), timeout=300.0)
                if not data:
                    break

                try:
                    message = json.loads(data.decode().strip())
                    response = self.handle_message(worker_id, message)
                    response_bytes = (json.dumps(response) + "\n").encode()
                    writer.write(response_bytes)
                    await writer.drain()

                    # After authorize, send current work
                    if message.get("method") == "mining.authorize" and response.get("result"):
                        work_notification = self.get_work_notification()
                        if work_notification:
                            writer.write((json.dumps(work_notification) + "\n").encode())
                            await writer.drain()

                except json.JSONDecodeError:
                    logger.debug(f"Invalid JSON from {worker_id}")
                except Exception as e:
                    logger.warning(f"Error handling message from {worker_id}: {e}")

        except asyncio.TimeoutError:
            logger.info(f"Worker {worker_id} timed out")
        except ConnectionResetError:
            logger.debug(f"Worker {worker_id} connection reset")
        finally:
            self.disconnect_worker(worker_id)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def broadcast_work(self) -> None:
        """Broadcast current work to all connected workers."""
        notification = self.get_work_notification()
        if not notification:
            return

        payload = (json.dumps(notification) + "\n").encode()
        disconnected = []

        for wid, writer in self._connections.items():
            try:
                writer.write(payload)
                await writer.drain()
            except Exception:
                disconnected.append(wid)

        for wid in disconnected:
            self.disconnect_worker(wid)

    async def broadcast_difficulty(self, worker_id: str, new_difficulty: float) -> None:
        """Send difficulty update to a specific worker."""
        writer = self._connections.get(worker_id)
        if not writer:
            return

        msg = {
            "method": "mining.set_difficulty",
            "params": [new_difficulty],
        }
        try:
            writer.write((json.dumps(msg) + "\n").encode())
            await writer.drain()
        except Exception:
            self.disconnect_worker(worker_id)
