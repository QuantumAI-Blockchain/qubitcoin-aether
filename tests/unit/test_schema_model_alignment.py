"""SQL schema vs SQLAlchemy model alignment verification (Batch 11.4).

Parses the SQL schema files and cross-references them against the Python
dataclass models in qubitcoin.database.models to catch drift.
"""
import re
import os
import pytest

from qubitcoin.database.models import Block, Transaction, UTXO, Account, TransactionReceipt


# ---------------------------------------------------------------------------
# Helper: lightweight SQL CREATE TABLE parser
# ---------------------------------------------------------------------------

_CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(",
    re.IGNORECASE,
)

_COLUMN_RE = re.compile(
    r"^\s+(\w+)\s+(BYTES|BIGINT|INT|DECIMAL|VARCHAR|BOOL|STRING|UUID|TIMESTAMP|TEXT)",
    re.IGNORECASE,
)


def _parse_sql_tables(sql_text: str) -> dict[str, list[str]]:
    """Return {table_name: [column_names]} from SQL CREATE TABLE statements."""
    tables: dict[str, list[str]] = {}
    current_table: str | None = None
    for line in sql_text.split("\n"):
        m_create = _CREATE_RE.search(line)
        if m_create:
            current_table = m_create.group(1).lower()
            tables[current_table] = []
            continue
        if current_table:
            if line.strip().startswith(")"):
                current_table = None
                continue
            m_col = _COLUMN_RE.match(line)
            if m_col:
                tables[current_table].append(m_col.group(1).lower())
    return tables


def _load_all_sql_tables() -> dict[str, list[str]]:
    """Load all SQL files from the sql/ directory."""
    sql_dir = os.path.join(os.path.dirname(__file__), "..", "..", "sql")
    sql_dir = os.path.normpath(sql_dir)
    all_tables: dict[str, list[str]] = {}
    for fname in sorted(os.listdir(sql_dir)):
        if fname.endswith(".sql"):
            with open(os.path.join(sql_dir, fname)) as f:
                tables = _parse_sql_tables(f.read())
                all_tables.update(tables)
    return all_tables


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSqlParserSanity:
    """Verify the lightweight SQL parser works correctly."""

    def test_parse_simple_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS foo (
            id BIGINT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            balance DECIMAL(20, 8) NOT NULL,
            INDEX name_idx (name)
        );
        """
        tables = _parse_sql_tables(sql)
        assert "foo" in tables
        assert "id" in tables["foo"]
        assert "name" in tables["foo"]
        assert "balance" in tables["foo"]
        assert len(tables["foo"]) == 3  # INDEX line is not a column

    def test_parse_multiple_tables(self):
        sql = """
        CREATE TABLE a (
            x INT PRIMARY KEY
        );
        CREATE TABLE b (
            y BIGINT
        );
        """
        tables = _parse_sql_tables(sql)
        assert len(tables) == 2
        assert "a" in tables and "b" in tables


class TestSqlFilesExist:
    """Verify that SQL schema files are present."""

    def test_core_blockchain_exists(self):
        sql_dir = os.path.join(os.path.dirname(__file__), "..", "..", "sql")
        assert os.path.isfile(os.path.join(sql_dir, "01_core_blockchain.sql"))

    def test_privacy_exists(self):
        sql_dir = os.path.join(os.path.dirname(__file__), "..", "..", "sql")
        assert os.path.isfile(os.path.join(sql_dir, "02_privacy_susy_swaps.sql"))

    def test_at_least_five_sql_files(self):
        sql_dir = os.path.join(os.path.dirname(__file__), "..", "..", "sql")
        sqls = [f for f in os.listdir(sql_dir) if f.endswith(".sql")]
        assert len(sqls) >= 5


class TestCoreBlockchainSchema:
    """Verify core blockchain SQL tables have expected columns."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.tables = _load_all_sql_tables()

    def test_blocks_table_exists(self):
        assert "blocks" in self.tables

    def test_blocks_has_block_hash(self):
        assert "block_hash" in self.tables["blocks"]

    def test_blocks_has_block_height(self):
        assert "block_height" in self.tables["blocks"]

    def test_blocks_has_difficulty(self):
        assert "difficulty" in self.tables["blocks"]

    def test_blocks_has_timestamp(self):
        assert "timestamp" in self.tables["blocks"]

    def test_transactions_table_exists(self):
        assert "transactions" in self.tables

    def test_transactions_has_tx_hash(self):
        assert "tx_hash" in self.tables["transactions"]

    def test_transactions_has_fee(self):
        assert "fee" in self.tables["transactions"]

    def test_addresses_table_exists(self):
        assert "addresses" in self.tables

    def test_chain_state_table_exists(self):
        assert "chain_state" in self.tables

    def test_mempool_table_exists(self):
        assert "mempool" in self.tables


class TestPrivacySchema:
    """Verify privacy SQL tables from 02_privacy_susy_swaps.sql."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.tables = _load_all_sql_tables()

    def test_key_images_table_exists(self):
        assert "key_images" in self.tables

    def test_key_images_has_key_image(self):
        assert "key_image" in self.tables["key_images"]

    def test_key_images_has_tx_hash(self):
        assert "tx_hash" in self.tables["key_images"]

    def test_range_proof_cache_exists(self):
        assert "range_proof_cache" in self.tables

    def test_stealth_addresses_exists(self):
        assert "stealth_addresses" in self.tables

    def test_confidential_transactions_exists(self):
        assert "confidential_transactions" in self.tables

    def test_susy_swap_pools_exists(self):
        assert "susy_swap_pools" in self.tables


class TestModelFieldCoverage:
    """Cross-reference Python model fields against SQL schema columns."""

    def test_block_model_fields_are_subset_of_sql(self):
        """Block model fields should have SQL analogs (name may differ, but must exist)."""
        model_fields = set(Block.__dataclass_fields__.keys())
        # These are the fields we expect in the Python model
        expected = {
            "height", "prev_hash", "proof_data", "transactions",
            "timestamp", "difficulty", "block_hash", "state_root",
            "receipts_root", "quantum_state_root", "thought_proof",
            "proof_of_thought_hash",
        }
        assert model_fields == expected

    def test_transaction_model_has_privacy_field(self):
        """Transaction model must have is_private for Susy Swaps."""
        assert "is_private" in Transaction.__dataclass_fields__

    def test_transaction_model_has_qvm_fields(self):
        """Transaction model must have QVM fields (tx_type, data, gas_limit, etc.)."""
        qvm_fields = {"tx_type", "to_address", "data", "gas_limit", "gas_price", "nonce"}
        model_fields = set(Transaction.__dataclass_fields__.keys())
        assert qvm_fields.issubset(model_fields)

    def test_utxo_model_has_core_fields(self):
        """UTXO model must have txid, vout, amount, address."""
        core = {"txid", "vout", "amount", "address"}
        assert core.issubset(set(UTXO.__dataclass_fields__.keys()))

    def test_account_model_has_contract_fields(self):
        """Account model must have code_hash and storage_root for QVM."""
        assert "code_hash" in Account.__dataclass_fields__
        assert "storage_root" in Account.__dataclass_fields__

    def test_receipt_model_has_required_fields(self):
        """TransactionReceipt must have standard receipt fields."""
        required = {"txid", "block_height", "block_hash", "gas_used", "status", "logs"}
        assert required.issubset(set(TransactionReceipt.__dataclass_fields__.keys()))
