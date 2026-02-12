"""Unit tests for privacy module (Susy Swaps)."""
import pytest


class TestPedersenCommitments:
    """Test Pedersen commitment operations."""

    def test_import(self):
        from qubitcoin.privacy.commitments import PedersenCommitment, Commitment
        assert PedersenCommitment is not None
        assert Commitment is not None

    def test_commit_returns_commitment(self):
        from qubitcoin.privacy.commitments import PedersenCommitment, Commitment
        c = PedersenCommitment.commit(100)
        assert isinstance(c, Commitment)
        assert c.value == 100
        assert c.blinding > 0
        assert c.point is not None

    def test_different_values_different_commitments(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        c1 = PedersenCommitment.commit(100)
        c2 = PedersenCommitment.commit(200)
        assert c1.point != c2.point

    def test_verify_sum_balanced(self):
        """Inputs sum == outputs sum: verify_sum should pass."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        # Create commitments where inputs = outputs
        # 100 + 50 = 90 + 60
        c_in1 = PedersenCommitment.commit(100)
        c_in2 = PedersenCommitment.commit(50)
        # For verify_sum to work, blinding factors must also balance.
        # Use explicit blindings that sum correctly.
        total_in_blinding = c_in1.blinding + c_in2.blinding
        # Create outputs with blindings that sum to the same total
        c_out1 = PedersenCommitment.commit(90, blinding=total_in_blinding - 42)
        c_out2 = PedersenCommitment.commit(60, blinding=42)
        result = PedersenCommitment.verify_sum(
            [c_in1, c_in2], [c_out1, c_out2]
        )
        assert result is True

    def test_generate_blinding(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        b1 = PedersenCommitment.generate_blinding()
        b2 = PedersenCommitment.generate_blinding()
        assert isinstance(b1, int)
        assert b1 > 0
        assert b1 != b2  # Random, should differ

    def test_commitment_serialization(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        c = PedersenCommitment.commit(42)
        hex_str = c.to_hex()
        assert isinstance(hex_str, str)
        assert len(hex_str) == 66  # 33 bytes compressed = 66 hex chars


class TestStealthAddresses:
    """Test stealth address system."""

    def test_import(self):
        from qubitcoin.privacy.stealth import StealthAddressManager, StealthKeyPair
        assert StealthAddressManager is not None
        assert StealthKeyPair is not None

    def test_generate_keypair(self):
        from qubitcoin.privacy.stealth import StealthAddressManager, StealthKeyPair
        kp = StealthAddressManager.generate_keypair()
        assert isinstance(kp, StealthKeyPair)
        assert isinstance(kp.spend_privkey, int)
        assert isinstance(kp.view_privkey, int)
        assert kp.spend_pubkey is not None
        assert kp.view_pubkey is not None

    def test_keypair_public_address(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        addr = kp.public_address()
        assert isinstance(addr, str)
        assert len(addr) > 0

    def test_create_and_scan_output(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        # Receiver generates keypair
        kp = StealthAddressManager.generate_keypair()
        # Sender creates stealth output
        stealth_out = StealthAddressManager.create_output(
            kp.spend_pubkey, kp.view_pubkey
        )
        assert stealth_out.one_time_address is not None
        assert stealth_out.ephemeral_pubkey is not None
        # Receiver scans
        is_mine = StealthAddressManager.scan_output(
            kp, stealth_out.ephemeral_pubkey, stealth_out.one_time_address
        )
        assert is_mine is True


class TestRangeProofs:
    """Test Bulletproofs range proofs."""

    def test_import(self):
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier
        assert RangeProofGenerator is not None
        assert RangeProofVerifier is not None

    def test_generate_proof(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProof
        c = PedersenCommitment.commit(42)
        proof = RangeProofGenerator.generate(value=42, blinding=c.blinding)
        assert isinstance(proof, RangeProof)
        assert proof.commitment is not None

    def test_verify_valid_proof(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier
        c = PedersenCommitment.commit(42)
        proof = RangeProofGenerator.generate(value=42, blinding=c.blinding)
        assert RangeProofVerifier.verify(proof) is True


class TestSusySwap:
    """Test confidential transaction builder."""

    def test_import(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        assert SusySwapBuilder is not None

    def test_build_basic_transaction(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        blinding = PedersenCommitment.generate_blinding()
        spending_key = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(
            txid='a' * 64, vout=0,
            value=100 * (10**8),  # atoms
            blinding=blinding,
            spending_key=spending_key,
        )
        builder.add_output(value=90 * (10**8))
        builder.set_fee(10 * (10**8))
        tx = builder.build()
        assert tx is not None
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 1
        assert tx.fee == 10 * (10**8)
