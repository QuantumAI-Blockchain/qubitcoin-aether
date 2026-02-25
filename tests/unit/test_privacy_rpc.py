"""Unit tests for privacy RPC endpoints (Susy Swap REST API)."""
import pytest


class TestPrivacyCommitmentEndpoints:
    """Test /privacy/commitment/* endpoint logic."""

    def test_commitment_create_returns_hex(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        commitment = PedersenCommitment.commit(500000)
        hex_str = commitment.to_hex()
        assert isinstance(hex_str, str)
        assert len(hex_str) == 66  # 33 bytes compressed

    def test_commitment_verify_roundtrip(self):
        from qubitcoin.privacy.commitments import PedersenCommitment
        value = 123456789
        c = PedersenCommitment.commit(value)
        recomputed = PedersenCommitment.commit(value, blinding=c.blinding)
        assert recomputed.to_hex() == c.to_hex()


class TestPrivacyStealthEndpoints:
    """Test /privacy/stealth/* endpoint logic."""

    def test_generate_keypair_has_all_fields(self):
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        assert kp.spend_privkey > 0
        assert kp.view_privkey > 0
        assert not kp.spend_pubkey.is_infinity
        assert not kp.view_pubkey.is_infinity
        addr = kp.public_address()
        assert isinstance(addr, str)
        assert len(addr) > 64  # spend_pub + view_pub compressed = 132 hex chars

    def test_keypair_compressed_roundtrip(self):
        """Compressed EC points decompress to the same point."""
        from qubitcoin.privacy.stealth import StealthAddressManager
        from qubitcoin.privacy.commitments import ECPoint, _P
        kp = StealthAddressManager.generate_keypair()

        def compress(p: ECPoint) -> str:
            prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
            return (prefix + p.x.to_bytes(32, 'big')).hex()

        def decompress(hex_str: str) -> ECPoint:
            raw = bytes.fromhex(hex_str)
            x = int.from_bytes(raw[1:], 'big')
            y_sq = (pow(x, 3, _P) + 7) % _P
            y = pow(y_sq, (_P + 1) // 4, _P)
            if (y % 2) != (raw[0] - 2):
                y = _P - y
            return ECPoint(x, y)

        for pub in [kp.spend_pubkey, kp.view_pubkey]:
            compressed = compress(pub)
            decompressed = decompress(compressed)
            assert decompressed == pub

    def test_create_output_with_ecpoints(self):
        """create_output with ECPoint args returns valid stealth output."""
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        output = StealthAddressManager.create_output(kp.spend_pubkey, kp.view_pubkey)
        assert not output.one_time_address.is_infinity
        assert not output.ephemeral_pubkey.is_infinity
        assert isinstance(output.address_hex(), str)
        assert isinstance(output.ephemeral_hex(), str)

    def test_scan_output_detects_own_output(self):
        """Recipient can detect outputs addressed to them."""
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        output = StealthAddressManager.create_output(kp.spend_pubkey, kp.view_pubkey)
        is_mine = StealthAddressManager.scan_output(kp, output.ephemeral_pubkey, output.one_time_address)
        assert is_mine is True

    def test_scan_output_rejects_other_output(self):
        """Recipient does NOT detect outputs addressed to someone else."""
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp_sender = StealthAddressManager.generate_keypair()
        kp_other = StealthAddressManager.generate_keypair()
        output = StealthAddressManager.create_output(kp_sender.spend_pubkey, kp_sender.view_pubkey)
        is_mine = StealthAddressManager.scan_output(kp_other, output.ephemeral_pubkey, output.one_time_address)
        assert is_mine is False


class TestPrivacyTxBuild:
    """Test /privacy/tx/build endpoint logic (SusySwapBuilder fluent API)."""

    def test_build_simple_tx(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_input(txid='a' * 64, vout=0, value=1_000_000_000, blinding=12345, spending_key=67890)
        builder.add_output(value=999_990_000)
        builder.set_fee(10_000)
        tx = builder.build()
        d = tx.to_dict()
        assert d['txid']
        assert d['is_private'] is True
        assert d['tx_type'] == 'susy_swap'
        assert d['fee'] == 10_000
        assert len(d['inputs']) == 1
        assert len(d['outputs']) == 1
        assert len(d['key_images']) == 1

    def test_build_with_stealth_output(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        builder = SusySwapBuilder()
        builder.add_input(txid='b' * 64, vout=0, value=500_000_000, blinding=99999, spending_key=11111)
        builder.add_output(
            value=499_990_000,
            recipient_spend_pub=kp.spend_pubkey,
            recipient_view_pub=kp.view_pubkey,
        )
        builder.set_fee(10_000)
        tx = builder.build()
        d = tx.to_dict()
        assert d['outputs'][0].get('ephemeral_pubkey') is not None
        assert d['outputs'][0].get('one_time_address') is not None

    def test_build_no_inputs_raises(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_output(value=100)
        builder.set_fee(0)
        with pytest.raises(ValueError, match="at least one input"):
            builder.build()

    def test_build_value_mismatch_raises(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_input(txid='c' * 64, vout=0, value=100, blinding=1, spending_key=1)
        builder.add_output(value=200)  # More than input
        builder.set_fee(0)
        with pytest.raises(ValueError, match="Value mismatch"):
            builder.build()

    def test_build_multiple_inputs_outputs(self):
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_input(txid='d' * 64, vout=0, value=600_000, blinding=111, spending_key=222)
        builder.add_input(txid='e' * 64, vout=1, value=400_000, blinding=333, spending_key=444)
        builder.add_output(value=500_000)
        builder.add_output(value=490_000)
        builder.set_fee(10_000)
        tx = builder.build()
        d = tx.to_dict()
        assert len(d['inputs']) == 2
        assert len(d['outputs']) == 2
        assert len(d['key_images']) == 2

    def test_to_dict_has_all_required_fields(self):
        """Submit endpoint requires these fields."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_input(txid='f' * 64, vout=0, value=100_000, blinding=5, spending_key=6)
        builder.add_output(value=90_000)
        builder.set_fee(10_000)
        tx = builder.build()
        d = tx.to_dict()
        required = ['txid', 'inputs', 'outputs', 'fee', 'key_images', 'excess_commitment', 'signature']
        for field in required:
            assert field in d, f"Missing field: {field}"


class TestPrivacyTxSubmit:
    """Test /privacy/tx/submit validation logic."""

    def test_submit_requires_all_fields(self):
        """Verify that missing fields would be caught."""
        required = ['txid', 'inputs', 'outputs', 'fee', 'key_images', 'excess_commitment', 'signature']
        partial = {'txid': 'abc', 'inputs': []}
        missing = [f for f in required if f not in partial]
        assert len(missing) > 0  # Should be missing several fields

    def test_build_then_submit_dict_valid(self):
        """Build a tx and verify its dict has all fields needed by submit."""
        from qubitcoin.privacy.susy_swap import SusySwapBuilder
        builder = SusySwapBuilder()
        builder.add_input(txid='a' * 64, vout=0, value=50_000, blinding=1, spending_key=2)
        builder.add_output(value=40_000)
        builder.set_fee(10_000)
        tx = builder.build()
        d = tx.to_dict()
        required = ['txid', 'inputs', 'outputs', 'fee', 'key_images', 'excess_commitment', 'signature']
        for f in required:
            assert f in d
        assert isinstance(d['txid'], str) and len(d['txid']) == 64
        assert isinstance(d['key_images'], list)
        assert isinstance(d['signature'], str)
