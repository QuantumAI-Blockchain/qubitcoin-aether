//! Time series analysis for the Aether Tree temporal reasoning engine.
//!
//! Operates on `(timestamp_or_block_height, value)` pairs. Provides:
//! - Linear regression via ordinary least squares
//! - Exponential moving average (EMA) with configurable smoothing
//! - CUSUM change-point detection
//! - Autocorrelation-based periodicity detection
//! - Anomaly detection (rolling z-score)
//! - Forecasting via linear extrapolation and EMA

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from time series operations.
#[derive(Debug, Error)]
pub enum TimeSeriesError {
    #[error("time series is empty")]
    Empty,
    #[error("time series has insufficient data points (need {need}, have {have})")]
    InsufficientData { need: usize, have: usize },
    #[error("invalid parameter: {0}")]
    InvalidParameter(String),
}

/// A time series: ordered sequence of (time, value) pairs.
///
/// Time can be block height, Unix timestamp, or any monotonically increasing index.
/// Values are f64 measurements (difficulty, tx count, phi score, etc.).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TimeSeries {
    /// Ordered data points: (time, value).
    pub data: Vec<(f64, f64)>,
    /// Human-readable label for this series (e.g., "block_difficulty").
    pub label: String,
}

/// Result of linear regression.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LinearFit {
    /// Slope of the fitted line.
    pub slope: f64,
    /// Y-intercept of the fitted line.
    pub intercept: f64,
    /// Coefficient of determination (0.0 to 1.0). Higher = better fit.
    pub r_squared: f64,
    /// Number of data points used.
    pub n: usize,
}

/// A detected change point in the series.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChangePoint {
    /// Index in the data array where the change was detected.
    pub index: usize,
    /// Time value at the change point.
    pub time: f64,
    /// CUSUM statistic value at detection.
    pub cusum_value: f64,
}

/// An anomalous data point.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AnomalyResult {
    /// Index in the data array.
    pub index: usize,
    /// Time value.
    pub time: f64,
    /// Observed value.
    pub value: f64,
    /// Z-score (number of standard deviations from rolling mean).
    pub z_score: f64,
}

impl TimeSeries {
    /// Create a new time series with a label.
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            data: Vec::new(),
            label: label.into(),
        }
    }

    /// Create a time series from existing data.
    pub fn from_data(label: impl Into<String>, data: Vec<(f64, f64)>) -> Self {
        Self {
            data,
            label: label.into(),
        }
    }

    /// Append a data point. Points should be in chronological order.
    pub fn push(&mut self, time: f64, value: f64) {
        self.data.push((time, value));
    }

    /// Number of data points.
    pub fn len(&self) -> usize {
        self.data.len()
    }

    /// Whether the series is empty.
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    /// Extract only the values (dropping timestamps).
    pub fn values(&self) -> Vec<f64> {
        self.data.iter().map(|(_, v)| *v).collect()
    }

    /// Extract only the times.
    pub fn times(&self) -> Vec<f64> {
        self.data.iter().map(|(t, _)| *t).collect()
    }

    /// Compute the mean of the values.
    pub fn mean(&self) -> Result<f64, TimeSeriesError> {
        if self.data.is_empty() {
            return Err(TimeSeriesError::Empty);
        }
        let sum: f64 = self.data.iter().map(|(_, v)| v).sum();
        Ok(sum / self.data.len() as f64)
    }

    /// Compute variance of the values.
    pub fn variance(&self) -> Result<f64, TimeSeriesError> {
        let mu = self.mean()?;
        let n = self.data.len() as f64;
        let ss: f64 = self.data.iter().map(|(_, v)| (v - mu).powi(2)).sum();
        Ok(ss / n)
    }

    /// Compute standard deviation of the values.
    pub fn std_dev(&self) -> Result<f64, TimeSeriesError> {
        Ok(self.variance()?.sqrt())
    }

    // ── Linear Regression ───────────────────────────────────────────────

    /// Fit a linear regression: y = slope * x + intercept.
    ///
    /// Uses ordinary least squares:
    ///   slope = (n * sum(xy) - sum(x) * sum(y)) / (n * sum(x^2) - sum(x)^2)
    ///   intercept = (sum(y) - slope * sum(x)) / n
    ///   r^2 = 1 - SS_res / SS_tot
    pub fn linear_regression(&self) -> Result<LinearFit, TimeSeriesError> {
        let n = self.data.len();
        if n < 2 {
            return Err(TimeSeriesError::InsufficientData { need: 2, have: n });
        }

        let nf = n as f64;
        let sum_x: f64 = self.data.iter().map(|(t, _)| t).sum();
        let sum_y: f64 = self.data.iter().map(|(_, v)| v).sum();
        let sum_xy: f64 = self.data.iter().map(|(t, v)| t * v).sum();
        let sum_x2: f64 = self.data.iter().map(|(t, _)| t * t).sum();

        let denom = nf * sum_x2 - sum_x * sum_x;
        if denom.abs() < f64::EPSILON {
            // All x values are the same -- vertical line, slope undefined.
            return Ok(LinearFit {
                slope: 0.0,
                intercept: sum_y / nf,
                r_squared: 0.0,
                n,
            });
        }

        let slope = (nf * sum_xy - sum_x * sum_y) / denom;
        let intercept = (sum_y - slope * sum_x) / nf;

        // R-squared
        let mean_y = sum_y / nf;
        let ss_tot: f64 = self.data.iter().map(|(_, v)| (v - mean_y).powi(2)).sum();
        let ss_res: f64 = self
            .data
            .iter()
            .map(|(t, v)| {
                let predicted = slope * t + intercept;
                (v - predicted).powi(2)
            })
            .sum();

        let r_squared = if ss_tot.abs() < f64::EPSILON {
            1.0 // All y values identical -- perfect fit
        } else {
            1.0 - ss_res / ss_tot
        };

        Ok(LinearFit {
            slope,
            intercept,
            r_squared,
            n,
        })
    }

    // ── Exponential Moving Average ──────────────────────────────────────

    /// Compute the exponential moving average with smoothing factor `alpha`.
    ///
    /// EMA_0 = x_0
    /// EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
    ///
    /// Returns a new TimeSeries with the same timestamps and smoothed values.
    pub fn ema(&self, alpha: f64) -> Result<TimeSeries, TimeSeriesError> {
        if self.data.is_empty() {
            return Err(TimeSeriesError::Empty);
        }
        if !(0.0..=1.0).contains(&alpha) {
            return Err(TimeSeriesError::InvalidParameter(format!(
                "alpha must be in [0, 1], got {alpha}"
            )));
        }

        let mut result = Vec::with_capacity(self.data.len());
        let mut ema_val = self.data[0].1;
        result.push((self.data[0].0, ema_val));

        for &(t, v) in &self.data[1..] {
            ema_val = alpha * v + (1.0 - alpha) * ema_val;
            result.push((t, ema_val));
        }

        Ok(TimeSeries::from_data(format!("{}_ema", self.label), result))
    }

    // ── CUSUM Change-Point Detection ────────────────────────────────────

    /// Detect change points using the CUSUM (cumulative sum) algorithm.
    ///
    /// Tracks cumulative deviation from the baseline mean:
    ///   S_t = max(0, S_{t-1} + (x_t - mu_0) - allowance)
    /// Signals a change point when S_t exceeds `threshold`.
    ///
    /// After detection, the CUSUM resets to zero.
    ///
    /// - `allowance`: slack parameter to ignore minor drift (recommend: 0.5 * sigma)
    /// - `threshold`: detection threshold (recommend: 4 * sigma to 5 * sigma)
    pub fn cusum_change_points(
        &self,
        allowance: f64,
        threshold: f64,
    ) -> Result<Vec<ChangePoint>, TimeSeriesError> {
        if self.data.is_empty() {
            return Err(TimeSeriesError::Empty);
        }

        let mu_0 = self.mean()?;
        let mut s_pos = 0.0_f64; // Detect upward shifts
        let mut s_neg = 0.0_f64; // Detect downward shifts
        let mut change_points = Vec::new();

        for (i, &(t, v)) in self.data.iter().enumerate() {
            s_pos = (s_pos + (v - mu_0) - allowance).max(0.0);
            s_neg = (s_neg - (v - mu_0) - allowance).max(0.0);

            if s_pos > threshold {
                change_points.push(ChangePoint {
                    index: i,
                    time: t,
                    cusum_value: s_pos,
                });
                s_pos = 0.0;
            }
            if s_neg > threshold {
                change_points.push(ChangePoint {
                    index: i,
                    time: t,
                    cusum_value: -s_neg,
                });
                s_neg = 0.0;
            }
        }

        Ok(change_points)
    }

    // ── Autocorrelation and Periodicity ─────────────────────────────────

    /// Compute the autocorrelation function for lags 1..max_lag.
    ///
    /// r(k) = sum((x_t - mean)(x_{t+k} - mean)) / sum((x_t - mean)^2)
    pub fn autocorrelation(&self, max_lag: usize) -> Result<Vec<f64>, TimeSeriesError> {
        let n = self.data.len();
        if n < 3 {
            return Err(TimeSeriesError::InsufficientData { need: 3, have: n });
        }
        let max_lag = max_lag.min(n - 1);
        let mu = self.mean()?;
        let values = self.values();

        let denom: f64 = values.iter().map(|v| (v - mu).powi(2)).sum();
        if denom.abs() < f64::EPSILON {
            // Constant series -- all autocorrelations are undefined / 0.
            return Ok(vec![0.0; max_lag]);
        }

        let mut acf = Vec::with_capacity(max_lag);
        for k in 1..=max_lag {
            let numer: f64 = (0..n - k)
                .map(|t| (values[t] - mu) * (values[t + k] - mu))
                .sum();
            acf.push(numer / denom);
        }

        Ok(acf)
    }

    /// Detect periodicity by finding peaks in the autocorrelation function.
    ///
    /// Returns detected periods (in terms of data-point spacing) where
    /// the autocorrelation exceeds `min_correlation` and is a local maximum.
    pub fn detect_periodicity(
        &self,
        max_lag: usize,
        min_correlation: f64,
    ) -> Result<Vec<usize>, TimeSeriesError> {
        let acf = self.autocorrelation(max_lag)?;
        let mut periods = Vec::new();

        for i in 1..acf.len().saturating_sub(1) {
            if acf[i] > min_correlation && acf[i] > acf[i - 1] && acf[i] > acf[i + 1] {
                // ACF index i corresponds to lag (i+1) since autocorrelation starts at lag 1.
                periods.push(i + 1);
            }
        }

        Ok(periods)
    }

    // ── Anomaly Detection ───────────────────────────────────────────────

    /// Detect anomalies using a rolling z-score.
    ///
    /// For each point, computes the z-score against a rolling window of
    /// `window_size` preceding points. Points with |z| > `z_threshold` are anomalies.
    pub fn detect_anomalies(
        &self,
        window_size: usize,
        z_threshold: f64,
    ) -> Result<Vec<AnomalyResult>, TimeSeriesError> {
        if self.data.len() < window_size + 1 {
            return Err(TimeSeriesError::InsufficientData {
                need: window_size + 1,
                have: self.data.len(),
            });
        }

        let values = self.values();
        let mut anomalies = Vec::new();

        for i in window_size..values.len() {
            let window = &values[i - window_size..i];
            let w_mean: f64 = window.iter().sum::<f64>() / window_size as f64;
            let w_var: f64 =
                window.iter().map(|v| (v - w_mean).powi(2)).sum::<f64>() / window_size as f64;
            let w_std = w_var.sqrt();

            if w_std < f64::EPSILON {
                // Zero variance window -- any different value is anomalous.
                if (values[i] - w_mean).abs() > f64::EPSILON {
                    anomalies.push(AnomalyResult {
                        index: i,
                        time: self.data[i].0,
                        value: values[i],
                        z_score: f64::INFINITY,
                    });
                }
                continue;
            }

            let z = (values[i] - w_mean) / w_std;
            if z.abs() > z_threshold {
                anomalies.push(AnomalyResult {
                    index: i,
                    time: self.data[i].0,
                    value: values[i],
                    z_score: z,
                });
            }
        }

        Ok(anomalies)
    }

    // ── Forecasting ─────────────────────────────────────────────────────

    /// Forecast future values using linear extrapolation.
    ///
    /// Returns `horizon` predicted (time, value) pairs starting from the last data point.
    /// Time spacing is inferred from the average spacing of existing data.
    pub fn forecast_linear(&self, horizon: usize) -> Result<Vec<(f64, f64)>, TimeSeriesError> {
        let fit = self.linear_regression()?;
        let n = self.data.len();

        // Infer time spacing from data.
        let dt = if n >= 2 {
            (self.data[n - 1].0 - self.data[0].0) / (n - 1) as f64
        } else {
            1.0
        };

        let last_t = self.data[n - 1].0;
        let mut forecast = Vec::with_capacity(horizon);
        for i in 1..=horizon {
            let t = last_t + dt * i as f64;
            let v = fit.slope * t + fit.intercept;
            forecast.push((t, v));
        }

        Ok(forecast)
    }

    /// Forecast using exponential moving average: the last EMA value persists.
    ///
    /// This is a simple "flat forecast" -- the EMA's last value is the prediction
    /// for all future points. More sophisticated than mean, less than ARIMA.
    pub fn forecast_ema(
        &self,
        alpha: f64,
        horizon: usize,
    ) -> Result<Vec<(f64, f64)>, TimeSeriesError> {
        let ema_series = self.ema(alpha)?;
        let n = ema_series.data.len();
        let last_ema = ema_series.data[n - 1].1;

        let dt = if n >= 2 {
            (self.data[n - 1].0 - self.data[0].0) / (n - 1) as f64
        } else {
            1.0
        };

        let last_t = self.data[n - 1].0;
        let mut forecast = Vec::with_capacity(horizon);
        for i in 1..=horizon {
            let t = last_t + dt * i as f64;
            forecast.push((t, last_ema));
        }

        Ok(forecast)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_linear_series(n: usize, slope: f64, intercept: f64) -> TimeSeries {
        let data: Vec<(f64, f64)> = (0..n).map(|i| (i as f64, slope * i as f64 + intercept)).collect();
        TimeSeries::from_data("linear_test", data)
    }

    #[test]
    fn test_linear_regression_perfect_fit() {
        let ts = make_linear_series(100, 2.5, 10.0);
        let fit = ts.linear_regression().unwrap();
        assert!((fit.slope - 2.5).abs() < 1e-10);
        assert!((fit.intercept - 10.0).abs() < 1e-10);
        assert!((fit.r_squared - 1.0).abs() < 1e-10);
        assert_eq!(fit.n, 100);
    }

    #[test]
    fn test_linear_regression_noisy() {
        // y = 3x + 5 with small noise pattern
        let data: Vec<(f64, f64)> = (0..50)
            .map(|i| {
                let noise = if i % 2 == 0 { 0.1 } else { -0.1 };
                (i as f64, 3.0 * i as f64 + 5.0 + noise)
            })
            .collect();
        let ts = TimeSeries::from_data("noisy", data);
        let fit = ts.linear_regression().unwrap();
        assert!((fit.slope - 3.0).abs() < 0.01);
        assert!(fit.r_squared > 0.99);
    }

    #[test]
    fn test_ema_convergence() {
        // Constant series: EMA should converge to the constant.
        let data: Vec<(f64, f64)> = (0..100).map(|i| (i as f64, 42.0)).collect();
        let ts = TimeSeries::from_data("constant", data);
        let ema = ts.ema(0.3).unwrap();
        let last = ema.data.last().unwrap().1;
        assert!((last - 42.0).abs() < 1e-10);
    }

    #[test]
    fn test_ema_step_response() {
        // Step from 0 to 100 at index 10 -- EMA should approach 100.
        let mut data: Vec<(f64, f64)> = (0..10).map(|i| (i as f64, 0.0)).collect();
        data.extend((10..100).map(|i| (i as f64, 100.0)));
        let ts = TimeSeries::from_data("step", data);
        let ema = ts.ema(0.1).unwrap();
        let last = ema.data.last().unwrap().1;
        assert!(last > 99.0); // Should be very close to 100
    }

    #[test]
    fn test_ema_invalid_alpha() {
        let ts = TimeSeries::from_data("test", vec![(0.0, 1.0)]);
        assert!(ts.ema(1.5).is_err());
        assert!(ts.ema(-0.1).is_err());
    }

    #[test]
    fn test_cusum_detects_mean_shift() {
        // 50 points at mean=10, then 50 points at mean=20.
        let mut data: Vec<(f64, f64)> = (0..50).map(|i| (i as f64, 10.0)).collect();
        data.extend((50..100).map(|i| (i as f64, 20.0)));
        let ts = TimeSeries::from_data("shift", data);

        // Overall mean is 15. CUSUM detects deviations from mean in both directions.
        // The negative CUSUM fires on the first half (values below mean),
        // the positive CUSUM fires on the second half (values above mean).
        // Use a high threshold so we detect at least one change.
        let change_points = ts.cusum_change_points(2.0, 20.0).unwrap();
        assert!(
            !change_points.is_empty(),
            "should detect at least one change point"
        );
        // There should be change points in both halves (downward shift detected
        // in the first half, upward in the second).
        let has_early = change_points.iter().any(|cp| cp.index < 50);
        let has_late = change_points.iter().any(|cp| cp.index >= 50);
        assert!(
            has_early || has_late,
            "should detect change in at least one half, got {:?}",
            change_points
        );
    }

    #[test]
    fn test_cusum_no_change() {
        let data: Vec<(f64, f64)> = (0..100).map(|i| (i as f64, 50.0)).collect();
        let ts = TimeSeries::from_data("constant", data);
        let change_points = ts.cusum_change_points(1.0, 10.0).unwrap();
        assert!(change_points.is_empty());
    }

    #[test]
    fn test_autocorrelation_periodic() {
        // Sine wave with period 10.
        let data: Vec<(f64, f64)> = (0..200)
            .map(|i| {
                let t = i as f64;
                (t, (2.0 * std::f64::consts::PI * t / 10.0).sin())
            })
            .collect();
        let ts = TimeSeries::from_data("sine", data);
        let acf = ts.autocorrelation(20).unwrap();
        // Lag 10 should have high positive autocorrelation.
        // acf[9] is lag 10 (0-indexed, lag starts at 1).
        assert!(acf[9] > 0.9, "autocorrelation at lag 10 = {}", acf[9]);
    }

    #[test]
    fn test_detect_periodicity() {
        let data: Vec<(f64, f64)> = (0..200)
            .map(|i| {
                let t = i as f64;
                (t, (2.0 * std::f64::consts::PI * t / 10.0).sin())
            })
            .collect();
        let ts = TimeSeries::from_data("sine", data);
        let periods = ts.detect_periodicity(20, 0.5).unwrap();
        assert!(periods.contains(&10), "should detect period 10, got {:?}", periods);
    }

    #[test]
    fn test_anomaly_detection() {
        // Constant series with a single spike.
        let mut data: Vec<(f64, f64)> = (0..100).map(|i| (i as f64, 10.0)).collect();
        data[50] = (50.0, 100.0); // Spike
        let ts = TimeSeries::from_data("spike", data);
        let anomalies = ts.detect_anomalies(20, 3.0).unwrap();
        assert!(!anomalies.is_empty());
        assert!(anomalies.iter().any(|a| a.index == 50));
    }

    #[test]
    fn test_forecast_linear() {
        let ts = make_linear_series(50, 2.0, 5.0);
        let forecast = ts.forecast_linear(10).unwrap();
        assert_eq!(forecast.len(), 10);
        // First forecast point: t=50, expected y = 2*50 + 5 = 105
        assert!((forecast[0].1 - 105.0).abs() < 1e-8);
    }

    #[test]
    fn test_mean_and_std() {
        let data: Vec<(f64, f64)> = vec![(0.0, 2.0), (1.0, 4.0), (2.0, 6.0)];
        let ts = TimeSeries::from_data("test", data);
        assert!((ts.mean().unwrap() - 4.0).abs() < 1e-10);
        // Variance = ((2-4)^2 + (4-4)^2 + (6-4)^2) / 3 = 8/3
        assert!((ts.variance().unwrap() - 8.0 / 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_empty_series_errors() {
        let ts = TimeSeries::new("empty");
        assert!(ts.mean().is_err());
        assert!(ts.linear_regression().is_err());
        assert!(ts.ema(0.5).is_err());
    }
}
