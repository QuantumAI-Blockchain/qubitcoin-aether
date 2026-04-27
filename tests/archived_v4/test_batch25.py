"""Unit tests for Batch 25: PoT explorer, Compliance proofs, Regulatory reports.

Tests:
  - ProofOfThoughtExplorer: record, query, range, Phi progression, stats
  - ComplianceProofStore: store, chain, verify, query, integrity
  - RegulatoryReportGenerator: MiCA, SEC, FinCEN, general, integrity
"""
import time
from unittest.mock import MagicMock

from qubitcoin.aether.pot_explorer import ProofOfThoughtExplorer, BlockThoughtData
from qubitcoin.qvm.compliance_proofs import (
    ComplianceProofStore, ComplianceProof, ProofType,
)
from qubitcoin.qvm.regulatory_reports import (
    RegulatoryReportGenerator, RegulatoryReport, ReportType, ReportPeriod,
)


# ---------------------------------------------------------------------------
# ProofOfThoughtExplorer tests
# ---------------------------------------------------------------------------

class TestProofOfThoughtExplorer:
    """Test Proof-of-Thought explorer."""

    def test_record_block_thought(self):
        explorer = ProofOfThoughtExplorer()
        data = explorer.record_block_thought(
            block_height=100, thought_hash='abc123',
            phi_value=2.5, knowledge_root='root_hash',
            reasoning_steps=[{'type': 'inductive', 'result': 'ok'}],
            validator_address='qbc1validator',
        )
        assert data.block_height == 100
        assert data.phi_value == 2.5
        assert len(data.reasoning_steps) == 1

    def test_get_block_thought(self):
        explorer = ProofOfThoughtExplorer()
        explorer.record_block_thought(block_height=50, phi_value=1.0)
        result = explorer.get_block_thought(50)
        assert result is not None
        assert result['block_height'] == 50
        assert result['phi_value'] == 1.0

    def test_get_nonexistent_block(self):
        explorer = ProofOfThoughtExplorer()
        result = explorer.get_block_thought(999)
        assert result is None

    def test_get_block_from_engine_cache(self):
        engine = MagicMock()
        pot = MagicMock()
        pot.thought_hash = 'hash1'
        pot.phi_value = 3.5
        pot.knowledge_root = 'root1'
        pot.reasoning_steps = [{'type': 'deductive'}]
        pot.validator_address = 'qbc1test'
        pot.timestamp = 1000.0
        engine._pot_cache = {42: pot}

        explorer = ProofOfThoughtExplorer(aether_engine=engine)
        result = explorer.get_block_thought(42)
        assert result is not None
        assert result['phi_value'] == 3.5

    def test_get_block_range(self):
        explorer = ProofOfThoughtExplorer()
        for h in range(10, 15):
            explorer.record_block_thought(block_height=h, phi_value=h * 0.1)
        results = explorer.get_block_range(10, 14)
        assert len(results) == 5
        assert results[0]['block_height'] == 10

    def test_phi_progression(self):
        explorer = ProofOfThoughtExplorer()
        for h in range(20):
            explorer.record_block_thought(block_height=h, phi_value=h * 0.2)
        progression = explorer.get_phi_progression(limit=5)
        assert len(progression) == 5
        assert 'phi_value' in progression[0]

    def test_consciousness_events(self):
        explorer = ProofOfThoughtExplorer()
        explorer.record_block_thought(block_height=1, phi_value=1.0)
        explorer.record_block_thought(
            block_height=2, phi_value=3.5,
            consciousness_event='phi_threshold_crossed',
        )
        explorer.record_block_thought(block_height=3, phi_value=2.0)

        events = explorer.get_consciousness_events()
        assert len(events) == 1
        assert events[0]['consciousness_event'] == 'phi_threshold_crossed'

    def test_reasoning_summary(self):
        explorer = ProofOfThoughtExplorer()
        explorer.record_block_thought(
            block_height=10, phi_value=2.0,
            reasoning_steps=[
                {'type': 'inductive', 'conclusion': 'Pattern found'},
                {'type': 'deductive', 'conclusion': 'Verified'},
                {'type': 'inductive', 'conclusion': 'Confirmed'},
            ],
            knowledge_node_ids=[1, 2, 3],
        )
        summary = explorer.get_reasoning_summary(10)
        assert summary['total_steps'] == 3
        assert summary['reasoning_types']['inductive'] == 2
        assert summary['reasoning_types']['deductive'] == 1
        assert len(summary['conclusions']) == 3

    def test_search_by_phi_range(self):
        explorer = ProofOfThoughtExplorer()
        for h in range(10):
            explorer.record_block_thought(block_height=h, phi_value=h * 0.5)
        results = explorer.search_by_phi_range(1.0, 3.0)
        assert all(1.0 <= r['phi_value'] <= 3.0 for r in results)

    def test_cache_eviction(self):
        explorer = ProofOfThoughtExplorer(max_cache=5)
        for h in range(10):
            explorer.record_block_thought(block_height=h, phi_value=1.0)
        assert len(explorer._block_data) == 5

    def test_get_stats(self):
        explorer = ProofOfThoughtExplorer()
        explorer.record_block_thought(block_height=1, phi_value=2.0)
        explorer.record_block_thought(block_height=2, phi_value=3.0)
        stats = explorer.get_stats()
        assert stats['blocks_explored'] == 2
        assert stats['phi_min'] == 2.0
        assert stats['phi_max'] == 3.0

    def test_block_thought_data_to_dict(self):
        data = BlockThoughtData(
            block_height=5, phi_value=1.5,
            reasoning_steps=[{'x': 1}],
            knowledge_nodes_ids=[10, 20],
            knowledge_nodes_created=2,
        )
        d = data.to_dict()
        assert d['block_height'] == 5
        assert d['reasoning_step_count'] == 1
        assert d['knowledge_nodes_created'] == 2


# ---------------------------------------------------------------------------
# ComplianceProofStore tests
# ---------------------------------------------------------------------------

class TestComplianceProofStore:
    """Test compliance proof storage."""

    def test_store_proof(self):
        store = ComplianceProofStore()
        proof = store.store_proof(
            proof_type='kyc_verification',
            address='0xabc123',
            block_height=100,
            proof_data={'kyc_level': 2},
        )
        assert proof.proof_type == 'kyc_verification'
        assert proof.address == '0xabc123'
        assert proof.proof_hash  # Hash should be generated

    def test_get_proof(self):
        store = ComplianceProofStore()
        proof = store.store_proof('kyc_verification', '0xtest', 10)
        result = store.get_proof(proof.proof_id)
        assert result is not None
        assert result['proof_type'] == 'kyc_verification'

    def test_get_nonexistent_proof(self):
        store = ComplianceProofStore()
        assert store.get_proof('nonexistent') is None

    def test_proof_chain_linkage(self):
        store = ComplianceProofStore()
        p1 = store.store_proof('kyc_verification', '0xtest', 10)
        p2 = store.store_proof('aml_screening', '0xtest', 20)
        # p2 should link to p1
        assert p2.previous_proof_hash == p1.proof_hash

    def test_proof_chain_per_address(self):
        store = ComplianceProofStore()
        # Different addresses have independent chains
        p1 = store.store_proof('kyc_verification', '0xalice', 10)
        p2 = store.store_proof('kyc_verification', '0xbob', 10)
        assert p2.previous_proof_hash == ''  # No previous for bob

    def test_get_address_proofs(self):
        store = ComplianceProofStore()
        for i in range(5):
            store.store_proof('kyc_verification', '0xtest', i)
        proofs = store.get_address_proofs('0xtest')
        assert len(proofs) == 5
        # Newest first
        assert proofs[0]['block_height'] == 4

    def test_get_address_proofs_filtered(self):
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xtest', 1)
        store.store_proof('aml_screening', '0xtest', 2)
        store.store_proof('kyc_verification', '0xtest', 3)

        proofs = store.get_address_proofs('0xtest', proof_type='kyc_verification')
        assert len(proofs) == 2
        assert all(p['proof_type'] == 'kyc_verification' for p in proofs)

    def test_get_block_proofs(self):
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xalice', 100)
        store.store_proof('aml_screening', '0xbob', 100)
        store.store_proof('kyc_verification', '0xcarol', 101)

        proofs = store.get_block_proofs(100)
        assert len(proofs) == 2

    def test_verify_proof_chain_intact(self):
        store = ComplianceProofStore()
        for i in range(3):
            store.store_proof('kyc_verification', '0xtest', i)
        result = store.verify_proof_chain('0xtest')
        assert result['total_proofs'] == 3
        assert result['valid_proofs'] == 3
        assert result['invalid_proofs'] == 0
        assert result['chain_intact'] is True

    def test_proof_integrity(self):
        proof = ComplianceProof(
            proof_id='test1', proof_type='kyc_verification',
            address='0xtest', block_height=10,
            proof_data={'level': 2},
        )
        assert proof.verify_integrity() is True
        # Tamper with data
        proof.proof_data['level'] = 3
        assert proof.verify_integrity() is False

    def test_proof_expiry(self):
        proof = ComplianceProof(
            proof_id='test', proof_type='kyc_verification',
            address='0xtest', block_height=10,
            expiry=time.time() - 1000,  # Already expired
        )
        assert proof.is_expired() is True

        proof2 = ComplianceProof(
            proof_id='test2', proof_type='kyc_verification',
            address='0xtest', block_height=10,
            expiry=0,  # Never expires
        )
        assert proof2.is_expired() is False

    def test_get_latest_proof(self):
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xtest', 1)
        store.store_proof('aml_screening', '0xtest', 2)
        store.store_proof('kyc_verification', '0xtest', 3)

        latest = store.get_latest_proof('0xtest')
        assert latest['block_height'] == 3

        latest_kyc = store.get_latest_proof('0xtest', 'kyc_verification')
        assert latest_kyc['proof_type'] == 'kyc_verification'

    def test_capacity_eviction(self):
        store = ComplianceProofStore(max_proofs=5)
        for i in range(10):
            store.store_proof('kyc_verification', f'0xaddr{i}', i)
        assert len(store._proofs) <= 6  # May have up to 6 during eviction

    def test_get_stats(self):
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xalice', 1)
        store.store_proof('aml_screening', '0xbob', 2)
        stats = store.get_stats()
        assert stats['total_proofs'] == 2
        assert stats['unique_addresses'] == 2
        assert 'kyc_verification' in stats['proof_types']

    def test_address_case_insensitive(self):
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xABC', 1)
        proofs = store.get_address_proofs('0xabc')
        assert len(proofs) == 1


# ---------------------------------------------------------------------------
# RegulatoryReportGenerator tests
# ---------------------------------------------------------------------------

class TestRegulatoryReportGenerator:
    """Test regulatory report generation."""

    def test_generate_mica_report(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            report_type='mica', period='monthly',
            block_start=0, block_end=1000,
        )
        assert report.report_type == 'mica'
        assert 'MiCA' in report.data['framework']
        assert report.data['token_classification']['type'] == 'utility_token'

    def test_generate_sec_report(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            report_type='sec', period='quarterly',
            block_start=0, block_end=5000,
        )
        assert report.report_type == 'sec'
        assert 'howey_test_analysis' in report.data
        assert report.data['howey_test_analysis']['classification'] == 'utility_token'

    def test_generate_fincen_report(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            report_type='fincen', period='annual',
            block_start=0, block_end=10000,
        )
        assert report.report_type == 'fincen'
        assert report.data['bsa_compliance']['customer_identification'] is True

    def test_generate_general_report(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            report_type='general', period='daily',
        )
        assert report.report_type == 'general'

    def test_report_with_compliance_engine(self):
        engine = MagicMock()
        policy = MagicMock()
        policy.tier = 0
        policy.kyc_level = 1
        engine.list_policies = MagicMock(return_value=[policy])

        gen = RegulatoryReportGenerator(compliance_engine=engine)
        report = gen.generate_report('mica', 'monthly')
        assert report.data['policy_summary']['total_policies'] == 1

    def test_report_with_proof_store(self):
        proof_store = MagicMock()
        proof_store.get_stats = MagicMock(return_value={
            'total_proofs': 42, 'unique_addresses': 10,
            'proof_types': {'kyc_verification': 30, 'aml_screening': 12},
        })

        gen = RegulatoryReportGenerator(proof_store=proof_store)
        report = gen.generate_report('sec', 'quarterly', block_start=0, block_end=100)
        assert report.data['proof_summary']['total_proofs'] == 42

    def test_report_integrity(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report('general', 'daily')
        assert report.verify_integrity() is True
        # Tamper
        report.data['extra'] = 'tampered'
        assert report.verify_integrity() is False

    def test_get_report(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report('mica', 'monthly')
        result = gen.get_report(report.report_id)
        assert result is not None
        assert result['report_type'] == 'mica'

    def test_get_nonexistent_report(self):
        gen = RegulatoryReportGenerator()
        assert gen.get_report('nonexistent') is None

    def test_list_reports(self):
        gen = RegulatoryReportGenerator()
        gen.generate_report('mica', 'monthly')
        gen.generate_report('sec', 'quarterly')
        gen.generate_report('fincen', 'annual')

        all_reports = gen.list_reports()
        assert len(all_reports) == 3

        mica_only = gen.list_reports(report_type='mica')
        assert len(mica_only) == 1

    def test_additional_data(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            'general', 'daily',
            additional_data={'auditor': 'External Audit Firm'},
        )
        assert report.data['additional']['auditor'] == 'External Audit Firm'

    def test_period_seconds(self):
        assert RegulatoryReportGenerator._period_seconds('daily') == 86400
        assert RegulatoryReportGenerator._period_seconds('weekly') == 604800
        assert RegulatoryReportGenerator._period_seconds('quarterly') == 7776000

    def test_report_to_dict(self):
        report = RegulatoryReport(
            report_id='test1', report_type='mica', period='monthly',
            data={'framework': 'test'},
        )
        d = report.to_dict()
        assert d['report_id'] == 'test1'
        assert 'is_valid' in d
        assert 'report_hash' in d

    def test_get_stats(self):
        gen = RegulatoryReportGenerator()
        gen.generate_report('mica', 'monthly')
        gen.generate_report('sec', 'quarterly')
        stats = gen.get_stats()
        assert stats['total_reports'] == 2
        assert 'mica' in stats['report_types']
        assert 'sec' in stats['report_types']

    def test_report_block_range(self):
        gen = RegulatoryReportGenerator()
        report = gen.generate_report(
            'general', 'daily', block_start=100, block_end=200,
        )
        assert report.block_range == (100, 200)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestBatch25Integration:
    """Integration tests across Batch 25 modules."""

    def test_proof_store_with_report_gen(self):
        """Compliance proofs feed into regulatory reports."""
        store = ComplianceProofStore()
        store.store_proof('kyc_verification', '0xalice', 10)
        store.store_proof('aml_screening', '0xbob', 20)

        gen = RegulatoryReportGenerator(proof_store=store)
        report = gen.generate_report('mica', 'monthly', block_start=0, block_end=100)
        assert report.data['proof_summary']['total_proofs'] == 2

    def test_pot_explorer_reasoning_types(self):
        """PoT explorer correctly categorizes reasoning types."""
        explorer = ProofOfThoughtExplorer()
        explorer.record_block_thought(
            block_height=1, phi_value=2.5,
            reasoning_steps=[
                {'type': 'inductive', 'conclusion': 'Pattern A'},
                {'type': 'deductive', 'conclusion': 'Therefore B'},
                {'type': 'abductive', 'conclusion': 'Hypothesis C'},
            ],
        )
        summary = explorer.get_reasoning_summary(1)
        assert summary['reasoning_types'] == {
            'inductive': 1, 'deductive': 1, 'abductive': 1,
        }
