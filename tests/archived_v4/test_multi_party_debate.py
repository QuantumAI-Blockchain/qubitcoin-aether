"""Unit tests for N-party debate with coalition formation."""
import pytest


class TestMultiPartyDebateImport:
    """Verify that all new types can be imported."""

    def test_import_coalition(self) -> None:
        from qubitcoin.aether.debate import Coalition
        c = Coalition(members=["a"], position="pos", strength=0.5)
        assert c.members == ["a"]

    def test_import_multi_party_debate_result(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebateResult
        r = MultiPartyDebateResult(
            topic="t", rounds=1, winner="w",
            coalitions=[], rounds_log=[],
        )
        assert r.winner == "w"

    def test_import_multi_party_debate(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        assert d.get_stats()['total_debates'] == 0


class TestAddParty:
    """Test party registration."""

    def test_add_single_party(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Alice", "pro quantum", 0.8)
        stats = d.get_stats()
        assert stats['num_parties'] == 1
        assert stats['parties'][0]['name'] == "Alice"

    def test_add_multiple_parties(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Alice", "pro", 0.8)
        d.add_party("Bob", "con", 0.6)
        d.add_party("Charlie", "neutral", 0.5)
        assert d.get_stats()['num_parties'] == 3

    def test_duplicate_party_raises(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Alice", "position", 0.5)
        with pytest.raises(ValueError, match="already exists"):
            d.add_party("Alice", "other", 0.7)

    def test_empty_name_raises(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        with pytest.raises(ValueError, match="name must not be empty"):
            d.add_party("", "position", 0.5)

    def test_empty_position_raises(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        with pytest.raises(ValueError, match="position must not be empty"):
            d.add_party("Alice", "", 0.5)

    def test_confidence_clamped_to_bounds(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Low", "pos", -0.5)
        d.add_party("High", "pos", 2.0)
        stats = d.get_stats()
        confs = {p['name']: p['confidence'] for p in stats['parties']}
        assert confs['Low'] == 0.0
        assert confs['High'] == 1.0


class TestFormCoalitions:
    """Test coalition formation logic."""

    def test_identical_positions_form_one_coalition(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "quantum is great", 0.8)
        d.add_party("B", "quantum is great", 0.6)
        coalitions = d.form_coalitions(threshold=0.7)
        assert len(coalitions) == 1
        assert set(coalitions[0].members) == {"A", "B"}
        assert abs(coalitions[0].strength - 1.4) < 0.01

    def test_different_positions_form_separate_coalitions(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "quantum computing is the future", 0.8)
        d.add_party("B", "classical hardware dominates everything", 0.7)
        coalitions = d.form_coalitions(threshold=0.7)
        assert len(coalitions) == 2

    def test_coalition_strength_is_sum_of_confidences(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "same position", 0.3)
        d.add_party("B", "same position", 0.4)
        d.add_party("C", "same position", 0.5)
        coalitions = d.form_coalitions(threshold=0.7)
        assert len(coalitions) == 1
        assert abs(coalitions[0].strength - 1.2) < 0.01

    def test_low_threshold_merges_more(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "quantum computing rocks", 0.6)
        d.add_party("B", "quantum computing is cool", 0.5)
        # With a low threshold these similar-ish strings should merge
        coalitions_low = d.form_coalitions(threshold=0.3)
        coalitions_high = d.form_coalitions(threshold=0.99)
        assert len(coalitions_low) <= len(coalitions_high)


class TestRunDebate:
    """Test the full debate execution."""

    def test_debate_with_two_parties(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Pro", "quantum supremacy is near", 0.9)
        d.add_party("Con", "classical will suffice for decades", 0.7)
        result = d.run_debate("future of computing", rounds=3)
        assert result.topic == "future of computing"
        assert result.rounds == 3
        assert len(result.coalitions) >= 1
        assert result.winner != ""
        assert len(result.rounds_log) == 3

    def test_debate_with_three_parties_coalition_wins(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        # Two parties share almost the same position -> they should coalesce
        d.add_party("Alice", "quantum is the future", 0.8)
        d.add_party("Bob", "quantum is the future", 0.7)
        # One party has a different view
        d.add_party("Eve", "classical computers dominate", 0.6)
        result = d.run_debate("computing paradigm", rounds=2)
        # The quantum coalition (Alice+Bob) should be stronger
        assert result.winner == "quantum is the future"

    def test_debate_fewer_than_two_parties(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("Solo", "only view", 0.5)
        result = d.run_debate("topic")
        assert result.rounds == 0
        assert result.winner == "only view"

    def test_debate_no_parties(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        result = d.run_debate("topic")
        assert result.winner == ""
        assert result.rounds == 0

    def test_debate_rounds_log_structure(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("X", "pos x", 0.6)
        d.add_party("Y", "pos y", 0.5)
        result = d.run_debate("test", rounds=2)
        assert len(result.rounds_log) == 2
        for entry in result.rounds_log:
            assert 'round' in entry
            assert 'arguments' in entry
            assert 'evaluations' in entry
            assert 'coalitions' in entry

    def test_debate_result_to_dict(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "pos a", 0.7)
        d.add_party("B", "pos b", 0.6)
        result = d.run_debate("topic", rounds=1)
        d_dict = result.to_dict()
        assert 'topic' in d_dict
        assert 'winner' in d_dict
        assert 'coalitions' in d_dict
        assert 'rounds_log' in d_dict

    def test_stats_after_debate(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "pos", 0.5)
        d.add_party("B", "other pos", 0.5)
        d.run_debate("t", rounds=1)
        stats = d.get_stats()
        assert stats['total_debates'] == 1

    def test_confidence_changes_during_debate(self) -> None:
        """Verify that parties' confidences are updated across rounds."""
        from qubitcoin.aether.debate import MultiPartyDebate
        d = MultiPartyDebate()
        d.add_party("A", "same stance", 0.5)
        d.add_party("B", "same stance", 0.5)
        d.add_party("C", "totally different opinion", 0.5)
        d.run_debate("topic", rounds=5)
        stats = d.get_stats()
        confs = {p['name']: p['confidence'] for p in stats['parties']}
        # A and B reinforce each other -> should have higher confidence
        # C is alone opposing -> should have lower confidence
        assert confs['A'] > confs['C']
        assert confs['B'] > confs['C']

    def test_position_similarity_static_method(self) -> None:
        from qubitcoin.aether.debate import MultiPartyDebate
        sim = MultiPartyDebate._position_similarity
        assert sim("hello world", "hello world") == 1.0
        assert sim("abc", "xyz") < 0.5
        assert sim("", "something") == 0.0
        assert sim("quantum future", "Quantum Future") == 1.0  # case insensitive
