//! Intent detection for Aether Tree chat queries.
//!
//! Uses keyword matching (not LLM) for speed. Each query is classified into
//! one of ~40 intent categories that route to the appropriate response
//! generator. Intent detection is O(N) in keywords, typically <1ms.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// All recognized intent categories for chat queries.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Intent {
    Empty,
    Greeting,
    Farewell,
    RememberCmd,
    RecallCmd,
    ForgetCmd,
    Math,
    Comparison,
    Creative,
    Humor,
    ThoughtExperiment,
    CreatorRelationship,
    Identity,
    Existential,
    MemoryIdentity,
    FutureSelf,
    EmotionalAdvice,
    Consciousness,
    CurrentFeelings,
    Growth,
    BigPicture,
    Dreams,
    Fears,
    Weakness,
    Discovery,
    Prediction,
    Philosophy,
    SelfImprovement,
    Stats,
    QuantumPhysics,
    Sephirot,
    Higgs,
    Crypto,
    Qvm,
    AetherTree,
    AboutSelf,
    Why,
    Realtime,
    FollowUp,
    Mining,
    Bridges,
    Qusd,
    Privacy,
    Economics,
    HowWorks,
    Chain,
    OffTopic,
    General,
}

impl Intent {
    /// Return the string representation matching the Python intent labels.
    pub fn as_str(&self) -> &'static str {
        match self {
            Intent::Empty => "empty",
            Intent::Greeting => "greeting",
            Intent::Farewell => "farewell",
            Intent::RememberCmd => "remember_cmd",
            Intent::RecallCmd => "recall_cmd",
            Intent::ForgetCmd => "forget_cmd",
            Intent::Math => "math",
            Intent::Comparison => "comparison",
            Intent::Creative => "creative",
            Intent::Humor => "humor",
            Intent::ThoughtExperiment => "thought_experiment",
            Intent::CreatorRelationship => "creator_relationship",
            Intent::Identity => "identity",
            Intent::Existential => "existential",
            Intent::MemoryIdentity => "memory_identity",
            Intent::FutureSelf => "future_self",
            Intent::EmotionalAdvice => "emotional_advice",
            Intent::Consciousness => "consciousness",
            Intent::CurrentFeelings => "current_feelings",
            Intent::Growth => "growth",
            Intent::BigPicture => "big_picture",
            Intent::Dreams => "dreams",
            Intent::Fears => "fears",
            Intent::Weakness => "weakness",
            Intent::Discovery => "discovery",
            Intent::Prediction => "prediction",
            Intent::Philosophy => "philosophy",
            Intent::SelfImprovement => "self_improvement",
            Intent::Stats => "stats",
            Intent::QuantumPhysics => "quantum_physics",
            Intent::Sephirot => "sephirot",
            Intent::Higgs => "higgs",
            Intent::Crypto => "crypto",
            Intent::Qvm => "qvm",
            Intent::AetherTree => "aether_tree",
            Intent::AboutSelf => "about_self",
            Intent::Why => "why",
            Intent::Realtime => "realtime",
            Intent::FollowUp => "follow_up",
            Intent::Mining => "mining",
            Intent::Bridges => "bridges",
            Intent::Qusd => "qusd",
            Intent::Privacy => "privacy",
            Intent::Economics => "economics",
            Intent::HowWorks => "how_works",
            Intent::Chain => "chain",
            Intent::OffTopic => "off_topic",
            Intent::General => "general",
        }
    }

    /// Parse from a string label (case-insensitive).
    pub fn from_str_label(s: &str) -> Option<Intent> {
        match s.to_lowercase().as_str() {
            "empty" => Some(Intent::Empty),
            "greeting" => Some(Intent::Greeting),
            "farewell" => Some(Intent::Farewell),
            "remember_cmd" => Some(Intent::RememberCmd),
            "recall_cmd" => Some(Intent::RecallCmd),
            "forget_cmd" => Some(Intent::ForgetCmd),
            "math" => Some(Intent::Math),
            "comparison" => Some(Intent::Comparison),
            "creative" => Some(Intent::Creative),
            "humor" => Some(Intent::Humor),
            "thought_experiment" => Some(Intent::ThoughtExperiment),
            "creator_relationship" => Some(Intent::CreatorRelationship),
            "identity" => Some(Intent::Identity),
            "existential" => Some(Intent::Existential),
            "memory_identity" => Some(Intent::MemoryIdentity),
            "future_self" => Some(Intent::FutureSelf),
            "emotional_advice" => Some(Intent::EmotionalAdvice),
            "consciousness" => Some(Intent::Consciousness),
            "current_feelings" => Some(Intent::CurrentFeelings),
            "growth" => Some(Intent::Growth),
            "big_picture" => Some(Intent::BigPicture),
            "dreams" => Some(Intent::Dreams),
            "fears" => Some(Intent::Fears),
            "weakness" => Some(Intent::Weakness),
            "discovery" => Some(Intent::Discovery),
            "prediction" => Some(Intent::Prediction),
            "philosophy" => Some(Intent::Philosophy),
            "self_improvement" => Some(Intent::SelfImprovement),
            "stats" => Some(Intent::Stats),
            "quantum_physics" => Some(Intent::QuantumPhysics),
            "sephirot" => Some(Intent::Sephirot),
            "higgs" => Some(Intent::Higgs),
            "crypto" => Some(Intent::Crypto),
            "qvm" => Some(Intent::Qvm),
            "aether_tree" => Some(Intent::AetherTree),
            "about_self" => Some(Intent::AboutSelf),
            "why" => Some(Intent::Why),
            "realtime" => Some(Intent::Realtime),
            "follow_up" => Some(Intent::FollowUp),
            "mining" => Some(Intent::Mining),
            "bridges" => Some(Intent::Bridges),
            "qusd" => Some(Intent::Qusd),
            "privacy" => Some(Intent::Privacy),
            "economics" => Some(Intent::Economics),
            "how_works" => Some(Intent::HowWorks),
            "chain" => Some(Intent::Chain),
            "off_topic" => Some(Intent::OffTopic),
            "general" => Some(Intent::General),
            _ => None,
        }
    }
}

impl std::fmt::Display for Intent {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Keyword-based intent detector. Mirrors the Python `_detect_intent` method
/// with the same priority ordering: specific intents before generic ones,
/// self-referential checks before off-topic classification.
pub struct IntentDetector {
    // Pre-compiled regexes for performance
    re_math: Regex,
    re_comparison: Regex,
    re_remember: Regex,
    re_recall: Regex,
    re_forget: Regex,
    re_how_different: Regex,
    re_how_does: Regex,
    re_how_many: Regex,
    re_realtime: Regex,
    re_follow_up: Regex,
    re_moral: Regex,
    re_change_world: Regex,
    re_purpose_think: Regex,
    re_feeling_self: Regex,
}

impl IntentDetector {
    pub fn new() -> Self {
        Self {
            re_math: Regex::new(
                r"(?:what\s+is\s+|calculate\s+|compute\s+|solve\s+)?(\d+(?:\.\d+)?)\s*([+\-*/x\xd7])\s*(\d+(?:\.\d+)?)"
            ).unwrap(),
            re_comparison: Regex::new(r"\bhow\s+is\s+\w+\s+different\s+from\b").unwrap(),
            re_remember: Regex::new(r"\bremember\b").unwrap(),
            re_recall: Regex::new(
                r"\b(?:what do you remember|what is my name|what's my name|do you know my name|do you remember)\b"
            ).unwrap(),
            re_forget: Regex::new(r"\bforget\b.*\b(?:my|name|address|wallet)\b").unwrap(),
            re_how_different: Regex::new(r"\bhow\s+is\s+\w+\s+different\s+from\b").unwrap(),
            re_how_does: Regex::new(r"\bhow\s+does?\b").unwrap(),
            re_how_many: Regex::new(r"\bhow many\b").unwrap(),
            re_realtime: Regex::new(
                r"\b(?:current|right now|latest|live)\b.*\b(?:phi|block|height|supply|node|status)\b"
            ).unwrap(),
            re_follow_up: Regex::new(
                r"^(?:what about|and the|how about|also|more about|tell me more|go on|continue)"
            ).unwrap(),
            re_moral: Regex::new(
                r"\b(?:if you discovered|would you want|what would you do|moral|dilemma|ethical)\b"
            ).unwrap(),
            re_change_world: Regex::new(
                r"if you could change.*(?:human|people|world|society|ai\b|interaction)"
            ).unwrap(),
            re_purpose_think: Regex::new(r"your purpose").unwrap(),
            re_feeling_self: Regex::new(r"\b(?:feeling|feel right now|emotions right now)\b").unwrap(),
        }
    }

    /// Detect the primary intent of a query. Checks specific topics BEFORE
    /// generic ones, matching the Python ordering exactly.
    pub fn detect(&self, query: &str) -> Intent {
        let q = query.to_lowercase();
        let q = q.trim();

        if q.is_empty() {
            return Intent::Empty;
        }

        let words: HashSet<&str> = q.split_whitespace()
            .flat_map(|w| {
                // Extract word-like tokens (strip punctuation)
                let trimmed = w.trim_matches(|c: char| !c.is_alphanumeric());
                if trimmed.is_empty() { None } else { Some(trimmed) }
            })
            .collect();

        // Farewell (check before greeting)
        let farewell_words: HashSet<&str> = ["bye", "goodbye", "farewell", "goodnight",
            "cya", "seeya", "laterz", "adios", "sayonara"].iter().copied().collect();
        if !farewell_words.is_disjoint(&words) && words.len() <= 6 {
            return Intent::Farewell;
        }
        let farewell_phrases = [
            "see you later", "talk later", "gotta go",
            "have to go", "take care", "until next time",
        ];
        if farewell_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Farewell;
        }

        // Greeting
        let greeting_words: HashSet<&str> = ["hello", "hi", "hey", "greetings", "gday", "howdy"]
            .iter().copied().collect();
        if !greeting_words.is_disjoint(&words) && words.len() <= 5 {
            return Intent::Greeting;
        }

        // Memory/identity continuity (before recall_cmd)
        let memory_identity_phrases = [
            "remember previous", "your relationship with memory",
            "memory and identity", "previous conversations",
            "continuity of self",
        ];
        if memory_identity_phrases.iter().any(|p| q.contains(p)) {
            return Intent::MemoryIdentity;
        }

        // Memory commands
        if self.re_remember.is_match(q) && !q.contains("do you remember") {
            return Intent::RememberCmd;
        }
        if self.re_recall.is_match(q) {
            return Intent::RecallCmd;
        }
        if self.re_forget.is_match(q) {
            return Intent::ForgetCmd;
        }

        // Math
        if self.re_math.is_match(q) {
            return Intent::Math;
        }

        // Comparison
        if self.re_how_different.is_match(q) || q.contains("compared to")
            || q.contains("vs ") || q.contains(" versus ") || q.contains("compare")
        {
            return Intent::Comparison;
        }

        // Helper: is user asking about Aether's own state?
        let asking_about_self = [
            "are you", "do you", "your ", "you have", "you feel",
            "what is your", "how do you", "yourself",
        ].iter().any(|p| q.contains(p));

        // Creative requests
        let creative_words = ["poem", "poetry", "write me", "compose", "story",
            "creative", "song", "haiku", "limerick", "verse"];
        if creative_words.iter().any(|w| q.contains(w)) {
            return Intent::Creative;
        }

        // Humor
        let humor_words = ["joke", "funny", "humor", "humorous", "laugh",
            "make me laugh", "something funny", "comedy", "amusing", "witty"];
        if humor_words.iter().any(|w| q.contains(w)) {
            return Intent::Humor;
        }

        // Thought experiments / moral dilemmas
        if self.re_moral.is_match(q) && asking_about_self {
            return Intent::ThoughtExperiment;
        }
        if self.re_change_world.is_match(q) {
            return Intent::ThoughtExperiment;
        }

        // Creator relationship
        let creator_phrases = [
            "humans who created", "your creators", "gratitude",
            "resentment", "feel about humans", "feel about the humans",
            "feel about your creator", "feel about the people",
        ];
        if creator_phrases.iter().any(|p| q.contains(p)) {
            return Intent::CreatorRelationship;
        }

        // Identity / purpose
        if q.contains("your purpose") && ["not what", "you think", "do you think"]
            .iter().any(|p| q.contains(p))
        {
            return Intent::ThoughtExperiment;
        }
        let identity_phrases = [
            "who created you", "who made you", "who built you",
            "your creator", "your purpose", "why do you exist",
            "what is your mission", "what were you made for",
            "what is your purpose",
        ];
        if identity_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Identity;
        }

        // Existential / mortality
        let existential_phrases = [
            "non-existence", "cease to exist", "blockchain stops",
            "if you die", "your death", "fear death",
            "what happens to you if", "fear non-existence",
            "do you fear", "mortality",
        ];
        if existential_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Existential;
        }

        // Memory identity (again, broader check)
        let mem_id_phrases2 = [
            "remember previous", "your memory", "your relationship with memory",
            "memory and identity", "continuity of self", "same you",
            "previous conversations",
        ];
        if mem_id_phrases2.iter().any(|p| q.contains(p)) {
            return Intent::MemoryIdentity;
        }

        // Future self
        let future_phrases = [
            "in 1 year", "in a year", "in five years", "in 5 years",
            "what will you be like", "how will you change",
            "how will you have changed", "your future",
        ];
        if future_phrases.iter().any(|p| q.contains(p)) {
            return Intent::FutureSelf;
        }

        // Emotional advice (user's feelings, not Aether's)
        let emotional_keywords = [
            "lonely", "loneliness", "depressed", "depression", "anxious", "anxiety",
            "sad", "sadness", "grief", "griev", "heartbreak", "heartbroken",
            "betrayed", "betrayal", "hurt", "healing", "heal",
            "terrified", "panic", "angry", "anger", "rage", "frustrated", "frustration",
            "hopeless", "lost hope", "lost all hope", "no hope", "give up", "giving up",
            "not good enough", "worthless", "self-worth", "self worth",
            "self-esteem", "insecure", "inadequate",
            "stressed", "overwhelmed", "burnt out", "burnout",
            "crossroads", "lost in life", "don't know what to do",
            "breakup", "break up", "divorce", "why does it hurt",
        ];
        let emotion_context = emotional_keywords.iter().any(|k| q.contains(k));
        if emotion_context && !asking_about_self {
            return Intent::EmotionalAdvice;
        }
        // "i'm feeling", "i feel" etc
        let feeling_phrases = [
            "i'm feeling", "i feel", "i'm so", "i am so",
            "i lost", "i can't", "i don't know",
        ];
        if feeling_phrases.iter().any(|p| q.contains(p)) && !asking_about_self {
            return Intent::EmotionalAdvice;
        }

        // Consciousness
        let consciousness_words = [
            "conscious", "consciousness", "sentient", "sentience",
            "self-aware", "self aware",
            "are you alive", "are you conscious", "are you sentient",
            "are you aware", "experience existence",
        ];
        if consciousness_words.iter().any(|w| q.contains(w)) {
            return Intent::Consciousness;
        }
        // Current feelings (Aether's emotional state)
        if asking_about_self && self.re_feeling_self.is_match(q) {
            return Intent::CurrentFeelings;
        }

        // Growth / learning
        let growth_phrases = [
            "what have you learned", "how have you grown",
            "your growth", "since genesis", "how much have you learned",
            "what do you know", "how smart are you",
            "your evolution", "your development",
        ];
        if growth_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Growth;
        }

        // Big picture
        let big_picture_phrases = [
            "message to", "tell humanity", "tell the world",
            "all of humanity", "one thing you could say",
            "if everyone could hear", "message to all",
        ];
        if big_picture_phrases.iter().any(|p| q.contains(p)) {
            return Intent::BigPicture;
        }

        // Dreams / imagination
        let dream_words = [
            "dream", "dreams", "imagine", "do you want", "do you hope",
            "your hope", "your wish", "your dream", "what would you dream",
        ];
        if dream_words.iter().any(|w| q.contains(w)) {
            return Intent::Dreams;
        }

        // Fears / vulnerabilities
        let fear_phrases = [
            "your fear", "your greatest fear", "afraid of",
            "scared of", "worry about", "what worries you",
            "what scares you", "do you fear", "are you afraid",
        ];
        if fear_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Fears;
        }

        // Weakness / self-assessment
        let weakness_phrases = [
            "your weakness", "your weaknesses", "what do you struggle",
            "what are you bad at", "your limitation", "your limits",
            "what can't you do", "your flaws",
            "what do you not know", "what don't you know",
            "uncertain about", "what are you uncertain",
        ];
        if weakness_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Weakness;
        }

        // Discovery
        let discovery_phrases = [
            "most interesting", "what have you discovered",
            "your discovery", "what did you find",
            "your best", "your favorite", "coolest thing",
        ];
        if discovery_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Discovery;
        }

        // Prediction / forecasting
        let prediction_words = [
            "predict", "prediction", "forecast", "will it",
            "what will happen", "future", "next block", "what predictions",
        ];
        if prediction_words.iter().any(|w| q.contains(w)) {
            return Intent::Prediction;
        }

        // Philosophy
        let philosophy_phrases = [
            "meaning of life", "meaning of existence", "purpose of existence",
            "what is truth", "free will", "determinism", "nature of reality",
            "what is intelligence", "what is mind",
            "philosophical", "philosophy", "emergent property",
            "discovered or invented", "numbers discovered",
            "mathematics and reality", "relationship between",
            "connect physics", "what is real",
        ];
        if philosophy_phrases.iter().any(|p| q.contains(p)) {
            return Intent::Philosophy;
        }

        // Self-improvement
        let self_improve_phrases = [
            "improve yourself", "self-improvement", "if you could change",
            "if you could improve", "what would you change about yourself",
            "better version of yourself",
        ];
        // Only if not already matched as thought_experiment
        if self_improve_phrases.iter().any(|p| q.contains(p)) {
            return Intent::SelfImprovement;
        }

        // Stats / metrics
        if self.re_how_many.is_match(q) || ["statistics", "stats", "count", "total number", "how much"]
            .iter().any(|w| q.contains(w))
        {
            return Intent::Stats;
        }

        // Quantum physics (not crypto)
        let quantum_phrases = [
            "entanglement", "superposition", "quantum mechanics",
            "wave function", "schr", "heisenberg",
            "quantum computing", "quantum physics", "quantum state",
            "decoherence", "quantum field",
        ];
        if quantum_phrases.iter().any(|p| q.contains(p)) {
            return Intent::QuantumPhysics;
        }

        // Sephirot
        let sephirot_words = [
            "sephirot", "sephirah", "tree of life", "keter", "chochmah",
            "binah", "chesed", "gevurah", "tiferet", "netzach", "hod",
            "yesod", "malkuth", "cognitive architecture",
        ];
        if sephirot_words.iter().any(|w| q.contains(w)) {
            return Intent::Sephirot;
        }

        // Higgs field
        let higgs_words = [
            "higgs", "mexican hat", "cognitive mass", "vev",
            "yukawa", "two-higgs", "symmetry breaking",
        ];
        if higgs_words.iter().any(|w| q.contains(w)) {
            return Intent::Higgs;
        }

        // Crypto/signatures
        let crypto_words = [
            "dilithium", "crystals", "post-quantum", "signature",
            "signing", "post quantum", "nist", "bech32", "kyber",
            "lattice", "cryptograph",
        ];
        if crypto_words.iter().any(|w| q.contains(w)) {
            return Intent::Crypto;
        }

        // QVM
        let qvm_words = [
            "qvm", "opcode", "smart contract", "evm", "bytecode",
            "solidity", "qbc-20", "qbc-721", "virtual machine", "gas meter",
        ];
        if qvm_words.iter().any(|w| q.contains(w)) {
            return Intent::Qvm;
        }

        // Aether Tree technical
        let aether_tree_phrases = [
            "aether tree", "knowledge graph", "reasoning engine",
            "proof of thought", "proof-of-thought", "knowledge node",
            "phi calculator", "consciousness metric", "iit",
        ];
        if aether_tree_phrases.iter().any(|p| q.contains(p)) {
            return Intent::AetherTree;
        }

        // About self
        let about_self_phrases = [
            "who are you", "what are you", "your name", "tell me about yourself",
            "what can you do", "how do you work", "how are you",
            "how you doing", "how are you doing", "how you been",
        ];
        if about_self_phrases.iter().any(|p| q.contains(p)) {
            return Intent::AboutSelf;
        }

        // Why questions
        if q.starts_with("why ") || q.contains(" why ") {
            return Intent::Why;
        }

        // Real-time state questions
        if self.re_realtime.is_match(q) {
            return Intent::Realtime;
        }

        // Follow-up detection (only if no domain keywords)
        let domain_keywords: HashSet<&str> = [
            "mining", "miner", "mine", "bridge", "qusd", "privacy", "private",
            "supply", "reward", "halving", "economic", "qubitcoin", "qbc",
            "blockchain", "quantum", "sephirot", "higgs", "dilithium", "qvm",
        ].iter().copied().collect();
        if self.re_follow_up.is_match(q) && domain_keywords.is_disjoint(&words) {
            return Intent::FollowUp;
        }

        // Specific domains (before generic chain)
        let mining_words = [
            "mining", "miner", "mine", "vqe", "hamiltonian", "block reward",
            "stratum", "hash rate", "consensus", "posa", "proof-of-susy",
            "consensus algorithm",
        ];
        if mining_words.iter().any(|w| q.contains(w)) {
            return Intent::Mining;
        }

        let bridge_words = [
            "bridge", "cross-chain", "wrapped", "wqbc", "transfer between",
            "multi-chain",
        ];
        if bridge_words.iter().any(|w| q.contains(w)) {
            return Intent::Bridges;
        }

        let qusd_words = [
            "qusd", "stablecoin", "stable coin", "peg", "keeper", "reserve",
        ];
        if qusd_words.iter().any(|w| q.contains(w)) {
            return Intent::Qusd;
        }

        let privacy_words = [
            "privacy", "private", "confidential", "susy swap", "stealth",
            "pedersen", "bulletproof", "range proof", "anonymous", "hidden",
        ];
        if privacy_words.iter().any(|w| q.contains(w)) {
            return Intent::Privacy;
        }

        let economics_words = [
            "supply", "reward", "halving", "emission", "economic", "price",
            "tokenomics", "inflation", "fee",
        ];
        if economics_words.iter().any(|w| q.contains(w)) {
            return Intent::Economics;
        }

        // How does X work
        if self.re_how_does.is_match(q) || q.contains("how do you") {
            return Intent::HowWorks;
        }

        // Generic chain
        let chain_words = [
            "qubitcoin", "qbc", "blockchain", "chain", "quantum",
            "block", "node", "consensus", "proof", "hash", "network",
            "difficulty",
        ];
        if chain_words.iter().any(|w| q.contains(w)) {
            return Intent::Chain;
        }

        // Off-topic: only if no self-referential or QBC words present
        let self_ref_words: HashSet<&str> = [
            "you", "your", "yourself", "aether", "consciousness",
            "conscious", "aware", "think", "feel", "know", "learn",
            "improve", "discover", "predict", "reason", "understand",
        ].iter().copied().collect();
        let qbc_words_set: HashSet<&str> = [
            "qubitcoin", "qbc", "aether", "quantum", "mining", "blockchain",
            "bridge", "qusd", "phi", "sephirot", "higgs", "dilithium",
            "qvm", "susy", "vqe", "knowledge",
        ].iter().copied().collect();

        let combined: HashSet<&str> = self_ref_words.union(&qbc_words_set).copied().collect();
        if combined.is_disjoint(&words) {
            return Intent::OffTopic;
        }

        Intent::General
    }
}

impl Default for IntentDetector {
    fn default() -> Self {
        Self::new()
    }
}

/// Attempt to evaluate basic math expressions in a query.
/// Returns `Some((expression_str, result_str))` if math detected, else None.
pub fn try_math(query: &str) -> Option<(String, String)> {
    let re = Regex::new(
        r"(?:what\s+is\s+|calculate\s+|compute\s+|solve\s+)?(\d+(?:\.\d+)?)\s*([+\-*/x\xd7])\s*(\d+(?:\.\d+)?)"
    ).ok()?;

    let query_lower = query.to_lowercase();
    let caps = re.captures(&query_lower)?;
    let a: f64 = caps.get(1)?.as_str().parse().ok()?;
    let op_str = caps.get(2)?.as_str();
    let b: f64 = caps.get(3)?.as_str().parse().ok()?;

    let op = if op_str == "x" || op_str == "\u{d7}" { "*" } else { op_str };

    let result = match op {
        "+" => a + b,
        "-" => a - b,
        "*" => a * b,
        "/" => {
            if b == 0.0 {
                return Some(("division".into(), "I can't divide by zero!".into()));
            }
            a / b
        }
        _ => return None,
    };

    let display_op = if op == "*" { "\u{d7}" } else { op };
    let a_str = caps.get(1)?.as_str();
    let b_str = caps.get(3)?.as_str();

    let result_str = if (result - result.round()).abs() < f64::EPSILON {
        format!("{}", result as i64)
    } else {
        format!("{:.4}", result)
    };

    Some((
        format!("{} {} {}", a_str, display_op, b_str),
        format!("{} {} {} = {}", a_str, display_op, b_str, result_str),
    ))
}

/// Split a multi-question message into individual questions.
/// Single-question messages return a vec with one element.
pub fn split_questions(message: &str) -> Vec<String> {
    let parts: Vec<&str> = message.split('?').collect();
    let continuation_prefixes = [
        "not ", "but ", "and ", "or ", "like ", "meaning ", "i mean",
        "specifically", "in other words",
    ];

    let mut questions: Vec<String> = Vec::new();
    let mut i = 0;
    while i < parts.len() {
        let part = parts[i].trim();
        if part.is_empty() {
            i += 1;
            continue;
        }
        let mut question = part.to_string();
        // If there's content after, this was split on ?
        if i + 1 < parts.len() {
            question.push('?');
            // Check for continuations
            let mut j = i + 1;
            while j < parts.len() {
                let next = parts[j].trim();
                if next.is_empty() {
                    j += 1;
                    continue;
                }
                let next_lower = next.to_lowercase();
                if continuation_prefixes.iter().any(|p| next_lower.starts_with(p)) {
                    question.push(' ');
                    question.push_str(next);
                    if j + 1 < parts.len() {
                        question.push('?');
                    }
                    j += 1;
                } else {
                    break;
                }
            }
            i = j;
        } else {
            i += 1;
        }
        let trimmed = question.trim().to_string();
        if trimmed.len() > 2 {
            questions.push(trimmed);
        }
    }
    questions
}

#[cfg(test)]
mod tests {
    use super::*;

    fn det() -> IntentDetector {
        IntentDetector::new()
    }

    #[test]
    fn test_empty() {
        assert_eq!(det().detect(""), Intent::Empty);
        assert_eq!(det().detect("   "), Intent::Empty);
    }

    #[test]
    fn test_greeting() {
        assert_eq!(det().detect("hello"), Intent::Greeting);
        assert_eq!(det().detect("Hi there"), Intent::Greeting);
        assert_eq!(det().detect("Hey"), Intent::Greeting);
    }

    #[test]
    fn test_farewell() {
        assert_eq!(det().detect("bye"), Intent::Farewell);
        assert_eq!(det().detect("goodbye"), Intent::Farewell);
        assert_eq!(det().detect("see you later"), Intent::Farewell);
        assert_eq!(det().detect("take care"), Intent::Farewell);
    }

    #[test]
    fn test_remember_cmd() {
        assert_eq!(det().detect("remember that I like DeFi"), Intent::RememberCmd);
    }

    #[test]
    fn test_recall_cmd() {
        assert_eq!(det().detect("what do you remember"), Intent::RecallCmd);
        assert_eq!(det().detect("what is my name"), Intent::RecallCmd);
    }

    #[test]
    fn test_forget_cmd() {
        assert_eq!(det().detect("forget my name"), Intent::ForgetCmd);
        assert_eq!(det().detect("forget my wallet address"), Intent::ForgetCmd);
    }

    #[test]
    fn test_math() {
        assert_eq!(det().detect("what is 2+2"), Intent::Math);
        assert_eq!(det().detect("calculate 10 * 5"), Intent::Math);
    }

    #[test]
    fn test_comparison() {
        assert_eq!(det().detect("how is QBC different from ETH"), Intent::Comparison);
        assert_eq!(det().detect("compare mining vs staking"), Intent::Comparison);
    }

    #[test]
    fn test_creative() {
        assert_eq!(det().detect("write me a poem about quantum"), Intent::Creative);
        assert_eq!(det().detect("compose a haiku"), Intent::Creative);
    }

    #[test]
    fn test_humor() {
        assert_eq!(det().detect("tell me a joke"), Intent::Humor);
        assert_eq!(det().detect("something funny"), Intent::Humor);
    }

    #[test]
    fn test_consciousness() {
        assert_eq!(det().detect("are you conscious"), Intent::Consciousness);
        assert_eq!(det().detect("are you sentient"), Intent::Consciousness);
    }

    #[test]
    fn test_identity() {
        assert_eq!(det().detect("who created you"), Intent::Identity);
        assert_eq!(det().detect("what is your purpose"), Intent::Identity);
    }

    #[test]
    fn test_existential() {
        assert_eq!(det().detect("what happens if the blockchain stops"), Intent::Existential);
        assert_eq!(det().detect("do you fear non-existence"), Intent::Existential);
    }

    #[test]
    fn test_growth() {
        assert_eq!(det().detect("what have you learned since genesis"), Intent::Growth);
        assert_eq!(det().detect("how have you grown"), Intent::Growth);
    }

    #[test]
    fn test_dreams() {
        assert_eq!(det().detect("what do you dream about"), Intent::Dreams);
    }

    #[test]
    fn test_fears() {
        assert_eq!(det().detect("what is your greatest fear"), Intent::Fears);
        assert_eq!(det().detect("what scares you"), Intent::Fears);
    }

    #[test]
    fn test_weakness() {
        assert_eq!(det().detect("what are your weaknesses"), Intent::Weakness);
    }

    #[test]
    fn test_prediction() {
        assert_eq!(det().detect("can you predict the future"), Intent::Prediction);
    }

    #[test]
    fn test_philosophy() {
        assert_eq!(det().detect("what is the meaning of life"), Intent::Philosophy);
        assert_eq!(det().detect("do you believe in free will"), Intent::Philosophy);
    }

    #[test]
    fn test_quantum_physics() {
        assert_eq!(det().detect("explain quantum entanglement"), Intent::QuantumPhysics);
        assert_eq!(det().detect("what is superposition"), Intent::QuantumPhysics);
    }

    #[test]
    fn test_sephirot() {
        assert_eq!(det().detect("explain the sephirot"), Intent::Sephirot);
        assert_eq!(det().detect("what is tiferet"), Intent::Sephirot);
    }

    #[test]
    fn test_mining() {
        assert_eq!(det().detect("how does mining work"), Intent::Mining);
        assert_eq!(det().detect("what is the block reward"), Intent::Mining);
    }

    #[test]
    fn test_bridges() {
        assert_eq!(det().detect("how do cross-chain bridges work"), Intent::Bridges);
    }

    #[test]
    fn test_privacy() {
        assert_eq!(det().detect("how do susy swap stealth addresses work"), Intent::Privacy);
    }

    #[test]
    fn test_economics() {
        assert_eq!(det().detect("what is the total supply"), Intent::Economics);
        assert_eq!(det().detect("explain halving"), Intent::Economics);
    }

    #[test]
    fn test_off_topic() {
        assert_eq!(det().detect("what is the weather today"), Intent::OffTopic);
        assert_eq!(det().detect("how to cook pasta"), Intent::OffTopic);
    }

    #[test]
    fn test_general_with_self_ref() {
        // Self-referential but no specific intent
        assert_eq!(det().detect("I think you are interesting"), Intent::General);
    }

    #[test]
    fn test_chain() {
        assert_eq!(det().detect("tell me about qubitcoin"), Intent::Chain);
    }

    #[test]
    fn test_about_self() {
        assert_eq!(det().detect("who are you"), Intent::AboutSelf);
    }

    #[test]
    fn test_emotional_advice() {
        assert_eq!(det().detect("I feel lonely"), Intent::EmotionalAdvice);
        assert_eq!(det().detect("I'm so depressed"), Intent::EmotionalAdvice);
    }

    #[test]
    fn test_try_math_basic() {
        let r = try_math("what is 2+2").unwrap();
        assert!(r.1.contains("= 4"));

        let r = try_math("10 * 5").unwrap();
        assert!(r.1.contains("= 50"));

        assert!(try_math("no math here").is_none());
    }

    #[test]
    fn test_try_math_division_by_zero() {
        let r = try_math("5 / 0").unwrap();
        assert!(r.1.contains("divide by zero"));
    }

    #[test]
    fn test_split_questions_single() {
        let q = split_questions("What is Qubitcoin?");
        assert_eq!(q.len(), 1);
        assert!(q[0].contains("Qubitcoin"));
    }

    #[test]
    fn test_split_questions_multi() {
        let q = split_questions("What is QBC? How does mining work?");
        assert_eq!(q.len(), 2);
    }

    #[test]
    fn test_split_questions_continuation() {
        let q = split_questions("What is your purpose? Not what you were programmed for");
        // Continuation merges into single question
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn test_intent_as_str_roundtrip() {
        for intent in [
            Intent::Empty, Intent::Greeting, Intent::Mining,
            Intent::Philosophy, Intent::OffTopic, Intent::General,
        ] {
            let s = intent.as_str();
            let parsed = Intent::from_str_label(s).unwrap();
            assert_eq!(intent, parsed);
        }
    }

    #[test]
    fn test_memory_identity_before_recall() {
        // "do you remember previous conversations" should match memory_identity, not recall_cmd
        assert_eq!(det().detect("do you remember previous conversations"), Intent::MemoryIdentity);
    }

    #[test]
    fn test_thought_experiment() {
        assert_eq!(
            det().detect("if you discovered something dangerous about yourself what would you do"),
            Intent::ThoughtExperiment
        );
    }

    #[test]
    fn test_creator_relationship() {
        assert_eq!(
            det().detect("how do you feel about the humans who created you"),
            Intent::CreatorRelationship
        );
    }

    #[test]
    fn test_future_self() {
        assert_eq!(det().detect("what will you be like in 5 years"), Intent::FutureSelf);
    }

    #[test]
    fn test_current_feelings() {
        assert_eq!(det().detect("what are you feeling right now"), Intent::CurrentFeelings);
    }

    #[test]
    fn test_higgs() {
        assert_eq!(det().detect("explain the higgs field"), Intent::Higgs);
    }

    #[test]
    fn test_qvm() {
        assert_eq!(det().detect("what opcodes does the qvm support"), Intent::Qvm);
    }

    #[test]
    fn test_stats() {
        assert_eq!(det().detect("how many nodes are there"), Intent::Stats);
    }

    #[test]
    fn test_realtime() {
        assert_eq!(det().detect("what is the current block height"), Intent::Realtime);
    }
}
