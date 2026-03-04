//! JSON mining protocol message parsing and serialization.
//!
//! Implements a simplified Stratum-like protocol adapted for VQE mining.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Incoming message from a miner.
#[derive(Debug, Clone, Deserialize)]
pub struct StratumRequest {
    pub id: Option<Value>,
    pub method: String,
    #[serde(default)]
    pub params: Vec<Value>,
}

/// Outgoing response to a miner.
#[derive(Debug, Clone, Serialize)]
pub struct StratumResponse {
    pub id: Option<Value>,
    pub result: Value,
    pub error: Option<StratumError>,
}

/// Server-initiated notification (no id).
#[derive(Debug, Clone, Serialize)]
pub struct StratumNotification {
    pub id: Option<Value>,
    pub method: String,
    pub params: Vec<Value>,
}

/// Stratum error.
#[derive(Debug, Clone, Serialize)]
pub struct StratumError {
    pub code: i32,
    pub message: String,
}

/// Parsed mining message type.
#[derive(Debug, Clone)]
pub enum MiningMessage {
    Subscribe { id: Value },
    Authorize { id: Value, worker_name: String, address: String },
    Submit { id: Value, worker_name: String, job_id: String, vqe_params: Vec<f64>, energy: f64, nonce: u64 },
    Unknown { id: Option<Value>, method: String },
}

impl MiningMessage {
    /// Parse a raw JSON string into a mining message.
    pub fn parse(text: &str) -> Result<Self, serde_json::Error> {
        let req: StratumRequest = serde_json::from_str(text)?;
        let id = req.id.unwrap_or(Value::Null);

        match req.method.as_str() {
            "mining.subscribe" => Ok(MiningMessage::Subscribe { id }),
            "mining.authorize" => {
                let worker_name = req.params.first()
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let address = req.params.get(1)
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                Ok(MiningMessage::Authorize { id, worker_name, address })
            }
            "mining.submit" => {
                let worker_name = req.params.first()
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let job_id = req.params.get(1)
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let vqe_params: Vec<f64> = req.params.get(2)
                    .and_then(|v| v.as_array())
                    .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
                    .unwrap_or_default();
                let energy = req.params.get(3)
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let nonce = req.params.get(4)
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                Ok(MiningMessage::Submit { id, worker_name, job_id, vqe_params, energy, nonce })
            }
            _ => Ok(MiningMessage::Unknown { id: Some(id), method: req.method }),
        }
    }
}

/// Create a subscribe response.
pub fn subscribe_response(id: Value, worker_id: &str) -> String {
    let resp = StratumResponse {
        id: Some(id),
        result: serde_json::json!([worker_id, "00000000"]),
        error: None,
    };
    serde_json::to_string(&resp).unwrap_or_default()
}

/// Create an authorize response.
pub fn authorize_response(id: Value, success: bool) -> String {
    let resp = StratumResponse {
        id: Some(id),
        result: Value::Bool(success),
        error: if success { None } else {
            Some(StratumError { code: 24, message: "Unauthorized".to_string() })
        },
    };
    serde_json::to_string(&resp).unwrap_or_default()
}

/// Create a submit response.
pub fn submit_response(id: Value, accepted: bool, reason: &str) -> String {
    let resp = StratumResponse {
        id: Some(id),
        result: Value::Bool(accepted),
        error: if accepted { None } else {
            Some(StratumError { code: 23, message: reason.to_string() })
        },
    };
    serde_json::to_string(&resp).unwrap_or_default()
}

/// Create a mining.notify notification.
pub fn notify_work(job_id: &str, prev_hash: &str, height: u64,
                   difficulty: f64, hamiltonian_seed: &str, clean_jobs: bool) -> String {
    let notif = StratumNotification {
        id: None,
        method: "mining.notify".to_string(),
        params: vec![
            Value::String(job_id.to_string()),
            Value::String(prev_hash.to_string()),
            serde_json::json!(height),
            serde_json::json!(difficulty),
            Value::String(hamiltonian_seed.to_string()),
            Value::Bool(clean_jobs),
        ],
    };
    serde_json::to_string(&notif).unwrap_or_default()
}

/// Create a mining.set_difficulty notification.
pub fn set_difficulty(difficulty: f64) -> String {
    let notif = StratumNotification {
        id: None,
        method: "mining.set_difficulty".to_string(),
        params: vec![serde_json::json!(difficulty)],
    };
    serde_json::to_string(&notif).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_subscribe() {
        let msg = r#"{"id": 1, "method": "mining.subscribe", "params": []}"#;
        let parsed = MiningMessage::parse(msg).unwrap();
        assert!(matches!(parsed, MiningMessage::Subscribe { .. }));
    }

    #[test]
    fn test_parse_authorize() {
        let msg = r#"{"id": 2, "method": "mining.authorize", "params": ["worker1", "qbc1addr"]}"#;
        let parsed = MiningMessage::parse(msg).unwrap();
        match parsed {
            MiningMessage::Authorize { worker_name, address, .. } => {
                assert_eq!(worker_name, "worker1");
                assert_eq!(address, "qbc1addr");
            }
            _ => panic!("Expected Authorize"),
        }
    }

    #[test]
    fn test_parse_submit() {
        let msg = r#"{"id": 3, "method": "mining.submit", "params": ["w1", "job1", [0.1, 0.2], -1.5, 42]}"#;
        let parsed = MiningMessage::parse(msg).unwrap();
        match parsed {
            MiningMessage::Submit { job_id, vqe_params, energy, nonce, .. } => {
                assert_eq!(job_id, "job1");
                assert_eq!(vqe_params, vec![0.1, 0.2]);
                assert_eq!(energy, -1.5);
                assert_eq!(nonce, 42);
            }
            _ => panic!("Expected Submit"),
        }
    }

    #[test]
    fn test_subscribe_response() {
        let resp = subscribe_response(Value::Number(1.into()), "worker-id-1");
        assert!(resp.contains("worker-id-1"));
    }

    #[test]
    fn test_notify_work() {
        let notif = notify_work("job1", "0xabc", 100, 1.5, "seed123", true);
        assert!(notif.contains("mining.notify"));
        assert!(notif.contains("job1"));
    }

    #[test]
    fn test_set_difficulty() {
        let notif = set_difficulty(2.5);
        assert!(notif.contains("mining.set_difficulty"));
        assert!(notif.contains("2.5"));
    }
}
