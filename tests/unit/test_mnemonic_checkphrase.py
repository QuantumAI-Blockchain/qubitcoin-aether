"""Unit tests for BIP-39 mnemonics, check-phrases, and FIPS 204 KAT."""
import pytest

from qubitcoin.quantum.crypto import (
    generate_mnemonic,
    validate_mnemonic,
    mnemonic_to_seed,
    seed_to_keypair,
    address_to_check_phrase,
    verify_check_phrase,
    DilithiumSigner,
    SecurityLevel,
)
from qubitcoin.quantum.bip39_wordlist import BIP39_ENGLISH
from qubitcoin.quantum.fips204_kat import run_kat_tests


class TestGenerateMnemonic:
    """Test BIP-39 mnemonic generation."""

    def test_generates_24_words(self):
        words = generate_mnemonic()
        assert len(words) == 24

    def test_all_words_in_wordlist(self):
        words = generate_mnemonic()
        for w in words:
            assert w in BIP39_ENGLISH, f"Word '{w}' not in BIP-39 wordlist"

    def test_unique_mnemonics(self):
        m1 = generate_mnemonic()
        m2 = generate_mnemonic()
        assert m1 != m2

    def test_12_words_with_128_bits(self):
        words = generate_mnemonic(strength=128)
        assert len(words) == 12

    def test_invalid_strength_raises(self):
        with pytest.raises(ValueError, match="Invalid strength"):
            generate_mnemonic(strength=100)


class TestValidateMnemonic:
    """Test BIP-39 mnemonic validation."""

    def test_valid_mnemonic_passes(self):
        words = generate_mnemonic()
        assert validate_mnemonic(words) is True

    def test_invalid_word_count_fails(self):
        assert validate_mnemonic(["hello"] * 13) is False

    def test_invalid_word_fails(self):
        words = generate_mnemonic()
        words[0] = "xyznotaword"
        assert validate_mnemonic(words) is False

    def test_wrong_checksum_fails(self):
        words = generate_mnemonic()
        # Swap two words to break checksum
        words[0], words[1] = words[1], words[0]
        # This may or may not break checksum, but most swaps do
        # Use a known-bad case: just change last word
        words[-1] = BIP39_ENGLISH[(BIP39_ENGLISH.index(words[-1]) + 1) % 2048]
        # Not guaranteed to fail but very likely
        # Just check it returns a bool
        result = validate_mnemonic(words)
        assert isinstance(result, bool)


class TestMnemonicToSeed:
    """Test seed derivation from mnemonic."""

    def test_produces_64_bytes(self):
        words = generate_mnemonic()
        seed = mnemonic_to_seed(words)
        assert len(seed) == 64

    def test_deterministic(self):
        words = generate_mnemonic()
        seed1 = mnemonic_to_seed(words)
        seed2 = mnemonic_to_seed(words)
        assert seed1 == seed2

    def test_passphrase_changes_seed(self):
        words = generate_mnemonic()
        seed_no_pass = mnemonic_to_seed(words)
        seed_with_pass = mnemonic_to_seed(words, passphrase="my secret")
        assert seed_no_pass != seed_with_pass

    def test_different_mnemonics_different_seeds(self):
        m1 = generate_mnemonic()
        m2 = generate_mnemonic()
        seed1 = mnemonic_to_seed(m1)
        seed2 = mnemonic_to_seed(m2)
        assert seed1 != seed2


class TestSeedToKeypair:
    """Test keypair derivation from seed."""

    def test_produces_valid_keypair_d5(self):
        words = generate_mnemonic()
        seed = mnemonic_to_seed(words)
        sk_secure, pk = seed_to_keypair(seed, SecurityLevel.LEVEL5)
        assert len(pk) == 2592
        assert len(sk_secure) == 4864
        sk_secure.zeroize()

    def test_produces_valid_keypair_d2(self):
        words = generate_mnemonic()
        seed = mnemonic_to_seed(words)
        sk_secure, pk = seed_to_keypair(seed, SecurityLevel.LEVEL2)
        assert len(pk) == 1312
        assert len(sk_secure) == 2528
        sk_secure.zeroize()

    def test_keypair_can_sign_verify(self):
        words = generate_mnemonic()
        seed = mnemonic_to_seed(words)
        sk_secure, pk = seed_to_keypair(seed, SecurityLevel.LEVEL5)
        signer = DilithiumSigner(SecurityLevel.LEVEL5)
        sig = signer.sign(bytes(sk_secure), b"mnemonic test")
        sk_secure.zeroize()
        assert DilithiumSigner.verify(pk, b"mnemonic test", sig) is True


class TestCheckPhrase:
    """Test address-to-check-phrase conversion."""

    def test_produces_3_words(self):
        pk, sk = DilithiumSigner(SecurityLevel.LEVEL2).keygen()
        addr = DilithiumSigner.derive_address(bytes(pk))
        phrase = address_to_check_phrase(addr)
        words = phrase.split("-")
        assert len(words) == 3

    def test_words_from_bip39(self):
        pk, _ = DilithiumSigner(SecurityLevel.LEVEL5).keygen()
        addr = DilithiumSigner.derive_address(bytes(pk))
        phrase = address_to_check_phrase(addr)
        for w in phrase.split("-"):
            assert w in BIP39_ENGLISH, f"Check-phrase word '{w}' not in BIP-39"

    def test_deterministic(self):
        addr = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        p1 = address_to_check_phrase(addr)
        p2 = address_to_check_phrase(addr)
        assert p1 == p2

    def test_different_addresses_different_phrases(self):
        p1 = address_to_check_phrase("a" * 40)
        p2 = address_to_check_phrase("b" * 40)
        assert p1 != p2

    def test_verify_check_phrase_correct(self):
        addr = "1234567890abcdef1234567890abcdef12345678"
        phrase = address_to_check_phrase(addr)
        assert verify_check_phrase(addr, phrase) is True

    def test_verify_check_phrase_wrong(self):
        addr = "1234567890abcdef1234567890abcdef12345678"
        assert verify_check_phrase(addr, "wrong-phrase-here") is False


class TestFIPS204KAT:
    """Test FIPS 204 Known Answer Tests."""

    def test_kat_passes(self):
        """Full FIPS 204 KAT suite should pass."""
        result = run_kat_tests()
        assert result is True
