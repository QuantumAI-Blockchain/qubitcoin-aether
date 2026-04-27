"""Unit tests for Sephirot Python node implementations."""
import pytest
from unittest.mock import MagicMock


class TestBaseSephirah:
    """Test abstract base class mechanics."""

    def test_cannot_instantiate_directly(self):
        from qubitcoin.aether.sephirot_nodes import BaseSephirah
        with pytest.raises(TypeError):
            BaseSephirah(None)

    def test_node_message_creation(self):
        from qubitcoin.aether.sephirot_nodes import NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        msg = NodeMessage(
            sender=SephirahRole.KETER,
            receiver=SephirahRole.TIFERET,
            payload={"type": "test"},
        )
        assert msg.sender == SephirahRole.KETER
        assert msg.receiver == SephirahRole.TIFERET
        assert len(msg.message_id) == 16
        assert msg.timestamp > 0

    def test_processing_result(self):
        from qubitcoin.aether.sephirot_nodes import ProcessingResult
        from qubitcoin.aether.sephirot import SephirahRole
        r = ProcessingResult(role=SephirahRole.BINAH, action="test")
        assert r.success is True
        assert r.confidence == 0.0


class TestCreateAllNodes:
    """Test the create_all_nodes factory."""

    def test_creates_ten_nodes(self):
        from qubitcoin.aether.sephirot_nodes import create_all_nodes
        nodes = create_all_nodes()
        assert len(nodes) == 10

    def test_all_roles_present(self):
        from qubitcoin.aether.sephirot_nodes import create_all_nodes
        from qubitcoin.aether.sephirot import SephirahRole
        nodes = create_all_nodes()
        for role in SephirahRole:
            assert role in nodes

    def test_each_is_base_sephirah(self):
        from qubitcoin.aether.sephirot_nodes import create_all_nodes, BaseSephirah
        nodes = create_all_nodes()
        for node in nodes.values():
            assert isinstance(node, BaseSephirah)


class TestKeterNode:
    """Test Keter — meta-learning and goal formation."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        from qubitcoin.aether.sephirot import SephirahRole
        node = KeterNode()
        assert node.role == SephirahRole.KETER
        assert node.state.qubits == 8

    def test_process_creates_goal(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        node = KeterNode()
        result = node.process({"block_height": 1})
        assert result.action == "goal_formation"
        assert result.output["goals"] >= 1

    def test_process_sends_to_tiferet(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        from qubitcoin.aether.sephirot import SephirahRole
        node = KeterNode()
        result = node.process({"block_height": 1})
        assert len(result.messages_out) >= 1
        assert result.messages_out[0].receiver == SephirahRole.TIFERET


class TestChochmahNode:
    """Test Chochmah — intuition and pattern discovery."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import ChochmahNode
        node = ChochmahNode()
        assert node.state.qubits == 6

    def test_process_without_kg(self):
        from qubitcoin.aether.sephirot_nodes import ChochmahNode
        node = ChochmahNode()
        result = node.process({"block_height": 1})
        assert result.action == "pattern_discovery"

    def test_process_with_kg_detects_patterns(self):
        from qubitcoin.aether.sephirot_nodes import ChochmahNode
        from qubitcoin.aether.knowledge_graph import KeterNode as KN
        kg = MagicMock()
        kg.nodes = {
            i: KN(node_id=i, source_block=i) for i in range(5)
        }
        node = ChochmahNode(kg)
        result = node.process({"block_height": 5})
        assert result.output["new_insight"] is True


class TestBinahNode:
    """Test Binah — logic and causal inference."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import BinahNode
        node = BinahNode()
        assert node.state.qubits == 4

    def test_verifies_insights(self):
        from qubitcoin.aether.sephirot_nodes import BinahNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = BinahNode()
        msg = NodeMessage(
            sender=SephirahRole.CHOCHMAH,
            receiver=SephirahRole.BINAH,
            payload={"type": "insight_for_verification", "insight": {"node_count": 5}},
        )
        node.receive_message(msg)
        result = node.process({})
        assert result.output["verified_this_cycle"] == 1

    def test_rejects_weak_insights(self):
        from qubitcoin.aether.sephirot_nodes import BinahNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = BinahNode()
        msg = NodeMessage(
            sender=SephirahRole.CHOCHMAH,
            receiver=SephirahRole.BINAH,
            payload={"type": "insight_for_verification", "insight": {"node_count": 1}},
        )
        node.receive_message(msg)
        result = node.process({})
        assert result.output["rejected_total"] == 1


class TestChesedNode:
    """Test Chesed — exploration and divergent thinking."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import ChesedNode
        node = ChesedNode()
        assert node.state.qubits == 10

    def test_sends_to_gevurah(self):
        from qubitcoin.aether.sephirot_nodes import ChesedNode
        from qubitcoin.aether.sephirot import SephirahRole
        node = ChesedNode()
        result = node.process({})
        assert len(result.messages_out) >= 1
        assert result.messages_out[0].receiver == SephirahRole.GEVURAH


class TestGevurahNode:
    """Test Gevurah — constraint and safety validation."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import GevurahNode
        node = GevurahNode()
        assert node.state.qubits == 3

    def test_approves_safe_exploration(self):
        from qubitcoin.aether.sephirot_nodes import GevurahNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = GevurahNode()
        msg = NodeMessage(
            sender=SephirahRole.CHESED,
            receiver=SephirahRole.GEVURAH,
            payload={"type": "exploration_report", "new_connections": 5},
        )
        node.receive_message(msg)
        result = node.process({})
        assert result.output["approved_this_cycle"] == 1

    def test_vetoes_excessive_exploration(self):
        from qubitcoin.aether.sephirot_nodes import GevurahNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = GevurahNode()
        msg = NodeMessage(
            sender=SephirahRole.CHESED,
            receiver=SephirahRole.GEVURAH,
            payload={"type": "exploration_report", "new_connections": 200},
        )
        node.receive_message(msg)
        result = node.process({})
        assert result.output["vetoed_this_cycle"] == 1


class TestTiferetNode:
    """Test Tiferet — integration and conflict resolution."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import TiferetNode
        node = TiferetNode()
        assert node.state.qubits == 12

    def test_integrates_messages(self):
        from qubitcoin.aether.sephirot_nodes import TiferetNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = TiferetNode()
        for i in range(3):
            msg = NodeMessage(
                sender=SephirahRole.KETER,
                receiver=SephirahRole.TIFERET,
                payload={"type": "goal_directive", "goal": {"id": i}},
            )
            node.receive_message(msg)
        result = node.process({})
        assert result.output["messages_integrated"] == 3
        # Should send to Malkuth
        assert len(result.messages_out) >= 1


class TestNetzachNode:
    """Test Netzach — reinforcement learning."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import NetzachNode
        node = NetzachNode()
        assert node.state.qubits == 5

    def test_learns_from_rewards(self):
        from qubitcoin.aether.sephirot_nodes import NetzachNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = NetzachNode()
        msg = NodeMessage(
            sender=SephirahRole.MALKUTH,
            receiver=SephirahRole.NETZACH,
            payload={"type": "reward_signal", "policy": "explore", "reward": 1.0},
        )
        node.receive_message(msg)
        result = node.process({})
        assert result.output["rewards_this_cycle"] == 1
        assert result.output["active_policies"] >= 1


class TestHodNode:
    """Test Hod — language and semantic encoding."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import HodNode
        node = HodNode()
        assert node.state.qubits == 7

    def test_process(self):
        from qubitcoin.aether.sephirot_nodes import HodNode
        node = HodNode()
        result = node.process({"block_height": 1})
        assert result.action == "semantic_encoding"


class TestYesodNode:
    """Test Yesod — memory and multimodal fusion."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import YesodNode
        node = YesodNode()
        assert node.state.qubits == 16

    def test_buffer_capacity(self):
        from qubitcoin.aether.sephirot_nodes import YesodNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = YesodNode()
        # Send more messages than buffer capacity
        for i in range(10):
            msg = NodeMessage(
                sender=SephirahRole.TIFERET,
                receiver=SephirahRole.YESOD,
                payload={"data": i},
            )
            node.receive_message(msg)
        result = node.process({})
        assert result.output["buffer_usage"] <= result.output["buffer_capacity"]
        assert result.output["consolidations"] >= 1


class TestMalkuthNode:
    """Test Malkuth — action and world interaction."""

    def test_init(self):
        from qubitcoin.aether.sephirot_nodes import MalkuthNode
        node = MalkuthNode()
        assert node.state.qubits == 4

    def test_executes_directives(self):
        from qubitcoin.aether.sephirot_nodes import MalkuthNode, NodeMessage
        from qubitcoin.aether.sephirot import SephirahRole
        node = MalkuthNode()
        msg = NodeMessage(
            sender=SephirahRole.TIFERET,
            receiver=SephirahRole.MALKUTH,
            payload={"type": "integrated_directive", "source_count": 3},
        )
        node.receive_message(msg)
        result = node.process({"block_height": 10})
        assert result.output["actions_this_cycle"] == 1
        # Should report back to Keter
        assert len(result.messages_out) >= 1
        assert result.messages_out[0].receiver == SephirahRole.KETER


class TestNodeCommunication:
    """Test inter-node message passing."""

    def test_message_round_trip(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode, TiferetNode, MalkuthNode
        keter = KeterNode()
        tiferet = TiferetNode()
        malkuth = MalkuthNode()

        # Keter processes and sends to Tiferet
        k_result = keter.process({"block_height": 1})
        for msg in k_result.messages_out:
            if msg.receiver == tiferet.role:
                tiferet.receive_message(msg)

        # Tiferet integrates and sends to Malkuth
        t_result = tiferet.process({"block_height": 1})
        for msg in t_result.messages_out:
            if msg.receiver == malkuth.role:
                malkuth.receive_message(msg)

        # Malkuth executes and reports to Keter
        m_result = malkuth.process({"block_height": 1})
        assert m_result.output["actions_this_cycle"] == 1
        assert len(m_result.messages_out) >= 1

    def test_get_status(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        node = KeterNode()
        node.process({"block_height": 1})
        status = node.get_status()
        assert status["role"] == "keter"
        assert status["active"] is True
        assert status["processing_count"] == 1
        assert status["qubits"] == 8
