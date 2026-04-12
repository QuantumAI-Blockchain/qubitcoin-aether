//! CSF Transport Layer -- Inter-Sephirot Messaging
//!
//! Biological model: Cerebrospinal Fluid (CSF) circulation through brain ventricles.
//!
//! Messages between Sephirot nodes flow as QBC transactions:
//! - Each message is a blockchain transaction with QBC attached for priority.
//! - Routing follows the Tree of Life topology (Keter -> Tiferet -> Malkuth).
//! - SUSY-paired nodes get instant quantum-entangled delivery.
//! - Backpressure prevents queue overload on congested nodes.
//! - Message fees fund the network and prevent spam.

use parking_lot::RwLock;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Max queue depth per node before backpressure triggers.
const MAX_NODE_PRESSURE: u32 = 50;

/// Pressure threshold (0-1) at which backpressure activates.
const BACKPRESSURE_THRESHOLD: f64 = 0.8;

/// Default message TTL (max hops).
const DEFAULT_TTL: u32 = 10;

// ---------------------------------------------------------------------------
// SephirahRole enum
// ---------------------------------------------------------------------------

/// The 10 Sephirot cognitive functions (Tree of Life).
///
/// Each variant maps to the lowercase string value used in Python
/// (`SephirahRole.KETER.value == "keter"`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
pub enum SephirahRole {
    Keter,
    Chochmah,
    Binah,
    Chesed,
    Gevurah,
    Tiferet,
    Netzach,
    Hod,
    Yesod,
    Malkuth,
}

impl SephirahRole {
    /// Lowercase string value matching the Python enum.
    pub fn value(&self) -> &'static str {
        match self {
            Self::Keter => "keter",
            Self::Chochmah => "chochmah",
            Self::Binah => "binah",
            Self::Chesed => "chesed",
            Self::Gevurah => "gevurah",
            Self::Tiferet => "tiferet",
            Self::Netzach => "netzach",
            Self::Hod => "hod",
            Self::Yesod => "yesod",
            Self::Malkuth => "malkuth",
        }
    }

    /// Parse from a string (case-insensitive).
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "keter" => Some(Self::Keter),
            "chochmah" => Some(Self::Chochmah),
            "binah" => Some(Self::Binah),
            "chesed" => Some(Self::Chesed),
            "gevurah" => Some(Self::Gevurah),
            "tiferet" => Some(Self::Tiferet),
            "netzach" => Some(Self::Netzach),
            "hod" => Some(Self::Hod),
            "yesod" => Some(Self::Yesod),
            "malkuth" => Some(Self::Malkuth),
            _ => None,
        }
    }

    /// Return all 10 roles in canonical order.
    pub fn all() -> &'static [SephirahRole; 10] {
        &[
            Self::Keter,
            Self::Chochmah,
            Self::Binah,
            Self::Chesed,
            Self::Gevurah,
            Self::Tiferet,
            Self::Netzach,
            Self::Hod,
            Self::Yesod,
            Self::Malkuth,
        ]
    }
}

/// SUSY expansion/constraint pairs -- must balance at golden ratio.
/// (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod)
const SUSY_PAIRS: &[(SephirahRole, SephirahRole)] = &[
    (SephirahRole::Chesed, SephirahRole::Gevurah),
    (SephirahRole::Chochmah, SephirahRole::Binah),
    (SephirahRole::Netzach, SephirahRole::Hod),
];

/// Tree of Life routing topology -- directed edges between Sephirot.
/// Defines which nodes can directly communicate.
fn topology() -> HashMap<SephirahRole, Vec<SephirahRole>> {
    use SephirahRole::*;
    let mut m = HashMap::new();
    m.insert(Keter, vec![Chochmah, Binah]);
    m.insert(Chochmah, vec![Keter, Binah, Chesed]);
    m.insert(Binah, vec![Keter, Chochmah, Gevurah]);
    m.insert(Chesed, vec![Chochmah, Gevurah, Tiferet]);
    m.insert(Gevurah, vec![Binah, Chesed, Tiferet]);
    m.insert(Tiferet, vec![Chesed, Gevurah, Netzach, Hod, Yesod]);
    m.insert(Netzach, vec![Tiferet, Hod, Yesod]);
    m.insert(Hod, vec![Tiferet, Netzach, Yesod]);
    m.insert(Yesod, vec![Tiferet, Netzach, Hod, Malkuth]);
    m.insert(Malkuth, vec![Yesod]);
    m
}

// ---------------------------------------------------------------------------
// CSFMessage
// ---------------------------------------------------------------------------

/// A message flowing between Sephirot nodes via CSF transport.
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct CSFMessage {
    /// Auto-generated sha256[:16] message identifier.
    pub msg_id: String,
    /// Source node (lowercase sephirah name).
    pub source: String,
    /// Destination node (lowercase sephirah name).
    pub destination: String,
    /// Message type: "signal", "query", "response", "broadcast".
    pub msg_type: String,
    /// Serialized payload (JSON string for Python interop).
    pub payload: String,
    /// QBC attached for priority ordering.
    pub priority_qbc: f64,
    /// Max hops before expiry.
    pub ttl: u32,
    /// Unix timestamp of creation.
    pub timestamp: f64,
    /// List of node values this message has visited.
    pub hops: Vec<String>,
    /// Whether the message has been delivered.
    pub delivered: bool,
}

#[pymethods]
impl CSFMessage {
    #[new]
    #[pyo3(signature = (
        source = String::from("keter"),
        destination = String::from("malkuth"),
        msg_type = String::from("signal"),
        payload = String::from("{}"),
        priority_qbc = 0.0,
        ttl = DEFAULT_TTL,
    ))]
    pub fn new(
        source: String,
        destination: String,
        msg_type: String,
        payload: String,
        priority_qbc: f64,
        ttl: u32,
    ) -> Self {
        let now = current_timestamp();
        let data = format!("{}:{}:{}", source, destination, now);
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let msg_id = format!("{:x}", hasher.finalize());
        let msg_id = msg_id[..16].to_string();

        CSFMessage {
            msg_id,
            source,
            destination,
            msg_type,
            payload,
            priority_qbc,
            ttl,
            timestamp: now,
            hops: Vec::new(),
            delivered: false,
        }
    }

    /// Convert to Python dict.
    pub fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        d.set_item("msg_id", &self.msg_id)?;
        d.set_item("source", &self.source)?;
        d.set_item("destination", &self.destination)?;
        d.set_item("msg_type", &self.msg_type)?;
        d.set_item("payload", &self.payload)?;
        d.set_item("priority_qbc", self.priority_qbc)?;
        d.set_item("ttl", self.ttl)?;
        d.set_item("timestamp", self.timestamp)?;
        d.set_item("hops", &self.hops)?;
        d.set_item("delivered", self.delivered)?;
        Ok(d)
    }

    fn __repr__(&self) -> String {
        format!(
            "CSFMessage(id='{}', {} -> {}, type='{}', priority={:.4}, ttl={}, delivered={})",
            self.msg_id,
            self.source,
            self.destination,
            self.msg_type,
            self.priority_qbc,
            self.ttl,
            self.delivered,
        )
    }
}

/// Internal (non-PyO3) constructor used by the transport layer.
impl CSFMessage {
    fn new_internal(
        source: SephirahRole,
        destination: SephirahRole,
        msg_type: &str,
        payload: String,
        priority_qbc: f64,
    ) -> Self {
        let now = current_timestamp();
        let data = format!("{}:{}:{}", source.value(), destination.value(), now);
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let msg_id = format!("{:x}", hasher.finalize());
        let msg_id = msg_id[..16].to_string();

        CSFMessage {
            msg_id,
            source: source.value().to_string(),
            destination: destination.value().to_string(),
            msg_type: msg_type.to_string(),
            payload,
            priority_qbc,
            ttl: DEFAULT_TTL,
            timestamp: now,
            hops: Vec::new(),
            delivered: false,
        }
    }

    /// Parse the source field into a SephirahRole.
    fn source_role(&self) -> Option<SephirahRole> {
        SephirahRole::from_str(&self.source)
    }

    /// Parse the destination field into a SephirahRole.
    fn dest_role(&self) -> Option<SephirahRole> {
        SephirahRole::from_str(&self.destination)
    }

    /// Parse the last hop into a SephirahRole.
    fn current_position(&self) -> Option<SephirahRole> {
        if let Some(last) = self.hops.last() {
            SephirahRole::from_str(last)
        } else {
            self.source_role()
        }
    }
}

// ---------------------------------------------------------------------------
// PressureMonitor
// ---------------------------------------------------------------------------

/// Monitors per-node message queue pressure and applies backpressure.
///
/// Biological model: Intracranial pressure monitoring -- when CSF pressure
/// in a brain region exceeds safe levels, flow is redirected.
struct PressureMonitor {
    max_pressure: u32,
    node_pressure: HashMap<SephirahRole, u32>,
    total_backpressure_events: u64,
}

impl PressureMonitor {
    fn new(max_pressure: u32) -> Self {
        let mut node_pressure = HashMap::new();
        for role in SephirahRole::all() {
            node_pressure.insert(*role, 0);
        }
        PressureMonitor {
            max_pressure,
            node_pressure,
            total_backpressure_events: 0,
        }
    }

    /// Record that a message was enqueued for a node.
    fn record_enqueue(&mut self, destination: SephirahRole) {
        let entry = self.node_pressure.entry(destination).or_insert(0);
        *entry += 1;
    }

    /// Record that a message was delivered/dropped for a node.
    fn record_dequeue(&mut self, destination: SephirahRole) {
        let entry = self.node_pressure.entry(destination).or_insert(0);
        *entry = entry.saturating_sub(1);
    }

    /// Check if a node's queue is above the backpressure threshold.
    fn is_congested(&self, node: SephirahRole) -> bool {
        let pressure = *self.node_pressure.get(&node).unwrap_or(&0);
        let threshold = (self.max_pressure as f64 * BACKPRESSURE_THRESHOLD) as u32;
        pressure >= threshold
    }

    /// Get normalized pressure for a node (0.0 to 1.0+).
    fn get_pressure(&self, node: SephirahRole) -> f64 {
        let pressure = *self.node_pressure.get(&node).unwrap_or(&0);
        pressure as f64 / self.max_pressure.max(1) as f64
    }

    /// Return the least congested neighbor from a list.
    fn get_least_congested_neighbor(
        &self,
        neighbors: &[SephirahRole],
    ) -> Option<SephirahRole> {
        if neighbors.is_empty() {
            return None;
        }
        neighbors
            .iter()
            .min_by_key(|n| *self.node_pressure.get(n).unwrap_or(&0))
            .copied()
    }

    /// Record a backpressure event.
    fn record_backpressure(&mut self) {
        self.total_backpressure_events += 1;
    }

    /// Get pressure monitor status as a dict-friendly structure.
    fn get_status(&self) -> PressureStatus {
        let mut node_pressure = HashMap::new();
        let mut congested_nodes = Vec::new();
        for role in SephirahRole::all() {
            node_pressure.insert(role.value().to_string(), self.get_pressure(*role));
            if self.is_congested(*role) {
                congested_nodes.push(role.value().to_string());
            }
        }
        PressureStatus {
            node_pressure,
            congested_nodes,
            total_backpressure_events: self.total_backpressure_events,
        }
    }
}

/// Serializable status snapshot from PressureMonitor.
struct PressureStatus {
    node_pressure: HashMap<String, f64>,
    congested_nodes: Vec<String>,
    total_backpressure_events: u64,
}

// ---------------------------------------------------------------------------
// QuantumEntangledChannel
// ---------------------------------------------------------------------------

/// Zero-latency messaging between SUSY-paired Sephirot nodes.
///
/// Biological model: Quantum entanglement between paired neural regions
/// allows instantaneous state correlation.
///
/// SUSY pairs (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod) share
/// entangled channels that bypass normal BFS routing.
struct QuantumEntangledChannel {
    /// Bidirectional pair lookup.
    pairs: HashMap<SephirahRole, SephirahRole>,
    entangled_deliveries: u64,
}

impl QuantumEntangledChannel {
    fn new() -> Self {
        let mut pairs = HashMap::new();
        for (expansion, constraint) in SUSY_PAIRS {
            pairs.insert(*expansion, *constraint);
            pairs.insert(*constraint, *expansion);
        }
        log::info!(
            "Quantum entangled channels initialized ({} SUSY pairs)",
            SUSY_PAIRS.len()
        );
        QuantumEntangledChannel {
            pairs,
            entangled_deliveries: 0,
        }
    }

    /// Check if two nodes share a quantum entangled channel.
    fn is_entangled(&self, source: SephirahRole, destination: SephirahRole) -> bool {
        self.pairs.get(&source) == Some(&destination)
    }

    /// Get the SUSY-entangled partner of a node, if any.
    #[allow(dead_code)]
    fn get_partner(&self, node: SephirahRole) -> Option<SephirahRole> {
        self.pairs.get(&node).copied()
    }

    /// Instantly deliver a message through the entangled channel.
    fn deliver_entangled(&mut self, msg: &mut CSFMessage) {
        msg.hops
            .push(format!("\u{27e8}entangled\u{27e9}\u{2192}{}", msg.destination));
        msg.delivered = true;
        self.entangled_deliveries += 1;
        log::debug!(
            "Quantum entangled delivery: {} <-> {}",
            msg.source,
            msg.destination
        );
    }

    /// Get entangled channel status.
    fn get_status(&self) -> EntangledStatus {
        let pairs_info: Vec<(String, String)> = SUSY_PAIRS
            .iter()
            .map(|(e, c)| (e.value().to_string(), c.value().to_string()))
            .collect();
        EntangledStatus {
            pairs: pairs_info,
            total_entangled_deliveries: self.entangled_deliveries,
        }
    }
}

/// Serializable status snapshot from QuantumEntangledChannel.
struct EntangledStatus {
    pairs: Vec<(String, String)>,
    total_entangled_deliveries: u64,
}

// ---------------------------------------------------------------------------
// CSFTransportInner (mutable state behind RwLock)
// ---------------------------------------------------------------------------

/// All mutable state for the transport layer, held behind a RwLock.
struct CSFTransportInner {
    /// Priority queue (sorted by QBC descending).
    queue: Vec<CSFMessage>,
    /// Delivered messages (history).
    delivered: Vec<CSFMessage>,
    /// Count of dropped messages.
    dropped: u64,
    /// Per-node pressure monitor.
    pressure: PressureMonitor,
    /// Quantum entangled channel for SUSY pairs.
    entangled: QuantumEntangledChannel,
    /// Cached topology for BFS.
    topology: HashMap<SephirahRole, Vec<SephirahRole>>,
}

impl CSFTransportInner {
    fn new() -> Self {
        CSFTransportInner {
            queue: Vec::new(),
            delivered: Vec::new(),
            dropped: 0,
            pressure: PressureMonitor::new(MAX_NODE_PRESSURE),
            entangled: QuantumEntangledChannel::new(),
            topology: topology(),
        }
    }

    /// BFS to find the next hop toward destination from current position.
    fn find_next_hop(
        &self,
        current: SephirahRole,
        destination: SephirahRole,
    ) -> Option<SephirahRole> {
        let mut visited = HashSet::new();
        visited.insert(current);

        let mut bfs_queue: VecDeque<(SephirahRole, SephirahRole)> = VecDeque::new();
        if let Some(neighbors) = self.topology.get(&current) {
            for neighbor in neighbors {
                bfs_queue.push_back((*neighbor, *neighbor)); // (node, first_hop)
                visited.insert(*neighbor);
            }
        }

        while let Some((node, first_hop)) = bfs_queue.pop_front() {
            if node == destination {
                return Some(first_hop);
            }
            if let Some(neighbors) = self.topology.get(&node) {
                for neighbor in neighbors {
                    if !visited.contains(neighbor) {
                        visited.insert(*neighbor);
                        bfs_queue.push_back((*neighbor, first_hop));
                    }
                }
            }
        }
        None
    }

    /// BFS shortest path between two nodes.
    fn find_path(
        &self,
        source: SephirahRole,
        destination: SephirahRole,
    ) -> Vec<SephirahRole> {
        if source == destination {
            return vec![source];
        }

        let mut visited = HashSet::new();
        visited.insert(source);

        let mut bfs_queue: VecDeque<(SephirahRole, Vec<SephirahRole>)> = VecDeque::new();
        bfs_queue.push_back((source, vec![source]));

        while let Some((node, path)) = bfs_queue.pop_front() {
            if let Some(neighbors) = self.topology.get(&node) {
                for neighbor in neighbors {
                    if *neighbor == destination {
                        let mut full_path = path.clone();
                        full_path.push(*neighbor);
                        return full_path;
                    }
                    if !visited.contains(neighbor) {
                        visited.insert(*neighbor);
                        let mut new_path = path.clone();
                        new_path.push(*neighbor);
                        bfs_queue.push_back((*neighbor, new_path));
                    }
                }
            }
        }
        Vec::new() // No path found
    }

    /// Send a message from one Sephirah to another.
    fn send(
        &mut self,
        source: SephirahRole,
        destination: SephirahRole,
        payload: String,
        msg_type: &str,
        priority_qbc: f64,
    ) -> CSFMessage {
        let mut msg = CSFMessage::new_internal(source, destination, msg_type, payload, priority_qbc);
        msg.hops.push(source.value().to_string());

        // Check for quantum-entangled shortcut (instant delivery for SUSY pairs)
        if self.entangled.is_entangled(source, destination) {
            self.entangled.deliver_entangled(&mut msg);
            self.delivered.push(msg.clone());
            return msg;
        }

        // Backpressure check: if destination is congested, deprioritize
        if self.pressure.is_congested(destination) {
            msg.priority_qbc *= 0.5;
            self.pressure.record_backpressure();
            log::debug!(
                "Backpressure: {} congested, deprioritizing",
                destination.value()
            );
        }

        self.pressure.record_enqueue(destination);
        self.queue.push(msg.clone());
        // Sort by priority (highest QBC first)
        self.queue
            .sort_by(|a, b| b.priority_qbc.partial_cmp(&a.priority_qbc).unwrap_or(std::cmp::Ordering::Equal));
        log::debug!(
            "CSF: {} -> {} [{}] priority={} QBC",
            source.value(),
            destination.value(),
            msg_type,
            priority_qbc
        );
        msg
    }

    /// Broadcast a message from one node to all its direct neighbors.
    fn broadcast(
        &mut self,
        source: SephirahRole,
        payload: String,
        priority_qbc: f64,
    ) -> Vec<CSFMessage> {
        let neighbors = self
            .topology
            .get(&source)
            .cloned()
            .unwrap_or_default();
        let mut messages = Vec::new();
        for dest in neighbors {
            let msg = self.send(source, dest, payload.clone(), "broadcast", priority_qbc);
            messages.push(msg);
        }
        messages
    }

    /// Process pending messages, routing them through the topology.
    /// Returns list of successfully delivered messages.
    fn process_queue(&mut self, max_messages: usize) -> Vec<CSFMessage> {
        let mut delivered_this_round = Vec::new();
        let mut remaining = Vec::new();

        let process_count = self.queue.len().min(max_messages);
        let unprocessed = self.queue.split_off(process_count);
        let to_process = std::mem::take(&mut self.queue);

        for mut msg in to_process {
            if msg.ttl == 0 {
                // TTL expired -- drop
                self.dropped += 1;
                if let Some(dest) = msg.dest_role() {
                    self.pressure.record_dequeue(dest);
                }
                continue;
            }

            let current = match msg.current_position() {
                Some(r) => r,
                None => {
                    self.dropped += 1;
                    continue;
                }
            };
            let destination = match msg.dest_role() {
                Some(r) => r,
                None => {
                    self.dropped += 1;
                    continue;
                }
            };

            let neighbors = self
                .topology
                .get(&current)
                .cloned()
                .unwrap_or_default();

            if destination == current {
                // Already at destination
                msg.delivered = true;
                self.delivered.push(msg.clone());
                delivered_this_round.push(msg.clone());
                self.pressure.record_dequeue(destination);
            } else if neighbors.contains(&destination) {
                // Direct neighbor -- deliver
                msg.hops.push(destination.value().to_string());
                msg.delivered = true;
                self.delivered.push(msg.clone());
                delivered_this_round.push(msg.clone());
                self.pressure.record_dequeue(destination);
            } else {
                // Route via shortest path -- prefer least-congested next hop
                let next_hop = self.find_next_hop(current, destination);
                if let Some(hop) = next_hop {
                    msg.hops.push(hop.value().to_string());
                    msg.ttl -= 1;
                    remaining.push(msg);
                } else {
                    self.dropped += 1;
                    self.pressure.record_dequeue(destination);
                }
            }
        }

        // Keep undelivered messages + remaining unprocessed
        self.queue = remaining;
        self.queue.extend(unprocessed);

        delivered_this_round
    }
}

// ---------------------------------------------------------------------------
// CSFTransport (PyO3 class)
// ---------------------------------------------------------------------------

/// Routes messages between Sephirot nodes following the Tree of Life topology.
///
/// Features:
/// - Priority queue: higher QBC = faster processing
/// - Topology-aware routing via BFS pathfinding
/// - TTL prevents infinite loops
/// - Quantum entangled delivery for SUSY pairs
/// - Backpressure on congested nodes
/// - Thread-safe via RwLock
#[pyclass]
pub struct CSFTransport {
    inner: Arc<RwLock<CSFTransportInner>>,
}

#[pymethods]
impl CSFTransport {
    #[new]
    pub fn new() -> Self {
        log::info!("CSF Transport initialized (Tree of Life topology + quantum entanglement)");
        CSFTransport {
            inner: Arc::new(RwLock::new(CSFTransportInner::new())),
        }
    }

    /// Send a message from one Sephirah to another.
    ///
    /// Args:
    ///     source: Sending node name (e.g. "keter", "chesed").
    ///     destination: Target node name.
    ///     payload: JSON string payload.
    ///     msg_type: "signal", "query", "response", or "broadcast".
    ///     priority_qbc: QBC attached for priority ordering.
    ///
    /// Returns:
    ///     The CSFMessage (delivered immediately if SUSY pair, else queued).
    #[pyo3(signature = (source, destination, payload, msg_type = "signal".to_string(), priority_qbc = 0.0))]
    pub fn send(
        &self,
        source: String,
        destination: String,
        payload: String,
        msg_type: String,
        priority_qbc: f64,
    ) -> PyResult<CSFMessage> {
        let src = SephirahRole::from_str(&source).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown sephirah: '{}'. Valid: keter, chochmah, binah, chesed, gevurah, tiferet, netzach, hod, yesod, malkuth",
                source
            ))
        })?;
        let dst = SephirahRole::from_str(&destination).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown sephirah: '{}'. Valid: keter, chochmah, binah, chesed, gevurah, tiferet, netzach, hod, yesod, malkuth",
                destination
            ))
        })?;
        let mut inner = self.inner.write();
        Ok(inner.send(src, dst, payload, &msg_type, priority_qbc))
    }

    /// Broadcast a message from one node to all its direct neighbors.
    ///
    /// Returns a list of CSFMessages (one per neighbor).
    #[pyo3(signature = (source, payload, priority_qbc = 0.0))]
    pub fn broadcast(
        &self,
        source: String,
        payload: String,
        priority_qbc: f64,
    ) -> PyResult<Vec<CSFMessage>> {
        let src = SephirahRole::from_str(&source).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Unknown sephirah: '{}'", source))
        })?;
        let mut inner = self.inner.write();
        Ok(inner.broadcast(src, payload, priority_qbc))
    }

    /// Process pending messages, routing them through the topology.
    ///
    /// Returns list of successfully delivered messages this round.
    #[pyo3(signature = (max_messages = 100))]
    pub fn process_queue(&self, max_messages: usize) -> Vec<CSFMessage> {
        let mut inner = self.inner.write();
        inner.process_queue(max_messages)
    }

    /// Find shortest path between two nodes in the topology.
    ///
    /// Returns list of node names along the path (empty if no path).
    pub fn find_path(&self, source: String, destination: String) -> PyResult<Vec<String>> {
        let src = SephirahRole::from_str(&source).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Unknown sephirah: '{}'", source))
        })?;
        let dst = SephirahRole::from_str(&destination).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown sephirah: '{}'",
                destination
            ))
        })?;
        let inner = self.inner.read();
        let path = inner.find_path(src, dst);
        Ok(path.iter().map(|r| r.value().to_string()).collect())
    }

    /// Check if two nodes are SUSY-entangled (instant delivery).
    pub fn is_entangled(&self, source: String, destination: String) -> PyResult<bool> {
        let src = SephirahRole::from_str(&source).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Unknown sephirah: '{}'", source))
        })?;
        let dst = SephirahRole::from_str(&destination).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown sephirah: '{}'",
                destination
            ))
        })?;
        let inner = self.inner.read();
        Ok(inner.entangled.is_entangled(src, dst))
    }

    /// Get transport statistics as a Python dict.
    pub fn get_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let inner = self.inner.read();
        let d = PyDict::new(py);
        d.set_item("queue_size", inner.queue.len())?;
        d.set_item("total_delivered", inner.delivered.len())?;
        d.set_item("total_dropped", inner.dropped)?;

        // Pressure status
        let pressure_status = inner.pressure.get_status();
        let pressure_dict = PyDict::new(py);
        let node_p_dict = PyDict::new(py);
        for (name, val) in &pressure_status.node_pressure {
            // Round to 3 decimal places
            node_p_dict.set_item(name, (*val * 1000.0).round() / 1000.0)?;
        }
        pressure_dict.set_item("node_pressure", node_p_dict)?;
        pressure_dict.set_item("congested_nodes", &pressure_status.congested_nodes)?;
        pressure_dict.set_item(
            "total_backpressure_events",
            pressure_status.total_backpressure_events,
        )?;
        d.set_item("pressure", pressure_dict)?;

        // Entangled channels status
        let ent_status = inner.entangled.get_status();
        let ent_dict = PyDict::new(py);
        let pairs_list: Vec<HashMap<String, String>> = ent_status
            .pairs
            .iter()
            .map(|(a, b)| {
                let mut m = HashMap::new();
                m.insert("a".to_string(), a.clone());
                m.insert("b".to_string(), b.clone());
                m
            })
            .collect();
        ent_dict.set_item("pairs", pairs_list)?;
        ent_dict.set_item(
            "total_entangled_deliveries",
            ent_status.total_entangled_deliveries,
        )?;
        d.set_item("entangled_channels", ent_dict)?;

        // Recent messages (last 20 delivered)
        let delivered_len = inner.delivered.len();
        let start = if delivered_len > 20 {
            delivered_len - 20
        } else {
            0
        };
        let recent_list = pyo3::types::PyList::empty(py);
        for m in &inner.delivered[start..] {
            let entry = PyDict::new(py);
            entry.set_item("id", &m.msg_id)?;
            entry.set_item("source", &m.source)?;
            entry.set_item("destination", &m.destination)?;
            entry.set_item("type", &m.msg_type)?;
            entry.set_item("hops", m.hops.len())?;
            entry.set_item("priority", m.priority_qbc)?;
            recent_list.append(entry)?;
        }
        d.set_item("recent_messages", recent_list)?;

        Ok(d)
    }

    /// Get the current queue size.
    pub fn queue_size(&self) -> usize {
        self.inner.read().queue.len()
    }

    /// Get the total number of delivered messages.
    pub fn total_delivered(&self) -> usize {
        self.inner.read().delivered.len()
    }

    /// Get the total number of dropped messages.
    pub fn total_dropped(&self) -> u64 {
        self.inner.read().dropped
    }

    /// Get the total number of entangled deliveries.
    pub fn total_entangled_deliveries(&self) -> u64 {
        self.inner.read().entangled.entangled_deliveries
    }

    /// Get the list of direct neighbors for a node.
    pub fn get_neighbors(&self, node: String) -> PyResult<Vec<String>> {
        let role = SephirahRole::from_str(&node).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Unknown sephirah: '{}'", node))
        })?;
        let inner = self.inner.read();
        let neighbors = inner.topology.get(&role).cloned().unwrap_or_default();
        Ok(neighbors.iter().map(|r| r.value().to_string()).collect())
    }

    /// Get the normalized pressure for a node (0.0 to 1.0+).
    pub fn get_pressure(&self, node: String) -> PyResult<f64> {
        let role = SephirahRole::from_str(&node).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Unknown sephirah: '{}'", node))
        })?;
        let inner = self.inner.read();
        Ok(inner.pressure.get_pressure(role))
    }

    fn __repr__(&self) -> String {
        let inner = self.inner.read();
        format!(
            "CSFTransport(queue={}, delivered={}, dropped={})",
            inner.queue.len(),
            inner.delivered.len(),
            inner.dropped
        )
    }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

/// Get the current Unix timestamp as f64.
fn current_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // SephirahRole tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_sephirah_role_roundtrip() {
        for role in SephirahRole::all() {
            let s = role.value();
            let parsed = SephirahRole::from_str(s).unwrap();
            assert_eq!(*role, parsed);
        }
    }

    #[test]
    fn test_sephirah_role_case_insensitive() {
        assert_eq!(SephirahRole::from_str("KETER"), Some(SephirahRole::Keter));
        assert_eq!(
            SephirahRole::from_str("Tiferet"),
            Some(SephirahRole::Tiferet)
        );
        assert_eq!(
            SephirahRole::from_str("malkuth"),
            Some(SephirahRole::Malkuth)
        );
    }

    #[test]
    fn test_sephirah_role_invalid() {
        assert_eq!(SephirahRole::from_str("invalid"), None);
        assert_eq!(SephirahRole::from_str(""), None);
    }

    #[test]
    fn test_all_roles_count() {
        assert_eq!(SephirahRole::all().len(), 10);
    }

    // -----------------------------------------------------------------------
    // Topology tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_topology_all_nodes_present() {
        let topo = topology();
        for role in SephirahRole::all() {
            assert!(
                topo.contains_key(role),
                "Topology missing node: {:?}",
                role
            );
        }
    }

    #[test]
    fn test_topology_bidirectional() {
        let topo = topology();
        for (node, neighbors) in &topo {
            for neighbor in neighbors {
                let reverse = topo.get(neighbor).expect("Missing node in topology");
                assert!(
                    reverse.contains(node),
                    "{:?} -> {:?} exists but reverse does not",
                    node,
                    neighbor
                );
            }
        }
    }

    #[test]
    fn test_topology_malkuth_only_yesod() {
        let topo = topology();
        let neighbors = topo.get(&SephirahRole::Malkuth).unwrap();
        assert_eq!(neighbors.len(), 1);
        assert_eq!(neighbors[0], SephirahRole::Yesod);
    }

    #[test]
    fn test_topology_tiferet_is_hub() {
        let topo = topology();
        let neighbors = topo.get(&SephirahRole::Tiferet).unwrap();
        assert_eq!(neighbors.len(), 5); // Chesed, Gevurah, Netzach, Hod, Yesod
    }

    // -----------------------------------------------------------------------
    // CSFMessage tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_message_creation() {
        let msg = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            1.5,
        );
        assert_eq!(msg.source, "keter");
        assert_eq!(msg.destination, "malkuth");
        assert_eq!(msg.msg_type, "signal");
        assert_eq!(msg.msg_id.len(), 16);
        assert!(!msg.delivered);
        assert_eq!(msg.ttl, DEFAULT_TTL);
        assert!(msg.timestamp > 0.0);
        assert!(msg.hops.is_empty());
        assert!((msg.priority_qbc - 1.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_message_unique_ids() {
        let msg1 = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            0.0,
        );
        // Tiny delay to ensure different timestamp
        std::thread::sleep(std::time::Duration::from_millis(1));
        let msg2 = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            0.0,
        );
        // IDs should differ because timestamp differs
        assert_ne!(msg1.msg_id, msg2.msg_id);
    }

    #[test]
    fn test_message_current_position() {
        let mut msg = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            0.0,
        );
        // No hops yet -- position is source
        assert_eq!(msg.current_position(), Some(SephirahRole::Keter));

        msg.hops.push("tiferet".to_string());
        assert_eq!(msg.current_position(), Some(SephirahRole::Tiferet));
    }

    // -----------------------------------------------------------------------
    // PressureMonitor tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_pressure_initial_zero() {
        let pm = PressureMonitor::new(50);
        for role in SephirahRole::all() {
            assert!((pm.get_pressure(*role) - 0.0).abs() < f64::EPSILON);
            assert!(!pm.is_congested(*role));
        }
    }

    #[test]
    fn test_pressure_enqueue_dequeue() {
        let mut pm = PressureMonitor::new(50);
        pm.record_enqueue(SephirahRole::Keter);
        pm.record_enqueue(SephirahRole::Keter);
        assert!((pm.get_pressure(SephirahRole::Keter) - 2.0 / 50.0).abs() < f64::EPSILON);

        pm.record_dequeue(SephirahRole::Keter);
        assert!((pm.get_pressure(SephirahRole::Keter) - 1.0 / 50.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_pressure_dequeue_floor_zero() {
        let mut pm = PressureMonitor::new(50);
        pm.record_dequeue(SephirahRole::Keter);
        assert!((pm.get_pressure(SephirahRole::Keter) - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_pressure_congestion_threshold() {
        let mut pm = PressureMonitor::new(50);
        // Threshold = 50 * 0.8 = 40
        for _ in 0..39 {
            pm.record_enqueue(SephirahRole::Tiferet);
        }
        assert!(!pm.is_congested(SephirahRole::Tiferet));

        pm.record_enqueue(SephirahRole::Tiferet); // 40th
        assert!(pm.is_congested(SephirahRole::Tiferet));
    }

    #[test]
    fn test_pressure_least_congested_neighbor() {
        let mut pm = PressureMonitor::new(50);
        pm.record_enqueue(SephirahRole::Chochmah);
        pm.record_enqueue(SephirahRole::Chochmah);
        pm.record_enqueue(SephirahRole::Binah);
        // Binah=1, Chochmah=2 => least congested = Binah
        let neighbors = vec![SephirahRole::Chochmah, SephirahRole::Binah];
        assert_eq!(
            pm.get_least_congested_neighbor(&neighbors),
            Some(SephirahRole::Binah)
        );
    }

    #[test]
    fn test_pressure_least_congested_empty() {
        let pm = PressureMonitor::new(50);
        assert_eq!(pm.get_least_congested_neighbor(&[]), None);
    }

    #[test]
    fn test_pressure_status() {
        let mut pm = PressureMonitor::new(50);
        pm.record_enqueue(SephirahRole::Keter);
        pm.record_backpressure();
        let status = pm.get_status();
        assert_eq!(status.total_backpressure_events, 1);
        assert!(status.congested_nodes.is_empty());
        let keter_pressure = status.node_pressure.get("keter").unwrap();
        assert!((*keter_pressure - 1.0 / 50.0).abs() < 0.001);
    }

    // -----------------------------------------------------------------------
    // QuantumEntangledChannel tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_entangled_susy_pairs() {
        let qec = QuantumEntangledChannel::new();
        // SUSY pairs should be entangled
        assert!(qec.is_entangled(SephirahRole::Chesed, SephirahRole::Gevurah));
        assert!(qec.is_entangled(SephirahRole::Gevurah, SephirahRole::Chesed));
        assert!(qec.is_entangled(SephirahRole::Chochmah, SephirahRole::Binah));
        assert!(qec.is_entangled(SephirahRole::Binah, SephirahRole::Chochmah));
        assert!(qec.is_entangled(SephirahRole::Netzach, SephirahRole::Hod));
        assert!(qec.is_entangled(SephirahRole::Hod, SephirahRole::Netzach));
    }

    #[test]
    fn test_entangled_non_pairs() {
        let qec = QuantumEntangledChannel::new();
        // Non-SUSY pairs should NOT be entangled
        assert!(!qec.is_entangled(SephirahRole::Keter, SephirahRole::Malkuth));
        assert!(!qec.is_entangled(SephirahRole::Tiferet, SephirahRole::Yesod));
        assert!(!qec.is_entangled(SephirahRole::Chesed, SephirahRole::Binah));
        assert!(!qec.is_entangled(SephirahRole::Keter, SephirahRole::Keter));
    }

    #[test]
    fn test_entangled_delivery() {
        let mut qec = QuantumEntangledChannel::new();
        let mut msg = CSFMessage::new_internal(
            SephirahRole::Chesed,
            SephirahRole::Gevurah,
            "signal",
            "{}".to_string(),
            0.0,
        );
        assert!(!msg.delivered);
        assert_eq!(qec.entangled_deliveries, 0);

        qec.deliver_entangled(&mut msg);
        assert!(msg.delivered);
        assert_eq!(msg.hops.len(), 1);
        assert!(msg.hops[0].contains("entangled"));
        assert!(msg.hops[0].contains("gevurah"));
        assert_eq!(qec.entangled_deliveries, 1);
    }

    #[test]
    fn test_entangled_get_partner() {
        let qec = QuantumEntangledChannel::new();
        assert_eq!(qec.get_partner(SephirahRole::Chesed), Some(SephirahRole::Gevurah));
        assert_eq!(qec.get_partner(SephirahRole::Gevurah), Some(SephirahRole::Chesed));
        assert_eq!(qec.get_partner(SephirahRole::Keter), None);
        assert_eq!(qec.get_partner(SephirahRole::Malkuth), None);
    }

    #[test]
    fn test_entangled_status() {
        let qec = QuantumEntangledChannel::new();
        let status = qec.get_status();
        assert_eq!(status.pairs.len(), 3);
        assert_eq!(status.total_entangled_deliveries, 0);
    }

    // -----------------------------------------------------------------------
    // CSFTransportInner -- find_path tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_find_path_same_node() {
        let inner = CSFTransportInner::new();
        let path = inner.find_path(SephirahRole::Keter, SephirahRole::Keter);
        assert_eq!(path, vec![SephirahRole::Keter]);
    }

    #[test]
    fn test_find_path_direct_neighbor() {
        let inner = CSFTransportInner::new();
        let path = inner.find_path(SephirahRole::Keter, SephirahRole::Chochmah);
        assert_eq!(path, vec![SephirahRole::Keter, SephirahRole::Chochmah]);
    }

    #[test]
    fn test_find_path_keter_to_malkuth() {
        let inner = CSFTransportInner::new();
        let path = inner.find_path(SephirahRole::Keter, SephirahRole::Malkuth);
        // Must pass through several nodes; shortest path length >= 4
        assert!(path.len() >= 4);
        assert_eq!(*path.first().unwrap(), SephirahRole::Keter);
        assert_eq!(*path.last().unwrap(), SephirahRole::Malkuth);

        // Validate each step is a valid topology edge
        for w in path.windows(2) {
            let topo = topology();
            let neighbors = topo.get(&w[0]).unwrap();
            assert!(
                neighbors.contains(&w[1]),
                "{:?} -> {:?} is not a topology edge",
                w[0],
                w[1]
            );
        }
    }

    #[test]
    fn test_find_path_malkuth_to_keter() {
        let inner = CSFTransportInner::new();
        let path = inner.find_path(SephirahRole::Malkuth, SephirahRole::Keter);
        assert!(path.len() >= 4);
        assert_eq!(*path.first().unwrap(), SephirahRole::Malkuth);
        assert_eq!(*path.last().unwrap(), SephirahRole::Keter);
    }

    #[test]
    fn test_find_path_all_pairs_connected() {
        let inner = CSFTransportInner::new();
        // The Tree of Life topology is fully connected -- all pairs should have a path
        for src in SephirahRole::all() {
            for dst in SephirahRole::all() {
                let path = inner.find_path(*src, *dst);
                assert!(
                    !path.is_empty(),
                    "No path from {:?} to {:?}",
                    src,
                    dst
                );
            }
        }
    }

    #[test]
    fn test_find_next_hop_direct_neighbor() {
        let inner = CSFTransportInner::new();
        let hop = inner.find_next_hop(SephirahRole::Keter, SephirahRole::Chochmah);
        assert_eq!(hop, Some(SephirahRole::Chochmah));
    }

    #[test]
    fn test_find_next_hop_multi_hop() {
        let inner = CSFTransportInner::new();
        let hop = inner.find_next_hop(SephirahRole::Keter, SephirahRole::Malkuth);
        // First hop from Keter toward Malkuth must be Chochmah or Binah
        assert!(
            hop == Some(SephirahRole::Chochmah) || hop == Some(SephirahRole::Binah),
            "Unexpected first hop: {:?}",
            hop
        );
    }

    // -----------------------------------------------------------------------
    // CSFTransportInner -- send tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_send_normal_message() {
        let mut inner = CSFTransportInner::new();
        let msg = inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            1.0,
        );
        assert!(!msg.delivered);
        assert_eq!(msg.hops, vec!["keter"]);
        assert_eq!(inner.queue.len(), 1);
        assert_eq!(inner.delivered.len(), 0);
    }

    #[test]
    fn test_send_entangled_instant_delivery() {
        let mut inner = CSFTransportInner::new();
        let msg = inner.send(
            SephirahRole::Chesed,
            SephirahRole::Gevurah,
            "{}".to_string(),
            "signal",
            1.0,
        );
        // SUSY pair -> instant delivery
        assert!(msg.delivered);
        assert_eq!(inner.queue.len(), 0);
        assert_eq!(inner.delivered.len(), 1);
        // Hops should have the initial source and entangled marker
        assert_eq!(msg.hops.len(), 2); // source + entangled hop
        assert!(msg.hops[1].contains("entangled"));
    }

    #[test]
    fn test_send_entangled_reverse_pair() {
        let mut inner = CSFTransportInner::new();
        let msg = inner.send(
            SephirahRole::Gevurah,
            SephirahRole::Chesed,
            "{}".to_string(),
            "signal",
            1.0,
        );
        assert!(msg.delivered);
        assert_eq!(inner.queue.len(), 0);
    }

    #[test]
    fn test_send_priority_ordering() {
        let mut inner = CSFTransportInner::new();
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "low".to_string(),
            "signal",
            1.0,
        );
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "high".to_string(),
            "signal",
            10.0,
        );
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "mid".to_string(),
            "signal",
            5.0,
        );
        assert_eq!(inner.queue.len(), 3);
        // Queue should be sorted by priority descending
        assert_eq!(inner.queue[0].payload, "high");
        assert_eq!(inner.queue[1].payload, "mid");
        assert_eq!(inner.queue[2].payload, "low");
    }

    #[test]
    fn test_send_backpressure_halves_priority() {
        let mut inner = CSFTransportInner::new();
        // Congest Malkuth: threshold = 50 * 0.8 = 40
        for _ in 0..40 {
            inner.pressure.record_enqueue(SephirahRole::Malkuth);
        }
        assert!(inner.pressure.is_congested(SephirahRole::Malkuth));

        let msg = inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            10.0,
        );
        // Priority should be halved due to backpressure
        assert!((msg.priority_qbc - 5.0).abs() < f64::EPSILON);
        assert!(inner.pressure.total_backpressure_events > 0);
    }

    // -----------------------------------------------------------------------
    // CSFTransportInner -- broadcast tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_broadcast_sends_to_all_neighbors() {
        let mut inner = CSFTransportInner::new();
        let msgs = inner.broadcast(SephirahRole::Tiferet, "{}".to_string(), 1.0);
        // Tiferet has 5 neighbors: Chesed, Gevurah, Netzach, Hod, Yesod
        // Chesed -> Gevurah is a SUSY pair -> entangled not applicable here since
        // we're sending FROM Tiferet
        // Tiferet -> Gevurah is NOT a SUSY pair
        // All should be broadcast type
        assert_eq!(msgs.len(), 5);
        for msg in &msgs {
            assert_eq!(msg.msg_type, "broadcast");
            assert_eq!(msg.source, "tiferet");
        }
    }

    #[test]
    fn test_broadcast_from_malkuth() {
        let mut inner = CSFTransportInner::new();
        let msgs = inner.broadcast(SephirahRole::Malkuth, "{}".to_string(), 0.5);
        // Malkuth only connects to Yesod
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].destination, "yesod");
    }

    #[test]
    fn test_broadcast_keter() {
        let mut inner = CSFTransportInner::new();
        let msgs = inner.broadcast(SephirahRole::Keter, "test".to_string(), 2.0);
        // Keter connects to Chochmah and Binah
        assert_eq!(msgs.len(), 2);
        let dests: HashSet<String> = msgs.iter().map(|m| m.destination.clone()).collect();
        assert!(dests.contains("chochmah"));
        assert!(dests.contains("binah"));
        // Chochmah/Binah is a SUSY pair, but Keter->Chochmah is not
        // so neither should be instant-delivered
        // Wait -- Keter->Chochmah is NOT a SUSY pair, and Keter->Binah is NOT a SUSY pair
        // So both should be queued normally
    }

    #[test]
    fn test_broadcast_with_entangled_pair() {
        let mut inner = CSFTransportInner::new();
        // Chesed connects to: Chochmah, Gevurah, Tiferet
        // Chesed -> Gevurah is a SUSY pair => instant delivery
        let msgs = inner.broadcast(SephirahRole::Chesed, "{}".to_string(), 1.0);
        assert_eq!(msgs.len(), 3);

        let mut entangled_count = 0;
        let mut queued_count = 0;
        for msg in &msgs {
            if msg.delivered {
                entangled_count += 1;
                assert_eq!(msg.destination, "gevurah");
            } else {
                queued_count += 1;
            }
        }
        assert_eq!(entangled_count, 1);
        assert_eq!(queued_count, 2);
        // Queue should have 2 messages (Chochmah, Tiferet)
        assert_eq!(inner.queue.len(), 2);
    }

    // -----------------------------------------------------------------------
    // CSFTransportInner -- process_queue tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_process_queue_direct_neighbor_delivery() {
        let mut inner = CSFTransportInner::new();
        // Send from Keter to Chochmah (direct neighbor)
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Chochmah,
            "{}".to_string(),
            "signal",
            1.0,
        );
        assert_eq!(inner.queue.len(), 1);

        let delivered = inner.process_queue(100);
        assert_eq!(delivered.len(), 1);
        assert!(delivered[0].delivered);
        assert_eq!(delivered[0].destination, "chochmah");
        assert_eq!(inner.queue.len(), 0);
    }

    #[test]
    fn test_process_queue_multi_hop() {
        let mut inner = CSFTransportInner::new();
        // Send from Keter to Malkuth (multi-hop: Keter -> ... -> Yesod -> Malkuth)
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            1.0,
        );

        // Process multiple rounds until delivered
        let mut total_delivered = 0;
        for _ in 0..10 {
            let delivered = inner.process_queue(100);
            total_delivered += delivered.len();
            if total_delivered > 0 {
                break;
            }
        }
        assert!(
            total_delivered > 0,
            "Message from Keter to Malkuth should eventually be delivered"
        );
    }

    #[test]
    fn test_process_queue_ttl_expiry() {
        let mut inner = CSFTransportInner::new();
        // Create a message with TTL=0 (already expired)
        let mut msg = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            1.0,
        );
        msg.ttl = 0;
        msg.hops.push("keter".to_string());
        inner.queue.push(msg);
        inner.pressure.record_enqueue(SephirahRole::Malkuth);

        let delivered = inner.process_queue(100);
        assert_eq!(delivered.len(), 0);
        assert_eq!(inner.dropped, 1);
        assert_eq!(inner.queue.len(), 0);
    }

    #[test]
    fn test_process_queue_ttl_decrement() {
        let mut inner = CSFTransportInner::new();
        // Keter to Malkuth requires multiple hops; TTL should decrement each intermediate hop
        let mut msg = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "signal",
            "{}".to_string(),
            1.0,
        );
        msg.ttl = 5;
        msg.hops.push("keter".to_string());
        inner.queue.push(msg);
        inner.pressure.record_enqueue(SephirahRole::Malkuth);

        // First process: Keter -> next hop (not Malkuth), TTL should decrement
        let delivered = inner.process_queue(100);
        if delivered.is_empty() {
            // Not yet delivered -- should be in remaining queue with decremented TTL
            assert_eq!(inner.queue.len(), 1);
            assert!(inner.queue[0].ttl < 5);
        }
    }

    #[test]
    fn test_process_queue_max_messages_limit() {
        let mut inner = CSFTransportInner::new();
        // Enqueue 5 messages
        for i in 0..5 {
            inner.send(
                SephirahRole::Keter,
                SephirahRole::Chochmah,
                format!("{{{}}}", i),
                "signal",
                i as f64,
            );
        }
        assert_eq!(inner.queue.len(), 5);

        // Process only 2
        let delivered = inner.process_queue(2);
        // The 2 highest-priority should have been processed (both direct neighbors -> delivered)
        assert_eq!(delivered.len(), 2);
        // Remaining 3 should still be in queue
        assert_eq!(inner.queue.len(), 3);
    }

    #[test]
    fn test_process_queue_same_source_destination() {
        let mut inner = CSFTransportInner::new();
        // Send a message where source == destination (edge case)
        let mut msg = CSFMessage::new_internal(
            SephirahRole::Keter,
            SephirahRole::Keter,
            "signal",
            "{}".to_string(),
            1.0,
        );
        msg.hops.push("keter".to_string());
        inner.queue.push(msg);
        inner.pressure.record_enqueue(SephirahRole::Keter);

        let delivered = inner.process_queue(100);
        assert_eq!(delivered.len(), 1);
        assert!(delivered[0].delivered);
    }

    #[test]
    fn test_process_queue_full_delivery_keter_to_malkuth() {
        let mut inner = CSFTransportInner::new();
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            1.0,
        );

        // Run process_queue enough times to ensure delivery
        let mut rounds = 0;
        while inner.queue.len() > 0 && rounds < 20 {
            inner.process_queue(100);
            rounds += 1;
        }
        // Message should be delivered
        assert_eq!(inner.queue.len(), 0);
        assert!(inner.delivered.len() > 0);
        let last = inner.delivered.last().unwrap();
        assert!(last.delivered);
        assert_eq!(last.destination, "malkuth");
    }

    #[test]
    fn test_process_queue_preserves_unprocessed() {
        let mut inner = CSFTransportInner::new();
        // Add 5 messages, process 2 -- the 3 unprocessed should remain
        for _ in 0..5 {
            inner.send(
                SephirahRole::Malkuth,
                SephirahRole::Keter,
                "{}".to_string(),
                "signal",
                1.0,
            );
        }
        let before = inner.queue.len();
        assert_eq!(before, 5);

        inner.process_queue(2);
        // 2 processed: if routing to non-neighbor, they go to remaining
        // 3 unprocessed stay in queue
        // Total should be <= 5 (some may have been delivered or moved to remaining)
        assert!(inner.queue.len() <= 5);
    }

    // -----------------------------------------------------------------------
    // CSFTransportInner -- integration tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_entangled_delivery_via_send() {
        let mut inner = CSFTransportInner::new();

        // All 3 SUSY pairs should get instant delivery
        let pairs = vec![
            (SephirahRole::Chesed, SephirahRole::Gevurah),
            (SephirahRole::Chochmah, SephirahRole::Binah),
            (SephirahRole::Netzach, SephirahRole::Hod),
        ];
        for (src, dst) in &pairs {
            let msg = inner.send(*src, *dst, "{}".to_string(), "signal", 1.0);
            assert!(
                msg.delivered,
                "Expected instant delivery for SUSY pair {:?}->{:?}",
                src,
                dst
            );
        }
        assert_eq!(inner.queue.len(), 0);
        assert_eq!(inner.delivered.len(), 3);
        assert_eq!(inner.entangled.entangled_deliveries, 3);
    }

    #[test]
    fn test_backpressure_reduces_priority_then_recovers() {
        let mut inner = CSFTransportInner::new();

        // Congest Malkuth
        for _ in 0..40 {
            inner.pressure.record_enqueue(SephirahRole::Malkuth);
        }

        // Send with priority 8.0 -- should be halved to 4.0
        let msg = inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            8.0,
        );
        assert!((msg.priority_qbc - 4.0).abs() < f64::EPSILON);

        // Relieve congestion
        for _ in 0..10 {
            inner.pressure.record_dequeue(SephirahRole::Malkuth);
        }
        // Malkuth now at 30 (below 40 threshold) -- not congested
        assert!(!inner.pressure.is_congested(SephirahRole::Malkuth));

        // Send again -- priority should NOT be halved
        let msg2 = inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            8.0,
        );
        assert!((msg2.priority_qbc - 8.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_stats_accuracy() {
        let mut inner = CSFTransportInner::new();

        // Send 2 normal + 1 entangled
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Chochmah,
            "{}".to_string(),
            "signal",
            1.0,
        );
        inner.send(
            SephirahRole::Tiferet,
            SephirahRole::Yesod,
            "{}".to_string(),
            "query",
            2.0,
        );
        inner.send(
            SephirahRole::Chesed,
            SephirahRole::Gevurah,
            "{}".to_string(),
            "signal",
            3.0,
        );

        assert_eq!(inner.queue.len(), 2);
        assert_eq!(inner.delivered.len(), 1); // entangled
        assert_eq!(inner.entangled.entangled_deliveries, 1);

        // Process queue
        let delivered = inner.process_queue(100);
        assert_eq!(delivered.len(), 2); // Both are direct neighbors
        assert_eq!(inner.queue.len(), 0);
        assert_eq!(inner.delivered.len(), 3); // 1 entangled + 2 normal
    }

    #[test]
    fn test_message_hops_trace() {
        let mut inner = CSFTransportInner::new();

        // Keter -> Malkuth: trace the full hop path
        inner.send(
            SephirahRole::Keter,
            SephirahRole::Malkuth,
            "{}".to_string(),
            "signal",
            1.0,
        );

        let mut rounds = 0;
        while !inner.queue.is_empty() && rounds < 20 {
            inner.process_queue(100);
            rounds += 1;
        }

        let msg = inner.delivered.last().unwrap();
        assert!(msg.delivered);
        // Hops should start with "keter" and end with "malkuth"
        assert_eq!(msg.hops.first().unwrap(), "keter");
        assert_eq!(msg.hops.last().unwrap(), "malkuth");
        // Each hop should be a valid sephirah name
        for hop in &msg.hops {
            assert!(
                SephirahRole::from_str(hop).is_some(),
                "Invalid hop in trace: '{}'",
                hop
            );
        }
        // Consecutive hops should be topology neighbors
        for w in msg.hops.windows(2) {
            let a = SephirahRole::from_str(&w[0]).unwrap();
            let b = SephirahRole::from_str(&w[1]).unwrap();
            let neighbors = inner.topology.get(&a).unwrap();
            assert!(
                neighbors.contains(&b),
                "Hop {:?} -> {:?} not in topology",
                a,
                b
            );
        }
    }

    #[test]
    fn test_concurrent_access_via_arc() {
        // Verify the Arc<RwLock> pattern compiles and works
        let inner = Arc::new(RwLock::new(CSFTransportInner::new()));

        // Writer
        {
            let mut w = inner.write();
            w.send(
                SephirahRole::Keter,
                SephirahRole::Chochmah,
                "{}".to_string(),
                "signal",
                1.0,
            );
        }

        // Reader
        {
            let r = inner.read();
            assert_eq!(r.queue.len(), 1);
        }

        // Process
        {
            let mut w = inner.write();
            let delivered = w.process_queue(100);
            assert_eq!(delivered.len(), 1);
        }
    }

    #[test]
    fn test_dropped_count_with_ttl_zero() {
        let mut inner = CSFTransportInner::new();
        // Create 3 messages with TTL=0
        for _ in 0..3 {
            let mut msg = CSFMessage::new_internal(
                SephirahRole::Keter,
                SephirahRole::Malkuth,
                "signal",
                "{}".to_string(),
                1.0,
            );
            msg.ttl = 0;
            msg.hops.push("keter".to_string());
            inner.queue.push(msg);
            inner.pressure.record_enqueue(SephirahRole::Malkuth);
        }
        inner.process_queue(100);
        assert_eq!(inner.dropped, 3);
    }

    #[test]
    fn test_find_path_returns_string_values() {
        // Test the public find_path that returns Vec<SephirahRole>
        let inner = CSFTransportInner::new();
        let path = inner.find_path(SephirahRole::Keter, SephirahRole::Tiferet);
        assert!(!path.is_empty());
        // Verify path values are valid sephirah names
        for role in &path {
            assert!(SephirahRole::from_str(role.value()).is_some());
        }
    }

    #[test]
    fn test_empty_queue_process() {
        let mut inner = CSFTransportInner::new();
        let delivered = inner.process_queue(100);
        assert!(delivered.is_empty());
        assert_eq!(inner.dropped, 0);
    }

    #[test]
    fn test_multiple_entangled_deliveries() {
        let mut inner = CSFTransportInner::new();
        // Send 10 entangled messages
        for _ in 0..10 {
            inner.send(
                SephirahRole::Chesed,
                SephirahRole::Gevurah,
                "{}".to_string(),
                "signal",
                1.0,
            );
        }
        assert_eq!(inner.queue.len(), 0);
        assert_eq!(inner.delivered.len(), 10);
        assert_eq!(inner.entangled.entangled_deliveries, 10);
    }
}
