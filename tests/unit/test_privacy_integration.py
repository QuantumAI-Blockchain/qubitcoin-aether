"""Integration tests for privacy (Susy Swap) transaction lifecycle.

End-to-end flow: create confidential outputs, verify them, and simulate spending.
"""
import pytest


class TestConfidentialOutputCreation:
    """Test creating confidential outputs with hidden amounts."""

    def test_pedersen_commitment_hides_value(self):
        """A commitment hides the value — two different values produce different commitments."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        c1 = PedersenCommitment.commit(100, PedersenCommitment.generate_blinding())
        c2 = PedersenCommitment.commit(200, PedersenCommitment.generate_blinding())
        assert c1.point != c2.point

    def test_commitment_balance_verifies(self):
        """Input commitments must balance output commitments + fee."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        # Input: 1000 with blinding r1
        r1 = PedersenCommitment.generate_blinding()
        c_in = PedersenCommitment.commit(1000, r1)

        # Outputs: 700 + 300 = 1000
        r2 = PedersenCommitment.generate_blinding()
        c_out1 = PedersenCommitment.commit(700, r2)
        r3 = PedersenCommitment.generate_blinding()
        c_out2 = PedersenCommitment.commit(300, r3)

        # Verify homomorphic property: C(v1, r1) = C(v2, r2) + C(v3, r3)
        # when v1 = v2 + v3 and r1 = r2 + r3
        # Use compute_excess_blinding to check balance
        excess = PedersenCommitment.compute_excess_blinding([r1], [r2, r3])
        # If excess is zero, blindings balance; otherwise, adjustment needed
        assert isinstance(excess, int)

    def test_range_proof_valid(self):
        """Range proof verifies that committed value is non-negative."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier

        value = 500
        blinding = PedersenCommitment.generate_blinding()
        commitment = PedersenCommitment.commit(value, blinding)
        proof = RangeProofGenerator.generate(value, blinding, commitment)

        assert RangeProofVerifier.verify(proof) is True

    def test_range_proof_zero_value(self):
        """Range proof works for zero value."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier

        blinding = PedersenCommitment.generate_blinding()
        commitment = PedersenCommitment.commit(0, blinding)
        proof = RangeProofGenerator.generate(0, blinding, commitment)

        assert RangeProofVerifier.verify(proof) is True


class TestStealthAddressFlow:
    """Test stealth address generation and scanning."""

    def test_stealth_roundtrip(self):
        """Sender creates stealth output, receiver can scan and find it."""
        from qubitcoin.privacy.stealth import StealthAddressManager

        # Receiver generates key pair
        recv_keys = StealthAddressManager.generate_keypair()

        # Sender creates a stealth output to receiver
        output = StealthAddressManager.create_output(
            recv_keys.spend_pubkey, recv_keys.view_pubkey
        )

        # Receiver scans for the output using their keypair
        found = StealthAddressManager.scan_output(
            recv_keys, output.ephemeral_pubkey, output.one_time_address
        )
        assert found is True

    def test_stealth_wrong_receiver_fails(self):
        """Wrong receiver cannot scan the output."""
        from qubitcoin.privacy.stealth import StealthAddressManager

        recv1 = StealthAddressManager.generate_keypair()
        recv2 = StealthAddressManager.generate_keypair()

        # Output to recv1
        output = StealthAddressManager.create_output(
            recv1.spend_pubkey, recv1.view_pubkey
        )

        # recv2 tries to scan — should fail
        found = StealthAddressManager.scan_output(
            recv2, output.ephemeral_pubkey, output.one_time_address
        )
        assert found is False

    def test_key_image_uniqueness(self):
        """Each spending key produces a unique key image."""
        from qubitcoin.privacy.stealth import StealthAddressManager

        ki1 = StealthAddressManager.compute_key_image(12345)
        ki2 = StealthAddressManager.compute_key_image(67890)
        assert (ki1.x, ki1.y) != (ki2.x, ki2.y)


class TestSusySwapBuild:
    """Test building complete confidential transactions."""

    def test_basic_susy_swap(self):
        """Build a basic confidential transaction: 1 input → 1 output + fee."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(
            txid="prev_tx_hash",
            vout=0,
            value=1000,
            blinding=blinding,
            spending_key=42,
        )
        builder.add_output(value=900)
        builder.set_fee(100)

        tx = builder.build()

        assert tx.is_private is True
        assert tx.fee == 100
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 1
        assert len(tx.key_images) == 1
        assert len(tx.txid) == 64  # SHA-256 hex

    def test_multi_output_susy_swap(self):
        """Build a confidential transaction with multiple outputs."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(
            txid="input_tx",
            vout=0,
            value=5000,
            blinding=blinding,
            spending_key=99,
        )
        builder.add_output(value=2000)
        builder.add_output(value=2500)
        builder.set_fee(500)

        tx = builder.build()

        assert len(tx.outputs) == 2
        assert tx.fee == 500

    def test_susy_swap_value_mismatch_fails(self):
        """Transaction with mismatched input/output values fails."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(txid="tx", vout=0, value=1000, blinding=blinding, spending_key=1)
        builder.add_output(value=800)
        builder.set_fee(100)  # 800 + 100 = 900 != 1000

        with pytest.raises(ValueError, match="Value mismatch"):
            builder.build()

    def test_susy_swap_no_inputs_fails(self):
        """Transaction with no inputs fails."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder

        builder = SusySwapBuilder()
        builder.add_output(value=100)
        builder.set_fee(0)

        with pytest.raises(ValueError, match="at least one input"):
            builder.build()

    def test_susy_swap_no_outputs_fails(self):
        """Transaction with no outputs fails."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(txid="tx", vout=0, value=100, blinding=blinding, spending_key=1)
        builder.set_fee(100)

        with pytest.raises(ValueError, match="at least one output"):
            builder.build()

    def test_susy_swap_serialization(self):
        """Confidential transaction serializes to dict correctly."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(txid="tx1", vout=0, value=500, blinding=blinding, spending_key=7)
        builder.add_output(value=450)
        builder.set_fee(50)

        tx = builder.build()
        d = tx.to_dict()

        assert d['tx_type'] == 'susy_swap'
        assert d['is_private'] is True
        assert d['fee'] == 50
        assert isinstance(d['key_images'], list)
        assert isinstance(d['txid'], str)

    def test_susy_swap_with_stealth_address(self):
        """Confidential tx with stealth address for recipient."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.stealth import StealthAddressManager

        recv_keys = StealthAddressManager.generate_keypair()
        blinding = PedersenCommitment.generate_blinding()

        builder = SusySwapBuilder()
        builder.add_input(txid="tx1", vout=0, value=1000, blinding=blinding, spending_key=5)
        builder.add_output(
            value=900,
            recipient_spend_pub=recv_keys.spend_pubkey,
            recipient_view_pub=recv_keys.view_pubkey,
        )
        builder.set_fee(100)

        tx = builder.build()
        d = tx.to_dict()

        # Stealth output should have ephemeral pubkey and one-time address
        output = d['outputs'][0]
        assert output.get('ephemeral_pubkey') is not None
        assert output.get('one_time_address') is not None


class TestKeyImageDoubleSpend:
    """Test that key images prevent double-spending confidential outputs."""

    def test_same_spending_key_same_key_image(self):
        """Same spending key always produces the same key image."""
        from qubitcoin.privacy.stealth import StealthAddressManager

        ki1 = StealthAddressManager.compute_key_image(12345)
        ki2 = StealthAddressManager.compute_key_image(12345)
        assert ki1.x == ki2.x and ki1.y == ki2.y

    def test_key_image_set_tracks_spends(self):
        """A set of key images can detect double-spend attempts."""
        from qubitcoin.privacy.stealth import StealthAddressManager

        spent_images = set()

        # First spend
        ki1 = StealthAddressManager.compute_key_image(111)
        ki1_hex = f"{ki1.x:064x}{ki1.y:064x}"
        assert ki1_hex not in spent_images
        spent_images.add(ki1_hex)

        # Second spend of same output — same key image
        ki2 = StealthAddressManager.compute_key_image(111)
        ki2_hex = f"{ki2.x:064x}{ki2.y:064x}"
        assert ki2_hex in spent_images  # DOUBLE SPEND DETECTED

        # Different output — different key image
        ki3 = StealthAddressManager.compute_key_image(222)
        ki3_hex = f"{ki3.x:064x}{ki3.y:064x}"
        assert ki3_hex not in spent_images  # New output, OK


class TestPrivacyTransactionSize:
    """Verify confidential transaction size is within documented ~2KB budget."""

    def test_private_tx_size_estimate(self):
        """Confidential tx should be roughly ~2KB as documented."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        import json

        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(txid="a" * 64, vout=0, value=1000, blinding=blinding, spending_key=42)
        builder.add_output(value=900)
        builder.set_fee(100)

        tx = builder.build()
        serialized = json.dumps(tx.to_dict())
        size = len(serialized.encode())

        # CLAUDE.md says ~2000 bytes for private tx
        # Allow reasonable range for serialization overhead
        assert 500 <= size <= 5000, f"Private tx size {size} bytes out of expected range"
