//! WebSocket event streaming types for real-time Aether Tree updates.
//!
//! Provides event types, a client registry, and broadcast filtering logic.
//! Actual WebSocket I/O is handled by the API layer; this module provides
//! the bookkeeping: client subscriptions, event buffering, eviction, and stats.
//!
//! Ported from: `src/qubitcoin/aether/ws_streaming.py` (319 LOC)

use std::collections::{HashMap, HashSet, VecDeque};

use chrono::Utc;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ─── Event Types ────────────────────────────────────────────────────────────

/// Valid WebSocket event types that clients can subscribe to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[pyclass(eq, eq_int)]
pub enum WSEventType {
    /// Chat response from Aether (session-scoped).
    AetherResponse,
    /// Phi value changes.
    PhiUpdate,
    /// New knowledge node added.
    KnowledgeNode,
    /// Consciousness threshold crossing.
    ConsciousnessEvent,
    /// QBC circulation metrics change.
    CirculationUpdate,
    /// QBC-20/721 transfer detected.
    TokenTransfer,
    /// Server heartbeat ping.
    Heartbeat,
}

#[pymethods]
impl WSEventType {
    /// Convert to the wire-format string used in JSON messages.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::AetherResponse => "aether_response",
            Self::PhiUpdate => "phi_update",
            Self::KnowledgeNode => "knowledge_node",
            Self::ConsciousnessEvent => "consciousness_event",
            Self::CirculationUpdate => "circulation_update",
            Self::TokenTransfer => "token_transfer",
            Self::Heartbeat => "heartbeat",
        }
    }

    /// Parse from wire-format string. Returns None for unknown types.
    #[staticmethod]
    pub fn from_str(s: &str) -> Option<WSEventType> {
        match s {
            "aether_response" => Some(Self::AetherResponse),
            "phi_update" => Some(Self::PhiUpdate),
            "knowledge_node" => Some(Self::KnowledgeNode),
            "consciousness_event" => Some(Self::ConsciousnessEvent),
            "circulation_update" => Some(Self::CirculationUpdate),
            "token_transfer" => Some(Self::TokenTransfer),
            "heartbeat" => Some(Self::Heartbeat),
            _ => None,
        }
    }

    /// Returns all subscribable event types (excludes Heartbeat).
    #[staticmethod]
    pub fn all_subscribable() -> Vec<WSEventType> {
        vec![
            Self::AetherResponse,
            Self::PhiUpdate,
            Self::KnowledgeNode,
            Self::ConsciousnessEvent,
            Self::CirculationUpdate,
            Self::TokenTransfer,
        ]
    }
}

/// A WebSocket event ready for serialization and broadcast.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct WSEvent {
    /// Event type tag.
    pub event_type: String,
    /// JSON payload.
    pub data: String,
    /// Unix timestamp (seconds).
    pub timestamp: f64,
    /// If true, this is a replayed buffered event.
    pub replayed: bool,
    /// Session scope (only for AetherResponse).
    pub session_id: Option<String>,
}

#[pymethods]
impl WSEvent {
    #[new]
    #[pyo3(signature = (event_type, data, session_id=None, replayed=false))]
    pub fn new(
        event_type: String,
        data: String,
        session_id: Option<String>,
        replayed: bool,
    ) -> Self {
        Self {
            event_type,
            data,
            timestamp: Utc::now().timestamp() as f64
                + (Utc::now().timestamp_subsec_millis() as f64 / 1000.0),
            replayed,
            session_id,
        }
    }

    /// Serialize to JSON string for sending over WebSocket.
    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}

// ─── Client ─────────────────────────────────────────────────────────────────

/// Represents a connected WebSocket client and its subscription state.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AetherWSClient {
    /// Unique client identifier.
    pub client_id: u64,
    /// Optional chat session binding.
    pub session_id: Option<String>,
    /// Set of subscribed event type strings.
    pub subscriptions: HashSet<String>,
    /// Unix timestamp when connected.
    pub connected_at: f64,
    /// Unix timestamp of last activity.
    pub last_activity: f64,
    /// Total messages sent to this client.
    pub messages_sent: u64,
}

#[pymethods]
impl AetherWSClient {
    #[new]
    #[pyo3(signature = (client_id, session_id=None, subscriptions=None))]
    pub fn new(
        client_id: u64,
        session_id: Option<String>,
        subscriptions: Option<HashSet<String>>,
    ) -> Self {
        let now = Utc::now().timestamp() as f64
            + (Utc::now().timestamp_subsec_millis() as f64 / 1000.0);

        let subs = subscriptions.unwrap_or_else(|| {
            let mut s = HashSet::new();
            s.insert("phi_update".to_string());
            s.insert("consciousness_event".to_string());
            s.insert("knowledge_node".to_string());
            s
        });

        Self {
            client_id,
            session_id,
            subscriptions: subs,
            connected_at: now,
            last_activity: now,
            messages_sent: 0,
        }
    }

    /// Check if this client is subscribed to the given event type.
    pub fn is_subscribed(&self, event_type: &str) -> bool {
        self.subscriptions.contains(event_type)
    }

    /// Record a sent message.
    pub fn record_send(&mut self) {
        let now = Utc::now().timestamp() as f64
            + (Utc::now().timestamp_subsec_millis() as f64 / 1000.0);
        self.last_activity = now;
        self.messages_sent += 1;
    }
}

// ─── Buffered Event ─────────────────────────────────────────────────────────

/// An event stored in the replay buffer.
#[derive(Debug, Clone)]
struct BufferedEvent {
    event_type: String,
    data: String,
    session_id: Option<String>,
    timestamp: f64,
}

// ─── Manager ────────────────────────────────────────────────────────────────

/// WebSocket streaming statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct WSStats {
    pub connected_clients: usize,
    pub max_clients: usize,
    pub total_events_broadcast: u64,
    pub buffer_sizes: HashMap<String, usize>,
}

/// Manages WebSocket client registry, subscriptions, event filtering, and buffering.
///
/// Does NOT perform actual I/O. The API layer calls `should_send` and `get_targets`
/// to determine which clients receive which events, then sends them.
#[pyclass]
pub struct AetherWSManager {
    clients: HashMap<u64, AetherWSClient>,
    max_clients: usize,
    total_events_broadcast: u64,
    event_buffer: HashMap<String, VecDeque<BufferedEvent>>,
    buffer_limit: usize,
}

#[pymethods]
impl AetherWSManager {
    #[new]
    #[pyo3(signature = (max_clients=1000, buffer_limit=100))]
    pub fn new(max_clients: usize, buffer_limit: usize) -> Self {
        Self {
            clients: HashMap::new(),
            max_clients,
            total_events_broadcast: 0,
            event_buffer: HashMap::new(),
            buffer_limit,
        }
    }

    /// Number of connected clients.
    #[getter]
    pub fn client_count(&self) -> usize {
        self.clients.len()
    }

    /// Register a new client. Returns the client_id used for tracking.
    /// If over capacity, evicts the oldest client.
    #[pyo3(signature = (client_id, session_id=None, subscriptions=None))]
    pub fn register(
        &mut self,
        client_id: u64,
        session_id: Option<String>,
        subscriptions: Option<HashSet<String>>,
    ) -> u64 {
        let valid_events: HashSet<String> = WSEventType::all_subscribable()
            .iter()
            .map(|e| e.as_str().to_string())
            .collect();

        let mut subs = subscriptions.unwrap_or_else(|| {
            let mut s = HashSet::new();
            s.insert("phi_update".to_string());
            s.insert("consciousness_event".to_string());
            s.insert("knowledge_node".to_string());
            s
        });

        // Filter to valid event types
        subs.retain(|s| valid_events.contains(s));

        // Session-scoped events require session_id
        if session_id.is_some() {
            subs.insert("aether_response".to_string());
        }

        let client = AetherWSClient::new(client_id, session_id, Some(subs));
        self.clients.insert(client_id, client);

        // Evict oldest if over capacity
        if self.clients.len() > self.max_clients {
            if let Some((&oldest_id, _)) = self
                .clients
                .iter()
                .min_by(|a, b| a.1.connected_at.partial_cmp(&b.1.connected_at).unwrap())
            {
                self.clients.remove(&oldest_id);
                log::info!(
                    "Aether WS: evicted oldest client (capacity {})",
                    self.max_clients
                );
            }
        }

        log::info!(
            "Aether WS: client registered (total: {})",
            self.clients.len()
        );
        client_id
    }

    /// Unregister a disconnected client.
    pub fn unregister(&mut self, client_id: u64) {
        if self.clients.remove(&client_id).is_some() {
            log::debug!(
                "Aether WS: client unregistered (total: {})",
                self.clients.len()
            );
        }
    }

    /// Determine which client IDs should receive a given event.
    /// Returns list of (client_id) for clients subscribed to this event type.
    /// For session-scoped events (aether_response), only matching sessions are included.
    #[pyo3(signature = (event_type, session_id=None))]
    pub fn get_targets(
        &self,
        event_type: &str,
        session_id: Option<&str>,
    ) -> Vec<u64> {
        // Validate event type
        if WSEventType::from_str(event_type).is_none() {
            return Vec::new();
        }

        self.clients
            .iter()
            .filter(|(_, client)| {
                if !client.subscriptions.contains(event_type) {
                    return false;
                }
                // Session-scoped: only send to matching session
                if event_type == "aether_response" {
                    if let Some(sid) = session_id {
                        return client.session_id.as_deref() == Some(sid);
                    }
                }
                true
            })
            .map(|(&id, _)| id)
            .collect()
    }

    /// Record that a message was successfully sent to a client.
    pub fn record_send(&mut self, client_id: u64) {
        if let Some(client) = self.clients.get_mut(&client_id) {
            client.record_send();
            self.total_events_broadcast += 1;
        }
    }

    /// Remove a list of client IDs (e.g. disconnected during broadcast).
    pub fn remove_clients(&mut self, client_ids: Vec<u64>) {
        for id in &client_ids {
            self.clients.remove(id);
        }
        if !client_ids.is_empty() {
            log::debug!(
                "Aether WS: removed {} disconnected clients",
                client_ids.len()
            );
        }
    }

    /// Get client IDs that have been inactive for longer than `threshold_secs`.
    pub fn get_inactive_clients(&self, threshold_secs: f64) -> Vec<u64> {
        let now = Utc::now().timestamp() as f64;
        self.clients
            .iter()
            .filter(|(_, c)| now - c.last_activity > threshold_secs)
            .map(|(&id, _)| id)
            .collect()
    }

    /// Buffer an event for later replay to reconnecting clients.
    #[pyo3(signature = (event_type, data, session_id=None))]
    pub fn buffer_event(
        &mut self,
        event_type: &str,
        data: &str,
        session_id: Option<String>,
    ) {
        let now = Utc::now().timestamp() as f64
            + (Utc::now().timestamp_subsec_millis() as f64 / 1000.0);
        let buf = self
            .event_buffer
            .entry(event_type.to_string())
            .or_insert_with(VecDeque::new);

        buf.push_back(BufferedEvent {
            event_type: event_type.to_string(),
            data: data.to_string(),
            session_id,
            timestamp: now,
        });

        // Trim to limit
        while buf.len() > self.buffer_limit {
            buf.pop_front();
        }
    }

    /// Get buffered events suitable for replaying to a client.
    /// Returns events from the last `max_age_secs` seconds, up to `max_per_type` per event type.
    /// Only includes events the client is subscribed to.
    #[pyo3(signature = (client_id, max_age_secs=300.0, max_per_type=10))]
    pub fn get_replay_events(
        &self,
        client_id: u64,
        max_age_secs: f64,
        max_per_type: usize,
    ) -> Vec<WSEvent> {
        let client = match self.clients.get(&client_id) {
            Some(c) => c,
            None => return Vec::new(),
        };

        let now = Utc::now().timestamp() as f64;
        let cutoff = now - max_age_secs;
        let mut result = Vec::new();

        for (event_type, events) in &self.event_buffer {
            if !client.subscriptions.contains(event_type) {
                continue;
            }

            let recent: Vec<_> = events
                .iter()
                .filter(|e| e.timestamp > cutoff)
                .collect();

            let start = if recent.len() > max_per_type {
                recent.len() - max_per_type
            } else {
                0
            };

            for ev in &recent[start..] {
                // Session scope filtering
                if event_type == "aether_response" {
                    if let Some(ref ev_session) = ev.session_id {
                        if client.session_id.as_deref() != Some(ev_session) {
                            continue;
                        }
                    }
                }

                result.push(WSEvent {
                    event_type: ev.event_type.clone(),
                    data: ev.data.clone(),
                    timestamp: ev.timestamp,
                    replayed: true,
                    session_id: ev.session_id.clone(),
                });
            }
        }

        result
    }

    /// Get streaming statistics.
    pub fn get_stats(&self) -> WSStats {
        let buffer_sizes: HashMap<String, usize> = self
            .event_buffer
            .iter()
            .map(|(k, v)| (k.clone(), v.len()))
            .collect();

        WSStats {
            connected_clients: self.clients.len(),
            max_clients: self.max_clients,
            total_events_broadcast: self.total_events_broadcast,
            buffer_sizes,
        }
    }

    /// Get info about all connected clients (for admin/debug).
    pub fn get_client_info(&self) -> Vec<AetherWSClient> {
        self.clients.values().cloned().collect()
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_type_roundtrip() {
        for et in WSEventType::all_subscribable() {
            let s = et.as_str();
            let parsed = WSEventType::from_str(s).unwrap();
            assert_eq!(et, parsed);
        }
    }

    #[test]
    fn test_event_type_unknown() {
        assert!(WSEventType::from_str("unknown_event").is_none());
    }

    #[test]
    fn test_ws_event_creation() {
        let evt = WSEvent::new(
            "phi_update".to_string(),
            r#"{"phi": 1.5}"#.to_string(),
            None,
            false,
        );
        assert_eq!(evt.event_type, "phi_update");
        assert!(!evt.replayed);
        assert!(evt.timestamp > 0.0);
    }

    #[test]
    fn test_ws_event_json() {
        let evt = WSEvent::new(
            "phi_update".to_string(),
            r#"{"phi": 1.5}"#.to_string(),
            None,
            false,
        );
        let json = serde_json::to_string(&evt).unwrap();
        assert!(json.contains("phi_update"));
    }

    #[test]
    fn test_client_creation_defaults() {
        let client = AetherWSClient::new(42, None, None);
        assert_eq!(client.client_id, 42);
        assert!(client.session_id.is_none());
        assert!(client.subscriptions.contains("phi_update"));
        assert!(client.subscriptions.contains("consciousness_event"));
        assert!(client.subscriptions.contains("knowledge_node"));
        assert_eq!(client.messages_sent, 0);
    }

    #[test]
    fn test_client_is_subscribed() {
        let client = AetherWSClient::new(1, None, None);
        assert!(client.is_subscribed("phi_update"));
        assert!(!client.is_subscribed("aether_response"));
    }

    #[test]
    fn test_client_record_send() {
        let mut client = AetherWSClient::new(1, None, None);
        let old_activity = client.last_activity;
        std::thread::sleep(std::time::Duration::from_millis(10));
        client.record_send();
        assert_eq!(client.messages_sent, 1);
        assert!(client.last_activity >= old_activity);
    }

    #[test]
    fn test_manager_register_unregister() {
        let mut mgr = AetherWSManager::new(100, 50);
        assert_eq!(mgr.client_count(), 0);

        mgr.register(1, None, None);
        assert_eq!(mgr.client_count(), 1);

        mgr.register(2, Some("session-abc".to_string()), None);
        assert_eq!(mgr.client_count(), 2);

        mgr.unregister(1);
        assert_eq!(mgr.client_count(), 1);

        mgr.unregister(999); // no-op
        assert_eq!(mgr.client_count(), 1);
    }

    #[test]
    fn test_manager_eviction() {
        let mut mgr = AetherWSManager::new(2, 50);
        mgr.register(1, None, None);
        mgr.register(2, None, None);
        assert_eq!(mgr.client_count(), 2);

        // Third registration should evict oldest
        mgr.register(3, None, None);
        assert_eq!(mgr.client_count(), 2);
    }

    #[test]
    fn test_manager_get_targets_basic() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, None, None); // defaults: phi_update, consciousness_event, knowledge_node
        mgr.register(2, Some("sess-1".to_string()), None);

        // Both clients subscribed to phi_update
        let targets = mgr.get_targets("phi_update", None);
        assert_eq!(targets.len(), 2);

        // Neither subscribed to token_transfer by default
        let targets = mgr.get_targets("token_transfer", None);
        assert!(targets.is_empty());
    }

    #[test]
    fn test_manager_get_targets_session_scoped() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, Some("sess-A".to_string()), None);
        mgr.register(2, Some("sess-B".to_string()), None);
        mgr.register(3, None, None); // no session

        // aether_response with session_id should only match the right session
        let targets = mgr.get_targets("aether_response", Some("sess-A"));
        assert_eq!(targets, vec![1]);

        let targets = mgr.get_targets("aether_response", Some("sess-B"));
        assert_eq!(targets, vec![2]);
    }

    #[test]
    fn test_manager_get_targets_invalid_event() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, None, None);
        let targets = mgr.get_targets("bogus_event", None);
        assert!(targets.is_empty());
    }

    #[test]
    fn test_manager_record_send() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, None, None);
        mgr.record_send(1);
        let stats = mgr.get_stats();
        assert_eq!(stats.total_events_broadcast, 1);
    }

    #[test]
    fn test_manager_remove_clients() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, None, None);
        mgr.register(2, None, None);
        mgr.register(3, None, None);
        mgr.remove_clients(vec![1, 3]);
        assert_eq!(mgr.client_count(), 1);
    }

    #[test]
    fn test_manager_buffer_and_replay() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.buffer_event("phi_update", r#"{"phi": 1.0}"#, None);
        mgr.buffer_event("phi_update", r#"{"phi": 1.5}"#, None);

        mgr.register(1, None, None);
        let events = mgr.get_replay_events(1, 300.0, 10);
        assert_eq!(events.len(), 2);
        assert!(events[0].replayed);
    }

    #[test]
    fn test_manager_buffer_limit() {
        let mut mgr = AetherWSManager::new(100, 3);
        for i in 0..5 {
            mgr.buffer_event("phi_update", &format!("{{\"v\": {}}}", i), None);
        }
        // Only last 3 should remain
        mgr.register(1, None, None);
        let events = mgr.get_replay_events(1, 300.0, 10);
        assert_eq!(events.len(), 3);
    }

    #[test]
    fn test_manager_replay_session_scope() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.buffer_event(
            "aether_response",
            r#"{"msg": "hello"}"#,
            Some("sess-X".to_string()),
        );
        mgr.buffer_event(
            "aether_response",
            r#"{"msg": "world"}"#,
            Some("sess-Y".to_string()),
        );

        // Client bound to sess-X should only get sess-X events
        mgr.register(1, Some("sess-X".to_string()), None);
        let events = mgr.get_replay_events(1, 300.0, 10);
        assert_eq!(events.len(), 1);
        assert!(events[0].data.contains("hello"));
    }

    #[test]
    fn test_manager_stats() {
        let mut mgr = AetherWSManager::new(100, 50);
        mgr.register(1, None, None);
        mgr.buffer_event("phi_update", "{}", None);
        let stats = mgr.get_stats();
        assert_eq!(stats.connected_clients, 1);
        assert_eq!(stats.max_clients, 100);
        assert_eq!(*stats.buffer_sizes.get("phi_update").unwrap(), 1);
    }

    #[test]
    fn test_manager_custom_subscriptions() {
        let mut mgr = AetherWSManager::new(100, 50);
        let mut subs = HashSet::new();
        subs.insert("token_transfer".to_string());
        subs.insert("circulation_update".to_string());
        subs.insert("invalid_event".to_string()); // should be filtered out
        mgr.register(1, None, Some(subs));

        let targets = mgr.get_targets("token_transfer", None);
        assert_eq!(targets.len(), 1);

        // phi_update not subscribed
        let targets = mgr.get_targets("phi_update", None);
        assert!(targets.is_empty());
    }
}
