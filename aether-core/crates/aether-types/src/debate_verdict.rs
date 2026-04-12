//! DebateVerdict — outcome of an adversarial debate in the Aether Tree.
//!
//! Four possible outcomes:
//! - Accepted: the proposition is accepted as valid knowledge
//! - Rejected: the proposition is rejected / refuted
//! - Modified: the proposition is accepted with modifications
//! - Undecided: insufficient evidence to reach a conclusion

use serde::{Deserialize, Serialize};
use std::fmt;
use std::str::FromStr;

/// The outcome of an adversarial debate.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DebateVerdict {
    Accepted,
    Rejected,
    Modified,
    Undecided,
}

impl fmt::Display for DebateVerdict {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DebateVerdict::Accepted => write!(f, "accepted"),
            DebateVerdict::Rejected => write!(f, "rejected"),
            DebateVerdict::Modified => write!(f, "modified"),
            DebateVerdict::Undecided => write!(f, "undecided"),
        }
    }
}

impl FromStr for DebateVerdict {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "accepted" | "accept" => Ok(DebateVerdict::Accepted),
            "rejected" | "reject" => Ok(DebateVerdict::Rejected),
            "modified" | "modify" => Ok(DebateVerdict::Modified),
            "undecided" => Ok(DebateVerdict::Undecided),
            _ => Err(format!("Unknown debate verdict: '{}'", s)),
        }
    }
}

impl DebateVerdict {
    /// Return the index for this verdict (used in NN scoring).
    pub fn index(&self) -> usize {
        match self {
            DebateVerdict::Accepted => 0,
            DebateVerdict::Rejected => 1,
            DebateVerdict::Modified => 2,
            DebateVerdict::Undecided => 3,
        }
    }

    /// Create from index.
    pub fn from_index(idx: usize) -> Self {
        match idx {
            0 => DebateVerdict::Accepted,
            1 => DebateVerdict::Rejected,
            2 => DebateVerdict::Modified,
            _ => DebateVerdict::Undecided,
        }
    }

    /// All verdict variants in order.
    pub const ALL: &'static [DebateVerdict] = &[
        DebateVerdict::Accepted,
        DebateVerdict::Rejected,
        DebateVerdict::Modified,
        DebateVerdict::Undecided,
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_display() {
        assert_eq!(DebateVerdict::Accepted.to_string(), "accepted");
        assert_eq!(DebateVerdict::Rejected.to_string(), "rejected");
        assert_eq!(DebateVerdict::Modified.to_string(), "modified");
        assert_eq!(DebateVerdict::Undecided.to_string(), "undecided");
    }

    #[test]
    fn test_from_str() {
        assert_eq!("accepted".parse::<DebateVerdict>().unwrap(), DebateVerdict::Accepted);
        assert_eq!("accept".parse::<DebateVerdict>().unwrap(), DebateVerdict::Accepted);
        assert_eq!("Rejected".parse::<DebateVerdict>().unwrap(), DebateVerdict::Rejected);
        assert_eq!("MODIFY".parse::<DebateVerdict>().unwrap(), DebateVerdict::Modified);
        assert_eq!("undecided".parse::<DebateVerdict>().unwrap(), DebateVerdict::Undecided);
        assert!("invalid".parse::<DebateVerdict>().is_err());
    }

    #[test]
    fn test_index_roundtrip() {
        for v in DebateVerdict::ALL {
            assert_eq!(DebateVerdict::from_index(v.index()), *v);
        }
    }

    #[test]
    fn test_serde_roundtrip() {
        let verdict = DebateVerdict::Modified;
        let json = serde_json::to_string(&verdict).unwrap();
        let parsed: DebateVerdict = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, verdict);
    }
}
