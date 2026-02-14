"""Tests for QVM ABI encoding/decoding (Batch 16.1)."""
import pytest

from qubitcoin.qvm.abi import (
    function_selector, encode_uint256, decode_uint256,
    encode_address, decode_address, encode_bool, decode_bool,
    encode_bytes32, decode_bytes32, encode_string, decode_string,
    encode_bytes_dynamic, decode_bytes_dynamic,
    encode_function_call, decode_function_call,
    encode_return_value,
)


class TestFunctionSelector:
    def test_selector_is_4_bytes(self):
        sel = function_selector("transfer(address,uint256)")
        assert len(sel) == 4

    def test_selector_deterministic(self):
        s1 = function_selector("balanceOf(address)")
        s2 = function_selector("balanceOf(address)")
        assert s1 == s2

    def test_different_sigs_different_selectors(self):
        s1 = function_selector("transfer(address,uint256)")
        s2 = function_selector("approve(address,uint256)")
        assert s1 != s2


class TestUint256:
    def test_encode_zero(self):
        result = encode_uint256(0)
        assert len(result) == 32
        assert result == b'\x00' * 32

    def test_encode_one(self):
        result = encode_uint256(1)
        assert result == b'\x00' * 31 + b'\x01'

    def test_encode_max(self):
        val = (1 << 256) - 1
        result = encode_uint256(val)
        assert result == b'\xff' * 32

    def test_roundtrip(self):
        for v in [0, 1, 255, 1000, 10**18, (1 << 256) - 1]:
            assert decode_uint256(encode_uint256(v)) == v

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            encode_uint256(-1)


class TestAddress:
    def test_encode_length(self):
        result = encode_address("0x" + "ab" * 20)
        assert len(result) == 32

    def test_left_padded(self):
        result = encode_address("0x" + "ab" * 20)
        assert result[:12] == b'\x00' * 12

    def test_roundtrip(self):
        addr = "0x" + "ab" * 20
        encoded = encode_address(addr)
        decoded = decode_address(encoded)
        assert decoded == addr

    def test_no_prefix(self):
        addr = "ab" * 20
        encoded = encode_address(addr)
        decoded = decode_address(encoded)
        assert decoded == "0x" + addr

    def test_short_address_zero_filled(self):
        encoded = encode_address("0x1")
        decoded = decode_address(encoded)
        assert decoded == "0x" + "00" * 19 + "01"


class TestBool:
    def test_true(self):
        encoded = encode_bool(True)
        assert decode_bool(encoded) is True

    def test_false(self):
        encoded = encode_bool(False)
        assert decode_bool(encoded) is False

    def test_true_is_one(self):
        assert encode_bool(True) == encode_uint256(1)


class TestBytes32:
    def test_exact_32(self):
        data = b'\xaa' * 32
        assert encode_bytes32(data) == data

    def test_shorter_right_padded(self):
        data = b'\xbb' * 10
        result = encode_bytes32(data)
        assert len(result) == 32
        assert result[:10] == data

    def test_longer_truncated(self):
        data = b'\xcc' * 50
        result = encode_bytes32(data)
        assert len(result) == 32
        assert result == data[:32]

    def test_roundtrip(self):
        data = b'\xdd' * 32
        assert decode_bytes32(encode_bytes32(data)) == data


class TestDynamicTypes:
    def test_encode_string(self):
        result = encode_string("hello")
        assert len(result) >= 64  # 32 length + 32 padded data

    def test_decode_string(self):
        encoded = encode_string("hello world")
        decoded = decode_string(encoded)
        assert decoded == "hello world"

    def test_empty_string(self):
        encoded = encode_string("")
        decoded = decode_string(encoded)
        assert decoded == ""

    def test_encode_bytes_dynamic(self):
        data = b'\xaa\xbb\xcc'
        encoded = encode_bytes_dynamic(data)
        decoded = decode_bytes_dynamic(encoded)
        assert decoded == data


class TestFunctionCall:
    def test_encode_transfer(self):
        calldata = encode_function_call(
            "transfer(address,uint256)",
            ["0x" + "ab" * 20, 1000],
            ["address", "uint256"],
        )
        assert len(calldata) == 4 + 32 + 32  # selector + 2 args

    def test_decode_transfer(self):
        addr = "0x" + "ab" * 20
        amount = 1000
        calldata = encode_function_call(
            "transfer(address,uint256)",
            [addr, amount],
            ["address", "uint256"],
        )
        selector, args = decode_function_call(calldata, ["address", "uint256"])
        assert selector == function_selector("transfer(address,uint256)")
        assert args[0] == addr
        assert args[1] == amount

    def test_encode_bool_arg(self):
        calldata = encode_function_call(
            "setApproval(bool)", [True], ["bool"]
        )
        _, args = decode_function_call(calldata, ["bool"])
        assert args[0] is True

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            encode_function_call("foo(int128)", [1], ["int128"])


class TestReturnValue:
    def test_encode_uint256_return(self):
        result = encode_return_value(42, "uint256")
        assert decode_uint256(result) == 42

    def test_encode_address_return(self):
        addr = "0x" + "ff" * 20
        result = encode_return_value(addr, "address")
        assert decode_address(result) == addr

    def test_encode_bool_return(self):
        result = encode_return_value(True, "bool")
        assert decode_bool(result) is True

    def test_unsupported_raises(self):
        with pytest.raises(ValueError):
            encode_return_value(1, "int128")
