"""Unit tests for ConceptFormation incremental refinement and merging."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from qubitcoin.aether.concept_formation import ConceptFormation
from qubitcoin.aether.knowledge_graph import KeterNode, KeterEdge


def _make_node(node_id: int, node_type: str = 'observation',
               content: dict = None, confidence: float = 0.7,
               source_block: int = 10, domain: str = 'general') -> KeterNode:
    """Helper to create a KeterNode without a real KnowledgeGraph."""
    return KeterNode(
        node_id=node_id,
        node_type=node_type,
        content=content or {'text': f'node_{node_id}', 'type': 'test'},
        confidence=confidence,
        source_block=source_block,
        domain=domain,
    )


def _make_concept_node(node_id: int, member_count: int = 3,
                       domain: str = 'general',
                       confidence: float = 0.6) -> KeterNode:
    """Helper to create a concept KeterNode."""
    return KeterNode(
        node_id=node_id,
        node_type='inference',
        content={
            'type': 'abstract_concept',
            'text': 'Concept: test theme',
            'theme_words': ['test', 'theme'],
            'member_count': member_count,
            'domain': domain,
            'source': 'concept_formation',
        },
        confidence=confidence,
        source_block=10,
        domain=domain,
    )


def _build_mock_kg(nodes: dict, adj_out: dict = None, adj_in: dict = None) -> MagicMock:
    """Build a mock KnowledgeGraph with the given nodes and adjacency."""
    kg = MagicMock()
    kg.nodes = nodes
    kg._adj_out = adj_out or {}
    kg._adj_in = adj_in or {}

    def add_edge_side_effect(from_id: int, to_id: int, edge_type: str = 'supports',
                             weight: float = 1.0):
        edge = KeterEdge(from_node_id=from_id, to_node_id=to_id,
                         edge_type=edge_type, weight=weight)
        kg._adj_out.setdefault(from_id, []).append(edge)
        kg._adj_in.setdefault(to_id, []).append(edge)
        return edge

    kg.add_edge = MagicMock(side_effect=add_edge_side_effect)

    def add_node_side_effect(node_type: str, content: dict, confidence: float,
                             source_block: int, domain: str = ''):
        new_id = max(nodes.keys()) + 1 if nodes else 1
        node = KeterNode(
            node_id=new_id, node_type=node_type, content=content,
            confidence=confidence, source_block=source_block, domain=domain,
        )
        nodes[new_id] = node
        return node

    kg.add_node = MagicMock(side_effect=add_node_side_effect)
    return kg


class TestRefineConceptBasic:
    """Test refine_concept method."""

    def test_refine_no_kg_returns_none(self) -> None:
        """Without a knowledge graph, refine returns None."""
        cf = ConceptFormation(knowledge_graph=None)
        result = cf.refine_concept(1, [])
        assert result is None

    def test_refine_missing_concept_returns_none(self) -> None:
        """If concept_id doesn't exist, returns None."""
        kg = _build_mock_kg(nodes={})
        cf = ConceptFormation(knowledge_graph=kg)
        result = cf.refine_concept(999, [_make_node(1)])
        assert result is None

    def test_refine_non_concept_node_returns_none(self) -> None:
        """If the node isn't an abstract_concept, returns None."""
        regular_node = _make_node(1, content={'type': 'observation', 'text': 'not a concept'})
        kg = _build_mock_kg(nodes={1: regular_node})
        cf = ConceptFormation(knowledge_graph=kg)
        result = cf.refine_concept(1, [_make_node(2)])
        assert result is None

    def test_refine_incorporates_new_nodes(self) -> None:
        """New nodes that meet similarity threshold get incorporated."""
        concept = _make_concept_node(100, member_count=3)
        member1 = _make_node(1)
        member2 = _make_node(2)
        member3 = _make_node(3)
        new_node = _make_node(4)

        nodes = {100: concept, 1: member1, 2: member2, 3: member3, 4: new_node}

        # Set up adjacency: concept -> members via 'abstracts' edges
        adj_out = {
            100: [
                KeterEdge(from_node_id=100, to_node_id=1, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=2, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=3, edge_type='abstracts'),
            ]
        }
        kg = _build_mock_kg(nodes=nodes, adj_out=adj_out)

        # Use a mock vector_index that returns high similarity for the new node
        mock_vi = MagicMock()
        mock_vi.get_embedding = MagicMock(return_value=None)  # No embeddings => fallback sim 0.4

        cf = ConceptFormation(knowledge_graph=kg, vector_index=mock_vi)
        # With fallback similarity of 0.4 and threshold 0.3, node should be incorporated
        result = cf.refine_concept(100, [new_node], similarity_threshold=0.3)

        assert result == 100
        # add_edge should have been called for the new node
        kg.add_edge.assert_called()
        assert cf._concepts_refined == 1

    def test_refine_skips_low_similarity_nodes(self) -> None:
        """Nodes below threshold are not incorporated."""
        concept = _make_concept_node(100, member_count=2)
        member1 = _make_node(1)
        member2 = _make_node(2)
        new_node = _make_node(3)

        nodes = {100: concept, 1: member1, 2: member2, 3: new_node}
        adj_out = {
            100: [
                KeterEdge(from_node_id=100, to_node_id=1, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=2, edge_type='abstracts'),
            ]
        }
        kg = _build_mock_kg(nodes=nodes, adj_out=adj_out)

        mock_vi = MagicMock()
        mock_vi.get_embedding = MagicMock(return_value=None)  # fallback sim = 0.4

        cf = ConceptFormation(knowledge_graph=kg, vector_index=mock_vi)
        # With threshold 0.9, fallback similarity of 0.4 won't meet it
        result = cf.refine_concept(100, [new_node], similarity_threshold=0.9)

        assert result is None
        assert cf._concepts_refined == 0

    def test_refine_updates_concept_metadata(self) -> None:
        """After incorporation, concept metadata (member_count, confidence) updates."""
        concept = _make_concept_node(100, member_count=2, confidence=0.6)
        member1 = _make_node(1, confidence=0.8)
        member2 = _make_node(2, confidence=0.9)
        new_node = _make_node(3, confidence=0.7, source_block=20)

        nodes = {100: concept, 1: member1, 2: member2, 3: new_node}
        adj_out = {
            100: [
                KeterEdge(from_node_id=100, to_node_id=1, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=2, edge_type='abstracts'),
            ]
        }
        kg = _build_mock_kg(nodes=nodes, adj_out=adj_out)

        mock_vi = MagicMock()
        mock_vi.get_embedding = MagicMock(return_value=None)

        cf = ConceptFormation(knowledge_graph=kg, vector_index=mock_vi)
        result = cf.refine_concept(100, [new_node], similarity_threshold=0.3)

        assert result == 100
        # member_count should now be 3
        assert concept.content['member_count'] == 3
        # source_block should be updated to max of members
        assert concept.source_block == 20


class TestMergeSimilarConcepts:
    """Test merge_similar_concepts method."""

    def test_merge_no_kg_returns_zero(self) -> None:
        """Without a knowledge graph, merge returns 0."""
        cf = ConceptFormation(knowledge_graph=None)
        assert cf.merge_similar_concepts() == 0

    def test_merge_single_concept_returns_zero(self) -> None:
        """With only one concept, nothing to merge."""
        concept = _make_concept_node(100)
        kg = _build_mock_kg(nodes={100: concept})
        cf = ConceptFormation(knowledge_graph=kg)
        assert cf.merge_similar_concepts() == 0

    def test_merge_dissimilar_concepts_returns_zero(self) -> None:
        """Concepts with low similarity are not merged."""
        concept_a = _make_concept_node(100, domain='physics')
        concept_b = _make_concept_node(200, domain='economics')
        member_a = _make_node(1)
        member_b = _make_node(2)

        nodes = {100: concept_a, 200: concept_b, 1: member_a, 2: member_b}
        adj_out = {
            100: [KeterEdge(from_node_id=100, to_node_id=1, edge_type='abstracts')],
            200: [KeterEdge(from_node_id=200, to_node_id=2, edge_type='abstracts')],
        }
        kg = _build_mock_kg(nodes=nodes, adj_out=adj_out)

        # Vector index returns empty centroids => similarity 0.0
        mock_vi = MagicMock()
        mock_vi.get_embedding = MagicMock(return_value=None)

        cf = ConceptFormation(knowledge_graph=kg, vector_index=mock_vi)
        merges = cf.merge_similar_concepts(threshold=0.85)
        assert merges == 0

    def test_merge_marks_discarded_concept(self) -> None:
        """After merge, the discarded concept is marked as merged_concept."""
        concept_a = _make_concept_node(100, member_count=3)
        concept_b = _make_concept_node(200, member_count=1)
        members = {i: _make_node(i) for i in range(1, 5)}

        nodes = {100: concept_a, 200: concept_b, **members}
        adj_out = {
            100: [
                KeterEdge(from_node_id=100, to_node_id=1, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=2, edge_type='abstracts'),
                KeterEdge(from_node_id=100, to_node_id=3, edge_type='abstracts'),
            ],
            200: [
                KeterEdge(from_node_id=200, to_node_id=4, edge_type='abstracts'),
            ],
        }
        kg = _build_mock_kg(nodes=nodes, adj_out=adj_out)

        # Mock vector index that returns identical embeddings => similarity 1.0
        mock_vi = MagicMock()
        mock_vi.get_embedding = MagicMock(return_value=[1.0, 0.0, 0.0])

        cf = ConceptFormation(knowledge_graph=kg, vector_index=mock_vi)
        merges = cf.merge_similar_concepts(threshold=0.85)

        assert merges == 1
        assert cf._concepts_merged == 1
        # The smaller concept (200, 1 member) should be marked as merged
        assert concept_b.content['type'] == 'merged_concept'
        assert concept_b.content['merged_into'] == 100


class TestGetStatsIncludesRefinement:
    """Test that get_stats includes refinement counters."""

    def test_stats_include_refinement_fields(self) -> None:
        cf = ConceptFormation()
        stats = cf.get_stats()
        assert 'concepts_refined' in stats
        assert 'concepts_split' in stats
        assert 'concepts_merged' in stats
        assert stats['concepts_refined'] == 0
        assert stats['concepts_split'] == 0
        assert stats['concepts_merged'] == 0
