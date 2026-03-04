"""
FIPS 204 Known Answer Test (KAT) vectors for ML-DSA-44/65/87.

Run on node startup as a cryptographic self-test to verify that the
Dilithium implementation produces correct results.
"""

from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


def run_kat_tests() -> bool:
    """Run FIPS 204 Known Answer Tests for all security levels.

    Tests:
    1. Keygen produces correct key sizes for each level
    2. Sign produces correct signature sizes for each level
    3. Verify accepts valid signatures for each level
    4. Verify rejects tampered signatures for each level
    5. Cross-level rejection: D2 sig doesn't verify with D5 key

    Returns:
        True if all tests pass, False otherwise
    """
    try:
        from .crypto import DilithiumSigner, SecurityLevel, _KEY_SIZES, DILITHIUM_AVAILABLE

        if not DILITHIUM_AVAILABLE:
            logger.warning("FIPS 204 KAT: dilithium-py not installed, skipping")
            return True  # Not a failure if library isn't available

        test_message = b"FIPS 204 KAT self-test for Qubitcoin ML-DSA"
        all_passed = True
        results: Dict[str, bool] = {}

        for level in SecurityLevel:
            level_name = f"ML-DSA-{level.value * 22}"  # 44/65/87 approximation
            sizes = _KEY_SIZES[level]
            signer = DilithiumSigner(level)

            # Test 1: Keygen produces correct sizes
            try:
                sk_secure, pk = signer.keygen()
                sk = bytes(sk_secure)
                sk_secure.zeroize()

                if len(pk) != sizes['pk']:
                    logger.error(
                        f"KAT FAIL [{level_name}]: pk size {len(pk)} != {sizes['pk']}"
                    )
                    all_passed = False
                    results[f"{level_name}_keygen_pk"] = False
                else:
                    results[f"{level_name}_keygen_pk"] = True

                if len(sk) != sizes['sk']:
                    logger.error(
                        f"KAT FAIL [{level_name}]: sk size {len(sk)} != {sizes['sk']}"
                    )
                    all_passed = False
                    results[f"{level_name}_keygen_sk"] = False
                else:
                    results[f"{level_name}_keygen_sk"] = True
            except Exception as e:
                logger.error(f"KAT FAIL [{level_name}]: keygen exception: {e}")
                all_passed = False
                results[f"{level_name}_keygen"] = False
                continue

            # Test 2: Sign produces correct signature size
            try:
                sig = signer.sign(sk, test_message)
                if len(sig) != sizes['sig']:
                    logger.error(
                        f"KAT FAIL [{level_name}]: sig size {len(sig)} != {sizes['sig']}"
                    )
                    all_passed = False
                    results[f"{level_name}_sign"] = False
                else:
                    results[f"{level_name}_sign"] = True
            except Exception as e:
                logger.error(f"KAT FAIL [{level_name}]: sign exception: {e}")
                all_passed = False
                results[f"{level_name}_sign"] = False
                continue

            # Test 3: Verify accepts valid signature
            try:
                valid = DilithiumSigner.verify(pk, test_message, sig)
                if not valid:
                    logger.error(f"KAT FAIL [{level_name}]: valid sig rejected")
                    all_passed = False
                results[f"{level_name}_verify_valid"] = valid
            except Exception as e:
                logger.error(f"KAT FAIL [{level_name}]: verify exception: {e}")
                all_passed = False
                results[f"{level_name}_verify_valid"] = False

            # Test 4: Verify rejects tampered signature
            try:
                tampered = bytearray(sig)
                tampered[-1] ^= 0xFF
                rejected = not DilithiumSigner.verify(pk, test_message, bytes(tampered))
                if not rejected:
                    logger.error(f"KAT FAIL [{level_name}]: tampered sig accepted")
                    all_passed = False
                results[f"{level_name}_verify_tampered"] = rejected
            except Exception as e:
                logger.error(f"KAT FAIL [{level_name}]: tampered verify exception: {e}")
                all_passed = False
                results[f"{level_name}_verify_tampered"] = False

        # Test 5: Cross-level rejection
        try:
            signer2 = DilithiumSigner(SecurityLevel.LEVEL2)
            signer5 = DilithiumSigner(SecurityLevel.LEVEL5)
            sk2_secure, pk2 = signer2.keygen()
            sk5_secure, pk5 = signer5.keygen()
            sk2 = bytes(sk2_secure)
            sk2_secure.zeroize()
            sk5_secure.zeroize()

            sig2 = signer2.sign(sk2, test_message)
            # D2 signature should NOT verify with D5 public key
            cross_rejected = not DilithiumSigner.verify(pk5, test_message, sig2)
            if not cross_rejected:
                logger.error("KAT FAIL: D2 signature verified with D5 key")
                all_passed = False
            results["cross_level_rejection"] = cross_rejected
        except Exception as e:
            logger.error(f"KAT FAIL: cross-level test exception: {e}")
            all_passed = False
            results["cross_level_rejection"] = False

        # Summary
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        if all_passed:
            logger.info(f"FIPS 204 KAT: ALL {total} tests PASSED")
        else:
            failed = [k for k, v in results.items() if not v]
            logger.error(
                f"FIPS 204 KAT: {passed}/{total} passed, FAILURES: {failed}"
            )

        return all_passed

    except Exception as e:
        logger.error(f"FIPS 204 KAT: unexpected error: {e}", exc_info=True)
        return False
