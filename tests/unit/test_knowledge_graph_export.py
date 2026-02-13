"""Unit tests for knowledge graph JSON-LD export and Phi visualization data."""
import pytest


class TestExportJsonLD:
    """Test knowledge graph JSON-LD export."""

    def _make_test_kg(self):
        """Create in-memory KnowledgeGraph without DB."""
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph, KeterNode, KeterEdge
        import types

        kg = object.__new__(KnowledgeGraph)
        kg.db = None
        kg.nodes = {}
        kg.edges = []
        kg._next_id = 1

        original_add = KnowledgeGraph.add_node

        def add_node_no_db(self, node_type, content, confidence, source_block):
            import time
            from qubitcoin.aether.knowledge_graph import KeterNode
            node = KeterNode(
                node_id=self._next_id,
                node_type=node_type,
                content=content,
                confidence=max(0.0, min(1.0, confidence)),
                source_block=source_block,
                timestamp=time.time(),
            )
            node.content_hash = node.calculate_hash()
            self._next_id += 1
            self.nodes[node.node_id] = node
            return node

        kg.add_node = types.MethodType(add_node_no_db, kg)

        original_edge = KnowledgeGraph.add_edge

        def add_edge_no_db(self, from_id, to_id, edge_type='supports', weight=1.0):
            edge = KeterEdge(from_node_id=from_id, to_node_id=to_id,
                             edge_type=edge_type, weight=weight)
            self.edges.append(edge)
            if from_id in self.nodes:
                self.nodes[from_id].edges_out.append(to_id)
            if to_id in self.nodes:
                self.nodes[to_id].edges_in.append(from_id)
            return edge

        kg.add_edge = types.MethodType(add_edge_no_db, kg)
        return kg

    def test_empty_graph_export(self):
        kg = self._make_test_kg()
        result = kg.export_json_ld()
        assert "@context" in result
        assert "@graph" in result
        assert len(result["@graph"]) == 0
        assert result["qbc:stats"]["exported_nodes"] == 0

    def test_single_node_export(self):
        kg = self._make_test_kg()
        kg.add_node("assertion", {"key": "value"}, 0.8, 1)
        result = kg.export_json_ld()
        assert len(result["@graph"]) == 1
        node_entry = result["@graph"][0]
        assert node_entry["@type"] == "qbc:KeterNode"
        assert node_entry["node_type"] == "assertion"
        assert node_entry["confidence"] == 0.8
        assert node_entry["source_block"] == 1
        assert "qbc:content" in node_entry

    def test_export_with_edges(self):
        kg = self._make_test_kg()
        n1 = kg.add_node("assertion", {"a": 1}, 0.9, 1)
        n2 = kg.add_node("observation", {"b": 2}, 0.7, 2)
        kg.add_edge(n1.node_id, n2.node_id, "supports")
        result = kg.export_json_ld()
        # 2 nodes + 1 edge
        assert len(result["@graph"]) == 3
        edge_entries = [e for e in result["@graph"] if e["@type"] == "qbc:KeterEdge"]
        assert len(edge_entries) == 1
        assert edge_entries[0]["qbc:edgeType"] == "supports"

    def test_export_with_limit(self):
        kg = self._make_test_kg()
        for i in range(10):
            kg.add_node("assertion", {"i": i}, 0.5, i)
        result = kg.export_json_ld(limit=3)
        nodes = [e for e in result["@graph"] if e["@type"] == "qbc:KeterNode"]
        assert len(nodes) == 3
        assert result["qbc:stats"]["exported_nodes"] == 3
        assert result["qbc:stats"]["total_nodes"] == 10

    def test_context_has_vocabulary(self):
        kg = self._make_test_kg()
        result = kg.export_json_ld()
        ctx = result["@context"]
        assert "@vocab" in ctx
        assert "qbc" in ctx
        assert "supports" in ctx
        assert "contradicts" in ctx
        assert "derives" in ctx

    def test_edges_only_between_exported_nodes(self):
        """Edges connecting non-exported nodes should be excluded."""
        kg = self._make_test_kg()
        n1 = kg.add_node("assertion", {"a": 1}, 0.9, 1)
        n2 = kg.add_node("assertion", {"b": 2}, 0.8, 2)
        n3 = kg.add_node("assertion", {"c": 3}, 0.7, 3)
        kg.add_edge(n1.node_id, n2.node_id, "supports")
        kg.add_edge(n2.node_id, n3.node_id, "derives")
        # Limit to 2 nodes (n1, n2), so edge n2->n3 should be excluded
        result = kg.export_json_ld(limit=2)
        edges = [e for e in result["@graph"] if e["@type"] == "qbc:KeterEdge"]
        assert len(edges) == 1  # Only n1->n2

    def test_node_without_content(self):
        kg = self._make_test_kg()
        kg.add_node("axiom", {}, 1.0, 0)
        result = kg.export_json_ld()
        node_entry = result["@graph"][0]
        # Empty content dict should NOT produce qbc:content key
        assert "qbc:content" not in node_entry


class TestPhiTimeseries:
    """Test Phi visualization time series data format."""

    def test_timeseries_structure(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(5):
            cd.record_measurement(block_height=i, phi_value=float(i) * 0.5)
        history = cd.get_phi_history(limit=5)
        # Simulate the endpoint extraction
        blocks = [h.get("block_height", 0) for h in history]
        phi_values = [h.get("phi", 0.0) for h in history]
        conscious = [h.get("is_conscious", False) for h in history]
        assert len(blocks) == 5
        assert len(phi_values) == 5
        assert len(conscious) == 5
        assert blocks == [0, 1, 2, 3, 4]

    def test_timeseries_limit(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(20):
            cd.record_measurement(block_height=i, phi_value=float(i) * 0.1)
        history = cd.get_phi_history(limit=5)
        assert len(history) == 5
        # Should be the last 5
        assert history[-1]["block_height"] == 19
