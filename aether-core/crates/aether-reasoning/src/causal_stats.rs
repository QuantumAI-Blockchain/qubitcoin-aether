//! Statistical tools for causal discovery.
//!
//! - Pearson correlation
//! - Partial correlation (recursive formula)
//! - Fisher-Z conditional independence test with p-value
//! - Feature extraction from knowledge graph nodes

use std::collections::{HashMap, HashSet};

/// Node-type encoding for feature vectors.
pub fn node_type_encoding(node_type: &str) -> f64 {
    match node_type {
        "assertion" => 0.0,
        "observation" => 0.25,
        "inference" => 0.5,
        "axiom" => 0.75,
        "prediction" => 1.0,
        "meta_observation" => 0.6,
        _ => 0.5,
    }
}

/// Maximum conditioning set depth for PC/FCI algorithms.
pub const MAX_CONDITIONING_DEPTH: usize = 3;

/// Pearson correlation between two equal-length vectors.
///
/// Returns 0.0 if either is empty or has zero variance.
pub fn pearson_correlation(x: &[f64], y: &[f64]) -> f64 {
    let n = x.len().min(y.len());
    if n == 0 {
        return 0.0;
    }

    let mean_x: f64 = x[..n].iter().sum::<f64>() / n as f64;
    let mean_y: f64 = y[..n].iter().sum::<f64>() / n as f64;

    let mut cov = 0.0_f64;
    let mut var_x = 0.0_f64;
    let mut var_y = 0.0_f64;

    for i in 0..n {
        let dx = x[i] - mean_x;
        let dy = y[i] - mean_y;
        cov += dx * dy;
        var_x += dx * dx;
        var_y += dy * dy;
    }

    if var_x < 1e-12 || var_y < 1e-12 {
        return 0.0;
    }

    cov / (var_x * var_y).sqrt()
}

/// Partial correlation between nodes a and b, controlling for the conditioning set.
///
/// Uses the recursive formula:
///   r_{ab|S} = (r_{ab|S\c} - r_{ac|S\c} * r_{bc|S\c}) /
///              sqrt((1 - r_{ac|S\c}^2) * (1 - r_{bc|S\c}^2))
pub fn partial_correlation(
    features: &HashMap<i64, Vec<f64>>,
    a_id: i64,
    b_id: i64,
    conditioning_ids: &[i64],
) -> f64 {
    if conditioning_ids.is_empty() {
        let fa = match features.get(&a_id) {
            Some(v) => v.as_slice(),
            None => return 0.0,
        };
        let fb = match features.get(&b_id) {
            Some(v) => v.as_slice(),
            None => return 0.0,
        };
        return pearson_correlation(fa, fb);
    }

    let rest = &conditioning_ids[..conditioning_ids.len() - 1];
    let c_id = conditioning_ids[conditioning_ids.len() - 1];

    let r_ab = partial_correlation(features, a_id, b_id, rest);
    let r_ac = partial_correlation(features, a_id, c_id, rest);
    let r_bc = partial_correlation(features, b_id, c_id, rest);

    let denom_sq = (1.0 - r_ac * r_ac) * (1.0 - r_bc * r_bc);
    if denom_sq <= 1e-12 {
        return 0.0;
    }

    (r_ab - r_ac * r_bc) / denom_sq.sqrt()
}

/// Fisher-Z conditional independence test.
///
/// Computes a p-value for the null hypothesis that node_a and node_b are
/// conditionally independent given the conditioning set.
///
/// Uses precision-matrix-based partial correlation when conditioning set is
/// non-empty, or plain Pearson correlation otherwise.
///
/// Returns p-value in [0, 1]. Values above alpha indicate independence.
pub fn fisher_z_p_value(
    features: &HashMap<i64, Vec<f64>>,
    node_a_id: i64,
    node_b_id: i64,
    conditioning_set: &[i64],
) -> f64 {
    // Gather involved node IDs
    let mut involved = vec![node_a_id, node_b_id];
    involved.extend_from_slice(conditioning_set);

    // Build data matrix (rows = feature dims, cols = nodes)
    let vecs: Vec<&Vec<f64>> = involved.iter()
        .filter_map(|nid| features.get(nid))
        .collect();

    if vecs.len() != involved.len() || vecs.iter().any(|v| v.is_empty()) {
        return 1.0; // Missing data — conservatively independent
    }

    let n_features = vecs[0].len();
    let n_vars = vecs.len();
    let n_cond = conditioning_set.len();

    // Need enough samples for degrees of freedom
    if n_features < n_cond + 5 {
        return 1.0;
    }

    // Compute correlation matrix
    let corr = compute_correlation_matrix(&vecs, n_features, n_vars);
    if corr.iter().any(|row| row.iter().any(|&v| v.is_nan())) {
        return 1.0;
    }

    // Compute partial correlation
    let r = if n_cond == 0 {
        corr[0][1]
    } else {
        // Precision matrix via Gaussian elimination
        match invert_matrix(&corr) {
            Some(precision) => {
                let denom = precision[0][0] * precision[1][1];
                if denom <= 1e-15 {
                    return 1.0;
                }
                -precision[0][1] / denom.sqrt()
            }
            None => return 1.0, // Singular matrix
        }
    };

    // Clamp r to avoid infinities
    let r = r.clamp(-0.999, 0.999);

    // Fisher z-transformation
    let z = 0.5 * ((1.0 + r) / (1.0 - r)).ln();

    // Test statistic: sqrt(n - |Z| - 3) * |z|
    let dof = n_features as i64 - n_cond as i64 - 3;
    if dof < 1 {
        return 1.0;
    }

    let z_stat = (dof as f64).sqrt() * z.abs();

    // Two-sided p-value from standard normal: erfc(z_stat / sqrt(2))
    erfc(z_stat / std::f64::consts::SQRT_2)
}

/// Compute correlation matrix from feature vectors.
fn compute_correlation_matrix(vecs: &[&Vec<f64>], n_features: usize, n_vars: usize) -> Vec<Vec<f64>> {
    // Each variable's values across features
    let mut means = vec![0.0_f64; n_vars];
    for j in 0..n_vars {
        for i in 0..n_features {
            means[j] += vecs[j][i];
        }
        means[j] /= n_features as f64;
    }

    let mut corr = vec![vec![0.0_f64; n_vars]; n_vars];

    // Compute variances and covariances
    let mut vars = vec![0.0_f64; n_vars];
    for j in 0..n_vars {
        for i in 0..n_features {
            let d = vecs[j][i] - means[j];
            vars[j] += d * d;
        }
    }

    for j1 in 0..n_vars {
        for j2 in j1..n_vars {
            if j1 == j2 {
                corr[j1][j2] = 1.0;
                continue;
            }
            let mut cov = 0.0;
            for i in 0..n_features {
                cov += (vecs[j1][i] - means[j1]) * (vecs[j2][i] - means[j2]);
            }
            let denom = (vars[j1] * vars[j2]).sqrt();
            let r = if denom < 1e-12 { 0.0 } else { cov / denom };
            corr[j1][j2] = r;
            corr[j2][j1] = r;
        }
    }

    corr
}

/// Invert a square matrix using Gauss-Jordan elimination.
/// Returns None if the matrix is singular.
fn invert_matrix(m: &[Vec<f64>]) -> Option<Vec<Vec<f64>>> {
    let n = m.len();
    // Augmented matrix [M | I]
    let mut aug: Vec<Vec<f64>> = Vec::with_capacity(n);
    for i in 0..n {
        let mut row = m[i].clone();
        row.resize(2 * n, 0.0);
        row[n + i] = 1.0;
        aug.push(row);
    }

    // Forward elimination with partial pivoting
    for col in 0..n {
        // Find pivot
        let mut max_row = col;
        let mut max_val = aug[col][col].abs();
        for row in (col + 1)..n {
            if aug[row][col].abs() > max_val {
                max_val = aug[row][col].abs();
                max_row = row;
            }
        }

        if max_val < 1e-15 {
            return None; // Singular
        }

        aug.swap(col, max_row);

        let pivot = aug[col][col];
        for j in 0..2 * n {
            aug[col][j] /= pivot;
        }

        for row in 0..n {
            if row == col {
                continue;
            }
            let factor = aug[row][col];
            for j in 0..2 * n {
                aug[row][j] -= factor * aug[col][j];
            }
        }
    }

    // Extract inverse from right half
    let inv: Vec<Vec<f64>> = aug.iter()
        .map(|row| row[n..].to_vec())
        .collect();

    Some(inv)
}

/// Complementary error function approximation.
///
/// Uses Abramowitz and Stegun approximation (7.1.28) for erfc.
fn erfc(x: f64) -> f64 {
    if x < 0.0 {
        return 2.0 - erfc(-x);
    }

    // Constants for rational approximation
    let p = 0.3275911;
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;

    let t = 1.0 / (1.0 + p * x);
    let t2 = t * t;
    let t3 = t2 * t;
    let t4 = t3 * t;
    let t5 = t4 * t;

    let poly = a1 * t + a2 * t2 + a3 * t3 + a4 * t4 + a5 * t5;
    poly * (-x * x).exp()
}

/// Build a 10-dimensional feature vector for each knowledge graph node.
///
/// Features: [confidence, source_block_norm, type_encoded, in_degree, out_degree,
///            avg_neighbor_conf, content_length, has_numeric, edge_diversity, domain_encoded]
pub fn build_feature_matrix(
    kg: &aether_graph::KnowledgeGraph,
    node_ids: &[i64],
) -> HashMap<i64, Vec<f64>> {
    if node_ids.is_empty() {
        return HashMap::new();
    }

    // Compute source_block normalization bounds
    let mut min_block = i64::MAX;
    let mut max_block = i64::MIN;
    for &nid in node_ids {
        if let Some(node) = kg.get_node(nid) {
            min_block = min_block.min(node.source_block);
            max_block = max_block.max(node.source_block);
        }
    }
    let block_range = if max_block > min_block { (max_block - min_block) as f64 } else { 1.0 };

    // Collect domains for encoding
    let mut domain_set: Vec<String> = Vec::new();
    for &nid in node_ids {
        if let Some(node) = kg.get_node(nid) {
            let d = if node.domain.is_empty() { "general".to_string() } else { node.domain.clone() };
            if !domain_set.contains(&d) {
                domain_set.push(d);
            }
        }
    }
    domain_set.sort();
    let domain_map: HashMap<String, f64> = domain_set.iter().enumerate()
        .map(|(i, d)| (d.clone(), i as f64 / domain_set.len().max(1) as f64))
        .collect();

    let mut features = HashMap::new();

    for &nid in node_ids {
        let node = match kg.get_node(nid) {
            Some(n) => n,
            None => continue,
        };

        let confidence = node.confidence;
        let source_block_norm = (node.source_block - min_block) as f64 / block_range;
        let type_encoded = node_type_encoding(&node.node_type);

        let out_edges = kg.get_edges_from(nid);
        let in_edges = kg.get_edges_to(nid);
        let out_degree = (out_edges.len() as f64 + 1.0).ln();
        let in_degree = (in_edges.len() as f64 + 1.0).ln();

        // Average neighbor confidence
        let mut neighbor_ids = HashSet::new();
        for e in &out_edges {
            neighbor_ids.insert(e.to_node_id);
        }
        for e in &in_edges {
            neighbor_ids.insert(e.from_node_id);
        }
        let avg_neighbor_conf = if neighbor_ids.is_empty() {
            confidence
        } else {
            let sum: f64 = neighbor_ids.iter()
                .filter_map(|&n| kg.get_node(n).map(|node| node.confidence))
                .sum();
            sum / neighbor_ids.len() as f64
        };

        // Content length
        let content_text = node.content.get("text").cloned().unwrap_or_default();
        let content_length = (content_text.len() as f64 / 500.0).min(1.0);

        // Has numeric data
        let has_numeric = if content_text.chars().any(|c| c.is_ascii_digit()) { 1.0 } else { 0.0 };

        // Edge type diversity (Shannon entropy)
        let mut edge_type_counts: HashMap<&str, usize> = HashMap::new();
        for e in &out_edges {
            *edge_type_counts.entry(&e.edge_type).or_insert(0) += 1;
        }
        for e in &in_edges {
            *edge_type_counts.entry(&e.edge_type).or_insert(0) += 1;
        }
        let total_edges: usize = edge_type_counts.values().sum();
        let mut edge_diversity = 0.0_f64;
        if total_edges > 0 {
            for &count in edge_type_counts.values() {
                let p = count as f64 / total_edges as f64;
                if p > 0.0 {
                    edge_diversity -= p * p.log2();
                }
            }
            edge_diversity = (edge_diversity / 3.0).min(1.0);
        }

        let domain = if node.domain.is_empty() { "general" } else { &node.domain };
        let domain_encoded = domain_map.get(domain).copied().unwrap_or(0.5);

        features.insert(nid, vec![
            confidence,
            source_block_norm,
            type_encoded,
            in_degree,
            out_degree,
            avg_neighbor_conf,
            content_length,
            has_numeric,
            edge_diversity,
            domain_encoded,
        ]);
    }

    features
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pearson_identical() {
        let x = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let r = pearson_correlation(&x, &x);
        assert!((r - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_pearson_opposite() {
        let x = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let y = vec![5.0, 4.0, 3.0, 2.0, 1.0];
        let r = pearson_correlation(&x, &y);
        assert!((r + 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_pearson_uncorrelated() {
        let x = vec![1.0, 0.0, -1.0, 0.0];
        let y = vec![0.0, 1.0, 0.0, -1.0];
        let r = pearson_correlation(&x, &y);
        assert!(r.abs() < 1e-10);
    }

    #[test]
    fn test_pearson_empty() {
        assert!((pearson_correlation(&[], &[1.0]) - 0.0).abs() < 1e-10);
    }

    #[test]
    fn test_pearson_zero_variance() {
        let x = vec![5.0, 5.0, 5.0];
        let y = vec![1.0, 2.0, 3.0];
        assert!((pearson_correlation(&x, &y) - 0.0).abs() < 1e-10);
    }

    #[test]
    fn test_partial_correlation_no_conditioning() {
        let mut features = HashMap::new();
        features.insert(1, vec![1.0, 2.0, 3.0]);
        features.insert(2, vec![2.0, 4.0, 6.0]);
        let r = partial_correlation(&features, 1, 2, &[]);
        assert!((r - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_partial_correlation_with_conditioning() {
        let mut features = HashMap::new();
        features.insert(1, vec![1.0, 2.0, 3.0, 4.0, 5.0]);
        features.insert(2, vec![2.0, 4.0, 6.0, 8.0, 10.0]);
        features.insert(3, vec![1.5, 3.0, 4.5, 6.0, 7.5]);
        let r = partial_correlation(&features, 1, 2, &[3]);
        // When conditioning on a perfectly correlated variable, partial corr should be near 0
        // In this case all three are perfectly correlated, so partial corr is undefined
        assert!(r.is_finite());
    }

    #[test]
    fn test_fisher_z_missing_data() {
        let features = HashMap::new();
        let p = fisher_z_p_value(&features, 1, 2, &[]);
        assert!((p - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_fisher_z_identical_vectors() {
        let mut features = HashMap::new();
        features.insert(1, vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]);
        features.insert(2, vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]);
        let p = fisher_z_p_value(&features, 1, 2, &[]);
        // Highly correlated -> low p-value (reject independence)
        assert!(p < 0.05);
    }

    #[test]
    fn test_erfc_zero() {
        let r = erfc(0.0);
        assert!((r - 1.0).abs() < 1e-3);
    }

    #[test]
    fn test_erfc_large() {
        let r = erfc(5.0);
        assert!(r < 1e-6);
    }

    #[test]
    fn test_erfc_negative() {
        let r = erfc(-1.0);
        assert!(r > 1.0);
        assert!(r < 2.0);
    }

    #[test]
    fn test_invert_matrix_identity() {
        let m = vec![vec![1.0, 0.0], vec![0.0, 1.0]];
        let inv = invert_matrix(&m).unwrap();
        assert!((inv[0][0] - 1.0).abs() < 1e-10);
        assert!((inv[1][1] - 1.0).abs() < 1e-10);
        assert!(inv[0][1].abs() < 1e-10);
    }

    #[test]
    fn test_invert_matrix_singular() {
        let m = vec![vec![1.0, 2.0], vec![2.0, 4.0]];
        assert!(invert_matrix(&m).is_none());
    }

    #[test]
    fn test_invert_matrix_2x2() {
        let m = vec![vec![4.0, 7.0], vec![2.0, 6.0]];
        let inv = invert_matrix(&m).unwrap();
        // Verify M * M^-1 ≈ I
        let prod_00 = m[0][0] * inv[0][0] + m[0][1] * inv[1][0];
        let prod_01 = m[0][0] * inv[0][1] + m[0][1] * inv[1][1];
        assert!((prod_00 - 1.0).abs() < 1e-10);
        assert!(prod_01.abs() < 1e-10);
    }

    #[test]
    fn test_node_type_encoding() {
        assert!((node_type_encoding("assertion") - 0.0).abs() < f64::EPSILON);
        assert!((node_type_encoding("axiom") - 0.75).abs() < f64::EPSILON);
        assert!((node_type_encoding("unknown") - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_build_feature_matrix() {
        let kg = aether_graph::KnowledgeGraph::new();
        let mut c = HashMap::new();
        c.insert("text".into(), "quantum entanglement test 42".into());
        kg.add_node("observation".into(), c, 0.8, 100, String::new());

        let features = build_feature_matrix(&kg, &[1]);
        assert!(features.contains_key(&1));
        let f = &features[&1];
        assert_eq!(f.len(), 10);
        assert!((f[0] - 0.8).abs() < 1e-10); // confidence
        assert!((f[2] - 0.25).abs() < 1e-10); // observation encoding
    }
}
