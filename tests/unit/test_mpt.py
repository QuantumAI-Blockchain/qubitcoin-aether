"""Tests for Merkle Patricia Trie (MPT) — EVM-compatible state proofs."""

import pytest

from qubitcoin.qvm.mpt import (
    EMPTY_ROOT,
    MerklePatriciaTrie,
    NodeType,
    StateTrie,
    StorageTrie,
    TrieNode,
    bytes_to_nibbles,
    compact_decode,
    compact_encode,
    keccak256,
    keccak256_hex,
    nibbles_to_bytes,
    rlp_encode,
    shared_prefix_length,
)


# ---------------------------------------------------------------------------
# Helper encoding tests
# ---------------------------------------------------------------------------

class TestNibbleConversion:
    def test_bytes_to_nibbles(self) -> None:
        assert bytes_to_nibbles(b'\xAB') == [0xA, 0xB]

    def test_bytes_to_nibbles_multi(self) -> None:
        assert bytes_to_nibbles(b'\x12\x34') == [1, 2, 3, 4]

    def test_nibbles_to_bytes(self) -> None:
        assert nibbles_to_bytes([0xA, 0xB]) == b'\xAB'

    def test_roundtrip(self) -> None:
        data = b'\xDE\xAD\xBE\xEF'
        assert nibbles_to_bytes(bytes_to_nibbles(data)) == data

    def test_odd_nibbles_rejected(self) -> None:
        with pytest.raises(ValueError):
            nibbles_to_bytes([1, 2, 3])


class TestCompactEncoding:
    def test_leaf_even(self) -> None:
        encoded = compact_encode([1, 2, 3, 4], is_leaf=True)
        nibbles, is_leaf = compact_decode(encoded)
        assert nibbles == [1, 2, 3, 4]
        assert is_leaf is True

    def test_leaf_odd(self) -> None:
        encoded = compact_encode([1, 2, 3], is_leaf=True)
        nibbles, is_leaf = compact_decode(encoded)
        assert nibbles == [1, 2, 3]
        assert is_leaf is True

    def test_extension_even(self) -> None:
        encoded = compact_encode([5, 6], is_leaf=False)
        nibbles, is_leaf = compact_decode(encoded)
        assert nibbles == [5, 6]
        assert is_leaf is False

    def test_extension_odd(self) -> None:
        encoded = compact_encode([7], is_leaf=False)
        nibbles, is_leaf = compact_decode(encoded)
        assert nibbles == [7]
        assert is_leaf is False

    def test_empty_nibbles(self) -> None:
        encoded = compact_encode([], is_leaf=True)
        nibbles, is_leaf = compact_decode(encoded)
        assert nibbles == []
        assert is_leaf is True


class TestSharedPrefix:
    def test_full_match(self) -> None:
        assert shared_prefix_length([1, 2, 3], [1, 2, 3]) == 3

    def test_partial_match(self) -> None:
        assert shared_prefix_length([1, 2, 3], [1, 2, 4]) == 2

    def test_no_match(self) -> None:
        assert shared_prefix_length([1, 2], [3, 4]) == 0

    def test_different_lengths(self) -> None:
        assert shared_prefix_length([1, 2, 3, 4], [1, 2]) == 2

    def test_empty(self) -> None:
        assert shared_prefix_length([], [1, 2]) == 0


class TestRlpEncode:
    def test_single_byte(self) -> None:
        assert rlp_encode(b'\x42') == b'\x42'

    def test_short_string(self) -> None:
        data = b'hello'
        encoded = rlp_encode(data)
        assert encoded[0] == 0x80 + len(data)
        assert encoded[1:] == data

    def test_empty_bytes(self) -> None:
        assert rlp_encode(b'') == b'\x80'

    def test_list(self) -> None:
        encoded = rlp_encode([b'\x01', b'\x02'])
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0

    def test_nested_list(self) -> None:
        encoded = rlp_encode([b'\x01', [b'\x02', b'\x03']])
        assert isinstance(encoded, bytes)


# ---------------------------------------------------------------------------
# Keccak-256 tests
# ---------------------------------------------------------------------------

class TestKeccak:
    def test_keccak_deterministic(self) -> None:
        assert keccak256(b'hello') == keccak256(b'hello')

    def test_keccak_different_inputs(self) -> None:
        assert keccak256(b'hello') != keccak256(b'world')

    def test_keccak_hex(self) -> None:
        h = keccak256_hex(b'test')
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)


# ---------------------------------------------------------------------------
# TrieNode tests
# ---------------------------------------------------------------------------

class TestTrieNode:
    def test_empty_node_encode(self) -> None:
        node = TrieNode(node_type=NodeType.EMPTY)
        assert node.encode() == b'\x80'

    def test_leaf_node_encode(self) -> None:
        node = TrieNode(
            node_type=NodeType.LEAF,
            path=[1, 2, 3],
            value=b'hello',
        )
        encoded = node.encode()
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0

    def test_leaf_node_hash(self) -> None:
        node = TrieNode(
            node_type=NodeType.LEAF,
            path=[1, 2, 3],
            value=b'hello',
        )
        h = node.hash()
        assert isinstance(h, bytes)

    def test_branch_node_encode(self) -> None:
        branch = TrieNode(node_type=NodeType.BRANCH, value=b'test')
        encoded = branch.encode()
        assert isinstance(encoded, bytes)


# ---------------------------------------------------------------------------
# MerklePatriciaTrie core tests
# ---------------------------------------------------------------------------

class TestMerklePatriciaTrie:
    def test_empty_trie(self) -> None:
        trie = MerklePatriciaTrie()
        assert trie.root_hash == EMPTY_ROOT
        assert trie.size == 0

    def test_single_insert(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        assert trie.size == 1
        assert trie.root_hash != EMPTY_ROOT

    def test_get_after_insert(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        assert trie.get(b'key1') == b'value1'

    def test_get_missing_key(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        assert trie.get(b'key2') is None

    def test_update_value(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        root1 = trie.root_hash
        trie.put(b'key1', b'value2')
        assert trie.get(b'key1') == b'value2'
        assert trie.root_hash != root1

    def test_multiple_inserts(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'alice', b'100')
        trie.put(b'bob', b'200')
        trie.put(b'charlie', b'300')
        assert trie.get(b'alice') == b'100'
        assert trie.get(b'bob') == b'200'
        assert trie.get(b'charlie') == b'300'

    def test_delete(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        trie.put(b'key2', b'value2')
        assert trie.delete(b'key1') is True
        assert trie.get(b'key1') is None
        assert trie.get(b'key2') == b'value2'

    def test_delete_missing(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        assert trie.delete(b'key999') is False

    def test_delete_restores_empty(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        trie.delete(b'key1')
        assert trie.size == 0

    def test_deterministic_root(self) -> None:
        """Same insertions should produce the same root hash."""
        trie1 = MerklePatriciaTrie()
        trie1.put(b'a', b'1')
        trie1.put(b'b', b'2')

        trie2 = MerklePatriciaTrie()
        trie2.put(b'a', b'1')
        trie2.put(b'b', b'2')

        assert trie1.root_hash == trie2.root_hash

    def test_insert_empty_value_deletes(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        trie.put(b'key1', b'')
        assert trie.get(b'key1') is None

    def test_many_inserts(self) -> None:
        trie = MerklePatriciaTrie()
        for i in range(100):
            trie.put(f'key_{i}'.encode(), f'val_{i}'.encode())
        for i in range(100):
            assert trie.get(f'key_{i}'.encode()) == f'val_{i}'.encode()

    def test_proof_generation(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'key1', b'value1')
        trie.put(b'key2', b'value2')
        proof = trie.get_proof(b'key1')
        assert isinstance(proof, list)
        assert len(proof) > 0

    def test_get_stats(self) -> None:
        trie = MerklePatriciaTrie()
        trie.put(b'a', b'1')
        trie.put(b'b', b'2')
        stats = trie.get_stats()
        assert stats['size'] == 2
        assert stats['root_hash'] != EMPTY_ROOT
        assert stats['node_count'] > 0

    def test_different_keys_different_roots(self) -> None:
        trie1 = MerklePatriciaTrie()
        trie1.put(b'key1', b'value')

        trie2 = MerklePatriciaTrie()
        trie2.put(b'key2', b'value')

        assert trie1.root_hash != trie2.root_hash


# ---------------------------------------------------------------------------
# StateTrie tests
# ---------------------------------------------------------------------------

class TestStateTrie:
    def test_put_get_account(self) -> None:
        trie = StateTrie()
        trie.put_account(
            address='a' * 40,
            nonce=1,
            balance=1000,
            storage_root='0' * 64,
            code_hash='0' * 64,
        )
        account = trie.get_account('a' * 40)
        assert account is not None
        assert account['address'] == 'a' * 40

    def test_missing_account(self) -> None:
        trie = StateTrie()
        assert trie.get_account('b' * 40) is None

    def test_account_proof(self) -> None:
        trie = StateTrie()
        trie.put_account(
            address='a' * 40,
            nonce=0,
            balance=0,
            storage_root='0' * 64,
            code_hash='0' * 64,
        )
        proof = trie.get_account_proof('a' * 40)
        assert 'address' in proof
        assert 'accountProof' in proof
        assert 'stateRoot' in proof
        assert proof['address'] == '0x' + 'a' * 40

    def test_multiple_accounts(self) -> None:
        trie = StateTrie()
        for i in range(10):
            addr = f'{i:040x}'
            trie.put_account(addr, i, i * 100, '0' * 64, '0' * 64)
        for i in range(10):
            addr = f'{i:040x}'
            assert trie.get_account(addr) is not None

    def test_state_root_changes(self) -> None:
        trie = StateTrie()
        root1 = trie.root_hash
        trie.put_account('a' * 40, 1, 100, '0' * 64, '0' * 64)
        root2 = trie.root_hash
        assert root1 != root2


# ---------------------------------------------------------------------------
# StorageTrie tests
# ---------------------------------------------------------------------------

class TestStorageTrie:
    def test_put_get_slot(self) -> None:
        trie = StorageTrie()
        trie.put_slot('0' * 64, b'\x01')
        assert trie.get_slot('0' * 64) == b'\x01'

    def test_missing_slot(self) -> None:
        trie = StorageTrie()
        assert trie.get_slot('0' * 64) is None

    def test_storage_proof(self) -> None:
        trie = StorageTrie()
        trie.put_slot('0' * 64, b'\x42')
        proof = trie.get_storage_proof('0' * 64)
        assert 'key' in proof
        assert 'proof' in proof
        assert 'storageRoot' in proof

    def test_multiple_slots(self) -> None:
        trie = StorageTrie()
        for i in range(20):
            key = f'{i:064x}'
            trie.put_slot(key, bytes([i]))
        for i in range(20):
            key = f'{i:064x}'
            assert trie.get_slot(key) == bytes([i])
