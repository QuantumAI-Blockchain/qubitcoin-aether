//! Linear Temporal Logic (LTL) for the Aether Tree.
//!
//! Implements bounded model checking over finite traces. A trace is a sequence of
//! states, where each state is a set of atomic propositions that hold at that timestep.
//!
//! Supported operators:
//! - `Prop(p)`: atomic proposition `p` holds at the current time
//! - `Not`, `And`, `Or`: boolean connectives
//! - `Next(f)`: `f` holds at the next timestep
//! - `Until(p, q)`: `p` holds until `q` becomes true
//! - `Eventually(f)`: `f` holds at some future time (sugar for `true Until f`)
//! - `Always(f)`: `f` holds at all future times (sugar for `Not(Eventually(Not(f)))`)
//! - `Since(p, q)`: past-time operator -- `p` has held since `q` was true
//!
//! Pattern extraction mines temporal invariants from observed traces.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// A Linear Temporal Logic formula.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TLFormula {
    /// Atomic proposition: true when the named proposition is in the current state.
    Prop(String),
    /// Logical negation.
    Not(Box<TLFormula>),
    /// Logical conjunction.
    And(Box<TLFormula>, Box<TLFormula>),
    /// Logical disjunction.
    Or(Box<TLFormula>, Box<TLFormula>),
    /// Next: formula holds at the next timestep.
    Next(Box<TLFormula>),
    /// Until: first formula holds at every step until the second becomes true.
    /// The second formula must eventually become true.
    Until(Box<TLFormula>, Box<TLFormula>),
    /// Eventually: formula holds at some future timestep (including current).
    Eventually(Box<TLFormula>),
    /// Always: formula holds at every timestep from now on.
    Always(Box<TLFormula>),
    /// Since (past-time): first has held at every past step since the second was true.
    Since(Box<TLFormula>, Box<TLFormula>),
}

impl std::fmt::Display for TLFormula {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TLFormula::Prop(p) => write!(f, "{p}"),
            TLFormula::Not(inner) => write!(f, "!({inner})"),
            TLFormula::And(a, b) => write!(f, "({a} & {b})"),
            TLFormula::Or(a, b) => write!(f, "({a} | {b})"),
            TLFormula::Next(inner) => write!(f, "X({inner})"),
            TLFormula::Until(a, b) => write!(f, "({a} U {b})"),
            TLFormula::Eventually(inner) => write!(f, "F({inner})"),
            TLFormula::Always(inner) => write!(f, "G({inner})"),
            TLFormula::Since(a, b) => write!(f, "({a} S {b})"),
        }
    }
}

/// Check if a finite trace satisfies a temporal formula.
///
/// A trace is a sequence of states, where each state (`HashSet<String>`) contains
/// the propositions that are true at that timestep.
///
/// For finite traces, `Always` means "at every remaining step" and `Eventually` means
/// "at some remaining step." `Until(p, q)` requires `q` to actually occur.
pub fn model_check(formula: &TLFormula, trace: &[HashSet<String>]) -> bool {
    check_at(formula, trace, 0)
}

/// Recursive model checker: evaluate formula at position `pos` in the trace.
fn check_at(formula: &TLFormula, trace: &[HashSet<String>], pos: usize) -> bool {
    if pos >= trace.len() {
        // Past the end of the trace. Semantics for finite traces:
        // - Prop is false (no state to check)
        // - Eventually is false (no future steps)
        // - Always is true (vacuously)
        // - Until is false (q never occurred)
        return match formula {
            TLFormula::Always(_) => true,
            TLFormula::Not(inner) => !check_at(inner, trace, pos),
            TLFormula::And(a, b) => check_at(a, trace, pos) && check_at(b, trace, pos),
            TLFormula::Or(a, b) => check_at(a, trace, pos) || check_at(b, trace, pos),
            _ => false,
        };
    }

    match formula {
        TLFormula::Prop(p) => trace[pos].contains(p),

        TLFormula::Not(inner) => !check_at(inner, trace, pos),

        TLFormula::And(a, b) => check_at(a, trace, pos) && check_at(b, trace, pos),

        TLFormula::Or(a, b) => check_at(a, trace, pos) || check_at(b, trace, pos),

        TLFormula::Next(inner) => check_at(inner, trace, pos + 1),

        TLFormula::Until(p, q) => {
            // q must become true at some point >= pos.
            // p must hold at every step from pos until (but not necessarily including)
            // the step where q becomes true.
            for i in pos..trace.len() {
                if check_at(q, trace, i) {
                    return true;
                }
                if !check_at(p, trace, i) {
                    return false;
                }
            }
            false // q never became true
        }

        TLFormula::Eventually(inner) => {
            for i in pos..trace.len() {
                if check_at(inner, trace, i) {
                    return true;
                }
            }
            false
        }

        TLFormula::Always(inner) => {
            for i in pos..trace.len() {
                if !check_at(inner, trace, i) {
                    return false;
                }
            }
            true
        }

        TLFormula::Since(p, q) => {
            // Past-time: there exists some j <= pos where q held, and p held at
            // every step from j+1 to pos (inclusive).
            for j in (0..=pos).rev() {
                if check_at(q, trace, j) {
                    // Check that p held from j+1 to pos.
                    let p_held = (j + 1..=pos).all(|k| check_at(p, trace, k));
                    if p_held {
                        return true;
                    }
                }
            }
            false
        }
    }
}

/// Mine temporal patterns from an observed trace.
///
/// Extracts:
/// 1. **Invariants** (Always): propositions true at every timestep.
/// 2. **Eventually patterns**: propositions that always appear within `k` steps
///    of any point in the trace (checked with `window = trace.len() / 4`).
/// 3. **Next patterns**: if prop A at time t implies prop B at time t+1.
/// 4. **Until patterns**: prop A holds until prop B appears.
pub fn extract_patterns(trace: &[HashSet<String>]) -> Vec<TLFormula> {
    if trace.is_empty() {
        return Vec::new();
    }

    let mut patterns = Vec::new();

    // Collect all propositions that appear anywhere in the trace.
    let all_props: HashSet<&String> = trace.iter().flat_map(|s| s.iter()).collect();

    // 1. Invariants: Always(Prop(p)) -- p holds at every step.
    for &p in &all_props {
        if trace.iter().all(|state| state.contains(p)) {
            patterns.push(TLFormula::Always(Box::new(TLFormula::Prop(p.clone()))));
        }
    }

    // 2. Eventually patterns: propositions that appear within a bounded window
    //    from every position. Use window = max(1, len/4).
    let window = (trace.len() / 4).max(1);
    for &p in &all_props {
        // Skip props already identified as invariants.
        if trace.iter().all(|state| state.contains(p)) {
            continue;
        }
        let eventually_within_window = (0..trace.len()).all(|start| {
            let end = (start + window).min(trace.len());
            (start..end).any(|i| trace[i].contains(p))
        });
        if eventually_within_window {
            patterns.push(TLFormula::Eventually(Box::new(TLFormula::Prop(p.clone()))));
        }
    }

    // 3. Next patterns: if A at time t, then B at time t+1.
    //    Only report if the implication holds for ALL occurrences of A (with t+1 in range).
    if trace.len() >= 2 {
        for &a in &all_props {
            for &b in &all_props {
                if a == b {
                    continue;
                }
                let a_count = (0..trace.len() - 1)
                    .filter(|&t| trace[t].contains(a))
                    .count();
                if a_count == 0 {
                    continue;
                }
                let implies = (0..trace.len() - 1)
                    .filter(|&t| trace[t].contains(a))
                    .all(|t| trace[t + 1].contains(b));
                if implies {
                    // A => Next(B) is equivalent to Always(A -> Next(B)),
                    // but we represent the discovered pattern as a Next relationship.
                    patterns.push(TLFormula::Next(Box::new(TLFormula::And(
                        Box::new(TLFormula::Prop(a.clone())),
                        Box::new(TLFormula::Prop(b.clone())),
                    ))));
                }
            }
        }
    }

    // 4. Until patterns: A holds continuously until B appears.
    //    Look for cases where A is consistently present before B's first appearance.
    for &a in &all_props {
        for &b in &all_props {
            if a == b {
                continue;
            }
            // Find first occurrence of B.
            let first_b = trace.iter().position(|s| s.contains(b));
            if let Some(fb) = first_b {
                if fb > 0 {
                    // Check that A holds at every step before first B.
                    let a_until_b = (0..fb).all(|t| trace[t].contains(a));
                    if a_until_b {
                        patterns.push(TLFormula::Until(
                            Box::new(TLFormula::Prop(a.clone())),
                            Box::new(TLFormula::Prop(b.clone())),
                        ));
                    }
                }
            }
        }
    }

    patterns
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(props: &[&str]) -> HashSet<String> {
        props.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn test_prop() {
        let trace = vec![state(&["a", "b"]), state(&["b", "c"])];
        assert!(model_check(&TLFormula::Prop("a".into()), &trace));
        assert!(model_check(&TLFormula::Prop("b".into()), &trace));
        assert!(!model_check(&TLFormula::Prop("c".into()), &trace));
    }

    #[test]
    fn test_not() {
        let trace = vec![state(&["a"])];
        assert!(!model_check(&TLFormula::Not(Box::new(TLFormula::Prop("a".into()))), &trace));
        assert!(model_check(&TLFormula::Not(Box::new(TLFormula::Prop("b".into()))), &trace));
    }

    #[test]
    fn test_and_or() {
        let trace = vec![state(&["a", "b"])];
        let f_and = TLFormula::And(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("b".into())),
        );
        assert!(model_check(&f_and, &trace));

        let f_or = TLFormula::Or(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("c".into())),
        );
        assert!(model_check(&f_or, &trace));
    }

    #[test]
    fn test_next() {
        let trace = vec![state(&["a"]), state(&["b"])];
        let f = TLFormula::Next(Box::new(TLFormula::Prop("b".into())));
        assert!(model_check(&f, &trace));

        let f2 = TLFormula::Next(Box::new(TLFormula::Prop("a".into())));
        assert!(!model_check(&f2, &trace));
    }

    #[test]
    fn test_eventually() {
        let trace = vec![state(&["a"]), state(&["b"]), state(&["c"])];
        assert!(model_check(
            &TLFormula::Eventually(Box::new(TLFormula::Prop("c".into()))),
            &trace
        ));
        assert!(!model_check(
            &TLFormula::Eventually(Box::new(TLFormula::Prop("d".into()))),
            &trace
        ));
    }

    #[test]
    fn test_always() {
        let trace = vec![state(&["a"]), state(&["a", "b"]), state(&["a"])];
        assert!(model_check(
            &TLFormula::Always(Box::new(TLFormula::Prop("a".into()))),
            &trace
        ));
        assert!(!model_check(
            &TLFormula::Always(Box::new(TLFormula::Prop("b".into()))),
            &trace
        ));
    }

    #[test]
    fn test_until() {
        // a holds at steps 0, 1; b appears at step 2.
        let trace = vec![state(&["a"]), state(&["a"]), state(&["b"])];
        let f = TLFormula::Until(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("b".into())),
        );
        assert!(model_check(&f, &trace));
    }

    #[test]
    fn test_until_fails_no_q() {
        // a holds forever but b never appears.
        let trace = vec![state(&["a"]), state(&["a"]), state(&["a"])];
        let f = TLFormula::Until(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("b".into())),
        );
        assert!(!model_check(&f, &trace));
    }

    #[test]
    fn test_until_p_breaks_before_q() {
        // a holds at step 0, drops at step 1, b at step 2.
        let trace = vec![state(&["a"]), state(&[]), state(&["b"])];
        let f = TLFormula::Until(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("b".into())),
        );
        assert!(!model_check(&f, &trace));
    }

    #[test]
    fn test_since() {
        // q was true at step 1, p held at steps 2 and 3.
        let trace = vec![state(&[]), state(&["q"]), state(&["p"]), state(&["p"])];
        let f = TLFormula::Since(
            Box::new(TLFormula::Prop("p".into())),
            Box::new(TLFormula::Prop("q".into())),
        );
        // Check at step 3: q at step 1, p at steps 2 and 3.
        assert!(check_at(&f, &trace, 3));
    }

    #[test]
    fn test_empty_trace() {
        let trace: Vec<HashSet<String>> = vec![];
        assert!(!model_check(&TLFormula::Prop("a".into()), &trace));
        assert!(model_check(
            &TLFormula::Always(Box::new(TLFormula::Prop("a".into()))),
            &trace
        ));
    }

    #[test]
    fn test_extract_invariants() {
        let trace = vec![state(&["a", "b"]), state(&["a", "c"]), state(&["a", "b"])];
        let patterns = extract_patterns(&trace);
        // "a" is present at every step -- should be an invariant.
        assert!(patterns.contains(&TLFormula::Always(Box::new(TLFormula::Prop("a".into())))));
        // "b" is NOT at every step.
        assert!(!patterns.contains(&TLFormula::Always(Box::new(TLFormula::Prop("b".into())))));
    }

    #[test]
    fn test_extract_until() {
        // "init" holds at steps 0-2, "ready" appears at step 3.
        let trace = vec![
            state(&["init"]),
            state(&["init"]),
            state(&["init"]),
            state(&["ready"]),
        ];
        let patterns = extract_patterns(&trace);
        let until = TLFormula::Until(
            Box::new(TLFormula::Prop("init".into())),
            Box::new(TLFormula::Prop("ready".into())),
        );
        assert!(patterns.contains(&until));
    }

    #[test]
    fn test_display() {
        let f = TLFormula::Always(Box::new(TLFormula::Until(
            Box::new(TLFormula::Prop("a".into())),
            Box::new(TLFormula::Prop("b".into())),
        )));
        assert_eq!(format!("{f}"), "G((a U b))");
    }
}
