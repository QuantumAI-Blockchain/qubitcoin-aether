//! aether-temporal: Temporal reasoning engine for the Aether Tree AI.
//!
//! Provides real temporal reasoning capabilities:
//!
//! - **Time series analysis**: Linear regression, EMA, change-point detection (CUSUM),
//!   periodicity detection via autocorrelation, anomaly detection, and forecasting.
//! - **Linear Temporal Logic (LTL)**: Bounded model checking over finite traces,
//!   pattern extraction (invariants, eventually, until, next patterns).
//! - **Prediction engine**: Multi-method prediction with verification and accuracy tracking.
//!   Methods compete on historical accuracy; confidence is calibrated against track record.
//! - **Granger causality**: Tests whether one time series provides statistically significant
//!   information about future values of another, using F-test on restricted vs unrestricted
//!   autoregressive models.
//!
//! These modules give the Aether Tree genuine temporal reasoning -- the ability to detect
//! causal time-dependencies, verify predictions against reality, and enforce temporal
//! invariants across knowledge evolution.

pub mod granger;
pub mod prediction;
pub mod temporal_logic;
pub mod time_series;

pub use granger::{bidirectional_granger, granger_test, CausalDirection, GrangerResult};
pub use prediction::{
    AccuracyTracker, Prediction, PredictionEngine, PredictionMethod, PredictionStatus,
    VerificationResult,
};
pub use temporal_logic::{extract_patterns, model_check, TLFormula};
pub use time_series::{AnomalyResult, ChangePoint, LinearFit, TimeSeries};
