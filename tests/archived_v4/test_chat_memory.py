"""Unit tests for ChatMemory — persistent cross-session memory for Aether chat."""
import json
import os
import tempfile

import pytest

from qubitcoin.aether.chat import ChatMemory


@pytest.fixture
def tmp_memory_path(tmp_path):
    """Provide a temp file path for ChatMemory persistence."""
    return str(tmp_path / "test_chat_memory.json")


class TestChatMemoryRememberRecall:
    """Test basic remember/recall operations."""

    def test_remember_and_recall(self, tmp_memory_path: str) -> None:
        """Storing a memory and recalling it returns the correct value."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "quantum computing")
        assert mem.recall("user1", "interest") == "quantum computing"

    def test_recall_missing_key_returns_none(self, tmp_memory_path: str) -> None:
        """Recalling a non-existent key returns None."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert mem.recall("user1", "nonexistent") is None

    def test_recall_missing_user_returns_none(self, tmp_memory_path: str) -> None:
        """Recalling from a non-existent user returns None."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert mem.recall("unknown_user", "interest") is None

    def test_recall_all_returns_all_memories(self, tmp_memory_path: str) -> None:
        """recall_all returns all stored key-value pairs for a user."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "DeFi")
        mem.remember("user1", "role", "developer")
        mem.remember("user1", "name", "Alice")
        all_mem = mem.recall_all("user1")
        assert all_mem == {"interest": "DeFi", "role": "developer", "name": "Alice"}

    def test_recall_all_empty_user(self, tmp_memory_path: str) -> None:
        """recall_all for unknown user returns empty dict."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert mem.recall_all("unknown") == {}

    def test_overwrite_memory(self, tmp_memory_path: str) -> None:
        """Storing the same key again overwrites the previous value."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "mining")
        mem.remember("user1", "interest", "staking")
        assert mem.recall("user1", "interest") == "staking"

    def test_multiple_users_isolated(self, tmp_memory_path: str) -> None:
        """Memories for different users are isolated."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "DeFi")
        mem.remember("user2", "interest", "NFTs")
        assert mem.recall("user1", "interest") == "DeFi"
        assert mem.recall("user2", "interest") == "NFTs"


class TestChatMemoryForget:
    """Test forget operation."""

    def test_forget_removes_key(self, tmp_memory_path: str) -> None:
        """Forgetting a key removes it from the user's memories."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "mining")
        mem.remember("user1", "role", "trader")
        mem.forget("user1", "interest")
        assert mem.recall("user1", "interest") is None
        assert mem.recall("user1", "role") == "trader"

    def test_forget_last_key_removes_user(self, tmp_memory_path: str) -> None:
        """Forgetting the last key for a user cleans up the user entry."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "mining")
        mem.forget("user1", "interest")
        assert mem.recall_all("user1") == {}

    def test_forget_nonexistent_key_no_error(self, tmp_memory_path: str) -> None:
        """Forgetting a key that doesn't exist does not raise."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "role", "dev")
        mem.forget("user1", "nonexistent")  # Should not raise
        assert mem.recall("user1", "role") == "dev"

    def test_forget_nonexistent_user_no_error(self, tmp_memory_path: str) -> None:
        """Forgetting from a non-existent user does not raise."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.forget("ghost", "key")  # Should not raise


class TestChatMemoryPersistence:
    """Test JSON file persistence."""

    def test_persistence_across_instances(self, tmp_memory_path: str) -> None:
        """Memories persist to disk and survive re-instantiation."""
        mem1 = ChatMemory(storage_path=tmp_memory_path)
        mem1.remember("user1", "interest", "quantum computing")
        mem1.remember("user1", "name", "Bob")

        # Create a new instance pointing to the same file
        mem2 = ChatMemory(storage_path=tmp_memory_path)
        assert mem2.recall("user1", "interest") == "quantum computing"
        assert mem2.recall("user1", "name") == "Bob"

    def test_persistence_file_created(self, tmp_memory_path: str) -> None:
        """The JSON file is created after the first remember call."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert not os.path.exists(tmp_memory_path)
        mem.remember("user1", "key", "value")
        assert os.path.exists(tmp_memory_path)

    def test_persistence_file_valid_json(self, tmp_memory_path: str) -> None:
        """The persistence file contains valid JSON."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        mem.remember("user1", "interest", "DeFi")
        with open(tmp_memory_path, "r") as f:
            data = json.load(f)
        assert data == {"user1": {"interest": "DeFi"}}

    def test_load_from_corrupted_file(self, tmp_memory_path: str) -> None:
        """Loading from a corrupted JSON file starts with empty memories."""
        with open(tmp_memory_path, "w") as f:
            f.write("not valid json {{{{")
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert mem.recall_all("user1") == {}

    def test_load_from_empty_file(self, tmp_memory_path: str) -> None:
        """Loading from an empty file starts with empty memories."""
        with open(tmp_memory_path, "w") as f:
            f.write("")
        mem = ChatMemory(storage_path=tmp_memory_path)
        assert mem.recall_all("user1") == {}

    def test_forget_persists(self, tmp_memory_path: str) -> None:
        """Forget operations are persisted to disk."""
        mem1 = ChatMemory(storage_path=tmp_memory_path)
        mem1.remember("user1", "a", "1")
        mem1.remember("user1", "b", "2")
        mem1.forget("user1", "a")

        mem2 = ChatMemory(storage_path=tmp_memory_path)
        assert mem2.recall("user1", "a") is None
        assert mem2.recall("user1", "b") == "2"


class TestChatMemoryExtraction:
    """Test automatic memory extraction from messages."""

    def test_extract_interest(self, tmp_memory_path: str) -> None:
        """Extracts interest from 'I'm interested in X' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("I'm interested in DeFi protocols", "")
        assert "interest" in result
        assert "defi" in result["interest"].lower()

    def test_extract_interest_curious(self, tmp_memory_path: str) -> None:
        """Extracts interest from 'I'm curious about X' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("I am curious about quantum computing", "")
        assert result.get("interest") == "quantum computing"

    def test_extract_role(self, tmp_memory_path: str) -> None:
        """Extracts role from 'I'm a developer' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("I'm a blockchain developer", "")
        assert "role" in result
        assert "blockchain developer" in result["role"]

    def test_extract_name(self, tmp_memory_path: str) -> None:
        """Extracts name from 'my name is X' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("My name is Alice", "")
        assert result.get("name") == "Alice"

    def test_extract_name_call_me(self, tmp_memory_path: str) -> None:
        """Extracts name from 'call me X' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("Please call me Bob", "")
        assert result.get("name") == "Bob"

    def test_extract_preferred_topic_mining(self, tmp_memory_path: str) -> None:
        """Extracts preferred topic from keyword detection."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("Tell me about mining on Qubitcoin", "")
        assert result.get("preferred_topic") == "mining"

    def test_extract_preferred_topic_defi(self, tmp_memory_path: str) -> None:
        """Extracts DeFi as preferred topic."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("What defi options are available?", "")
        assert result.get("preferred_topic") == "DeFi"

    def test_extract_nothing_from_generic(self, tmp_memory_path: str) -> None:
        """Returns empty dict for generic messages with no extractable info."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("Hello there", "Hi!")
        # 'hello' doesn't match any extraction patterns
        assert "interest" not in result
        assert "role" not in result
        assert "name" not in result

    def test_extract_multiple_facts(self, tmp_memory_path: str) -> None:
        """Can extract multiple facts from a single message."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories(
            "My name is Alice and I'm interested in quantum stuff", ""
        )
        assert result.get("name") == "Alice"
        assert "interest" in result
        assert "preferred_topic" in result  # 'quantum' keyword triggers this too

    def test_extract_want_to_learn(self, tmp_memory_path: str) -> None:
        """Extracts interest from 'I want to learn about X' pattern."""
        mem = ChatMemory(storage_path=tmp_memory_path)
        result = mem.extract_memories("I want to learn about staking", "")
        assert result.get("interest") == "staking"
        assert result.get("preferred_topic") == "staking"
