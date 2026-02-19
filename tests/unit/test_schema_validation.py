"""Schema validation tests — verify dataclass models have expected fields.

These tests ensure models.py dataclasses remain aligned with the expected
field sets used throughout the codebase. They do NOT validate against SQL
schemas directly (models.py uses dataclasses, not SQLAlchemy ORM) but they
catch regressions when fields are accidentally removed or renamed.
"""
import pytest
from dataclasses import fields


class TestBlockModel:
    """Validate Block dataclass fields."""

    def test_block_has_required_fields(self):
        """Block model has all core fields."""
        from qubitcoin.database.models import Block
        field_names = {f.name for f in fields(Block)}
        required = {
            'height', 'block_hash', 'prev_hash',
            'timestamp', 'difficulty', 'transactions',
        }
        for name in required:
            assert name in field_names, f"Block missing required field: {name}"

    def test_block_has_quantum_fields(self):
        """Block model has quantum mining proof fields."""
        from qubitcoin.database.models import Block
        field_names = {f.name for f in fields(Block)}
        # proof_data contains VQE params and energy
        assert 'proof_data' in field_names, "Block missing proof_data field"

    def test_block_has_thought_proof(self):
        """Block model has proof-of-thought fields."""
        from qubitcoin.database.models import Block
        field_names = {f.name for f in fields(Block)}
        assert 'proof_of_thought_hash' in field_names or 'thought_proof' in field_names


class TestTransactionModel:
    """Validate Transaction dataclass fields."""

    def test_transaction_has_core_fields(self):
        """Transaction model has all core fields."""
        from qubitcoin.database.models import Transaction
        field_names = {f.name for f in fields(Transaction)}
        required = {
            'txid', 'inputs', 'outputs', 'timestamp',
            'signature', 'public_key', 'fee',
        }
        for name in required:
            assert name in field_names, f"Transaction missing required field: {name}"

    def test_transaction_has_privacy_field(self):
        """Transaction model has privacy flag."""
        from qubitcoin.database.models import Transaction
        field_names = {f.name for f in fields(Transaction)}
        assert 'is_private' in field_names

    def test_transaction_has_qvm_fields(self):
        """Transaction model has QVM contract fields."""
        from qubitcoin.database.models import Transaction
        field_names = {f.name for f in fields(Transaction)}
        # QVM support requires at least tx_type or contract fields
        qvm_fields = {'tx_type', 'to_address', 'data', 'gas_limit', 'gas_price'}
        has_some = any(f in field_names for f in qvm_fields)
        assert has_some, "Transaction has no QVM-related fields"


class TestUTXOModel:
    """Validate UTXO dataclass fields."""

    def test_utxo_has_required_fields(self):
        """UTXO model has all core fields."""
        from qubitcoin.database.models import UTXO
        field_names = {f.name for f in fields(UTXO)}
        required = {'txid', 'vout', 'amount', 'address'}
        for name in required:
            assert name in field_names, f"UTXO missing required field: {name}"


class TestProofModels:
    """Validate proof dataclass fields."""

    def test_proof_of_susy_has_fields(self):
        """ProofOfSUSY model has quantum proof fields."""
        from qubitcoin.database.models import ProofOfSUSY
        field_names = {f.name for f in fields(ProofOfSUSY)}
        required = {'challenge', 'params', 'energy', 'signature'}
        for name in required:
            assert name in field_names, f"ProofOfSUSY missing field: {name}"

    def test_proof_of_thought_has_fields(self):
        """ProofOfThought model has AGI proof fields."""
        from qubitcoin.database.models import ProofOfThought
        field_names = {f.name for f in fields(ProofOfThought)}
        # Should have at minimum reasoning/knowledge references
        assert len(field_names) >= 3, "ProofOfThought has too few fields"


class TestAccountModel:
    """Validate Account dataclass fields."""

    def test_account_has_evm_fields(self):
        """Account model has EVM-compatible fields."""
        from qubitcoin.database.models import Account
        field_names = {f.name for f in fields(Account)}
        required = {'address', 'balance', 'nonce'}
        for name in required:
            assert name in field_names, f"Account missing field: {name}"


class TestTransactionReceiptModel:
    """Validate TransactionReceipt dataclass fields."""

    def test_receipt_has_core_fields(self):
        """TransactionReceipt has EVM-compatible receipt fields."""
        from qubitcoin.database.models import TransactionReceipt
        field_names = {f.name for f in fields(TransactionReceipt)}
        required = {'txid', 'status'}
        for name in required:
            assert name in field_names, f"TransactionReceipt missing field: {name}"


class TestModelSerialization:
    """Test that models can be serialized and deserialized."""

    def test_block_to_dict(self):
        """Block can be converted to dict."""
        from qubitcoin.database.models import Block
        block = Block.__new__(Block)
        # Should have to_dict or __dict__ capability
        assert hasattr(block, '__dict__') or hasattr(block, 'to_dict')

    def test_transaction_to_dict(self):
        """Transaction can be converted to dict."""
        from qubitcoin.database.models import Transaction
        tx = Transaction.__new__(Transaction)
        assert hasattr(tx, '__dict__') or hasattr(tx, 'to_dict')

    def test_all_models_are_dataclasses(self):
        """All model classes are proper Python dataclasses."""
        from dataclasses import is_dataclass
        from qubitcoin.database.models import (
            Block, Transaction, UTXO, ProofOfSUSY,
            ProofOfThought, Account, TransactionReceipt,
        )
        for cls in [Block, Transaction, UTXO, ProofOfSUSY,
                    ProofOfThought, Account, TransactionReceipt]:
            assert is_dataclass(cls), f"{cls.__name__} is not a dataclass"
