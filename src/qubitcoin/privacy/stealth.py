"""
Stealth Address System for Qubitcoin Susy Swaps

Stealth addresses provide recipient privacy by generating a unique,
one-time address for every transaction. Even if an observer knows
the recipient's public address, they cannot link received transactions.

Protocol:
  1. Recipient publishes (spend_pubkey, view_pubkey).
  2. Sender generates ephemeral keypair (r, R = r*G).
  3. Sender computes shared_secret = hash(r * view_pubkey).
  4. One-time address = spend_pubkey + shared_secret * G.
  5. Sender publishes R (ephemeral pubkey) in the transaction.
  6. Recipient scans: for each R, computes shared_secret = hash(view_privkey * R),
     checks if spend_pubkey + shared_secret*G matches the output address.
  7. If match, recipient can spend using spend_privkey + shared_secret.
"""
import hashlib
import os
from typing import Tuple, Optional
from dataclasses import dataclass

from .commitments import (
    ECPoint, G, INFINITY, _N, _P,
    _scalar_mult, _point_add,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StealthKeyPair:
    """A stealth address key pair (spend + view)."""
    spend_privkey: int
    spend_pubkey: ECPoint
    view_privkey: int
    view_pubkey: ECPoint

    def public_address(self) -> str:
        """Get the publishable stealth address (spend_pub || view_pub)."""
        def compress(p: ECPoint) -> bytes:
            prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
            return prefix + p.x.to_bytes(32, 'big')
        return (compress(self.spend_pubkey) + compress(self.view_pubkey)).hex()


@dataclass
class StealthOutput:
    """A stealth transaction output."""
    one_time_address: ECPoint  # The one-time destination address
    ephemeral_pubkey: ECPoint  # R = r*G, published in transaction
    shared_secret: int          # Used internally, not published

    def address_hex(self) -> str:
        """Get hex representation of one-time address."""
        p = self.one_time_address
        prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
        return (prefix + p.x.to_bytes(32, 'big')).hex()

    def ephemeral_hex(self) -> str:
        """Get hex representation of ephemeral pubkey."""
        p = self.ephemeral_pubkey
        prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
        return (prefix + p.x.to_bytes(32, 'big')).hex()


def _hash_to_scalar(point: ECPoint) -> int:
    """Hash an EC point to a scalar (Fiat-Shamir style)."""
    if point.is_infinity:
        data = b'\x00' * 33
    else:
        prefix = b'\x02' if point.y % 2 == 0 else b'\x03'
        data = prefix + point.x.to_bytes(32, 'big')
    h = hashlib.sha256(b"Qubitcoin_stealth_v1" + data).digest()
    return int.from_bytes(h, 'big') % _N


class StealthAddressManager:
    """Manage stealth addresses for privacy transactions."""

    @staticmethod
    def generate_keypair() -> StealthKeyPair:
        """Generate a new stealth key pair (spend + view keys).

        Returns:
            StealthKeyPair with both spend and view private/public keys.
        """
        spend_priv = int.from_bytes(os.urandom(32), 'big') % _N
        view_priv = int.from_bytes(os.urandom(32), 'big') % _N
        spend_pub = _scalar_mult(spend_priv, G)
        view_pub = _scalar_mult(view_priv, G)
        return StealthKeyPair(
            spend_privkey=spend_priv,
            spend_pubkey=spend_pub,
            view_privkey=view_priv,
            view_pubkey=view_pub,
        )

    @staticmethod
    def create_output(recipient_spend_pub: ECPoint,
                      recipient_view_pub: ECPoint) -> StealthOutput:
        """Create a stealth output for a recipient (sender side).

        Args:
            recipient_spend_pub: Recipient's public spend key.
            recipient_view_pub: Recipient's public view key.

        Returns:
            StealthOutput containing the one-time address and ephemeral key.
        """
        # Generate ephemeral keypair
        r = int.from_bytes(os.urandom(32), 'big') % _N
        R = _scalar_mult(r, G)

        # Shared secret = hash(r * view_pub)
        shared_point = _scalar_mult(r, recipient_view_pub)
        shared_secret = _hash_to_scalar(shared_point)

        # One-time address = spend_pub + shared_secret * G
        ss_G = _scalar_mult(shared_secret, G)
        one_time_addr = _point_add(recipient_spend_pub, ss_G)

        return StealthOutput(
            one_time_address=one_time_addr,
            ephemeral_pubkey=R,
            shared_secret=shared_secret,
        )

    @staticmethod
    def scan_output(keypair: StealthKeyPair, ephemeral_pubkey: ECPoint,
                    output_address: ECPoint) -> bool:
        """Scan a transaction output to check if it belongs to us (recipient side).

        Args:
            keypair: Our stealth key pair.
            ephemeral_pubkey: R from the transaction.
            output_address: The one-time address in the output.

        Returns:
            True if this output is destined for us.
        """
        # Compute shared secret = hash(view_priv * R)
        shared_point = _scalar_mult(keypair.view_privkey, ephemeral_pubkey)
        shared_secret = _hash_to_scalar(shared_point)

        # Expected address = spend_pub + shared_secret * G
        ss_G = _scalar_mult(shared_secret, G)
        expected = _point_add(keypair.spend_pubkey, ss_G)

        return expected == output_address

    @staticmethod
    def compute_spending_key(keypair: StealthKeyPair,
                             ephemeral_pubkey: ECPoint) -> int:
        """Compute the private key to spend a stealth output (recipient side).

        Args:
            keypair: Our stealth key pair.
            ephemeral_pubkey: R from the transaction we want to spend.

        Returns:
            The private key that controls the one-time address.
        """
        # shared_secret = hash(view_priv * R)
        shared_point = _scalar_mult(keypair.view_privkey, ephemeral_pubkey)
        shared_secret = _hash_to_scalar(shared_point)

        # spending_key = spend_priv + shared_secret (mod N)
        return (keypair.spend_privkey + shared_secret) % _N

    @staticmethod
    def compute_key_image(spending_key: int) -> ECPoint:
        """Compute a key image for double-spend prevention.

        Key image I = spending_key * hash_to_point(spending_key * G)
        The key image is deterministic per spending key, so attempting to
        spend the same output twice produces the same key image.

        Args:
            spending_key: The private spending key.

        Returns:
            Key image point.
        """
        pub = _scalar_mult(spending_key, G)
        # hash_to_point: we hash the public key and multiply
        hp = _hash_to_scalar(pub)
        hp_point = _scalar_mult(hp, G)
        return _scalar_mult(spending_key, hp_point)
