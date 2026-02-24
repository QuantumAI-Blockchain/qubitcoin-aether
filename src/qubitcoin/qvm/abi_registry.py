"""
ABI Registry for QVM Contracts

Stores and retrieves contract ABIs (Application Binary Interfaces) so deployed
contracts can be verified and interacted with using human-readable function
signatures rather than raw bytecode.

Provides in-memory storage with optional CockroachDB persistence.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContractABIRecord:
    """Stores an ABI registration for a single contract address."""
    address: str
    abi: List[Dict]
    registered_at: float
    verified: bool = False
    source_code: Optional[str] = None
    compiler_version: Optional[str] = None
    verified_at: Optional[float] = None
    abi_hash: str = ""

    def __post_init__(self) -> None:
        if not self.abi_hash:
            self.abi_hash = hashlib.sha256(
                json.dumps(self.abi, sort_keys=True).encode()
            ).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        return {
            "address": self.address,
            "abi": self.abi,
            "abi_hash": self.abi_hash,
            "registered_at": self.registered_at,
            "verified": self.verified,
            "source_code": self.source_code,
            "compiler_version": self.compiler_version,
            "verified_at": self.verified_at,
        }


class ABIRegistry:
    """Registry for contract ABIs with optional database persistence.

    Stores ABI definitions by contract address, supports verification
    marking, and provides lookup for contract interaction tooling.
    """

    def __init__(self, db_manager: object = None) -> None:
        """
        Args:
            db_manager: Optional DatabaseManager for CockroachDB persistence.
                        When None, operates in memory-only mode.
        """
        self._db = db_manager
        # In-memory index: normalized address -> ContractABIRecord
        self._records: Dict[str, ContractABIRecord] = {}
        logger.info("ABI Registry initialized")

    # ── Core Operations ───────────────────────────────────────────────

    def register_abi(self, address: str, abi: List[Dict]) -> None:
        """Store an ABI for a contract address.

        Overwrites any previously registered ABI for the same address.

        Args:
            address: Contract address (hex string, case-insensitive).
            abi: List of ABI entry dicts (functions, events, etc.).
        """
        normalized = address.lower().strip()
        record = ContractABIRecord(
            address=normalized,
            abi=abi,
            registered_at=time.time(),
        )
        self._records[normalized] = record
        self._persist(record)
        logger.info(f"ABI registered for {normalized[:16]}... ({len(abi)} entries)")

    def get_abi(self, address: str) -> Optional[List[Dict]]:
        """Retrieve the ABI for a contract address.

        Args:
            address: Contract address to look up.

        Returns:
            The ABI list, or None if no ABI is registered.
        """
        normalized = address.lower().strip()
        record = self._records.get(normalized)
        if record is None:
            record = self._load(normalized)
        return record.abi if record else None

    def get_record(self, address: str) -> Optional[ContractABIRecord]:
        """Retrieve the full ABI record for a contract.

        Args:
            address: Contract address.

        Returns:
            The ContractABIRecord, or None.
        """
        normalized = address.lower().strip()
        record = self._records.get(normalized)
        if record is None:
            record = self._load(normalized)
        return record

    def verify_contract(self, address: str, source_code: str,
                        compiler_version: str) -> bool:
        """Mark a contract as verified by associating source code.

        The source_code is stored alongside the ABI so that anyone can
        independently confirm the deployed bytecode matches the source.

        Args:
            address: Contract address.
            source_code: Solidity / QSol source code.
            compiler_version: Compiler version used (e.g. '0.8.24').

        Returns:
            True if the contract was found and marked verified, False otherwise.
        """
        normalized = address.lower().strip()
        record = self._records.get(normalized)
        if record is None:
            record = self._load(normalized)
        if record is None:
            logger.warning(f"Cannot verify {normalized[:16]}...: no ABI registered")
            return False

        record.verified = True
        record.source_code = source_code
        record.compiler_version = compiler_version
        record.verified_at = time.time()
        self._records[normalized] = record
        self._persist(record)
        logger.info(f"Contract verified: {normalized[:16]}... (compiler {compiler_version})")
        return True

    def is_verified(self, address: str) -> bool:
        """Check if a contract has been verified.

        Args:
            address: Contract address.

        Returns:
            True if the contract is registered and verified.
        """
        normalized = address.lower().strip()
        record = self._records.get(normalized)
        if record is None:
            record = self._load(normalized)
        return record.verified if record else False

    def get_verified_contracts(self) -> List[str]:
        """Get addresses of all verified contracts.

        Returns:
            List of verified contract addresses.
        """
        # Merge in-memory with DB if available
        self._load_all()
        return [
            addr for addr, rec in self._records.items()
            if rec.verified
        ]

    def get_all_contracts(self) -> List[str]:
        """Get addresses of all contracts with registered ABIs.

        Returns:
            List of all registered contract addresses.
        """
        self._load_all()
        return list(self._records.keys())

    def get_stats(self) -> Dict:
        """Get registry statistics.

        Returns:
            Dict with total_registered, total_verified counts.
        """
        self._load_all()
        total = len(self._records)
        verified = sum(1 for r in self._records.values() if r.verified)
        return {
            "total_registered": total,
            "total_verified": verified,
            "total_unverified": total - verified,
        }

    # ── Persistence Helpers ───────────────────────────────────────────

    def _persist(self, record: ContractABIRecord) -> None:
        """Write record to CockroachDB if available."""
        if not self._db:
            return
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text("""
                        UPSERT INTO contract_abis
                            (address, abi, abi_hash, registered_at,
                             verified, source_code, compiler_version, verified_at)
                        VALUES (:addr, CAST(:abi AS jsonb), :abi_hash, :registered_at,
                                :verified, :source_code, :compiler_version, :verified_at)
                    """),
                    {
                        "addr": record.address,
                        "abi": json.dumps(record.abi),
                        "abi_hash": record.abi_hash,
                        "registered_at": record.registered_at,
                        "verified": record.verified,
                        "source_code": record.source_code,
                        "compiler_version": record.compiler_version,
                        "verified_at": record.verified_at,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"ABI persist skipped (table may not exist): {e}")

    def _load(self, address: str) -> Optional[ContractABIRecord]:
        """Load a single record from DB."""
        if not self._db:
            return None
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                row = session.execute(
                    text("""
                        SELECT address, abi, abi_hash, registered_at,
                               verified, source_code, compiler_version, verified_at
                        FROM contract_abis WHERE address = :addr
                    """),
                    {"addr": address},
                ).fetchone()
                if row:
                    record = ContractABIRecord(
                        address=row[0],
                        abi=json.loads(row[1]) if isinstance(row[1], str) else row[1],
                        registered_at=float(row[3]) if row[3] else time.time(),
                        verified=bool(row[4]),
                        source_code=row[5],
                        compiler_version=row[6],
                        verified_at=float(row[7]) if row[7] else None,
                        abi_hash=row[2] or "",
                    )
                    self._records[address] = record
                    return record
        except Exception as e:
            logger.debug(f"ABI load skipped: {e}")
        return None

    def _load_all(self) -> None:
        """Bulk-load all records from DB into memory cache."""
        if not self._db:
            return
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                rows = session.execute(
                    text("""
                        SELECT address, abi, abi_hash, registered_at,
                               verified, source_code, compiler_version, verified_at
                        FROM contract_abis
                    """)
                ).fetchall()
                for row in rows:
                    addr = row[0]
                    if addr not in self._records:
                        self._records[addr] = ContractABIRecord(
                            address=addr,
                            abi=json.loads(row[1]) if isinstance(row[1], str) else row[1],
                            registered_at=float(row[3]) if row[3] else time.time(),
                            verified=bool(row[4]),
                            source_code=row[5],
                            compiler_version=row[6],
                            verified_at=float(row[7]) if row[7] else None,
                            abi_hash=row[2] or "",
                        )
        except Exception as e:
            logger.debug(f"ABI bulk load skipped: {e}")
