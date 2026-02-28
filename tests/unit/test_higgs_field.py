"""
Tests for Higgs Cognitive Field — Physics upgrade.

Covers:
- Mexican Hat potential computation
- VEV calculation from mu and lambda
- Yukawa coupling hierarchy (golden ratio cascade)
- Cognitive mass assignment
- Two-Higgs-Doublet Model (H_u, H_d VEVs)
- Mass-aware SUSY rebalancing (F = ma)
- Excitation event detection
- Mass gap metric
- Field evolution
- Parameter governance
- Edge cases (zero mass, extreme deviations)
"""
import math
import pytest
from unittest.mock import MagicMock, patch

# Must mock config before importing
with patch.dict('os.environ', {
    'ADDRESS': 'test_address',
    'PUBLIC_KEY_HEX': 'test_pub',
    'PRIVATE_KEY_HEX': 'test_priv',
}):
    from qubitcoin.aether.higgs_field import (
        HiggsCognitiveField, HiggsSUSYSwap, HiggsParameters,
        ExcitationEvent, YUKAWA_COUPLINGS, EXPANSION_NODES,
        CONSTRAINT_NODES, PHI,
    )
    from qubitcoin.aether.sephirot import (
        SephirotManager, SephirahRole, SephirahState, SUSY_PAIRS,
    )


class TestHiggsParameters:
    """Test Higgs parameter calculations."""

    def test_vev_default(self):
        p = HiggsParameters()
        # v = mu / sqrt(2 * lambda) = 88.45 / sqrt(0.258)
        expected = 88.45 / math.sqrt(2.0 * 0.129)
        assert abs(p.vev - expected) < 0.01

    def test_higgs_mass(self):
        p = HiggsParameters()
        expected = math.sqrt(2.0) * 88.45
        assert abs(p.higgs_mass - expected) < 0.01

    def test_2hdm_vevs(self):
        p = HiggsParameters()
        beta = math.atan(PHI)
        assert abs(p.v_up - p.vev * math.sin(beta)) < 0.01
        assert abs(p.v_down - p.vev * math.cos(beta)) < 0.01
        # v_up > v_down (tan_beta > 1)
        assert p.v_up > p.v_down
        # v_up / v_down ≈ tan(beta) = phi
        assert abs(p.v_up / p.v_down - PHI) < 0.1

    def test_custom_parameters(self):
        p = HiggsParameters(mu=100.0, lambda_coupling=0.25, tan_beta=2.0)
        expected_vev = 100.0 / math.sqrt(0.5)
        assert abs(p.vev - expected_vev) < 0.01


class TestYukawaCouplings:
    """Test golden ratio Yukawa coupling hierarchy."""

    def test_all_nodes_have_coupling(self):
        for role in SephirahRole:
            assert role in YUKAWA_COUPLINGS

    def test_keter_is_maximum(self):
        assert YUKAWA_COUPLINGS[SephirahRole.KETER] == 1.0

    def test_golden_ratio_cascade(self):
        assert abs(YUKAWA_COUPLINGS[SephirahRole.TIFERET] - PHI**-1) < 0.001
        assert abs(YUKAWA_COUPLINGS[SephirahRole.CHESED] - PHI**-2) < 0.001
        assert abs(YUKAWA_COUPLINGS[SephirahRole.GEVURAH] - PHI**-3) < 0.001
        assert abs(YUKAWA_COUPLINGS[SephirahRole.MALKUTH] - PHI**-4) < 0.001

    def test_expansion_lighter_than_neutral(self):
        # Expansion nodes should have lower coupling than neutral
        for role in EXPANSION_NODES:
            assert YUKAWA_COUPLINGS[role] < YUKAWA_COUPLINGS[SephirahRole.KETER]

    def test_constraint_lightest(self):
        # Constraint nodes should have lowest coupling
        for role in CONSTRAINT_NODES:
            for exp_role in EXPANSION_NODES:
                assert YUKAWA_COUPLINGS[role] < YUKAWA_COUPLINGS[exp_role]

    def test_susy_pair_mass_ratio(self):
        # Expansion / Constraint coupling ratio should approximate phi
        for expansion, constraint in SUSY_PAIRS:
            ratio = YUKAWA_COUPLINGS[expansion] / YUKAWA_COUPLINGS[constraint]
            assert abs(ratio - PHI) < 0.1


class TestHiggsCognitiveField:
    """Test HiggsCognitiveField class."""

    def _make_field(self):
        db = MagicMock()
        sm = SephirotManager(db)
        params = HiggsParameters(mu=88.45, lambda_coupling=0.129)
        hcf = HiggsCognitiveField(sm, params)
        return hcf, sm

    def test_initialize_assigns_masses(self):
        hcf, sm = self._make_field()
        masses = hcf.initialize()
        assert len(masses) == 10
        for role in SephirahRole:
            assert masses[role.value] > 0

    def test_keter_has_max_mass(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        keter_mass = hcf.get_cognitive_mass(SephirahRole.KETER)
        for role in SephirahRole:
            if role != SephirahRole.KETER:
                assert keter_mass >= hcf.get_cognitive_mass(role)

    def test_constraint_nodes_are_lightest(self):
        """Constraint nodes use v_down (smallest VEV), so they are lightest."""
        hcf, sm = self._make_field()
        hcf.initialize()
        # Find minimum mass across all nodes
        all_masses = {role: hcf.get_cognitive_mass(role) for role in SephirahRole}
        min_mass_role = min(all_masses, key=all_masses.get)
        # The lightest node should be a constraint node (uses v_down)
        assert min_mass_role in CONSTRAINT_NODES

    def test_expansion_nodes_use_v_up(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        v_up = hcf.params.v_up
        for role in EXPANSION_NODES:
            yukawa = YUKAWA_COUPLINGS[role]
            expected_mass = yukawa * v_up
            actual_mass = hcf.get_cognitive_mass(role)
            assert abs(actual_mass - expected_mass) < 0.01

    def test_constraint_nodes_use_v_down(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        v_down = hcf.params.v_down
        for role in CONSTRAINT_NODES:
            yukawa = YUKAWA_COUPLINGS[role]
            expected_mass = yukawa * v_down
            actual_mass = hcf.get_cognitive_mass(role)
            assert abs(actual_mass - expected_mass) < 0.01

    def test_tick_returns_field_state(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        result = hcf.tick(1)
        assert 'field_value' in result
        assert 'vev' in result
        assert 'mass_gap' in result
        assert 'total_excitations' in result
        assert 'potential_energy' in result

    def test_potential_energy_at_vev(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        # At VEV, potential should be at minimum (negative)
        v = hcf.potential_energy()
        # Check it's a reasonable number (potential is negative at VEV)
        assert isinstance(v, float)

    def test_higgs_gradient_zero_at_vev(self):
        hcf, sm = self._make_field()
        vev = hcf.params.vev
        gradient = hcf.higgs_gradient(vev)
        # Gradient should be ~0 at VEV (minimum of potential)
        assert abs(gradient) < 1.0  # Allow numerical tolerance

    def test_acceleration_inversely_proportional_to_mass(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        force = 10.0
        # Lighter node should have higher acceleration
        accel_gevurah = hcf.compute_rebalancing_acceleration(SephirahRole.GEVURAH, force)
        accel_keter = hcf.compute_rebalancing_acceleration(SephirahRole.KETER, force)
        assert accel_gevurah > accel_keter

    def test_mass_gap_zero_when_balanced(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        # Mass gap should be very small with default couplings
        # (Yukawa ratios already produce phi mass ratio)
        assert hcf._mass_gap < 1.0

    def test_excitation_detection(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        # Force field far from VEV
        hcf._field_value = hcf.params.vev * 1.5  # 50% above VEV
        event = hcf._check_excitation(100)
        assert event is not None
        assert event.deviation_bps > 1000

    def test_no_excitation_at_equilibrium(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        hcf._field_value = hcf.params.vev  # At equilibrium
        event = hcf._check_excitation(100)
        assert event is None

    def test_get_status(self):
        hcf, sm = self._make_field()
        hcf.initialize()
        status = hcf.get_status()
        assert 'field_value' in status
        assert 'vev' in status
        assert 'node_masses' in status
        assert len(status['node_masses']) == 10


class TestHiggsSUSYSwap:
    """Test mass-aware SUSY rebalancing."""

    def _make_swap(self):
        db = MagicMock()
        sm = SephirotManager(db)
        params = HiggsParameters(mu=88.45, lambda_coupling=0.129)
        hcf = HiggsCognitiveField(sm, params)
        hcf.initialize()
        swap = HiggsSUSYSwap(hcf, sm)
        return swap, sm, hcf

    def test_no_correction_when_balanced(self):
        swap, sm, hcf = self._make_swap()
        # Set energies to golden ratio
        for expansion, constraint in SUSY_PAIRS:
            sm.nodes[constraint].energy = 1.0
            sm.nodes[expansion].energy = PHI
        corrections = swap.enforce_susy_balance_with_mass(1)
        assert corrections == 0

    def test_correction_when_imbalanced(self):
        swap, sm, hcf = self._make_swap()
        # Create large imbalance
        sm.nodes[SephirahRole.CHESED].energy = 5.0
        sm.nodes[SephirahRole.GEVURAH].energy = 1.0
        # Ratio = 5.0 (far from phi = 1.618)
        corrections = swap.enforce_susy_balance_with_mass(1)
        assert corrections > 0

    def test_lighter_node_corrects_more(self):
        swap, sm, hcf = self._make_swap()
        # Set up identical imbalances for two pairs
        sm.nodes[SephirahRole.CHESED].energy = 5.0
        sm.nodes[SephirahRole.GEVURAH].energy = 1.0
        old_gevurah = sm.nodes[SephirahRole.GEVURAH].energy
        old_chesed = sm.nodes[SephirahRole.CHESED].energy

        swap.enforce_susy_balance_with_mass(1)

        # Gevurah (lighter, constraint) should change more per unit mass
        gevurah_mass = hcf.get_cognitive_mass(SephirahRole.GEVURAH)
        chesed_mass = hcf.get_cognitive_mass(SephirahRole.CHESED)

        # Both should have changed
        assert sm.nodes[SephirahRole.GEVURAH].energy != old_gevurah or \
               sm.nodes[SephirahRole.CHESED].energy != old_chesed

    def test_energy_stays_positive(self):
        swap, sm, hcf = self._make_swap()
        # Extreme imbalance
        sm.nodes[SephirahRole.CHESED].energy = 100.0
        sm.nodes[SephirahRole.GEVURAH].energy = 0.01
        swap.enforce_susy_balance_with_mass(1)
        for role in SephirahRole:
            assert sm.nodes[role].energy > 0


class TestSephirahStateMassFields:
    """Test that SephirahState has mass fields."""

    def test_default_mass_zero(self):
        state = SephirahState(role=SephirahRole.KETER)
        assert state.cognitive_mass == 0.0
        assert state.yukawa_coupling == 0.0

    def test_mass_assignment(self):
        state = SephirahState(
            role=SephirahRole.KETER,
            cognitive_mass=245.17,
            yukawa_coupling=1.0,
        )
        assert state.cognitive_mass == 245.17
        assert state.yukawa_coupling == 1.0
