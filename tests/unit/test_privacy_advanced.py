"""Comprehensive privacy module tests — Pedersen commitments, stealth addresses,
range proofs, and confidential transaction verification."""
import pytest


class TestPedersenCommitmentAdvanced:
    """Extended Pedersen commitment tests."""

    def test_commit_with_explicit_blinding(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        blinding = PedersenCommitment.generate_blinding()
        c = PedersenCommitment.commit(500, blinding=blinding)
        assert c.blinding == blinding
        assert c.value == 500

    def test_same_value_different_blinding(self):
        """Same value with different blindings produces different commitments."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        c1 = PedersenCommitment.commit(100)
        c2 = PedersenCommitment.commit(100)
        assert c1.point != c2.point  # Random blindings differ

    def test_zero_value_commitment(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        c = PedersenCommitment.commit(0)
        assert c.value == 0
        assert c.point is not None

    def test_large_value_commitment(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        c = PedersenCommitment.commit(10**18)  # Very large value
        assert c.point is not None

    def test_verify_sum_unbalanced_fails(self):
        """Inputs != outputs should fail verification."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        c_in = PedersenCommitment.commit(100)
        c_out = PedersenCommitment.commit(200)
        # Blindings don't match, and values don't match
        result = PedersenCommitment.verify_sum([c_in], [c_out])
        assert result is False

    def test_commitment_hex_roundtrip(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        c = PedersenCommitment.commit(42)
        hex_str = c.to_hex()
        assert isinstance(hex_str, str)
        assert len(hex_str) > 0

    def test_multiple_inputs_outputs_balanced(self):
        """Multiple inputs and outputs that balance."""
        from qubitcoin.privacy.commitments import PedersenCommitment
        # Create 3 inputs: 100, 200, 300 = 600 total
        c_in1 = PedersenCommitment.commit(100)
        c_in2 = PedersenCommitment.commit(200)
        c_in3 = PedersenCommitment.commit(300)
        total_blinding = c_in1.blinding + c_in2.blinding + c_in3.blinding

        # Create 2 outputs: 250, 350 = 600 total (matching blindings)
        c_out1 = PedersenCommitment.commit(250, blinding=total_blinding - 77)
        c_out2 = PedersenCommitment.commit(350, blinding=77)

        result = PedersenCommitment.verify_sum(
            [c_in1, c_in2, c_in3], [c_out1, c_out2]
        )
        assert result is True


class TestStealthAddressAdvanced:
    """Extended stealth address tests."""

    def test_different_keypairs_different_addresses(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp1 = StealthAddressManager.generate_keypair()
        kp2 = StealthAddressManager.generate_keypair()
        assert kp1.public_address() != kp2.public_address()

    def test_output_not_scannable_by_wrong_key(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        sender_kp = StealthAddressManager.generate_keypair()
        receiver_kp = StealthAddressManager.generate_keypair()
        wrong_kp = StealthAddressManager.generate_keypair()

        output = StealthAddressManager.create_output(
            receiver_kp.spend_pubkey, receiver_kp.view_pubkey
        )
        # Wrong keypair should not detect this output
        is_mine = StealthAddressManager.scan_output(
            wrong_kp, output.ephemeral_pubkey, output.one_time_address
        )
        assert is_mine is False

    def test_multiple_outputs_scannable(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        receiver = StealthAddressManager.generate_keypair()

        # Create multiple outputs to the same receiver
        outputs = []
        for _ in range(3):
            out = StealthAddressManager.create_output(
                receiver.spend_pubkey, receiver.view_pubkey
            )
            outputs.append(out)

        # All should be scannable by receiver
        for out in outputs:
            is_mine = StealthAddressManager.scan_output(
                receiver, out.ephemeral_pubkey, out.one_time_address
            )
            assert is_mine is True

    def test_each_output_unique_address(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        receiver = StealthAddressManager.generate_keypair()

        out1 = StealthAddressManager.create_output(
            receiver.spend_pubkey, receiver.view_pubkey
        )
        out2 = StealthAddressManager.create_output(
            receiver.spend_pubkey, receiver.view_pubkey
        )
        assert out1.one_time_address != out2.one_time_address


class TestRangeProofAdvanced:
    """Extended range proof tests."""

    def test_proof_for_zero(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier
        c = PedersenCommitment.commit(0)
        proof = RangeProofGenerator.generate(value=0, blinding=c.blinding)
        assert RangeProofVerifier.verify(proof) is True

    def test_proof_for_large_value(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator, RangeProofVerifier
        c = PedersenCommitment.commit(2**32 - 1)
        proof = RangeProofGenerator.generate(value=2**32 - 1, blinding=c.blinding)
        assert RangeProofVerifier.verify(proof) is True

    def test_proof_has_expected_fields(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator
        c = PedersenCommitment.commit(42)
        proof = RangeProofGenerator.generate(value=42, blinding=c.blinding)
        assert proof.commitment is not None
        # Bulletproof inner-product structure
        assert hasattr(proof, 'A')
        assert hasattr(proof, 'S')
        assert hasattr(proof, 'tau_x')


class TestSusySwapAdvanced:
    """Extended confidential transaction tests."""

    def test_multiple_inputs(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        builder = SusySwapBuilder()
        for i in range(3):
            blinding = PedersenCommitment.generate_blinding()
            builder.add_input(
                txid=f"{'a' * 63}{i}", vout=0,
                value=50 * (10**8),
                blinding=blinding,
                spending_key=PedersenCommitment.generate_blinding(),
            )
        builder.add_output(value=140 * (10**8))
        builder.set_fee(10 * (10**8))
        tx = builder.build()
        assert len(tx.inputs) == 3
        assert len(tx.outputs) == 1

    def test_multiple_outputs(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(
            txid='b' * 64, vout=0,
            value=100 * (10**8),
            blinding=blinding,
            spending_key=PedersenCommitment.generate_blinding(),
        )
        builder.add_output(value=40 * (10**8))
        builder.add_output(value=50 * (10**8))
        builder.set_fee(10 * (10**8))
        tx = builder.build()
        assert len(tx.outputs) == 2

    def test_key_image_unique_per_input(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        builder = SusySwapBuilder()
        for i in range(2):
            blinding = PedersenCommitment.generate_blinding()
            builder.add_input(
                txid=f"{'c' * 63}{i}", vout=0,
                value=50 * (10**8),
                blinding=blinding,
                spending_key=PedersenCommitment.generate_blinding(),
            )
        builder.add_output(value=90 * (10**8))
        builder.set_fee(10 * (10**8))
        tx = builder.build()
        # Key images should be unique (inputs may be dicts or objects)
        key_images = []
        for inp in tx.inputs:
            ki = inp['key_image'] if isinstance(inp, dict) else inp.key_image
            key_images.append(str(ki))
        assert len(set(key_images)) == len(key_images)

    def test_transaction_has_balance_proof(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.commitments import PedersenCommitment
        blinding = PedersenCommitment.generate_blinding()
        builder = SusySwapBuilder()
        builder.add_input(
            txid='d' * 64, vout=0,
            value=100 * (10**8),
            blinding=blinding,
            spending_key=PedersenCommitment.generate_blinding(),
        )
        builder.add_output(value=90 * (10**8))
        builder.set_fee(10 * (10**8))
        tx = builder.build()
        assert tx.excess_commitment is not None  # Balance proof (commitment to zero)
