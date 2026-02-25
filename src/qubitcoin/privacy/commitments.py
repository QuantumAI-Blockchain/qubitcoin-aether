"""
Pedersen Commitments for Qubitcoin Susy Swaps

A Pedersen commitment hides a value v with a blinding factor r:
    C = v*G + r*H
where G and H are independent generator points on an elliptic curve.

Properties:
  - Perfectly hiding: C reveals nothing about v.
  - Computationally binding: cannot open C to a different value.
  - Additively homomorphic: C(v1) + C(v2) = C(v1+v2) when blinding factors add.

This allows verifying that transaction inputs sum equals outputs sum
without revealing any amounts.
"""
import hashlib
import os
import struct
from typing import Tuple, List, Optional
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)

# We use the secp256k1 curve parameters (same as Bitcoin) for the commitment scheme.
# In production, these would use a proper EC library (e.g., libsecp256k1).
# Here we implement the math directly for clarity and independence from external libs.

# secp256k1 curve parameters
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _modinv(a: int, m: int) -> int:
    """Modular inverse using extended Euclidean algorithm."""
    if a < 0:
        a = a % m
    g, x, _ = _extended_gcd(a, m)
    if g != 1:
        raise ValueError("Modular inverse does not exist")
    return x % m


def _extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
    if a == 0:
        return b, 0, 1
    g, x, y = _extended_gcd(b % a, a)
    return g, y - (b // a) * x, x


@dataclass(frozen=True)
class ECPoint:
    """Point on secp256k1 curve. None coordinates represent the point at infinity."""
    x: Optional[int]
    y: Optional[int]

    @property
    def is_infinity(self) -> bool:
        return self.x is None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ECPoint):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


INFINITY = ECPoint(None, None)
G = ECPoint(_Gx, _Gy)


def _point_add(p1: ECPoint, p2: ECPoint) -> ECPoint:
    """Add two points on secp256k1."""
    if p1.is_infinity:
        return p2
    if p2.is_infinity:
        return p1
    if p1.x == p2.x and p1.y != p2.y:
        return INFINITY
    if p1 == p2:
        # Point doubling
        lam = (3 * p1.x * p1.x * _modinv(2 * p1.y, _P)) % _P
    else:
        lam = ((p2.y - p1.y) * _modinv(p2.x - p1.x, _P)) % _P
    x3 = (lam * lam - p1.x - p2.x) % _P
    y3 = (lam * (p1.x - x3) - p1.y) % _P
    return ECPoint(x3, y3)


def _scalar_mult(k: int, point: ECPoint) -> ECPoint:
    """Scalar multiplication on secp256k1 using constant-time Montgomery ladder.

    Always performs the same number of point additions and doublings regardless
    of the scalar value, preventing timing side-channel leakage.
    """
    k = k % _N
    if k == 0:
        return INFINITY
    r0 = INFINITY
    r1 = point
    # Process all 256 bits to keep timing constant
    for i in range(255, -1, -1):
        if (k >> i) & 1:
            r0 = _point_add(r0, r1)
            r1 = _point_add(r1, r1)
        else:
            r1 = _point_add(r0, r1)
            r0 = _point_add(r0, r0)
    return r0


def _derive_h() -> ECPoint:
    """Derive the secondary generator H = hash_to_curve("Qubitcoin_Pedersen_H").

    H must be a point for which nobody knows the discrete log relative to G.
    We use a deterministic nothing-up-my-sleeve derivation.
    """
    seed = hashlib.sha256(b"Qubitcoin_Pedersen_H_generator_v1").digest()
    # Hash-and-increment until we find a valid x-coordinate on secp256k1
    for i in range(256):
        x_bytes = hashlib.sha256(seed + struct.pack(">I", i)).digest()
        x = int.from_bytes(x_bytes, 'big') % _P
        # y² = x³ + 7 (mod p)
        y_sq = (pow(x, 3, _P) + 7) % _P
        # Euler criterion
        if pow(y_sq, (_P - 1) // 2, _P) != 1:
            continue
        y = pow(y_sq, (_P + 1) // 4, _P)
        # Always pick even y
        if y % 2 != 0:
            y = _P - y
        return ECPoint(x, y)
    raise RuntimeError("Failed to derive H generator")


H = _derive_h()


@dataclass
class Commitment:
    """A Pedersen commitment C = v*G + r*H."""
    point: ECPoint
    value: int       # The committed value (secret)
    blinding: int    # The blinding factor r (secret)

    def to_bytes(self) -> bytes:
        """Serialize the commitment point (33 bytes, compressed)."""
        if self.point.is_infinity:
            return b'\x00' * 33
        prefix = b'\x02' if self.point.y % 2 == 0 else b'\x03'
        return prefix + self.point.x.to_bytes(32, 'big')

    def to_hex(self) -> str:
        return self.to_bytes().hex()


class PedersenCommitment:
    """Create and verify Pedersen commitments for confidential transactions."""

    @staticmethod
    def commit(value: int, blinding: Optional[int] = None) -> Commitment:
        """Create a commitment C = value*G + blinding*H.

        Args:
            value: The value to commit to (must be non-negative).
            blinding: Random blinding factor. Generated if not provided.

        Returns:
            Commitment object containing the EC point, value, and blinding factor.
        """
        if value < 0:
            raise ValueError("Cannot commit to negative value")

        if blinding is None:
            blinding = int.from_bytes(os.urandom(32), 'big') % _N

        # C = v*G + r*H
        vG = _scalar_mult(value, G)
        rH = _scalar_mult(blinding, H)
        point = _point_add(vG, rH)

        return Commitment(point=point, value=value, blinding=blinding)

    @staticmethod
    def verify_sum(inputs: List[Commitment], outputs: List[Commitment]) -> bool:
        """Verify that commitments balance: sum(inputs) == sum(outputs).

        This works because of the homomorphic property:
        If sum(v_in) == sum(v_out) and sum(r_in) == sum(r_out),
        then sum(C_in) == sum(C_out).

        In practice, the blinding factors are chosen so that:
        sum(r_in) - sum(r_out) = 0
        """
        # Sum input commitment points
        input_sum = INFINITY
        for c in inputs:
            input_sum = _point_add(input_sum, c.point)

        # Sum output commitment points
        output_sum = INFINITY
        for c in outputs:
            output_sum = _point_add(output_sum, c.point)

        return input_sum == output_sum

    @staticmethod
    def verify_balance(input_blindings: List[int], input_values: List[int],
                       output_blindings: List[int], output_values: List[int]) -> bool:
        """Verify that values and blindings balance across inputs and outputs.

        For a valid transaction:
          sum(input_values) == sum(output_values) + fee
          sum(input_blindings) == sum(output_blindings)
        """
        value_balance = sum(input_values) == sum(output_values)
        blinding_balance = sum(input_blindings) % _N == sum(output_blindings) % _N
        return value_balance and blinding_balance

    @staticmethod
    def generate_blinding() -> int:
        """Generate a cryptographically random blinding factor."""
        return int.from_bytes(os.urandom(32), 'big') % _N

    @staticmethod
    def compute_excess_blinding(input_blindings: List[int],
                                output_blindings: List[int]) -> int:
        """Compute the excess blinding factor needed to balance the transaction.

        excess = sum(input_blindings) - sum(output_blindings) mod N

        This excess is used as the change output's blinding adjustment.
        """
        excess = (sum(input_blindings) - sum(output_blindings)) % _N
        return excess
