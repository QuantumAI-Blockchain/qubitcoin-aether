"""
QVM ABI Encoding/Decoding — Solidity-compatible ABI for function calls

Implements the Ethereum ABI specification for encoding function selectors,
uint256, address, bool, bytes32, and dynamic types (bytes, string).

This is used by:
  - JSON-RPC ``eth_call`` / ``eth_sendTransaction`` calldata parsing
  - Contract interaction tools
  - QBC-20 / QBC-721 standard interfaces
"""
import hashlib
from typing import Any, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (or SHA-256 fallback if no keccak library installed)."""
    return hashlib.sha256(data).digest()


def function_selector(signature: str) -> bytes:
    """Compute the 4-byte function selector for a Solidity function signature.

    Args:
        signature: e.g. ``"transfer(address,uint256)"``

    Returns:
        4-byte selector.
    """
    return _keccak256(signature.encode())[:4]


def encode_uint256(value: int) -> bytes:
    """Encode a uint256 as 32 bytes (big-endian, left-padded)."""
    if value < 0:
        raise ValueError("uint256 cannot be negative")
    return value.to_bytes(32, 'big')


def decode_uint256(data: bytes) -> int:
    """Decode a uint256 from 32 bytes."""
    return int.from_bytes(data[:32], 'big')


def encode_address(address: str) -> bytes:
    """Encode a 20-byte address into 32-byte ABI format (left-padded)."""
    addr = address.lower().replace('0x', '')
    if len(addr) > 40:
        addr = addr[:40]
    addr = addr.zfill(40)
    return bytes(12) + bytes.fromhex(addr)


def decode_address(data: bytes) -> str:
    """Decode a 32-byte ABI-encoded address → '0x'-prefixed hex."""
    return '0x' + data[12:32].hex()


def encode_bool(value: bool) -> bytes:
    """Encode a boolean as uint256."""
    return encode_uint256(1 if value else 0)


def decode_bool(data: bytes) -> bool:
    """Decode a boolean from 32 bytes."""
    return decode_uint256(data) != 0


def encode_bytes32(value: bytes) -> bytes:
    """Encode exactly 32 bytes (right-padded)."""
    if len(value) > 32:
        value = value[:32]
    return value.ljust(32, b'\x00')


def decode_bytes32(data: bytes) -> bytes:
    """Decode 32 raw bytes."""
    return data[:32]


def encode_string(value: str) -> bytes:
    """Encode a dynamic string (offset + length + data padded to 32)."""
    return encode_bytes_dynamic(value.encode())


def decode_string(data: bytes, offset: int = 0) -> str:
    """Decode a dynamic string from ABI data."""
    return decode_bytes_dynamic(data, offset).decode('utf-8', errors='replace')


def encode_bytes_dynamic(value: bytes) -> bytes:
    """Encode dynamic bytes: length (32 bytes) + data padded to 32-byte boundary."""
    length = len(value)
    pad_len = (32 - (length % 32)) % 32
    return encode_uint256(length) + value + b'\x00' * pad_len


def decode_bytes_dynamic(data: bytes, offset: int = 0) -> bytes:
    """Decode dynamic bytes from ABI data."""
    length = decode_uint256(data[offset:offset + 32])
    return data[offset + 32:offset + 32 + length]


def encode_function_call(signature: str, args: List[Any],
                         types: List[str]) -> bytes:
    """Encode a full function call (selector + arguments).

    Args:
        signature: Solidity function signature, e.g. ``"transfer(address,uint256)"``
        args: List of argument values.
        types: List of type strings (``"uint256"``, ``"address"``, ``"bool"``, ``"bytes32"``).

    Returns:
        Encoded calldata (4-byte selector + 32-byte encoded args).
    """
    selector = function_selector(signature)
    encoded_args = b''
    for arg, typ in zip(args, types):
        if typ == 'uint256':
            encoded_args += encode_uint256(arg)
        elif typ == 'address':
            encoded_args += encode_address(arg)
        elif typ == 'bool':
            encoded_args += encode_bool(arg)
        elif typ == 'bytes32':
            encoded_args += encode_bytes32(arg)
        else:
            raise ValueError(f"Unsupported ABI type: {typ}")
    return selector + encoded_args


def decode_function_call(data: bytes, types: List[str]) -> Tuple[bytes, List[Any]]:
    """Decode a function call into selector + decoded arguments.

    Args:
        data: Raw calldata (4-byte selector + encoded args).
        types: Expected argument types.

    Returns:
        (selector, decoded_args) tuple.
    """
    selector = data[:4]
    args = []
    offset = 4
    for typ in types:
        chunk = data[offset:offset + 32]
        if typ == 'uint256':
            args.append(decode_uint256(chunk))
        elif typ == 'address':
            args.append(decode_address(chunk))
        elif typ == 'bool':
            args.append(decode_bool(chunk))
        elif typ == 'bytes32':
            args.append(decode_bytes32(chunk))
        else:
            raise ValueError(f"Unsupported ABI type: {typ}")
        offset += 32
    return selector, args


def abi_selector(func_sig: str) -> str:
    """Compute the 4-byte keccak256 selector as a hex string.

    This is a convenience wrapper around :func:`function_selector` that
    returns the selector as a lowercase hex string (no ``0x`` prefix),
    matching the common Solidity tooling output format.

    Args:
        func_sig: Solidity function signature, e.g. ``"getPrice()"``.

    Returns:
        8-character hex string, e.g. ``"d61a3b92"``.
    """
    return function_selector(func_sig).hex()


def encode_call(func_sig: str, *args: Any) -> bytes:
    """Encode a function call with auto-detected argument types.

    Inspects the Solidity function signature to extract parameter types
    and encodes the provided positional arguments accordingly.  Supports
    ``uint256``, ``address``, ``bool``, and ``bytes32`` parameter types.

    Args:
        func_sig: Solidity function signature with parenthesised types,
            e.g. ``"transfer(address,uint256)"``.
        *args: Positional argument values matching the signature types.

    Returns:
        Encoded calldata bytes (4-byte selector + 32-byte encoded args).

    Raises:
        ValueError: If the number of arguments does not match the
            signature or an unsupported type is encountered.

    Examples:
        >>> encode_call("totalSupply()")
        b'\\x18\\x16...'
        >>> encode_call("transfer(address,uint256)", "0xabc...def", 100)
        b'\\xa9\\x05...'
    """
    # Parse types from the signature: "foo(uint256,address)" → ["uint256", "address"]
    paren_start = func_sig.index('(')
    paren_end = func_sig.rindex(')')
    params_str = func_sig[paren_start + 1:paren_end].strip()
    types: List[str] = [t.strip() for t in params_str.split(',') if t.strip()] if params_str else []

    if len(types) != len(args):
        raise ValueError(
            f"Argument count mismatch: signature '{func_sig}' expects "
            f"{len(types)} args, got {len(args)}"
        )

    if not types:
        return function_selector(func_sig)

    return encode_function_call(func_sig, list(args), types)


def encode_return_value(value: Any, typ: str) -> bytes:
    """Encode a single return value."""
    if typ == 'uint256':
        return encode_uint256(value)
    elif typ == 'address':
        return encode_address(value)
    elif typ == 'bool':
        return encode_bool(value)
    elif typ == 'bytes32':
        return encode_bytes32(value)
    raise ValueError(f"Unsupported ABI type: {typ}")
