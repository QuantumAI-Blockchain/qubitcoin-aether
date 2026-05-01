//! Mexican-hat potential, vacuum expectation value, and modified Newtonian dynamics.
//!
//! The Mexican-hat (sombrero) potential is the central mechanism of spontaneous
//! symmetry breaking in the Higgs sector of the Standard Model and in SUGRA:
//!
//! ```text
//! V(phi) = -mu^2 |phi|^2 + lambda |phi|^4
//! ```
//!
//! At the minimum, the field acquires a vacuum expectation value (VEV):
//!
//! ```text
//! VEV = sqrt(mu^2 / (2 * lambda))
//! ```
//!
//! The bimetric extension introduces a Yukawa-type modification to Newtonian
//! gravity, where the massive spin-2 graviton mediates a short-range force
//! with an oscillatory phase structure tied to the Sephirot cognitive geometry.

use libm;

// ---------------------------------------------------------------------------
// Physical and mathematical constants
// ---------------------------------------------------------------------------

/// Newtonian gravitational constant (m^3 kg^-1 s^-2).
pub const G: f64 = 6.6743e-11;

/// Speed of light in vacuum (m/s).
pub const C: f64 = 2.99792458e8;

/// Reduced Planck constant (J*s).
pub const HBAR: f64 = 1.054571817e-34;

/// Electron-volt in joules (J/eV).
pub const EV: f64 = 1.602176634e-19;

/// Golden ratio phi = (1 + sqrt(5)) / 2.
pub const PHI: f64 = 1.618033988749895;

/// Inverse golden ratio phi^-1 = phi - 1.
pub const PHI_INV: f64 = 0.6180339887498949;

/// phi^-2.
pub const PHI_INV_SQ: f64 = 0.3819660112501051;

/// 2 * pi.
pub const TWO_PI: f64 = 6.283185307179586;

/// Golden angle = 2*pi / phi^2 (radians).
/// This is the angle that produces maximal irrational spacing on a circle,
/// identical to the divergence angle in sunflower phyllotaxis.
pub const GOLDEN_ANGLE: f64 = 2.399963229728653;

// ---------------------------------------------------------------------------
// Mexican-hat potential
// ---------------------------------------------------------------------------

/// Evaluate the Mexican-hat (sombrero) potential.
///
/// ```text
/// V(phi) = -mu^2 * |phi|^2 + lambda * |phi|^4
/// ```
///
/// # Arguments
/// * `phi` — Field value (real scalar; we use |phi| = phi for the radial mode).
/// * `mu_sq` — mu^2 parameter controlling the depth of the potential well.
///   Must be positive for symmetry breaking to occur.
/// * `lambda` — Quartic self-coupling. Must be positive for the potential
///   to be bounded from below.
///
/// # Returns
/// The potential energy V(phi).
///
/// # Physics
/// When mu^2 > 0 and lambda > 0, the origin phi = 0 is a local maximum
/// (the "top of the hat"). The minimum forms a circle at |phi| = VEV,
/// spontaneously breaking the U(1) symmetry.
pub fn mexican_hat_potential(phi: f64, mu_sq: f64, lambda: f64) -> f64 {
    let phi_sq = phi * phi;
    -mu_sq * phi_sq + lambda * phi_sq * phi_sq
}

/// Compute the vacuum expectation value (VEV) of the Mexican-hat potential.
///
/// ```text
/// VEV = sqrt(mu^2 / (2 * lambda))
/// ```
///
/// This is the field value at the bottom of the potential well, where
/// dV/d(phi) = 0 and d^2V/d(phi)^2 > 0.
///
/// # Arguments
/// * `mu_sq` — mu^2 parameter (must be > 0).
/// * `lambda` — Quartic coupling (must be > 0).
///
/// # Returns
/// The VEV. Returns 0.0 if either parameter is non-positive (no symmetry breaking).
pub fn vev(mu_sq: f64, lambda: f64) -> f64 {
    if mu_sq <= 0.0 || lambda <= 0.0 {
        return 0.0;
    }
    libm::sqrt(mu_sq / (2.0 * lambda))
}

/// Compute the Compton wavelength of a massive particle.
///
/// ```text
/// lambda_C = hbar / (m' * c)
/// ```
///
/// where m' is the particle mass in eV/c^2 (converted internally to kg).
///
/// # Arguments
/// * `m_prime_ev` — Mass of the massive graviton in eV/c^2.
///
/// # Returns
/// The Compton wavelength in meters. Returns `f64::INFINITY` if mass is zero.
///
/// # Physics
/// The Compton wavelength sets the range of the Yukawa-type force mediated
/// by the massive spin-2 graviton in Hassan-Rosen bimetric gravity.
/// For m' ~ 10^-3 eV, lambda_C ~ 0.2 mm (tabletop gravity experiment range).
pub fn compton_wavelength(m_prime_ev: f64) -> f64 {
    if m_prime_ev == 0.0 {
        return f64::INFINITY;
    }
    let m_kg = m_prime_ev * EV / (C * C);
    HBAR / (m_kg * C)
}

/// Compute the modified gravitational acceleration in bimetric gravity.
///
/// In Hassan-Rosen bimetric gravity, the massive spin-2 mode mediates a
/// Yukawa-type correction to Newtonian gravity:
///
/// ```text
/// a(r) = -G*M/r^2 * [1 + alpha * exp(-r/lambda_C) * cos(theta) * (1 + r/lambda_C)]
/// ```
///
/// # Arguments
/// * `r` — Radial distance from the source mass (meters). Must be > 0.
/// * `m_plate` — Source mass (kg).
/// * `alpha` — Bimetric coupling strength (dimensionless). Encodes the
///   mixing angle between the massless and massive graviton eigenstates.
/// * `theta` — Bimetric phase angle (radians). From the Sephirot phase
///   structure, this determines whether the correction is attractive or
///   repulsive at a given orientation.
/// * `lambda_c` — Compton wavelength of the massive graviton (meters).
///   Sets the range of the correction.
///
/// # Returns
/// The gravitational acceleration (m/s^2, negative = attractive).
/// Returns 0.0 if r <= 0.
///
/// # Physics
/// The cos(theta) factor connects the bimetric graviton mass to the
/// cognitive phase geometry of the Sephirot. The (1 + r/lambda_C) polynomial
/// factor arises from the spin-2 propagator structure (vs spin-0 Yukawa
/// which lacks it). At r >> lambda_C, the correction is exponentially
/// suppressed and we recover standard Newtonian gravity.
pub fn modified_acceleration(
    r: f64,
    m_plate: f64,
    alpha: f64,
    theta: f64,
    lambda_c: f64,
) -> f64 {
    if r <= 0.0 {
        return 0.0;
    }
    let newtonian = -G * m_plate / (r * r);
    let ratio = r / lambda_c;
    let yukawa = alpha * libm::exp(-ratio) * libm::cos(theta) * (1.0 + ratio);
    newtonian * (1.0 + yukawa)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: approximate f64 equality with tolerance.
    fn approx_eq(a: f64, b: f64, tol: f64) -> bool {
        libm::fabs(a - b) < tol
    }

    #[test]
    fn test_mexican_hat_at_origin() {
        // V(0) = 0 regardless of parameters.
        assert_eq!(mexican_hat_potential(0.0, 88.17, 0.129), 0.0);
    }

    #[test]
    fn test_mexican_hat_shape() {
        let mu_sq = 88.17;
        let lambda = 0.129;
        let v = vev(mu_sq, lambda);

        // At VEV, the potential is at its minimum.
        let v_at_vev = mexican_hat_potential(v, mu_sq, lambda);
        let v_at_zero = mexican_hat_potential(0.0, mu_sq, lambda);
        let v_at_large = mexican_hat_potential(v * 2.0, mu_sq, lambda);

        // VEV minimum is below origin.
        assert!(v_at_vev < v_at_zero, "V(VEV) should be < V(0)");
        // Large field values rise above VEV minimum.
        assert!(v_at_large > v_at_vev, "V(2*VEV) should be > V(VEV)");
    }

    #[test]
    fn test_mexican_hat_symmetry() {
        let mu_sq = 88.17;
        let lambda = 0.129;
        // V(phi) = V(-phi) since all terms are even powers.
        let v_pos = mexican_hat_potential(5.0, mu_sq, lambda);
        let v_neg = mexican_hat_potential(-5.0, mu_sq, lambda);
        assert!(approx_eq(v_pos, v_neg, 1e-10));
    }

    #[test]
    fn test_vev_calculation() {
        // QBC Higgs parameters: mu^2 = 88.17, lambda = 0.129
        // VEV = sqrt(88.17 / (2 * 0.129)) = sqrt(341.744...) ~ 18.487...
        let v = vev(88.17, 0.129);
        assert!(
            approx_eq(v, 18.487, 0.01),
            "VEV should be ~18.487, got {}",
            v
        );
    }

    #[test]
    fn test_vev_known_values() {
        // Simple case: mu^2 = 2, lambda = 1 => VEV = sqrt(2/2) = 1.0
        assert!(approx_eq(vev(2.0, 1.0), 1.0, 1e-12));

        // mu^2 = 8, lambda = 1 => VEV = sqrt(8/2) = 2.0
        assert!(approx_eq(vev(8.0, 1.0), 2.0, 1e-12));
    }

    #[test]
    fn test_vev_no_breaking() {
        // Non-positive mu^2 => no symmetry breaking.
        assert_eq!(vev(0.0, 0.129), 0.0);
        assert_eq!(vev(-1.0, 0.129), 0.0);
        // Non-positive lambda => no symmetry breaking.
        assert_eq!(vev(88.17, 0.0), 0.0);
        assert_eq!(vev(88.17, -1.0), 0.0);
    }

    #[test]
    fn test_compton_wavelength_known() {
        // Electron mass: 0.511e6 eV
        // lambda_C = hbar / (m_e * c) = 1.054e-34 / (9.109e-31 * 3e8) ~ 3.86e-13 m
        let lc = compton_wavelength(0.511e6);
        assert!(
            lc > 3.8e-13 && lc < 3.9e-13,
            "Electron Compton wavelength should be ~3.86e-13 m, got {}",
            lc
        );
    }

    #[test]
    fn test_compton_wavelength_zero_mass() {
        assert_eq!(compton_wavelength(0.0), f64::INFINITY);
    }

    #[test]
    fn test_compton_wavelength_inverse_mass() {
        // Heavier particles have shorter Compton wavelengths.
        let lc_light = compton_wavelength(1.0);
        let lc_heavy = compton_wavelength(1000.0);
        assert!(lc_light > lc_heavy);
    }

    #[test]
    fn test_modified_acceleration_newtonian_limit() {
        // When alpha = 0, we recover pure Newtonian gravity.
        let r = 1.0;
        let m = 1.0;
        let a = modified_acceleration(r, m, 0.0, 0.0, 1.0);
        let a_newton = -G * m / (r * r);
        assert!(approx_eq(a, a_newton, 1e-30));
    }

    #[test]
    fn test_modified_acceleration_large_distance() {
        // At r >> lambda_C, the Yukawa correction is exponentially suppressed.
        let lambda_c = 1.0;
        let r = 100.0 * lambda_c; // 100 Compton wavelengths away
        let m = 1.0;
        let a = modified_acceleration(r, m, 1.0, 0.0, lambda_c);
        let a_newton = -G * m / (r * r);
        // Should be very close to Newtonian.
        let relative_diff = libm::fabs((a - a_newton) / a_newton);
        assert!(
            relative_diff < 1e-10,
            "At r >> lambda_C, should recover Newtonian gravity, relative diff = {}",
            relative_diff
        );
    }

    #[test]
    fn test_modified_acceleration_theta_pi_half() {
        // At theta = pi/2, cos(theta) = 0 => no Yukawa correction.
        let a = modified_acceleration(1.0, 1.0, 1.0, core::f64::consts::FRAC_PI_2, 1.0);
        let a_newton = -G / 1.0;
        assert!(approx_eq(a, a_newton, 1e-20));
    }

    #[test]
    fn test_modified_acceleration_zero_r() {
        assert_eq!(modified_acceleration(0.0, 1.0, 1.0, 0.0, 1.0), 0.0);
    }

    #[test]
    fn test_modified_acceleration_repulsive_phase() {
        // At theta = pi, cos(theta) = -1, so with positive alpha the
        // correction reduces the attractive force (or makes it repulsive
        // if alpha is large enough).
        let a_attractive = modified_acceleration(0.5, 1.0, 0.5, 0.0, 1.0);
        let a_repulsive = modified_acceleration(0.5, 1.0, 0.5, core::f64::consts::PI, 1.0);
        // Attractive phase should produce stronger (more negative) acceleration.
        assert!(a_attractive < a_repulsive);
    }

    #[test]
    fn test_constants_consistency() {
        // Golden ratio identity: phi^2 = phi + 1
        assert!(approx_eq(PHI * PHI, PHI + 1.0, 1e-14));
        // phi * phi_inv = 1
        assert!(approx_eq(PHI * PHI_INV, 1.0, 1e-14));
        // phi_inv^2
        assert!(approx_eq(PHI_INV * PHI_INV, PHI_INV_SQ, 1e-14));
        // Golden angle = 2*pi / phi^2
        assert!(approx_eq(GOLDEN_ANGLE, TWO_PI / (PHI * PHI), 1e-12));
    }
}
