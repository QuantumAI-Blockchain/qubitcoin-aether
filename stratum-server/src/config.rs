//! Configuration for the Stratum server, loaded from environment.

use std::env;

/// Stratum server configuration.
#[derive(Debug, Clone)]
pub struct StratumConfig {
    /// WebSocket listen host
    pub host: String,
    /// WebSocket listen port
    pub port: u16,
    /// Maximum concurrent workers
    pub max_workers: usize,
    /// Share difficulty divisor (pool difficulty = network difficulty / divisor)
    pub share_difficulty_divisor: f64,
    /// gRPC address of the Python node bridge
    pub node_grpc_addr: String,
}

impl StratumConfig {
    /// Load configuration from environment variables.
    pub fn from_env() -> Self {
        Self {
            host: env::var("STRATUM_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            port: env::var("STRATUM_PORT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(3333),
            max_workers: env::var("STRATUM_MAX_WORKERS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(100),
            share_difficulty_divisor: env::var("STRATUM_SHARE_DIFFICULTY_DIVISOR")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(16.0),
            node_grpc_addr: env::var("NODE_GRPC_ADDR")
                .unwrap_or_else(|_| "http://127.0.0.1:50053".to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let cfg = StratumConfig::from_env();
        assert_eq!(cfg.port, 3333);
        assert_eq!(cfg.max_workers, 100);
        assert!(cfg.share_difficulty_divisor > 0.0);
    }
}
