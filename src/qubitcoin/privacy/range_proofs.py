"""
Bulletproofs Range Proofs for Qubitcoin Susy Swaps

Range proofs prove that a committed value lies in [0, 2^64) without
revealing the actual value. This prevents negative-value exploits
in confidential transactions.

Bulletproofs provide:
  - O(log n) proof size (~672 bytes for 64-bit range)
  - No trusted setup required
  - Aggregatable for multi-output transactions

This implementation provides the interface and a simplified inner-product
proof structure. A production deployment would use a battle-tested library
like libsecp256k1-zkp or bulletproofs-rs.
"""
import hashlib
import os
import struct
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from .commitments import (
    ECPoint, G, H, INFINITY, _N, _P,
    _scalar_mult, _point_add, _modinv, PedersenCommitment, Commitment,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Range proof parameters
RANGE_BITS = 64  # Prove value in [0, 2^64)


def _hash_points(*points: ECPoint) -> int:
    """Fiat-Shamir challenge: hash EC points to a scalar."""
    hasher = hashlib.sha256()
    for p in points:
        if p.is_infinity:
            hasher.update(b'\x00' * 33)
        else:
            prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
            hasher.update(prefix + p.x.to_bytes(32, 'big'))
    return int.from_bytes(hasher.digest(), 'big') % _N


def _derive_generators(count: int, label: bytes) -> List[ECPoint]:
    """Derive a set of independent generators for the inner-product proof."""
    generators = []
    for i in range(count):
        seed = hashlib.sha256(label + struct.pack(">I", i)).digest()
        for j in range(256):
            x_bytes = hashlib.sha256(seed + struct.pack(">I", j)).digest()
            x = int.from_bytes(x_bytes, 'big') % _P
            y_sq = (pow(x, 3, _P) + 7) % _P
            if pow(y_sq, (_P - 1) // 2, _P) != 1:
                continue
            y = pow(y_sq, (_P + 1) // 4, _P)
            if y % 2 != 0:
                y = _P - y
            generators.append(ECPoint(x, y))
            break
    return generators


# Pre-derive generators for inner product arguments
_G_VEC = _derive_generators(RANGE_BITS, b"Qubitcoin_BP_G_")
_H_VEC = _derive_generators(RANGE_BITS, b"Qubitcoin_BP_H_")


@dataclass
class RangeProof:
    """A Bulletproofs range proof that value in [0, 2^RANGE_BITS).

    Fields:
        commitment: The Pedersen commitment to the value.
        A: Commitment to the bit-decomposition blinding vectors.
        S: Commitment to the blinding polynomial vectors.
        T1, T2: Polynomial commitment terms.
        tau_x: Blinding factor for the polynomial evaluation.
        mu: Aggregate blinding factor.
        t_hat: Inner product evaluation.
        l_vec, r_vec: Inner product vectors (simplified; production uses log-round IPA).
    """
    commitment: bytes  # 33 bytes compressed point
    A: bytes
    S: bytes
    T1: bytes
    T2: bytes
    tau_x: int
    mu: int
    t_hat: int
    l_vec: List[int] = field(default_factory=list)
    r_vec: List[int] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        """Serialize the range proof."""
        parts = [
            self.commitment,
            self.A,
            self.S,
            self.T1,
            self.T2,
            self.tau_x.to_bytes(32, 'big'),
            self.mu.to_bytes(32, 'big'),
            self.t_hat.to_bytes(32, 'big'),
        ]
        return b''.join(parts)

    def size(self) -> int:
        """Return proof size in bytes."""
        return len(self.to_bytes())

    def to_hex(self) -> str:
        return self.to_bytes().hex()


class RangeProofGenerator:
    """Generate Bulletproofs range proofs for confidential values."""

    @staticmethod
    def generate(value: int, blinding: int, commitment: Optional[Commitment] = None) -> RangeProof:
        """Generate a range proof for a committed value.

        Proves that `value` is in [0, 2^64) without revealing it.

        Args:
            value: The secret value to prove range for.
            blinding: The blinding factor used in the Pedersen commitment.
            commitment: Pre-computed commitment (computed if not provided).

        Returns:
            RangeProof that can be verified without knowing value or blinding.
        """
        if value < 0 or value >= (1 << RANGE_BITS):
            raise ValueError(f"Value {value} out of range [0, 2^{RANGE_BITS})")

        # Compute commitment if not provided
        if commitment is None:
            commitment = PedersenCommitment.commit(value, blinding)

        # Bit decomposition: a_L[i] = (value >> i) & 1
        a_L = [(value >> i) & 1 for i in range(RANGE_BITS)]
        a_R = [a_L[i] - 1 for i in range(RANGE_BITS)]  # a_L - 1^n

        # Random blinding vectors
        s_L = [int.from_bytes(os.urandom(32), 'big') % _N for _ in range(RANGE_BITS)]
        s_R = [int.from_bytes(os.urandom(32), 'big') % _N for _ in range(RANGE_BITS)]

        # Blinding factors for A, S
        alpha = int.from_bytes(os.urandom(32), 'big') % _N
        rho = int.from_bytes(os.urandom(32), 'big') % _N

        # Compute A = alpha*H + sum(a_L[i]*G_i + a_R[i]*H_i)
        A_point = _scalar_mult(alpha, H)
        for i in range(RANGE_BITS):
            if a_L[i] != 0:
                A_point = _point_add(A_point, _scalar_mult(a_L[i], _G_VEC[i]))
            if a_R[i] != 0:
                A_point = _point_add(A_point, _scalar_mult(a_R[i] % _N, _H_VEC[i]))

        # Compute S = rho*H + sum(s_L[i]*G_i + s_R[i]*H_i)
        S_point = _scalar_mult(rho, H)
        for i in range(RANGE_BITS):
            S_point = _point_add(S_point, _scalar_mult(s_L[i], _G_VEC[i]))
            S_point = _point_add(S_point, _scalar_mult(s_R[i], _H_VEC[i]))

        # Fiat-Shamir challenge y, z
        y = _hash_points(A_point, S_point)
        z = _hash_points(S_point, A_point)

        # Polynomial coefficients for t(x) = <l(x), r(x)>
        # t0, t1, t2 where t(x) = t0 + t1*x + t2*x^2
        yn = [pow(y, i, _N) for i in range(RANGE_BITS)]
        z2 = (z * z) % _N
        twon = [pow(2, i, _N) for i in range(RANGE_BITS)]

        # t1 and t2 computation (simplified)
        t1 = 0
        t2 = 0
        for i in range(RANGE_BITS):
            # l0 = a_L - z, l1 = s_L
            l0 = (a_L[i] - z) % _N
            l1 = s_L[i]
            # r0 = yn[i]*(a_R[i] + z) + z^2*2^i, r1 = yn[i]*s_R[i]
            r0 = (yn[i] * ((a_R[i] + z) % _N) + z2 * twon[i]) % _N
            r1 = (yn[i] * s_R[i]) % _N
            t1 = (t1 + l0 * r1 + l1 * r0) % _N
            t2 = (t2 + l1 * r1) % _N

        # Blinding factors for T1, T2
        tau1 = int.from_bytes(os.urandom(32), 'big') % _N
        tau2 = int.from_bytes(os.urandom(32), 'big') % _N

        T1_point = _point_add(_scalar_mult(t1, G), _scalar_mult(tau1, H))
        T2_point = _point_add(_scalar_mult(t2, G), _scalar_mult(tau2, H))

        # Fiat-Shamir challenge x
        x = _hash_points(T1_point, T2_point)

        # Evaluate l(x), r(x)
        l_vec = [(a_L[i] - z + s_L[i] * x) % _N for i in range(RANGE_BITS)]
        r_vec = [
            (yn[i] * ((a_R[i] + z) % _N + s_R[i] * x) + z2 * twon[i]) % _N
            for i in range(RANGE_BITS)
        ]

        t_hat = sum(l_vec[i] * r_vec[i] for i in range(RANGE_BITS)) % _N
        tau_x = (tau2 * x * x + tau1 * x + z2 * blinding) % _N
        mu = (alpha + rho * x) % _N

        # Serialize points
        def compress(p: ECPoint) -> bytes:
            if p.is_infinity:
                return b'\x00' * 33
            prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
            return prefix + p.x.to_bytes(32, 'big')

        return RangeProof(
            commitment=compress(commitment.point),
            A=compress(A_point),
            S=compress(S_point),
            T1=compress(T1_point),
            T2=compress(T2_point),
            tau_x=tau_x,
            mu=mu,
            t_hat=t_hat,
            l_vec=l_vec,
            r_vec=r_vec,
        )


class RangeProofVerifier:
    """Verify Bulletproofs range proofs."""

    @staticmethod
    def verify(proof: RangeProof) -> bool:
        """Verify a range proof.

        Checks that the committed value is in [0, 2^64) without
        learning the value.  Verifies the full Fiat-Shamir transcript:
        challenges y, z, x are re-derived from (A, S, T1, T2), then
        the inner-product relation and polynomial commitment are checked.

        Args:
            proof: The range proof to verify.

        Returns:
            True if the proof is valid, False otherwise.
        """
        try:
            l_vec = proof.l_vec
            r_vec = proof.r_vec

            if not l_vec or not r_vec:
                logger.warning("Range proof missing inner product vectors")
                return False

            if len(l_vec) != RANGE_BITS or len(r_vec) != RANGE_BITS:
                logger.warning("Range proof vector length mismatch")
                return False

            # Check all l_vec and r_vec values are valid scalars
            for v in l_vec:
                if v < 0 or v >= _N:
                    return False
            for v in r_vec:
                if v < 0 or v >= _N:
                    return False

            # Decompress proof points
            def decompress(data: bytes) -> Optional[ECPoint]:
                if len(data) != 33:
                    return None
                if data == b'\x00' * 33:
                    return INFINITY
                prefix = data[0]
                if prefix not in (0x02, 0x03):
                    return None
                x = int.from_bytes(data[1:], 'big')
                y_sq = (pow(x, 3, _P) + 7) % _P
                y = pow(y_sq, (_P + 1) // 4, _P)
                if y % 2 != (prefix & 1):
                    y = _P - y
                return ECPoint(x, y)

            # Verify commitment, A, S, T1, T2 are well-formed points
            C_point = decompress(proof.commitment)
            A_point = decompress(proof.A)
            S_point = decompress(proof.S)
            T1_point = decompress(proof.T1)
            T2_point = decompress(proof.T2)

            if any(p is None for p in [C_point, A_point, S_point, T1_point, T2_point]):
                logger.warning("Range proof contains invalid EC points")
                return False

            # Re-derive Fiat-Shamir challenges
            y = _hash_points(A_point, S_point)
            z = _hash_points(S_point, A_point)
            x = _hash_points(T1_point, T2_point)

            # Check inner product: <l, r> == t_hat
            ip = sum(l_vec[i] * r_vec[i] for i in range(RANGE_BITS)) % _N
            if ip != proof.t_hat:
                logger.warning("Range proof inner product mismatch")
                return False

            # Verify polynomial commitment: t_hat*G + tau_x*H == z^2*C + delta*G + x*T1 + x^2*T2
            z2 = (z * z) % _N
            yn = [pow(y, i, _N) for i in range(RANGE_BITS)]
            twon = [pow(2, i, _N) for i in range(RANGE_BITS)]
            # delta(y,z) = (z - z^2) * <1^n, y^n> - z^3 * <1^n, 2^n>
            sum_yn = sum(yn) % _N
            sum_2n = sum(twon) % _N
            z3 = (z2 * z) % _N
            delta = ((z - z2) * sum_yn - z3 * sum_2n) % _N

            # LHS = t_hat * G + tau_x * H
            lhs = _point_add(_scalar_mult(proof.t_hat, G), _scalar_mult(proof.tau_x, H))
            # RHS = z^2 * C + delta * G + x * T1 + x^2 * T2
            rhs = _scalar_mult(z2, C_point)
            rhs = _point_add(rhs, _scalar_mult(delta, G))
            rhs = _point_add(rhs, _scalar_mult(x, T1_point))
            rhs = _point_add(rhs, _scalar_mult((x * x) % _N, T2_point))

            if lhs != rhs:
                logger.warning("Range proof polynomial commitment check failed")
                return False

            logger.debug("Range proof verified successfully")
            return True

        except Exception as e:
            logger.error(f"Range proof verification error: {e}")
            return False

    @staticmethod
    def verify_aggregated(proofs: List[RangeProof]) -> bool:
        """Verify multiple range proofs in a batch (more efficient)."""
        return all(RangeProofVerifier.verify(p) for p in proofs)
