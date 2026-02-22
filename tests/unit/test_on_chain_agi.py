"""Unit tests for Phase 6: OnChainAGI bridge."""
import hashlib
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestOnChainAGIInit:
    """Test OnChainAGI initialization."""

    def test_import(self):
        from qubitcoin.aether.on_chain import OnChainAGI
        assert OnChainAGI is not None

    @patch('qubitcoin.aether.on_chain.Config')
    def test_init_no_contracts(self, mock_config):
        """Init with no contract addresses configured."""
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = ''
        mock_config.PROOF_OF_THOUGHT_ADDRESS = ''
        mock_config.CONSTITUTIONAL_AI_ADDRESS = ''
        mock_config.TREASURY_DAO_ADDRESS = ''
        mock_config.UPGRADE_GOVERNOR_ADDRESS = ''
        mock_config.AETHER_KERNEL_ADDRESS = ''

        sm = MagicMock()
        sm.qvm = MagicMock()
        agi = OnChainAGI(sm)

        stats = agi.get_stats()
        assert stats['phi_writes'] == 0
        assert stats['pot_submissions'] == 0
        assert all(not v for v in stats['contracts_configured'].values())

    @patch('qubitcoin.aether.on_chain.Config')
    def test_init_with_contracts(self, mock_config):
        """Init with some contract addresses configured."""
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = ''
        mock_config.TREASURY_DAO_ADDRESS = ''
        mock_config.UPGRADE_GOVERNOR_ADDRESS = ''
        mock_config.AETHER_KERNEL_ADDRESS = 'c' * 40

        sm = MagicMock()
        sm.qvm = MagicMock()
        agi = OnChainAGI(sm)

        stats = agi.get_stats()
        assert stats['contracts_configured']['consciousness_dashboard'] is True
        assert stats['contracts_configured']['proof_of_thought'] is True
        assert stats['contracts_configured']['treasury_dao'] is False


class TestStaticCall:
    """Test read-only contract calls."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config, dashboard='', pot='', constitution='',
                  treasury='', governor=''):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = dashboard
        mock_config.PROOF_OF_THOUGHT_ADDRESS = pot
        mock_config.CONSTITUTIONAL_AI_ADDRESS = constitution
        mock_config.TREASURY_DAO_ADDRESS = treasury
        mock_config.UPGRADE_GOVERNOR_ADDRESS = governor
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_static_call_no_qvm(self):
        """Static call returns None when QVM is unavailable."""
        agi, sm = self._make_agi(dashboard='a' * 40)
        agi._qvm = None
        result = agi._static_call('a' * 40, b'\x00' * 4)
        assert result is None

    def test_static_call_no_address(self):
        """Static call returns None for empty address."""
        agi, sm = self._make_agi()
        result = agi._static_call('', b'\x00' * 4)
        assert result is None

    def test_static_call_exception(self):
        """Static call handles exceptions gracefully."""
        agi, sm = self._make_agi(dashboard='a' * 40)
        agi._qvm.static_call.side_effect = Exception("test error")
        result = agi._static_call('a' * 40, b'\x00' * 4)
        assert result is None
        assert agi._errors == 1


class TestWriteCall:
    """Test state-changing contract calls."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_write_call_no_sm(self):
        """Write call returns False when StateManager is unavailable."""
        agi, sm = self._make_agi()
        agi._sm = None
        result = agi._write_call('a' * 40, b'\x00' * 4, 1)
        assert result is False

    def test_write_call_no_address(self):
        """Write call returns False for empty address."""
        agi, sm = self._make_agi()
        result = agi._write_call('', b'\x00' * 4, 1)
        assert result is False

    def test_write_call_success(self):
        """Write call returns True when transaction succeeds."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        result = agi._write_call('a' * 40, b'\x00' * 4, 1)
        assert result is True

    def test_write_call_failure(self):
        """Write call returns False when transaction fails."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 0
        sm.process_transaction.return_value = receipt

        result = agi._write_call('a' * 40, b'\x00' * 4, 1)
        assert result is False

    def test_write_call_exception(self):
        """Write call handles exceptions gracefully."""
        agi, sm = self._make_agi()
        sm.process_transaction.side_effect = Exception("tx error")

        result = agi._write_call('a' * 40, b'\x00' * 4, 1)
        assert result is False
        assert agi._errors == 1


class TestConsciousnessDashboard:
    """Test 6.1: ConsciousnessDashboard contract integration."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_record_phi_no_address(self):
        """record_phi_onchain returns False with no dashboard address."""
        agi, sm = self._make_agi()
        agi._dashboard_addr = ''
        result = agi.record_phi_onchain(100, 2.5)
        assert result is False

    def test_record_phi_success(self):
        """record_phi_onchain increments counter on success."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        result = agi.record_phi_onchain(
            block_height=100, phi_value=2.5,
            integration=0.8, differentiation=0.6,
            coherence=0.7, knowledge_nodes=500, knowledge_edges=200
        )
        assert result is True
        assert agi._phi_writes == 1

    def test_get_onchain_phi_no_address(self):
        """get_onchain_phi returns None with no dashboard address."""
        agi, sm = self._make_agi()
        agi._dashboard_addr = ''
        result = agi.get_onchain_phi()
        assert result is None

    def test_get_onchain_phi_decodes(self):
        """get_onchain_phi correctly decodes uint256 to float."""
        from qubitcoin.aether.on_chain import PHI_PRECISION
        agi, sm = self._make_agi()
        # Simulate static_call returning 2500 (= 2.5 * 1000)
        raw_value = (2500).to_bytes(32, 'big')
        agi._qvm.static_call.return_value = raw_value

        result = agi.get_onchain_phi()
        assert result == 2500 / PHI_PRECISION  # 2.5

    def test_get_consciousness_status_no_address(self):
        """Returns None with no dashboard address."""
        agi, sm = self._make_agi()
        agi._dashboard_addr = ''
        result = agi.get_onchain_consciousness_status()
        assert result is None

    def test_get_consciousness_status_short_result(self):
        """Returns None if result is too short."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = b'\x00' * 100  # Too short
        result = agi.get_onchain_consciousness_status()
        assert result is None

    def test_get_consciousness_status_decodes(self):
        """Correctly decodes 8 uint256 values."""
        agi, sm = self._make_agi()
        data = b''
        data += (2500).to_bytes(32, 'big')  # phi = 2.5
        data += (3000).to_bytes(32, 'big')  # threshold = 3.0
        data += (0).to_bytes(32, 'big')     # above_threshold = false
        data += (2800).to_bytes(32, 'big')  # highest = 2.8
        data += (50).to_bytes(32, 'big')    # measurements = 50
        data += (3).to_bytes(32, 'big')     # events = 3
        data += (0).to_bytes(32, 'big')     # ever_conscious = false
        data += (0).to_bytes(32, 'big')     # genesis_block = 0
        agi._qvm.static_call.return_value = data

        result = agi.get_onchain_consciousness_status()
        assert result is not None
        assert result['phi'] == 2.5
        assert result['threshold'] == 3.0
        assert result['above_threshold'] is False
        assert result['highest_phi'] == 2.8
        assert result['total_measurements'] == 50
        assert result['total_events'] == 3

    def test_record_genesis_no_address(self):
        """record_genesis returns False with no address."""
        agi, sm = self._make_agi()
        agi._dashboard_addr = ''
        assert agi.record_genesis() is False


class TestProofOfThought:
    """Test 6.2: Proof-of-Thought on-chain verification."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_submit_proof_no_address(self):
        """Returns False with no PoT contract address."""
        agi, sm = self._make_agi()
        agi._pot_addr = ''
        result = agi.submit_proof_onchain(1, 'abc' * 20, 'def' * 20)
        assert result is False

    def test_submit_proof_success(self):
        """Increments counter on successful submission."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        result = agi.submit_proof_onchain(
            block_height=100,
            thought_hash='a' * 64,
            knowledge_root='b' * 64,
            submitter='c' * 40,
        )
        assert result is True
        assert agi._pot_submissions == 1

    def test_get_proof_by_block_no_address(self):
        """Returns None with no PoT address."""
        agi, sm = self._make_agi()
        agi._pot_addr = ''
        result = agi.get_proof_by_block(100)
        assert result is None

    def test_get_proof_by_block_found(self):
        """Returns proof ID when proof exists."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (42).to_bytes(32, 'big')
        result = agi.get_proof_by_block(100)
        assert result == 42

    def test_get_proof_by_block_not_found(self):
        """Returns None when proof ID is 0."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (0).to_bytes(32, 'big')
        result = agi.get_proof_by_block(100)
        assert result is None


class TestConstitutionalAI:
    """Test 6.3: Constitutional AI safety enforcement."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_check_vetoed_no_address(self):
        """Returns False (no veto) with no constitution address."""
        agi, sm = self._make_agi()
        agi._constitution_addr = ''
        assert agi.check_operation_vetoed("test op") is False

    def test_check_vetoed_true(self):
        """Detects vetoed operation."""
        agi, sm = self._make_agi()
        # Return true for vetoed
        agi._qvm.static_call.return_value = (1).to_bytes(32, 'big')
        assert agi.check_operation_vetoed("dangerous op") is True
        assert agi._veto_checks == 1

    def test_check_vetoed_false(self):
        """Returns False when operation is not vetoed."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (0).to_bytes(32, 'big')
        assert agi.check_operation_vetoed("safe op") is False

    def test_get_principle_count_no_address(self):
        """Returns (0, 0) with no address."""
        agi, sm = self._make_agi()
        agi._constitution_addr = ''
        assert agi.get_principle_count() == (0, 0)

    def test_get_principle_count_decodes(self):
        """Correctly decodes principle counts."""
        agi, sm = self._make_agi()
        data = (10).to_bytes(32, 'big') + (8).to_bytes(32, 'big')
        agi._qvm.static_call.return_value = data
        total, active = agi.get_principle_count()
        assert total == 10
        assert active == 8


class TestGovernance:
    """Test 6.4: On-chain governance."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_treasury_balance_no_address(self):
        """Returns None with no treasury address."""
        agi, sm = self._make_agi()
        agi._treasury_addr = ''
        assert agi.get_treasury_balance() is None

    def test_treasury_balance_decodes(self):
        """Correctly decodes treasury balance."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (1000000).to_bytes(32, 'big')
        balance = agi.get_treasury_balance()
        assert balance == 1000000
        assert agi._governance_reads == 1

    def test_proposal_count_no_address(self):
        """Returns None with no treasury address."""
        agi, sm = self._make_agi()
        agi._treasury_addr = ''
        assert agi.get_proposal_count() is None

    def test_proposal_count_decodes(self):
        """Correctly decodes proposal count."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (5).to_bytes(32, 'big')
        count = agi.get_proposal_count()
        assert count == 5

    def test_upgrade_proposal_count_no_address(self):
        """Returns None with no governor address."""
        agi, sm = self._make_agi()
        agi._governor_addr = ''
        assert agi.get_upgrade_proposal_count() is None

    def test_upgrade_proposal_count_decodes(self):
        """Correctly decodes upgrade proposal count."""
        agi, sm = self._make_agi()
        agi._qvm.static_call.return_value = (3).to_bytes(32, 'big')
        count = agi.get_upgrade_proposal_count()
        assert count == 3


class TestProcessBlock:
    """Test the combined per-block integration hook."""

    @patch('qubitcoin.aether.on_chain.Config')
    def _make_agi(self, mock_config):
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = 'b' * 40
        mock_config.CONSTITUTIONAL_AI_ADDRESS = 'c' * 40
        mock_config.TREASURY_DAO_ADDRESS = 'd' * 40
        mock_config.UPGRADE_GOVERNOR_ADDRESS = 'e' * 40
        mock_config.AETHER_KERNEL_ADDRESS = '0' * 40
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        return OnChainAGI(sm), sm

    def test_process_block_phi_at_interval(self):
        """Phi written at interval blocks."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        phi_result = {'phi_value': 2.5, 'integration': 0.8,
                      'differentiation': 0.6, 'coherence': 0.7,
                      'num_nodes': 500, 'num_edges': 200}

        result = agi.process_block(
            block_height=10,  # divisible by interval=10
            phi_result=phi_result,
            thought_hash='a' * 64,
            knowledge_root='b' * 64,
            validator_address='c' * 40,
        )
        assert result['phi_written'] is True
        assert result['pot_submitted'] is True

    def test_process_block_phi_off_interval(self):
        """Phi not written at non-interval blocks."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        phi_result = {'phi_value': 2.5}

        result = agi.process_block(
            block_height=13,  # NOT divisible by 10
            phi_result=phi_result,
            thought_hash='a' * 64,
            knowledge_root='b' * 64,
        )
        assert result['phi_written'] is False
        assert result['pot_submitted'] is True

    def test_process_block_no_thought_hash(self):
        """PoT not submitted without thought hash."""
        agi, sm = self._make_agi()
        receipt = MagicMock()
        receipt.status = 1
        sm.process_transaction.return_value = receipt

        result = agi.process_block(
            block_height=10,
            phi_result={'phi_value': 1.0},
            thought_hash='',
            knowledge_root='',
        )
        assert result['pot_submitted'] is False


class TestGetStats:
    """Test statistics reporting."""

    @patch('qubitcoin.aether.on_chain.Config')
    def test_stats_structure(self, mock_config):
        """Stats dict has expected structure."""
        from qubitcoin.aether.on_chain import OnChainAGI
        mock_config.CONSCIOUSNESS_DASHBOARD_ADDRESS = 'a' * 40
        mock_config.PROOF_OF_THOUGHT_ADDRESS = ''
        mock_config.CONSTITUTIONAL_AI_ADDRESS = ''
        mock_config.TREASURY_DAO_ADDRESS = ''
        mock_config.UPGRADE_GOVERNOR_ADDRESS = ''
        mock_config.AETHER_KERNEL_ADDRESS = ''
        mock_config.ONCHAIN_PHI_INTERVAL = 10

        sm = MagicMock()
        sm.qvm = MagicMock()
        agi = OnChainAGI(sm)

        stats = agi.get_stats()
        assert 'phi_writes' in stats
        assert 'pot_submissions' in stats
        assert 'veto_checks' in stats
        assert 'governance_reads' in stats
        assert 'errors' in stats
        assert 'contracts_configured' in stats
        assert len(stats['contracts_configured']) == 5
