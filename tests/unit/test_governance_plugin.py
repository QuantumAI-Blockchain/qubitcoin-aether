"""Tests for Governance Plugin (Batch 18.1)."""
import pytest

from qubitcoin.qvm.governance_plugin import (
    GovernancePlugin,
    Proposal,
    ProposalState,
    Vote,
    VoteChoice,
    create_plugin,
)
from qubitcoin.qvm.plugins import PluginManager, HookType


class TestGovernanceLifecycle:
    def test_name_and_version(self):
        p = GovernancePlugin()
        assert p.name() == 'governance'
        assert p.version() == '0.1.0'

    def test_start_stop(self):
        p = GovernancePlugin()
        p.on_load()
        p.on_start()
        assert p._started is True
        p.on_stop()
        assert p._started is False

    def test_create_plugin_factory(self):
        p = create_plugin()
        assert isinstance(p, GovernancePlugin)


class TestProposalCreation:
    def test_create_proposal(self):
        g = GovernancePlugin()
        p = g.create_proposal('Test', 'A test proposal', 'alice')
        assert p.title == 'Test'
        assert p.proposer == 'alice'
        assert p.state == ProposalState.PENDING

    def test_proposal_to_dict(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'bob')
        d = p.to_dict()
        assert d['title'] == 'T'
        assert d['state'] == 'PENDING'

    def test_unique_ids(self):
        g = GovernancePlugin()
        p1 = g.create_proposal('A', '', 'alice')
        p2 = g.create_proposal('B', '', 'alice')
        assert p1.proposal_id != p2.proposal_id


class TestVoting:
    def test_activate_and_vote(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'proposer')
        g.activate_proposal(p.proposal_id)
        vote = g.cast_vote(p.proposal_id, 'voter1', VoteChoice.FOR, 10.0)
        assert vote is not None
        assert vote.choice == VoteChoice.FOR

    def test_cannot_vote_on_pending(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'proposer')
        vote = g.cast_vote(p.proposal_id, 'voter1', VoteChoice.FOR)
        assert vote is None

    def test_no_double_vote(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'proposer')
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'voter1', VoteChoice.FOR)
        v2 = g.cast_vote(p.proposal_id, 'voter1', VoteChoice.AGAINST)
        assert v2 is None

    def test_multiple_voters(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'proposer')
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.FOR, 5.0)
        g.cast_vote(p.proposal_id, 'b', VoteChoice.AGAINST, 3.0)
        g.cast_vote(p.proposal_id, 'c', VoteChoice.ABSTAIN, 2.0)
        assert p.for_weight == 5.0
        assert p.against_weight == 3.0
        assert p.total_weight == 10.0


class TestTally:
    def test_tally_passed(self):
        g = GovernancePlugin(total_stake=100.0)
        p = g.create_proposal('T', 'D', 'proposer', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.FOR, 15.0)
        result = g.tally(p.proposal_id)
        assert result['passed'] is True
        assert result['quorum_met'] is True

    def test_tally_rejected_no_quorum(self):
        g = GovernancePlugin(total_stake=1000.0)
        p = g.create_proposal('T', 'D', 'proposer', quorum=0.5)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.FOR, 1.0)
        result = g.tally(p.proposal_id)
        assert result['quorum_met'] is False
        assert result['passed'] is False

    def test_tally_rejected_against_wins(self):
        g = GovernancePlugin(total_stake=100.0)
        p = g.create_proposal('T', 'D', 'proposer', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.FOR, 5.0)
        g.cast_vote(p.proposal_id, 'b', VoteChoice.AGAINST, 10.0)
        result = g.tally(p.proposal_id)
        assert result['passed'] is False

    def test_tally_nonexistent(self):
        g = GovernancePlugin()
        assert g.tally('nope') is None


class TestExecution:
    def test_execute_passed(self):
        g = GovernancePlugin(total_stake=100.0)
        p = g.create_proposal('T', 'D', 'proposer', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.FOR, 20.0)
        g.tally(p.proposal_id)
        assert g.execute_proposal(p.proposal_id) is True
        assert p.state == ProposalState.EXECUTED

    def test_cannot_execute_rejected(self):
        g = GovernancePlugin(total_stake=100.0)
        p = g.create_proposal('T', 'D', 'proposer', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'a', VoteChoice.AGAINST, 20.0)
        g.tally(p.proposal_id)
        assert g.execute_proposal(p.proposal_id) is False


class TestCancellation:
    def test_cancel_by_proposer(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'alice')
        assert g.cancel_proposal(p.proposal_id, 'alice') is True
        assert p.state == ProposalState.CANCELLED

    def test_cannot_cancel_by_others(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'alice')
        assert g.cancel_proposal(p.proposal_id, 'bob') is False

    def test_cannot_cancel_executed(self):
        g = GovernancePlugin(total_stake=10.0)
        p = g.create_proposal('T', 'D', 'alice', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'v', VoteChoice.FOR, 5.0)
        g.tally(p.proposal_id)
        g.execute_proposal(p.proposal_id)
        assert g.cancel_proposal(p.proposal_id, 'alice') is False


class TestListAndStats:
    def test_list_all(self):
        g = GovernancePlugin()
        g.create_proposal('A', '', 'a')
        g.create_proposal('B', '', 'b')
        assert len(g.list_proposals()) == 2

    def test_list_by_state(self):
        g = GovernancePlugin()
        p1 = g.create_proposal('A', '', 'a')
        g.create_proposal('B', '', 'b')
        g.activate_proposal(p1.proposal_id)
        assert len(g.list_proposals(state=ProposalState.ACTIVE)) == 1

    def test_stats(self):
        g = GovernancePlugin()
        g.create_proposal('A', '', 'a')
        stats = g.get_stats()
        assert stats['total_proposals'] == 1

    def test_get_proposal(self):
        g = GovernancePlugin()
        p = g.create_proposal('T', 'D', 'a')
        assert g.get_proposal(p.proposal_id) is p
        assert g.get_proposal('nonexistent') is None


class TestPreExecuteHook:
    def test_no_governance_required(self):
        g = GovernancePlugin()
        result = g._pre_execute_hook({})
        assert result is None

    def test_governance_not_found(self):
        g = GovernancePlugin()
        result = g._pre_execute_hook({'requires_governance': 'missing'})
        assert result['governance_approved'] is False

    def test_governance_approved(self):
        g = GovernancePlugin(total_stake=10.0)
        p = g.create_proposal('T', 'D', 'a', quorum=0.1)
        g.activate_proposal(p.proposal_id)
        g.cast_vote(p.proposal_id, 'v', VoteChoice.FOR, 5.0)
        g.tally(p.proposal_id)
        g.execute_proposal(p.proposal_id)
        result = g._pre_execute_hook({'requires_governance': p.proposal_id})
        assert result['governance_approved'] is True
