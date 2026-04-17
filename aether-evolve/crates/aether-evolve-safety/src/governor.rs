use aether_evolve_core::{AetherMetrics, CodeDiff, EvolveConfig};
use anyhow::{bail, Result};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::Mutex;
use tracing::{info, warn};

pub struct SafetyGovernor {
    config: EvolveConfig,
    api_calls_this_minute: Arc<AtomicU32>,
    code_changes_this_hour: Arc<AtomicU32>,
    minute_start: Arc<Mutex<Instant>>,
    hour_start: Arc<Mutex<Instant>>,
}

impl SafetyGovernor {
    pub fn new(config: EvolveConfig) -> Self {
        Self {
            config,
            api_calls_this_minute: Arc::new(AtomicU32::new(0)),
            code_changes_this_hour: Arc::new(AtomicU32::new(0)),
            minute_start: Arc::new(Mutex::new(Instant::now())),
            hour_start: Arc::new(Mutex::new(Instant::now())),
        }
    }

    /// Check if a code change is allowed.
    pub async fn check_code_change(&self, diffs: &[CodeDiff]) -> Result<()> {
        // Check forbidden files
        for diff in diffs {
            for forbidden in &self.config.safety.forbidden_files {
                if diff.file_path.contains(forbidden) {
                    bail!(
                        "Safety: Cannot modify forbidden file '{}' (contains '{}')",
                        diff.file_path,
                        forbidden
                    );
                }
            }
        }

        // Check rate limit
        self.reset_if_expired().await;
        let changes = self.code_changes_this_hour.load(Ordering::Relaxed);
        if changes >= self.config.safety.max_code_changes_per_hour {
            bail!(
                "Safety: Code change rate limit exceeded ({}/{})",
                changes,
                self.config.safety.max_code_changes_per_hour
            );
        }

        // Check diff count
        if diffs.len() > 3 {
            warn!(
                count = diffs.len(),
                "More than 3 diffs in a single step — proceed with caution"
            );
        }

        Ok(())
    }

    /// Record that a code change was made.
    pub fn record_code_change(&self) {
        self.code_changes_this_hour.fetch_add(1, Ordering::Relaxed);
    }

    /// Check if an API call is allowed (rate limiting).
    pub async fn check_api_call(&self) -> Result<()> {
        self.reset_if_expired().await;
        let calls = self.api_calls_this_minute.load(Ordering::Relaxed);
        if calls >= self.config.safety.max_api_calls_per_minute {
            bail!(
                "Safety: API rate limit exceeded ({}/{})",
                calls,
                self.config.safety.max_api_calls_per_minute
            );
        }
        Ok(())
    }

    /// Record an API call.
    pub fn record_api_call(&self) {
        self.api_calls_this_minute.fetch_add(1, Ordering::Relaxed);
    }

    /// Check if a regression occurred and rollback is needed.
    pub fn should_rollback(&self, pre: &AetherMetrics, post: &AetherMetrics) -> bool {
        let delta_phi = post.phi.hms_phi - pre.phi.hms_phi;
        let threshold = self.config.safety.auto_rollback_threshold;

        if delta_phi < threshold {
            warn!(
                delta_phi,
                threshold, "Regression detected — recommending rollback"
            );
            return true;
        }

        // Also rollback if gates decreased
        if post.gates_passed < pre.gates_passed {
            warn!(
                pre_gates = pre.gates_passed,
                post_gates = post.gates_passed,
                "Gate regression — recommending rollback"
            );
            return true;
        }

        false
    }

    /// Check seed count limit.
    pub fn check_seed_count(&self, count: u32) -> Result<()> {
        if count > self.config.safety.max_seeds_per_step {
            bail!(
                "Safety: Seed count {} exceeds limit {}",
                count,
                self.config.safety.max_seeds_per_step
            );
        }
        Ok(())
    }

    async fn reset_if_expired(&self) {
        let now = Instant::now();

        let mut minute = self.minute_start.lock().await;
        if now.duration_since(*minute).as_secs() >= 60 {
            *minute = now;
            self.api_calls_this_minute.store(0, Ordering::Relaxed);
        }

        let mut hour = self.hour_start.lock().await;
        if now.duration_since(*hour).as_secs() >= 3600 {
            *hour = now;
            self.code_changes_this_hour.store(0, Ordering::Relaxed);
            info!("Safety counters reset");
        }
    }
}
