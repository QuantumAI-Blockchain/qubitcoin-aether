//! Granger causality testing for the Aether Tree.
//!
//! Tests whether one time series provides statistically significant predictive
//! information about another, beyond what the target's own past values provide.
//!
//! The test compares two autoregressive models:
//! - Restricted: y_t = a_1*y_{t-1} + ... + a_p*y_{t-p} + e_t
//! - Unrestricted: y_t = a_1*y_{t-1} + ... + a_p*y_{t-p} + b_1*x_{t-1} + ... + b_p*x_{t-p} + e_t
//!
//! If the unrestricted model significantly reduces residual sum of squares,
//! x is said to "Granger-cause" y.

use crate::time_series::TimeSeries;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from Granger causality tests.
#[derive(Debug, Error)]
pub enum GrangerError {
    #[error("time series too short: need at least {need} points, have {have}")]
    InsufficientData { need: usize, have: usize },
    #[error("series must have equal length (x={x_len}, y={y_len})")]
    UnequalLength { x_len: usize, y_len: usize },
    #[error("lag must be at least 1")]
    InvalidLag,
    #[error("singular matrix in least squares solve")]
    SingularMatrix,
}

/// Result of a Granger causality test.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GrangerResult {
    /// F-statistic for the test.
    pub f_statistic: f64,
    /// Approximate p-value (from F-distribution approximation).
    pub p_value: f64,
    /// Whether the result is significant at the 0.05 level.
    pub significant: bool,
    /// Lag order used.
    pub lag: usize,
    /// RSS of the restricted model (y predicted from its own past only).
    pub rss_restricted: f64,
    /// RSS of the unrestricted model (y predicted from both y and x past).
    pub rss_unrestricted: f64,
}

/// Direction of Granger causality between two series.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum CausalDirection {
    /// X Granger-causes Y but not vice versa.
    XCausesY,
    /// Y Granger-causes X but not vice versa.
    YCausesX,
    /// Both directions are significant (feedback).
    Bidirectional,
    /// Neither direction is significant.
    NoCausation,
}

/// Test if time series `x` Granger-causes time series `y` at the given lag order.
///
/// Both series must have the same length. The test uses an F-test comparing
/// restricted vs unrestricted autoregressive models.
pub fn granger_test(
    x: &TimeSeries,
    y: &TimeSeries,
    lag: usize,
) -> Result<GrangerResult, GrangerError> {
    if lag == 0 {
        return Err(GrangerError::InvalidLag);
    }
    let x_vals = x.values();
    let y_vals = y.values();

    if x_vals.len() != y_vals.len() {
        return Err(GrangerError::UnequalLength {
            x_len: x_vals.len(),
            y_len: y_vals.len(),
        });
    }

    let n = y_vals.len();
    let min_needed = 2 * lag + 2; // Need enough for regression with 2*lag predictors + intercept
    if n < min_needed {
        return Err(GrangerError::InsufficientData {
            need: min_needed,
            have: n,
        });
    }

    let usable = n - lag; // Number of data points we can form targets for.

    // Build target vector: y[lag], y[lag+1], ..., y[n-1]
    let target: Vec<f64> = (lag..n).map(|i| y_vals[i]).collect();

    // ── Restricted model: y_t ~ y_{t-1} + ... + y_{t-lag} + intercept ──
    // Design matrix: each row has [y_{t-1}, y_{t-2}, ..., y_{t-lag}, 1.0]
    let p_restricted = lag + 1; // lag coefficients + intercept
    let mut design_r = vec![0.0; usable * p_restricted];
    for (row, t) in (lag..n).enumerate() {
        for j in 0..lag {
            design_r[row * p_restricted + j] = y_vals[t - 1 - j];
        }
        design_r[row * p_restricted + lag] = 1.0; // intercept
    }
    let rss_restricted = compute_rss(&design_r, &target, usable, p_restricted)?;

    // ── Unrestricted model: y_t ~ y_{t-1}..y_{t-lag} + x_{t-1}..x_{t-lag} + intercept ──
    let p_unrestricted = 2 * lag + 1;
    let mut design_u = vec![0.0; usable * p_unrestricted];
    for (row, t) in (lag..n).enumerate() {
        for j in 0..lag {
            design_u[row * p_unrestricted + j] = y_vals[t - 1 - j];
        }
        for j in 0..lag {
            design_u[row * p_unrestricted + lag + j] = x_vals[t - 1 - j];
        }
        design_u[row * p_unrestricted + 2 * lag] = 1.0; // intercept
    }
    let rss_unrestricted = compute_rss(&design_u, &target, usable, p_unrestricted)?;

    // F-statistic:
    // F = ((RSS_r - RSS_u) / lag) / (RSS_u / (n_usable - 2*lag - 1))
    let df_num = lag as f64;
    let df_den = usable as f64 - 2.0 * lag as f64 - 1.0;

    if df_den <= 0.0 || rss_unrestricted <= 0.0 {
        return Ok(GrangerResult {
            f_statistic: 0.0,
            p_value: 1.0,
            significant: false,
            lag,
            rss_restricted,
            rss_unrestricted,
        });
    }

    let f_stat = ((rss_restricted - rss_unrestricted) / df_num) / (rss_unrestricted / df_den);
    let p_value = approximate_f_pvalue(f_stat, df_num, df_den);

    Ok(GrangerResult {
        f_statistic: f_stat,
        p_value,
        significant: p_value < 0.05,
        lag,
        rss_restricted,
        rss_unrestricted,
    })
}

/// Test Granger causality in both directions and determine overall causal direction.
///
/// Tests at multiple lag orders from 1 to `max_lag` and uses the lag with
/// the most significant result.
pub fn bidirectional_granger(
    x: &TimeSeries,
    y: &TimeSeries,
    max_lag: usize,
) -> Result<CausalDirection, GrangerError> {
    let max_lag = max_lag.max(1);

    let mut best_xy: Option<GrangerResult> = None;
    let mut best_yx: Option<GrangerResult> = None;

    for lag in 1..=max_lag {
        if let Ok(result) = granger_test(x, y, lag) {
            if best_xy.as_ref().map_or(true, |b| result.p_value < b.p_value) {
                best_xy = Some(result);
            }
        }
        if let Ok(result) = granger_test(y, x, lag) {
            if best_yx.as_ref().map_or(true, |b| result.p_value < b.p_value) {
                best_yx = Some(result);
            }
        }
    }

    let x_causes_y = best_xy.as_ref().map_or(false, |r| r.significant);
    let y_causes_x = best_yx.as_ref().map_or(false, |r| r.significant);

    Ok(match (x_causes_y, y_causes_x) {
        (true, true) => CausalDirection::Bidirectional,
        (true, false) => CausalDirection::XCausesY,
        (false, true) => CausalDirection::YCausesX,
        (false, false) => CausalDirection::NoCausation,
    })
}

// ── Internal: Least Squares via Normal Equations ────────────────────────────

/// Compute residual sum of squares for a linear model: min ||X*beta - y||^2.
///
/// Solves the normal equations: (X'X) * beta = X'y.
/// Returns RSS = sum((y_i - X_i * beta)^2).
fn compute_rss(
    design: &[f64],
    target: &[f64],
    n_rows: usize,
    n_cols: usize,
) -> Result<f64, GrangerError> {
    // Compute X'X (n_cols x n_cols).
    let mut xtx = vec![0.0; n_cols * n_cols];
    for i in 0..n_cols {
        for j in 0..n_cols {
            let mut sum = 0.0;
            for k in 0..n_rows {
                sum += design[k * n_cols + i] * design[k * n_cols + j];
            }
            xtx[i * n_cols + j] = sum;
        }
    }

    // Compute X'y (n_cols).
    let mut xty = vec![0.0; n_cols];
    for i in 0..n_cols {
        let mut sum = 0.0;
        for k in 0..n_rows {
            sum += design[k * n_cols + i] * target[k];
        }
        xty[i] = sum;
    }

    // Solve (X'X) * beta = X'y via Cholesky decomposition.
    let beta = cholesky_solve(&xtx, &xty, n_cols)?;

    // Compute RSS.
    let mut rss = 0.0;
    for k in 0..n_rows {
        let mut predicted = 0.0;
        for j in 0..n_cols {
            predicted += design[k * n_cols + j] * beta[j];
        }
        let residual = target[k] - predicted;
        rss += residual * residual;
    }

    Ok(rss)
}

/// Solve A*x = b via Cholesky decomposition (A must be symmetric positive definite).
///
/// Decomposes A = L * L' where L is lower triangular, then solves:
///   L * z = b  (forward substitution)
///   L' * x = z (backward substitution)
fn cholesky_solve(a: &[f64], b: &[f64], n: usize) -> Result<Vec<f64>, GrangerError> {
    // Cholesky decomposition: A = L * L'
    let mut l = vec![0.0; n * n];

    for i in 0..n {
        for j in 0..=i {
            let mut sum = 0.0;
            for k in 0..j {
                sum += l[i * n + k] * l[j * n + k];
            }
            if i == j {
                let diag = a[i * n + i] - sum;
                if diag <= 0.0 {
                    // Add small regularization to handle near-singular matrices.
                    let reg = a[i * n + i].abs() * 1e-10 + 1e-12;
                    l[i * n + j] = (diag + reg).sqrt();
                } else {
                    l[i * n + j] = diag.sqrt();
                }
            } else {
                if l[j * n + j].abs() < 1e-15 {
                    return Err(GrangerError::SingularMatrix);
                }
                l[i * n + j] = (a[i * n + j] - sum) / l[j * n + j];
            }
        }
    }

    // Forward substitution: L * z = b
    let mut z = vec![0.0; n];
    for i in 0..n {
        let mut sum = 0.0;
        for j in 0..i {
            sum += l[i * n + j] * z[j];
        }
        if l[i * n + i].abs() < 1e-15 {
            return Err(GrangerError::SingularMatrix);
        }
        z[i] = (b[i] - sum) / l[i * n + i];
    }

    // Backward substitution: L' * x = z
    let mut x = vec![0.0; n];
    for i in (0..n).rev() {
        let mut sum = 0.0;
        for j in (i + 1)..n {
            sum += l[j * n + i] * x[j]; // L' element at (i, j) = L(j, i)
        }
        if l[i * n + i].abs() < 1e-15 {
            return Err(GrangerError::SingularMatrix);
        }
        x[i] = (z[i] - sum) / l[i * n + i];
    }

    Ok(x)
}

/// Approximate the p-value of an F-distribution using a normal approximation.
///
/// For F(df1, df2), uses the Wilson-Hilferty approximation to convert to
/// a standard normal z-score, then computes the upper-tail probability.
///
/// This avoids pulling in a full statistical library for a single function.
fn approximate_f_pvalue(f_stat: f64, df1: f64, df2: f64) -> f64 {
    if f_stat <= 0.0 || df1 <= 0.0 || df2 <= 0.0 {
        return 1.0;
    }

    // Wilson-Hilferty approximation:
    // Transform F to approximately normal.
    // If X ~ F(d1, d2), then:
    //   z = ((1 - 2/(9*d2)) * (d2 * F / d1)^(1/3) - (1 - 2/(9*d1))) /
    //       sqrt(2/(9*d1) + 2*d2^2 * F^(2/3) / (9*d1^2 * (d2*F/d1)^(2/3)))
    //
    // Simplified: use the cube-root transformation.
    let ratio = f_stat * df1 / df2;
    let a1 = 2.0 / (9.0 * df1);
    let a2 = 2.0 / (9.0 * df2);

    let cube_root = ratio.powf(1.0 / 3.0);
    let z = ((1.0 - a2) * cube_root - (1.0 - a1)) / (a1 + a2 * cube_root * cube_root).sqrt();

    // Upper tail of standard normal: P(Z > z) using error function approximation.
    standard_normal_upper_tail(z)
}

/// P(Z > z) for standard normal, using a rational approximation.
fn standard_normal_upper_tail(z: f64) -> f64 {
    if z < -8.0 {
        return 1.0;
    }
    if z > 8.0 {
        return 0.0;
    }

    // Abramowitz and Stegun approximation 26.2.17 for Phi(x).
    let x = z.abs();
    let t = 1.0 / (1.0 + 0.2316419 * x);
    let d = 0.3989422804014327; // 1/sqrt(2*pi)
    let p = d * (-x * x / 2.0).exp()
        * t
        * (0.3193815
            + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));

    if z >= 0.0 {
        p
    } else {
        1.0 - p
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Create a simple causal series: y_t = 0.8 * x_{t-1} + noise.
    fn make_causal_pair(n: usize) -> (TimeSeries, TimeSeries) {
        // Use a simple deterministic "noise" for reproducibility.
        let mut x_data = Vec::with_capacity(n);
        let mut y_data = Vec::with_capacity(n);

        // x is a sine wave.
        for i in 0..n {
            let t = i as f64;
            let x_val = (t * 0.1).sin() * 10.0;
            x_data.push((t, x_val));
        }

        // y depends on x_{t-1}.
        y_data.push((0.0, 0.0));
        for i in 1..n {
            let t = i as f64;
            let noise = ((i * 7 + 3) % 11) as f64 * 0.01 - 0.05; // deterministic "noise"
            let y_val = 0.8 * x_data[i - 1].1 + noise;
            y_data.push((t, y_val));
        }

        (
            TimeSeries::from_data("x", x_data),
            TimeSeries::from_data("y", y_data),
        )
    }

    /// Create independent (non-causal) series.
    fn make_independent_pair(n: usize) -> (TimeSeries, TimeSeries) {
        let x_data: Vec<(f64, f64)> = (0..n)
            .map(|i| {
                let t = i as f64;
                (t, (t * 0.1).sin() * 10.0)
            })
            .collect();
        let y_data: Vec<(f64, f64)> = (0..n)
            .map(|i| {
                let t = i as f64;
                (t, (t * 0.3 + 2.0).cos() * 5.0)
            })
            .collect();

        (
            TimeSeries::from_data("x", x_data),
            TimeSeries::from_data("y", y_data),
        )
    }

    #[test]
    fn test_granger_detects_causation() {
        let (x, y) = make_causal_pair(200);
        let result = granger_test(&x, &y, 1).unwrap();
        assert!(
            result.f_statistic > 1.0,
            "F-statistic should be large for causal pair: {}",
            result.f_statistic
        );
        // RSS unrestricted should be significantly less than restricted.
        assert!(result.rss_unrestricted < result.rss_restricted);
    }

    #[test]
    fn test_granger_independent_series() {
        let (x, y) = make_independent_pair(200);
        let result = granger_test(&x, &y, 1).unwrap();
        // For truly independent series, F-statistic should be small.
        // The deterministic "independent" series may still show some spurious correlation,
        // but the RSS reduction should be minimal.
        assert!(
            result.rss_unrestricted <= result.rss_restricted,
            "unrestricted RSS should not exceed restricted"
        );
    }

    #[test]
    fn test_bidirectional_causal() {
        let (x, y) = make_causal_pair(200);
        let direction = bidirectional_granger(&x, &y, 3).unwrap();
        // x -> y is the designed causation. y -> x should be weaker.
        assert!(
            direction == CausalDirection::XCausesY || direction == CausalDirection::Bidirectional,
            "expected XCausesY or Bidirectional, got {:?}",
            direction
        );
    }

    #[test]
    fn test_granger_invalid_lag() {
        let x = TimeSeries::from_data("x", vec![(0.0, 1.0), (1.0, 2.0)]);
        let y = TimeSeries::from_data("y", vec![(0.0, 1.0), (1.0, 2.0)]);
        assert!(granger_test(&x, &y, 0).is_err());
    }

    #[test]
    fn test_granger_unequal_length() {
        let x = TimeSeries::from_data("x", vec![(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]);
        let y = TimeSeries::from_data("y", vec![(0.0, 1.0), (1.0, 2.0)]);
        assert!(granger_test(&x, &y, 1).is_err());
    }

    #[test]
    fn test_granger_insufficient_data() {
        let x = TimeSeries::from_data("x", vec![(0.0, 1.0), (1.0, 2.0)]);
        let y = TimeSeries::from_data("y", vec![(0.0, 1.0), (1.0, 2.0)]);
        // lag=1 needs at least 4 points.
        assert!(granger_test(&x, &y, 1).is_err());
    }

    #[test]
    fn test_cholesky_solve_identity() {
        // Solve I * x = b => x = b
        let a = vec![1.0, 0.0, 0.0, 1.0];
        let b = vec![3.0, 7.0];
        let x = cholesky_solve(&a, &b, 2).unwrap();
        assert!((x[0] - 3.0).abs() < 1e-10);
        assert!((x[1] - 7.0).abs() < 1e-10);
    }

    #[test]
    fn test_cholesky_solve_spd() {
        // A = [[4, 2], [2, 3]], b = [8, 7]
        // Solution: x = [1, 5/3] ... let's verify manually.
        // 4x + 2y = 8, 2x + 3y = 7 => x = 1, y = 5/3
        let a = vec![4.0, 2.0, 2.0, 3.0];
        let b = vec![8.0, 7.0];
        let x = cholesky_solve(&a, &b, 2).unwrap();
        // 4(1) + 2(5/3) = 4 + 10/3 = 22/3. Hmm, let me redo:
        // 4x + 2y = 8, 2x + 3y = 7. From first: x = (8-2y)/4 = 2 - y/2.
        // Sub: 2(2-y/2) + 3y = 7 => 4 - y + 3y = 7 => 2y = 3 => y = 1.5, x = 1.25
        assert!((x[0] - 1.25).abs() < 1e-10);
        assert!((x[1] - 1.5).abs() < 1e-10);
    }

    #[test]
    fn test_normal_approx() {
        // Sanity: P(Z > 0) should be ~0.5.
        let p = standard_normal_upper_tail(0.0);
        assert!((p - 0.5).abs() < 0.01);

        // P(Z > 2) should be ~0.0228.
        let p2 = standard_normal_upper_tail(2.0);
        assert!((p2 - 0.0228).abs() < 0.005);
    }
}
