//! Robinson's unification algorithm with occurs check.
//!
//! Unification is the core operation of logical inference. Given two terms,
//! it finds the most general substitution (if any) that makes them identical.
//!
//! This implementation includes the **occurs check** to prevent unsound
//! infinite-term bindings (e.g., X = f(X) is rejected).

use crate::formula::Formula;
use crate::term::Term;
use rustc_hash::FxHashMap;
use thiserror::Error;

/// A substitution: mapping from variable IDs to terms.
pub type Substitution = FxHashMap<u32, Term>;

/// Errors that can occur during unification.
#[derive(Debug, Error)]
pub enum UnifyError {
    #[error("occurs check failed: variable ?{var} appears in term")]
    OccursCheck { var: u32 },
    #[error("functor mismatch: {0} vs {1}")]
    FunctorMismatch(u32, u32),
    #[error("arity mismatch: {0} vs {1}")]
    ArityMismatch(usize, usize),
    #[error("cannot unify constant {0} with constant {1}")]
    ConstantMismatch(u32, u32),
    #[error("structural mismatch: cannot unify different term kinds")]
    StructuralMismatch,
}

/// Apply a substitution to a term (walk the bindings).
pub fn apply(sub: &Substitution, term: &Term) -> Term {
    term.substitute(sub)
}

/// Compose two substitutions: apply `other` to every term in `base`, then merge.
/// `compose(s1, s2)` produces a substitution equivalent to first applying s1, then s2.
pub fn compose(base: &Substitution, other: &Substitution) -> Substitution {
    let mut result: Substitution = base
        .iter()
        .map(|(&var, term)| (var, term.substitute(other)))
        .collect();
    // Add bindings from `other` that are not in `base`.
    for (&var, term) in other {
        result.entry(var).or_insert_with(|| term.clone());
    }
    result
}

/// Robinson's unification algorithm.
///
/// Given two terms, returns the most general unifier (MGU) if one exists.
/// Returns `None` if the terms cannot be unified.
///
/// Includes the occurs check to ensure soundness: `X` cannot be bound to
/// a term containing `X` (which would create an infinite term).
pub fn unify(t1: &Term, t2: &Term) -> Option<Substitution> {
    unify_with_sub(t1, t2, Substitution::default())
}

fn unify_with_sub(t1: &Term, t2: &Term, sub: Substitution) -> Option<Substitution> {
    let t1 = apply(&sub, t1);
    let t2 = apply(&sub, t2);

    // 1. Identical terms -- already unified.
    if t1 == t2 {
        return Some(sub);
    }

    match (&t1, &t2) {
        // 2. Variable on the left: bind it (with occurs check).
        (Term::Variable(v), _) => {
            if t2.contains_var(*v) {
                None // Occurs check failure
            } else {
                let mut new_sub = sub;
                new_sub.insert(*v, t2);
                Some(new_sub)
            }
        }

        // 3. Variable on the right: bind it (with occurs check).
        (_, Term::Variable(v)) => {
            if t1.contains_var(*v) {
                None // Occurs check failure
            } else {
                let mut new_sub = sub;
                new_sub.insert(*v, t1);
                Some(new_sub)
            }
        }

        // 4. Both compound: same functor and arity, unify arguments pairwise.
        (Term::Compound(f1, args1), Term::Compound(f2, args2)) => {
            if f1 != f2 || args1.len() != args2.len() {
                return None;
            }
            let mut current_sub = sub;
            for (a1, a2) in args1.iter().zip(args2.iter()) {
                match unify_with_sub(a1, a2, current_sub) {
                    Some(s) => current_sub = s,
                    None => return None,
                }
            }
            Some(current_sub)
        }

        // 5. All other combinations fail.
        _ => None,
    }
}

/// Unify two atomic formulas.
///
/// Two atoms `P(t1, ..., tn)` and `P(s1, ..., sn)` unify if they have the
/// same predicate symbol and arity, and all corresponding term pairs unify.
pub fn unify_atoms(f1: &Formula, f2: &Formula) -> Option<Substitution> {
    match (f1, f2) {
        (Formula::Atom(p1, args1), Formula::Atom(p2, args2)) => {
            if p1 != p2 || args1.len() != args2.len() {
                return None;
            }
            let mut sub = Substitution::default();
            for (a1, a2) in args1.iter().zip(args2.iter()) {
                match unify_with_sub(a1, a2, sub) {
                    Some(s) => sub = s,
                    None => return None,
                }
            }
            Some(sub)
        }
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::term::Symbol;

    fn sym(id: u32) -> Symbol {
        Symbol(id)
    }

    #[test]
    fn test_unify_identical_constants() {
        let t = Term::Constant(sym(0));
        let sub = unify(&t, &t).unwrap();
        assert!(sub.is_empty());
    }

    #[test]
    fn test_unify_variable_to_constant() {
        let x = Term::Variable(0);
        let c = Term::Constant(sym(1));
        let sub = unify(&x, &c).unwrap();
        assert_eq!(sub.get(&0).unwrap(), &Term::Constant(sym(1)));
    }

    #[test]
    fn test_unify_compound_terms() {
        // f(X, b) and f(a, Y) should unify with {X -> a, Y -> b}
        let f = sym(0);
        let a = sym(1);
        let b = sym(2);
        let t1 = Term::Compound(f, vec![Term::Variable(0), Term::Constant(b)]);
        let t2 = Term::Compound(f, vec![Term::Constant(a), Term::Variable(1)]);
        let sub = unify(&t1, &t2).unwrap();
        assert_eq!(apply(&sub, &Term::Variable(0)), Term::Constant(a));
        assert_eq!(apply(&sub, &Term::Variable(1)), Term::Constant(b));
    }

    #[test]
    fn test_unify_occurs_check_failure() {
        // X and f(X) should fail (infinite term)
        let t1 = Term::Variable(0);
        let t2 = Term::Compound(sym(0), vec![Term::Variable(0)]);
        assert!(unify(&t1, &t2).is_none());
    }

    #[test]
    fn test_unify_nested_compounds() {
        // f(g(X), Y) and f(g(a), b) should unify with {X -> a, Y -> b}
        let f = sym(0);
        let g = sym(1);
        let a = sym(2);
        let b = sym(3);
        let t1 = Term::Compound(
            f,
            vec![
                Term::Compound(g, vec![Term::Variable(0)]),
                Term::Variable(1),
            ],
        );
        let t2 = Term::Compound(
            f,
            vec![
                Term::Compound(g, vec![Term::Constant(a)]),
                Term::Constant(b),
            ],
        );
        let sub = unify(&t1, &t2).unwrap();
        assert_eq!(apply(&sub, &Term::Variable(0)), Term::Constant(a));
        assert_eq!(apply(&sub, &Term::Variable(1)), Term::Constant(b));
    }

    #[test]
    fn test_unify_functor_mismatch() {
        let t1 = Term::Compound(sym(0), vec![Term::Constant(sym(2))]);
        let t2 = Term::Compound(sym(1), vec![Term::Constant(sym(2))]);
        assert!(unify(&t1, &t2).is_none());
    }

    #[test]
    fn test_unify_arity_mismatch() {
        let f = sym(0);
        let t1 = Term::Compound(f, vec![Term::Constant(sym(1))]);
        let t2 = Term::Compound(f, vec![Term::Constant(sym(1)), Term::Constant(sym(2))]);
        assert!(unify(&t1, &t2).is_none());
    }

    #[test]
    fn test_unify_constant_mismatch() {
        let t1 = Term::Constant(sym(0));
        let t2 = Term::Constant(sym(1));
        assert!(unify(&t1, &t2).is_none());
    }

    #[test]
    fn test_unify_two_variables() {
        // X and Y should unify with {X -> Y} or {Y -> X}
        let t1 = Term::Variable(0);
        let t2 = Term::Variable(1);
        let sub = unify(&t1, &t2).unwrap();
        // One should be bound to the other
        assert!(sub.len() == 1);
    }

    #[test]
    fn test_unify_atoms() {
        let pred = sym(0);
        let a = sym(1);
        let f1 = Formula::Atom(pred, vec![Term::Variable(0)]);
        let f2 = Formula::Atom(pred, vec![Term::Constant(a)]);
        let sub = unify_atoms(&f1, &f2).unwrap();
        assert_eq!(apply(&sub, &Term::Variable(0)), Term::Constant(a));
    }

    #[test]
    fn test_compose_substitutions() {
        let a = sym(0);
        let b = sym(1);
        let mut s1 = Substitution::default();
        s1.insert(0, Term::Variable(1)); // X -> Y
        let mut s2 = Substitution::default();
        s2.insert(1, Term::Constant(a)); // Y -> a

        let composed = compose(&s1, &s2);
        // X should now map to a (through Y)
        assert_eq!(apply(&composed, &Term::Variable(0)), Term::Constant(a));
        // Y should map to a
        assert_eq!(apply(&composed, &Term::Variable(1)), Term::Constant(a));

        // Verify independent binding preserved
        let mut s3 = Substitution::default();
        s3.insert(2, Term::Constant(b));
        let composed2 = compose(&s1, &s3);
        assert_eq!(apply(&composed2, &Term::Variable(2)), Term::Constant(b));
    }
}
