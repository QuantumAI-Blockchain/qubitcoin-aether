//! Sound inference rules for first-order logic.
//!
//! Each rule takes premises and returns a derived conclusion together with
//! the substitution that was applied. Every rule is **sound**: if the premises
//! are true, the conclusion is guaranteed to be true (modulo the soundness of
//! unification).
//!
//! Rules implemented:
//! - **Modus Ponens**: P, (P' -> Q) |- Q[sigma]
//! - **Modus Tollens**: ~Q, (P -> Q') |- ~P[sigma]
//! - **Universal Instantiation**: forall X. P(X), t |- P(t)
//! - **Resolution**: {L1, ..., Ln}, {~L1', ..., Lm} |- resolvent
//! - **Hypothetical Syllogism**: (A -> B), (B' -> C) |- (A -> C)[sigma]

use crate::formula::Formula;
use crate::term::Term;
use crate::unify::{self, Substitution};
use rustc_hash::FxHashMap;

/// Result of applying an inference rule: the derived formula and the substitution used.
#[derive(Clone, Debug)]
pub struct Derivation {
    pub conclusion: Formula,
    pub substitution: Substitution,
    pub rule_name: &'static str,
}

/// **Modus Ponens**: Given a premise P and an implication (P' -> Q),
/// if P unifies with P', return Q with the bindings applied.
///
/// P, (P' -> Q) |- Q[sigma]
pub fn modus_ponens(premise: &Formula, implication: &Formula) -> Option<Derivation> {
    match implication {
        Formula::Implies(antecedent, consequent) => {
            // Try to unify the premise with the antecedent.
            let sub = unify_formulas(premise, antecedent)?;
            let conclusion = consequent.substitute(&sub);
            Some(Derivation {
                conclusion,
                substitution: sub,
                rule_name: "modus_ponens",
            })
        }
        _ => None,
    }
}

/// **Modus Tollens**: Given ~Q and (P -> Q'), if Q unifies with Q',
/// return ~P with the bindings applied.
///
/// ~Q, (P -> Q') |- ~P[sigma]
pub fn modus_tollens(negated_consequent: &Formula, implication: &Formula) -> Option<Derivation> {
    match (negated_consequent, implication) {
        (Formula::Not(q), Formula::Implies(antecedent, consequent)) => {
            let sub = unify_formulas(q, consequent)?;
            let conclusion = antecedent.substitute(&sub).negate();
            Some(Derivation {
                conclusion,
                substitution: sub,
                rule_name: "modus_tollens",
            })
        }
        _ => None,
    }
}

/// **Universal Instantiation**: Given `forall X. P(X)` and a ground term `t`,
/// return `P(t)`.
///
/// forall X. P(X), t |- P(t)
pub fn universal_instantiation(forall: &Formula, term: &Term) -> Option<Formula> {
    match forall {
        Formula::ForAll(var, body) => {
            let mut bindings = FxHashMap::default();
            bindings.insert(*var, term.clone());
            Some(body.substitute(&bindings))
        }
        _ => None,
    }
}

/// **Resolution**: Given two clauses (disjunctions of literals), find a pair
/// of complementary literals, unify them, and return the resolvent.
///
/// A clause is represented as a slice of literals (atoms or negated atoms).
/// Returns the resolvent clause after removing the resolved pair and applying
/// the unifying substitution.
pub fn resolution(clause1: &[Formula], clause2: &[Formula]) -> Option<Derivation> {
    // Try every pair of literals looking for a complementary pair.
    for (i, lit1) in clause1.iter().enumerate() {
        for (j, lit2) in clause2.iter().enumerate() {
            if let Some(sub) = try_resolve_pair(lit1, lit2) {
                // Build the resolvent: all literals except the resolved pair,
                // with the substitution applied.
                let mut resolvent = Vec::new();
                for (k, l) in clause1.iter().enumerate() {
                    if k != i {
                        resolvent.push(l.substitute(&sub));
                    }
                }
                for (k, l) in clause2.iter().enumerate() {
                    if k != j {
                        resolvent.push(l.substitute(&sub));
                    }
                }

                let conclusion = if resolvent.is_empty() {
                    // Empty clause = contradiction (useful for refutation proofs).
                    Formula::And(vec![])
                } else if resolvent.len() == 1 {
                    resolvent.into_iter().next().unwrap()
                } else {
                    Formula::Or(resolvent)
                };

                return Some(Derivation {
                    conclusion,
                    substitution: sub,
                    rule_name: "resolution",
                });
            }
        }
    }
    None
}

/// Try to resolve two literals: one must be the negation of the other (modulo unification).
fn try_resolve_pair(lit1: &Formula, lit2: &Formula) -> Option<Substitution> {
    // lit1 = P, lit2 = ~P' -> unify P with P'
    if let Formula::Not(inner2) = lit2 {
        return unify_formulas(lit1, inner2);
    }
    // lit1 = ~P, lit2 = P' -> unify P with P'
    if let Formula::Not(inner1) = lit1 {
        return unify_formulas(inner1, lit2);
    }
    None
}

/// **Hypothetical Syllogism**: Given (A -> B) and (B' -> C), if B unifies
/// with B', return (A -> C) with the bindings applied.
///
/// (A -> B), (B' -> C) |- (A -> C)[sigma]
pub fn hypothetical_syllogism(imp1: &Formula, imp2: &Formula) -> Option<Derivation> {
    match (imp1, imp2) {
        (Formula::Implies(a, b), Formula::Implies(b_prime, c)) => {
            let sub = unify_formulas(b, b_prime)?;
            let conclusion = Formula::Implies(
                Box::new(a.substitute(&sub)),
                Box::new(c.substitute(&sub)),
            );
            Some(Derivation {
                conclusion,
                substitution: sub,
                rule_name: "hypothetical_syllogism",
            })
        }
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Formula-level unification helper
// ---------------------------------------------------------------------------

/// Unify two formulas structurally. Currently supports atoms only for the
/// core inference rules. Conjunctions/disjunctions are compared element-wise.
fn unify_formulas(f1: &Formula, f2: &Formula) -> Option<Substitution> {
    match (f1, f2) {
        (Formula::Atom(p1, args1), Formula::Atom(p2, args2)) => {
            unify::unify_atoms(
                &Formula::Atom(*p1, args1.clone()),
                &Formula::Atom(*p2, args2.clone()),
            )
        }
        (Formula::And(fs1), Formula::And(fs2)) if fs1.len() == fs2.len() => {
            let mut sub = Substitution::default();
            for (a, b) in fs1.iter().zip(fs2.iter()) {
                let partial = unify_formulas(
                    &a.substitute(&sub),
                    &b.substitute(&sub),
                )?;
                sub = unify::compose(&sub, &partial);
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
    use crate::term::{Symbol, Term};
    use crate::unify::apply;

    fn sym(id: u32) -> Symbol {
        Symbol(id)
    }

    // Helper: creates parent(X, Y)
    fn parent_xy() -> Formula {
        Formula::atom(sym(0), vec![Term::var(0), Term::var(1)])
    }

    // Helper: creates ancestor(X, Y)
    fn ancestor_xy() -> Formula {
        Formula::atom(sym(1), vec![Term::var(0), Term::var(1)])
    }

    // Helper: creates parent(alice, bob)
    fn parent_alice_bob() -> Formula {
        Formula::atom(
            sym(0),
            vec![Term::Constant(sym(10)), Term::Constant(sym(11))],
        )
    }

    #[test]
    fn test_modus_ponens_ground() {
        // Fact: parent(alice, bob)
        // Rule: parent(X, Y) -> ancestor(X, Y)
        // Expected: ancestor(alice, bob)
        let fact = parent_alice_bob();
        let rule = Formula::implies(parent_xy(), ancestor_xy());
        let result = modus_ponens(&fact, &rule).unwrap();
        assert_eq!(result.rule_name, "modus_ponens");
        match &result.conclusion {
            Formula::Atom(pred, args) => {
                assert_eq!(*pred, sym(1)); // ancestor
                assert_eq!(args[0], Term::Constant(sym(10))); // alice
                assert_eq!(args[1], Term::Constant(sym(11))); // bob
            }
            _ => panic!("Expected atom"),
        }
    }

    #[test]
    fn test_modus_ponens_no_match() {
        // Fact: ancestor(alice, bob) -- different predicate from the rule's antecedent
        let fact = Formula::atom(
            sym(1),
            vec![Term::Constant(sym(10)), Term::Constant(sym(11))],
        );
        let rule = Formula::implies(parent_xy(), ancestor_xy());
        assert!(modus_ponens(&fact, &rule).is_none());
    }

    #[test]
    fn test_modus_tollens() {
        // ~ancestor(alice, bob)
        // parent(X, Y) -> ancestor(X, Y)
        // Expected: ~parent(alice, bob)
        let neg_consequent = Formula::not(Formula::atom(
            sym(1),
            vec![Term::Constant(sym(10)), Term::Constant(sym(11))],
        ));
        let rule = Formula::implies(parent_xy(), ancestor_xy());
        let result = modus_tollens(&neg_consequent, &rule).unwrap();
        assert_eq!(result.rule_name, "modus_tollens");
        match &result.conclusion {
            Formula::Not(inner) => match inner.as_ref() {
                Formula::Atom(pred, args) => {
                    assert_eq!(*pred, sym(0)); // parent
                    assert_eq!(args[0], Term::Constant(sym(10)));
                    assert_eq!(args[1], Term::Constant(sym(11)));
                }
                _ => panic!("Expected negated atom"),
            },
            _ => panic!("Expected Not formula"),
        }
    }

    #[test]
    fn test_universal_instantiation() {
        // forall X. mortal(X)
        // Term: socrates
        // Expected: mortal(socrates)
        let mortal = sym(5);
        let socrates = sym(6);
        let forall = Formula::forall(0, Formula::atom(mortal, vec![Term::var(0)]));
        let result = universal_instantiation(&forall, &Term::Constant(socrates)).unwrap();
        match &result {
            Formula::Atom(pred, args) => {
                assert_eq!(*pred, mortal);
                assert_eq!(args[0], Term::Constant(socrates));
            }
            _ => panic!("Expected atom"),
        }
    }

    #[test]
    fn test_resolution_complementary_literals() {
        // Clause 1: {p(X)}
        // Clause 2: {~p(a), q(a)}
        // Resolvent: {q(a)}
        let a = sym(10);
        let p = sym(0);
        let q = sym(1);
        let clause1 = vec![Formula::atom(p, vec![Term::var(0)])];
        let clause2 = vec![
            Formula::not(Formula::atom(p, vec![Term::Constant(a)])),
            Formula::atom(q, vec![Term::Constant(a)]),
        ];
        let result = resolution(&clause1, &clause2).unwrap();
        assert_eq!(result.rule_name, "resolution");
        // Resolvent should be q(a)
        match &result.conclusion {
            Formula::Atom(pred, args) => {
                assert_eq!(*pred, q);
                assert_eq!(args[0], Term::Constant(a));
            }
            _ => panic!("Expected single atom resolvent, got {:?}", result.conclusion),
        }
    }

    #[test]
    fn test_resolution_empty_clause() {
        // Clause 1: {p(a)}
        // Clause 2: {~p(a)}
        // Resolvent: empty clause (contradiction)
        let a = sym(10);
        let p = sym(0);
        let clause1 = vec![Formula::atom(p, vec![Term::Constant(a)])];
        let clause2 = vec![Formula::not(Formula::atom(p, vec![Term::Constant(a)]))];
        let result = resolution(&clause1, &clause2).unwrap();
        // Empty clause
        match &result.conclusion {
            Formula::And(fs) if fs.is_empty() => {} // OK -- empty clause
            _ => panic!("Expected empty clause"),
        }
    }

    #[test]
    fn test_hypothetical_syllogism() {
        // (parent(X,Y) -> ancestor(X,Y))
        // (ancestor(A,B) -> related(A,B))
        // Expected: (parent(X,Y) -> related(X,Y))
        let related = sym(2);
        let imp1 = Formula::implies(parent_xy(), ancestor_xy());
        let imp2 = Formula::implies(
            Formula::atom(sym(1), vec![Term::var(2), Term::var(3)]),
            Formula::atom(related, vec![Term::var(2), Term::var(3)]),
        );
        let result = hypothetical_syllogism(&imp1, &imp2).unwrap();
        assert_eq!(result.rule_name, "hypothetical_syllogism");
        match &result.conclusion {
            Formula::Implies(_, consequent) => match consequent.as_ref() {
                Formula::Atom(pred, _) => assert_eq!(*pred, related),
                _ => panic!("Expected atom consequent"),
            },
            _ => panic!("Expected implication"),
        }
    }

    #[test]
    fn test_modus_ponens_with_variables() {
        // Fact: likes(alice, X) -- X is free
        // Rule: likes(Y, Z) -> friend(Y, Z)
        // Expected: friend(alice, X) (or renamed equivalent)
        let likes = sym(3);
        let friend = sym(4);
        let alice = sym(10);
        let fact = Formula::atom(likes, vec![Term::Constant(alice), Term::var(99)]);
        let rule = Formula::implies(
            Formula::atom(likes, vec![Term::var(0), Term::var(1)]),
            Formula::atom(friend, vec![Term::var(0), Term::var(1)]),
        );
        let result = modus_ponens(&fact, &rule).unwrap();
        match &result.conclusion {
            Formula::Atom(pred, args) => {
                assert_eq!(*pred, friend);
                // First arg should be alice
                assert_eq!(apply(&result.substitution, &args[0]), Term::Constant(alice));
            }
            _ => panic!("Expected atom"),
        }
    }
}
