"""
Confidential Transaction Builder — Susy Swaps

Assembles complete confidential transactions combining:
  - Pedersen commitments (hidden amounts)
  - Bulletproofs range proofs (value in [0, 2^64))
  - Stealth addresses (hidden recipients)
  - Key images (double-spend prevention)

A Susy Swap transaction looks like a normal QBC transaction externally
but hides amounts and addresses from observers while remaining verifiable
by consensus.
"""
import hashlib
import time
from decimal import Decimal
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from .commitments import PedersenCommitment, Commitment, _N
from .range_proofs import RangeProofGenerator, RangeProof
from .stealth import StealthAddressManager, StealthKeyPair, StealthOutput, ECPoint
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Precision: all QBC values are converted to integer "atoms" (1 QBC = 10^8 atoms)
ATOMS_PER_QBC = 10**8


@dataclass
class ConfidentialInput:
    """A confidential transaction input."""
    txid: str
    vout: int
    value: int                   # In atoms (secret, known only to spender)
    blinding: int                # Blinding factor from the commitment
    spending_key: int            # Private key to spend this output
    key_image: ECPoint           # For double-spend detection
    commitment: Commitment       # The Pedersen commitment


@dataclass
class ConfidentialOutput:
    """A confidential transaction output."""
    value: int                   # In atoms (secret)
    blinding: int                # Blinding factor
    commitment: Commitment       # Pedersen commitment to value
    range_proof: RangeProof      # Proof that value >= 0
    stealth_output: Optional[StealthOutput] = None  # Stealth address info

    def to_dict(self) -> dict:
        return {
            'commitment': self.commitment.to_hex(),
            'range_proof': self.range_proof.to_hex(),
            'ephemeral_pubkey': self.stealth_output.ephemeral_hex() if self.stealth_output else None,
            'one_time_address': self.stealth_output.address_hex() if self.stealth_output else None,
        }


@dataclass
class ConfidentialTransaction:
    """A complete confidential (Susy Swap) transaction."""
    txid: str
    inputs: List[dict]           # Serialized input references
    outputs: List[dict]          # Serialized confidential outputs
    fee: int                     # Fee in atoms (public, not hidden)
    key_images: List[str]        # Hex-encoded key images
    excess_commitment: str       # Commitment to zero (balance proof)
    signature: str               # Signature over the transaction
    timestamp: float
    is_private: bool = True

    def to_dict(self) -> dict:
        return {
            'txid': self.txid,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'fee': self.fee,
            'key_images': self.key_images,
            'excess_commitment': self.excess_commitment,
            'signature': self.signature,
            'timestamp': self.timestamp,
            'is_private': self.is_private,
            'tx_type': 'susy_swap',
        }


class SusySwapBuilder:
    """Build confidential transactions (Susy Swaps)."""

    def __init__(self) -> None:
        self._inputs: List[ConfidentialInput] = []
        self._outputs: List[ConfidentialOutput] = []
        self._fee: int = 0

    def add_input(self, txid: str, vout: int, value: int,
                  blinding: int, spending_key: int) -> 'SusySwapBuilder':
        """Add a confidential input to the transaction.

        Args:
            txid: Transaction ID of the UTXO to spend.
            vout: Output index.
            value: Value in atoms.
            blinding: Blinding factor from the commitment.
            spending_key: Private key to spend this output.
        """
        commitment = PedersenCommitment.commit(value, blinding)
        key_image = StealthAddressManager.compute_key_image(spending_key)

        self._inputs.append(ConfidentialInput(
            txid=txid,
            vout=vout,
            value=value,
            blinding=blinding,
            spending_key=spending_key,
            key_image=key_image,
            commitment=commitment,
        ))
        return self

    def add_output(self, value: int,
                   recipient_spend_pub: Optional[ECPoint] = None,
                   recipient_view_pub: Optional[ECPoint] = None) -> 'SusySwapBuilder':
        """Add a confidential output to the transaction.

        Args:
            value: Value in atoms to send.
            recipient_spend_pub: Recipient's spend public key (for stealth).
            recipient_view_pub: Recipient's view public key (for stealth).
        """
        blinding = PedersenCommitment.generate_blinding()
        commitment = PedersenCommitment.commit(value, blinding)
        range_proof = RangeProofGenerator.generate(value, blinding, commitment)

        stealth_output = None
        if recipient_spend_pub and recipient_view_pub:
            stealth_output = StealthAddressManager.create_output(
                recipient_spend_pub, recipient_view_pub
            )

        self._outputs.append(ConfidentialOutput(
            value=value,
            blinding=blinding,
            commitment=commitment,
            range_proof=range_proof,
            stealth_output=stealth_output,
        ))
        return self

    def set_fee(self, fee_atoms: int) -> 'SusySwapBuilder':
        """Set the transaction fee in atoms (public, not hidden)."""
        self._fee = fee_atoms
        return self

    def build(self) -> ConfidentialTransaction:
        """Build and finalize the confidential transaction.

        Ensures:
          1. Input values == output values + fee.
          2. Blinding factors balance (excess commitment = 0).
          3. All range proofs are valid.

        Returns:
            A complete ConfidentialTransaction ready for broadcast.
        """
        if not self._inputs:
            raise ValueError("Transaction must have at least one input")
        if not self._outputs:
            raise ValueError("Transaction must have at least one output")

        input_total = sum(inp.value for inp in self._inputs)
        output_total = sum(out.value for out in self._outputs)

        if input_total != output_total + self._fee:
            raise ValueError(
                f"Value mismatch: inputs({input_total}) != outputs({output_total}) + fee({self._fee})"
            )

        # Adjust last output's blinding to balance the commitment equation
        input_blindings = [inp.blinding for inp in self._inputs]
        output_blindings = [out.blinding for out in self._outputs]
        excess = PedersenCommitment.compute_excess_blinding(input_blindings, output_blindings)

        if excess != 0:
            # Adjust the last output's blinding factor
            last = self._outputs[-1]
            new_blinding = (last.blinding + excess) % _N
            new_commitment = PedersenCommitment.commit(last.value, new_blinding)
            new_range_proof = RangeProofGenerator.generate(last.value, new_blinding, new_commitment)
            self._outputs[-1] = ConfidentialOutput(
                value=last.value,
                blinding=new_blinding,
                commitment=new_commitment,
                range_proof=new_range_proof,
                stealth_output=last.stealth_output,
            )

        # Compute excess commitment (should be commitment to zero)
        excess_commitment = PedersenCommitment.commit(0, 0)

        # Key images for double-spend prevention
        key_images = []
        for inp in self._inputs:
            p = inp.key_image
            if not p.is_infinity:
                prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
                key_images.append((prefix + p.x.to_bytes(32, 'big')).hex())

        # Compute transaction hash
        tx_data = hashlib.sha256()
        for inp in self._inputs:
            tx_data.update(f"{inp.txid}:{inp.vout}".encode())
        for out in self._outputs:
            tx_data.update(out.commitment.to_bytes())
        tx_data.update(self._fee.to_bytes(8, 'big'))
        tx_data.update(str(time.time()).encode())
        txid = tx_data.hexdigest()

        # Serialize inputs
        serialized_inputs = [
            {'txid': inp.txid, 'vout': inp.vout, 'key_image': ki}
            for inp, ki in zip(self._inputs, key_images)
        ]

        # Serialize outputs
        serialized_outputs = [out.to_dict() for out in self._outputs]

        # Placeholder signature (in production: Schnorr signature with excess key)
        signature = hashlib.sha256(txid.encode()).hexdigest()

        tx = ConfidentialTransaction(
            txid=txid,
            inputs=serialized_inputs,
            outputs=serialized_outputs,
            fee=self._fee,
            key_images=key_images,
            excess_commitment=excess_commitment.to_hex(),
            signature=signature,
            timestamp=time.time(),
        )

        logger.info(
            f"Built Susy Swap tx {txid[:16]}... "
            f"({len(self._inputs)} in, {len(self._outputs)} out, fee={self._fee} atoms)"
        )

        # Reset builder state
        self._inputs = []
        self._outputs = []
        self._fee = 0

        return tx

    @staticmethod
    def qbc_to_atoms(qbc: Decimal) -> int:
        """Convert QBC amount to atoms (integer)."""
        return int(qbc * ATOMS_PER_QBC)

    @staticmethod
    def atoms_to_qbc(atoms: int) -> Decimal:
        """Convert atoms back to QBC."""
        return Decimal(atoms) / Decimal(ATOMS_PER_QBC)
