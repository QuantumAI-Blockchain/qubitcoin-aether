//! Partial Ancestral Graph (PAG) data structures for FCI algorithm output.
//!
//! A PAG represents an equivalence class of MAGs (Maximal Ancestral Graphs)
//! that are Markov equivalent given the observed conditional independencies.
//!
//! Edge endpoint marks:
//! - Tail  `-`  : definite non-ancestor
//! - Arrow `>`  : definite ancestor
//! - Circle `o` : ambiguous (could be tail or arrow)

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

/// Edge endpoint mark in a PAG.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EndpointMark {
    Tail,
    Arrow,
    Circle,
}

impl EndpointMark {
    pub fn as_str(&self) -> &'static str {
        match self {
            EndpointMark::Tail => "-",
            EndpointMark::Arrow => ">",
            EndpointMark::Circle => "o",
        }
    }

    pub fn display_char(&self) -> char {
        match self {
            EndpointMark::Tail => '-',
            EndpointMark::Arrow => '>',
            EndpointMark::Circle => 'o',
        }
    }
}

impl std::fmt::Display for EndpointMark {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// An edge in a Partial Ancestral Graph.
///
/// Each edge has two endpoints with marks at each node.
/// - `mark_a='>' and mark_b='-'` means A <-- B (B causes A)
/// - `mark_a='-' and mark_b='>'` means A --> B (A causes B)
/// - `mark_a='>' and mark_b='>'` means A <-> B (bidirected / latent confounder)
/// - `mark_a='o' and mark_b='>'` means A o-> B (A possibly causes B)
/// - `mark_a='o' and mark_b='o'` means A o-o B (fully ambiguous)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PAGEdge {
    pub node_a: i64,
    pub node_b: i64,
    pub mark_a: EndpointMark,
    pub mark_b: EndpointMark,
}

impl PAGEdge {
    pub fn new(node_a: i64, node_b: i64, mark_a: EndpointMark, mark_b: EndpointMark) -> Self {
        Self { node_a, node_b, mark_a, mark_b }
    }

    /// True if A --> B (tail at A, arrow at B).
    pub fn is_directed(&self) -> bool {
        self.mark_a == EndpointMark::Tail && self.mark_b == EndpointMark::Arrow
    }

    /// True if A <-> B (arrow at both ends — latent confounder).
    pub fn is_bidirected(&self) -> bool {
        self.mark_a == EndpointMark::Arrow && self.mark_b == EndpointMark::Arrow
    }

    /// True if A o-> B (circle at A, arrow at B).
    pub fn is_partially_directed(&self) -> bool {
        self.mark_a == EndpointMark::Circle && self.mark_b == EndpointMark::Arrow
    }

    /// True if A o-o B (circle at both ends).
    pub fn is_nondirected(&self) -> bool {
        self.mark_a == EndpointMark::Circle && self.mark_b == EndpointMark::Circle
    }

    /// Check if there is an arrowhead at the given node.
    pub fn has_arrowhead_at(&self, node: i64) -> bool {
        if node == self.node_a { self.mark_a == EndpointMark::Arrow }
        else if node == self.node_b { self.mark_b == EndpointMark::Arrow }
        else { false }
    }

    /// Check if there is a tail at the given node.
    pub fn has_tail_at(&self, node: i64) -> bool {
        if node == self.node_a { self.mark_a == EndpointMark::Tail }
        else if node == self.node_b { self.mark_b == EndpointMark::Tail }
        else { false }
    }

    /// Check if there is a circle at the given node.
    pub fn has_circle_at(&self, node: i64) -> bool {
        if node == self.node_a { self.mark_a == EndpointMark::Circle }
        else if node == self.node_b { self.mark_b == EndpointMark::Circle }
        else { false }
    }

    /// Get the endpoint mark at the specified node.
    pub fn get_mark_at(&self, node: i64) -> Option<EndpointMark> {
        if node == self.node_a { Some(self.mark_a) }
        else if node == self.node_b { Some(self.mark_b) }
        else { None }
    }

    /// Set the endpoint mark at the specified node.
    pub fn set_mark_at(&mut self, node: i64, mark: EndpointMark) {
        if node == self.node_a {
            self.mark_a = mark;
        } else if node == self.node_b {
            self.mark_b = mark;
        }
    }

    /// Return the other node in this edge.
    pub fn other_node(&self, node: i64) -> Option<i64> {
        if node == self.node_a { Some(self.node_b) }
        else if node == self.node_b { Some(self.node_a) }
        else { None }
    }

    /// Canonical pair key (min, max) for HashMap storage.
    pub fn canonical_key(&self) -> (i64, i64) {
        (self.node_a.min(self.node_b), self.node_a.max(self.node_b))
    }

    /// Human-readable edge type string.
    pub fn edge_type_str(&self) -> &'static str {
        if self.is_directed() { "directed" }
        else if self.is_bidirected() { "bidirected" }
        else if self.mark_a == EndpointMark::Arrow && self.mark_b == EndpointMark::Tail { "directed_reverse" }
        else if self.is_partially_directed() { "partially_directed" }
        else if self.mark_a == EndpointMark::Arrow && self.mark_b == EndpointMark::Circle { "partially_directed_reverse" }
        else if self.is_nondirected() { "nondirected" }
        else { "other" }
    }
}

impl std::fmt::Display for PAGEdge {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let left = match self.mark_a {
            EndpointMark::Arrow => '<',
            EndpointMark::Circle => 'o',
            EndpointMark::Tail => '-',
        };
        let right = self.mark_b.display_char();
        write!(f, "PAGEdge({} {}--{} {})", self.node_a, left, right, self.node_b)
    }
}

/// Partial Ancestral Graph — the output of the FCI algorithm.
///
/// Edges are stored keyed by canonical pair (min, max) to ensure
/// a single entry per undirected pair.
#[derive(Debug)]
pub struct PAG {
    pub edges: HashMap<(i64, i64), PAGEdge>,
    pub nodes: HashSet<i64>,
}

impl PAG {
    pub fn new() -> Self {
        Self {
            edges: HashMap::new(),
            nodes: HashSet::new(),
        }
    }

    /// Add or update an edge in the PAG.
    pub fn add_edge(&mut self, node_a: i64, node_b: i64, mark_a: EndpointMark, mark_b: EndpointMark) -> &PAGEdge {
        self.nodes.insert(node_a);
        self.nodes.insert(node_b);
        let key = (node_a.min(node_b), node_a.max(node_b));
        let edge = PAGEdge::new(node_a, node_b, mark_a, mark_b);
        self.edges.insert(key, edge);
        &self.edges[&key]
    }

    /// Get edge between two nodes, or None if not present.
    pub fn get_edge(&self, node_a: i64, node_b: i64) -> Option<&PAGEdge> {
        let key = (node_a.min(node_b), node_a.max(node_b));
        self.edges.get(&key)
    }

    /// Get mutable edge between two nodes.
    pub fn get_edge_mut(&mut self, node_a: i64, node_b: i64) -> Option<&mut PAGEdge> {
        let key = (node_a.min(node_b), node_a.max(node_b));
        self.edges.get_mut(&key)
    }

    /// Check if an edge exists between two nodes.
    pub fn has_edge(&self, node_a: i64, node_b: i64) -> bool {
        let key = (node_a.min(node_b), node_a.max(node_b));
        self.edges.contains_key(&key)
    }

    /// Remove an edge from the PAG.
    pub fn remove_edge(&mut self, node_a: i64, node_b: i64) {
        let key = (node_a.min(node_b), node_a.max(node_b));
        self.edges.remove(&key);
    }

    /// Get all nodes adjacent to the given node.
    pub fn get_adjacent(&self, node: i64) -> Vec<i64> {
        let mut neighbors = Vec::new();
        for edge in self.edges.values() {
            if let Some(other) = edge.other_node(node) {
                neighbors.push(other);
            }
        }
        neighbors
    }

    /// Get all edges that have an arrowhead pointing at the given node.
    pub fn get_edges_with_arrowhead_at(&self, node: i64) -> Vec<&PAGEdge> {
        self.edges.values()
            .filter(|e| e.has_arrowhead_at(node))
            .collect()
    }

    /// Get all definitely directed edges (A --> B or B --> A).
    pub fn get_directed_edges(&self) -> Vec<&PAGEdge> {
        self.edges.values()
            .filter(|e| e.is_directed() || (e.mark_a == EndpointMark::Arrow && e.mark_b == EndpointMark::Tail))
            .collect()
    }

    /// Get all bidirected edges (A <-> B).
    pub fn get_bidirected_edges(&self) -> Vec<&PAGEdge> {
        self.edges.values().filter(|e| e.is_bidirected()).collect()
    }

    /// Get all partially directed edges.
    pub fn get_partially_directed_edges(&self) -> Vec<&PAGEdge> {
        self.edges.values()
            .filter(|e| e.is_partially_directed()
                || (e.mark_a == EndpointMark::Arrow && e.mark_b == EndpointMark::Circle))
            .collect()
    }

    /// Get all nondirected edges (A o-o B).
    pub fn get_nondirected_edges(&self) -> Vec<&PAGEdge> {
        self.edges.values().filter(|e| e.is_nondirected()).collect()
    }

    /// Summary statistics.
    pub fn summary(&self) -> PAGSummary {
        PAGSummary {
            total_edges: self.edges.len(),
            directed: self.get_directed_edges().len(),
            bidirected: self.get_bidirected_edges().len(),
            partially_directed: self.get_partially_directed_edges().len(),
            nondirected: self.get_nondirected_edges().len(),
            total_nodes: self.nodes.len(),
        }
    }
}

impl Default for PAG {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Display for PAG {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = self.summary();
        write!(f, "PAG(nodes={}, edges={}, directed={}, bidirected={})",
            s.total_nodes, s.total_edges, s.directed, s.bidirected)
    }
}

/// Summary statistics for a PAG.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PAGSummary {
    pub total_edges: usize,
    pub directed: usize,
    pub bidirected: usize,
    pub partially_directed: usize,
    pub nondirected: usize,
    pub total_nodes: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_endpoint_mark_display() {
        assert_eq!(EndpointMark::Tail.as_str(), "-");
        assert_eq!(EndpointMark::Arrow.as_str(), ">");
        assert_eq!(EndpointMark::Circle.as_str(), "o");
    }

    #[test]
    fn test_pag_edge_directed() {
        let e = PAGEdge::new(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        assert!(e.is_directed());
        assert!(!e.is_bidirected());
        assert!(!e.is_nondirected());
        assert!(!e.is_partially_directed());
        assert_eq!(e.edge_type_str(), "directed");
    }

    #[test]
    fn test_pag_edge_bidirected() {
        let e = PAGEdge::new(1, 2, EndpointMark::Arrow, EndpointMark::Arrow);
        assert!(!e.is_directed());
        assert!(e.is_bidirected());
        assert_eq!(e.edge_type_str(), "bidirected");
    }

    #[test]
    fn test_pag_edge_partially_directed() {
        let e = PAGEdge::new(1, 2, EndpointMark::Circle, EndpointMark::Arrow);
        assert!(e.is_partially_directed());
        assert_eq!(e.edge_type_str(), "partially_directed");
    }

    #[test]
    fn test_pag_edge_nondirected() {
        let e = PAGEdge::new(1, 2, EndpointMark::Circle, EndpointMark::Circle);
        assert!(e.is_nondirected());
        assert_eq!(e.edge_type_str(), "nondirected");
    }

    #[test]
    fn test_pag_edge_arrowhead_at() {
        let e = PAGEdge::new(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        assert!(!e.has_arrowhead_at(1));
        assert!(e.has_arrowhead_at(2));
        assert!(!e.has_arrowhead_at(3));
    }

    #[test]
    fn test_pag_edge_set_mark() {
        let mut e = PAGEdge::new(1, 2, EndpointMark::Circle, EndpointMark::Circle);
        e.set_mark_at(2, EndpointMark::Arrow);
        assert_eq!(e.mark_b, EndpointMark::Arrow);
        assert!(e.is_partially_directed());
    }

    #[test]
    fn test_pag_edge_other_node() {
        let e = PAGEdge::new(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        assert_eq!(e.other_node(1), Some(2));
        assert_eq!(e.other_node(2), Some(1));
        assert_eq!(e.other_node(3), None);
    }

    #[test]
    fn test_pag_edge_canonical_key() {
        let e1 = PAGEdge::new(5, 3, EndpointMark::Tail, EndpointMark::Arrow);
        let e2 = PAGEdge::new(3, 5, EndpointMark::Arrow, EndpointMark::Tail);
        assert_eq!(e1.canonical_key(), (3, 5));
        assert_eq!(e2.canonical_key(), (3, 5));
    }

    #[test]
    fn test_pag_add_and_get() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        assert!(pag.has_edge(1, 2));
        assert!(pag.has_edge(2, 1)); // Undirected lookup
        assert!(!pag.has_edge(1, 3));
    }

    #[test]
    fn test_pag_get_adjacent() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        pag.add_edge(1, 3, EndpointMark::Circle, EndpointMark::Circle);
        let adj = pag.get_adjacent(1);
        assert_eq!(adj.len(), 2);
        assert!(adj.contains(&2));
        assert!(adj.contains(&3));
    }

    #[test]
    fn test_pag_remove_edge() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        assert!(pag.has_edge(1, 2));
        pag.remove_edge(1, 2);
        assert!(!pag.has_edge(1, 2));
    }

    #[test]
    fn test_pag_summary() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        pag.add_edge(3, 4, EndpointMark::Arrow, EndpointMark::Arrow);
        pag.add_edge(5, 6, EndpointMark::Circle, EndpointMark::Circle);
        let s = pag.summary();
        assert_eq!(s.total_edges, 3);
        assert_eq!(s.directed, 1);
        assert_eq!(s.bidirected, 1);
        assert_eq!(s.nondirected, 1);
        assert_eq!(s.total_nodes, 6);
    }

    #[test]
    fn test_pag_get_edges_with_arrowhead() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        pag.add_edge(3, 2, EndpointMark::Circle, EndpointMark::Arrow);
        pag.add_edge(4, 2, EndpointMark::Tail, EndpointMark::Tail);
        let arrows_at_2 = pag.get_edges_with_arrowhead_at(2);
        assert_eq!(arrows_at_2.len(), 2);
    }

    #[test]
    fn test_pag_mut_edge() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Circle, EndpointMark::Circle);
        if let Some(e) = pag.get_edge_mut(1, 2) {
            e.set_mark_at(2, EndpointMark::Arrow);
        }
        let e = pag.get_edge(1, 2).unwrap();
        assert!(e.is_partially_directed());
    }

    #[test]
    fn test_pag_display() {
        let mut pag = PAG::new();
        pag.add_edge(1, 2, EndpointMark::Tail, EndpointMark::Arrow);
        let s = format!("{}", pag);
        assert!(s.contains("PAG"));
        assert!(s.contains("directed=1"));
    }
}
