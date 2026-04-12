//! Lifecycle phases for the AetherOrchestrator.

use serde::{Deserialize, Serialize};

/// Current lifecycle phase of the orchestrator.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum LifecyclePhase {
    /// Not yet initialized.
    Created,
    /// Startup in progress (loading DB state, seeding genesis).
    Starting,
    /// Fully operational — processing blocks.
    Running,
    /// Graceful shutdown in progress.
    ShuttingDown,
    /// Stopped.
    Stopped,
}

impl Default for LifecyclePhase {
    fn default() -> Self {
        LifecyclePhase::Created
    }
}

impl std::fmt::Display for LifecyclePhase {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LifecyclePhase::Created => write!(f, "created"),
            LifecyclePhase::Starting => write!(f, "starting"),
            LifecyclePhase::Running => write!(f, "running"),
            LifecyclePhase::ShuttingDown => write!(f, "shutting_down"),
            LifecyclePhase::Stopped => write!(f, "stopped"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_phase() {
        assert_eq!(LifecyclePhase::default(), LifecyclePhase::Created);
    }

    #[test]
    fn test_display() {
        assert_eq!(LifecyclePhase::Running.to_string(), "running");
        assert_eq!(LifecyclePhase::ShuttingDown.to_string(), "shutting_down");
    }
}
