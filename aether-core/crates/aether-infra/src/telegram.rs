//! Telegram bot message types, command parser, and response formatter.
//!
//! Provides parsing of Telegram webhook payloads, command routing, reply
//! construction (including Mini App buttons), wallet linking, and bot
//! statistics. Actual HTTP I/O (sending messages, receiving webhooks) is
//! handled by the API layer.
//!
//! Ported from: `src/qubitcoin/aether/telegram_bot.py` (477 LOC)

use std::collections::HashMap;

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ─── Telegram User ──────────────────────────────────────────────────────────

/// Telegram user data extracted from a webhook update.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct TelegramUser {
    pub id: i64,
    pub first_name: String,
    pub last_name: String,
    pub username: String,
    pub language_code: String,
    pub is_premium: bool,
}

#[pymethods]
impl TelegramUser {
    #[new]
    #[pyo3(signature = (id, first_name="".to_string(), last_name="".to_string(), username="".to_string(), language_code="en".to_string(), is_premium=false))]
    pub fn new(
        id: i64,
        first_name: String,
        last_name: String,
        username: String,
        language_code: String,
        is_premium: bool,
    ) -> Self {
        Self {
            id,
            first_name,
            last_name,
            username,
            language_code,
            is_premium,
        }
    }

    /// Formatted display name.
    pub fn display_name(&self) -> String {
        if self.last_name.is_empty() {
            self.first_name.clone()
        } else {
            format!("{} {}", self.first_name, self.last_name)
        }
    }

    /// Parse from a Telegram "from" JSON object.
    #[staticmethod]
    pub fn from_json(json_str: &str) -> PyResult<Self> {
        let v: serde_json::Value = serde_json::from_str(json_str)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(Self {
            id: v["id"].as_i64().unwrap_or(0),
            first_name: v["first_name"].as_str().unwrap_or("").to_string(),
            last_name: v["last_name"].as_str().unwrap_or("").to_string(),
            username: v["username"].as_str().unwrap_or("").to_string(),
            language_code: v["language_code"].as_str().unwrap_or("en").to_string(),
            is_premium: v["is_premium"].as_bool().unwrap_or(false),
        })
    }
}

// ─── Telegram Message ───────────────────────────────────────────────────────

/// A parsed Telegram message from a webhook update.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct TelegramMessage {
    pub message_id: i64,
    pub chat_id: i64,
    pub user: TelegramUser,
    pub text: String,
    pub date: i64,
}

#[pymethods]
impl TelegramMessage {
    #[new]
    #[pyo3(signature = (message_id, chat_id, user, text="".to_string(), date=0))]
    pub fn new(
        message_id: i64,
        chat_id: i64,
        user: TelegramUser,
        text: String,
        date: i64,
    ) -> Self {
        Self {
            message_id,
            chat_id,
            user,
            text,
            date,
        }
    }

    /// Parse a raw Telegram message JSON object.
    #[staticmethod]
    pub fn from_json(json_str: &str) -> PyResult<Option<Self>> {
        let v: serde_json::Value = serde_json::from_str(json_str)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

        let user_data = &v["from"];
        if user_data.is_null() {
            return Ok(None);
        }

        let user = TelegramUser {
            id: user_data["id"].as_i64().unwrap_or(0),
            first_name: user_data["first_name"].as_str().unwrap_or("").to_string(),
            last_name: user_data["last_name"].as_str().unwrap_or("").to_string(),
            username: user_data["username"].as_str().unwrap_or("").to_string(),
            language_code: user_data["language_code"]
                .as_str()
                .unwrap_or("en")
                .to_string(),
            is_premium: user_data["is_premium"].as_bool().unwrap_or(false),
        };

        let chat = &v["chat"];
        Ok(Some(Self {
            message_id: v["message_id"].as_i64().unwrap_or(0),
            chat_id: chat["id"].as_i64().unwrap_or(0),
            user,
            text: v["text"].as_str().unwrap_or("").to_string(),
            date: v["date"].as_i64().unwrap_or(0),
        }))
    }
}

// ─── Command Types ──────────────────────────────────────────────────────────

/// Recognized bot commands.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[pyclass(eq, eq_int)]
pub enum TelegramCommand {
    Start,
    Chat,
    Earn,
    Wallet,
    Refer,
    Stats,
    Help,
    Unknown,
}

#[pymethods]
impl TelegramCommand {
    /// Parse a command string (e.g. "/start", "/chat@BotName").
    #[staticmethod]
    pub fn parse(text: &str) -> (Self, Vec<String>) {
        let trimmed = text.trim();
        if !trimmed.starts_with('/') {
            return (Self::Unknown, Vec::new());
        }

        let parts: Vec<&str> = trimmed.split_whitespace().collect();
        let cmd_part = parts[0].to_lowercase();
        // Strip @BotUsername suffix
        let cmd = cmd_part.split('@').next().unwrap_or("");
        let args: Vec<String> = parts[1..].iter().map(|s| s.to_string()).collect();

        let command = match cmd {
            "/start" => Self::Start,
            "/chat" => Self::Chat,
            "/earn" => Self::Earn,
            "/wallet" => Self::Wallet,
            "/refer" => Self::Refer,
            "/stats" => Self::Stats,
            "/help" => Self::Help,
            _ => Self::Unknown,
        };

        (command, args)
    }

    /// Wire-format string.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Start => "/start",
            Self::Chat => "/chat",
            Self::Earn => "/earn",
            Self::Wallet => "/wallet",
            Self::Refer => "/refer",
            Self::Stats => "/stats",
            Self::Help => "/help",
            Self::Unknown => "/unknown",
        }
    }
}

// ─── Reply Types ────────────────────────────────────────────────────────────

/// A constructed Telegram reply (sendMessage payload).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct TelegramReply {
    pub method: String,
    pub chat_id: i64,
    pub text: String,
    pub parse_mode: Option<String>,
    /// JSON-encoded reply_markup (inline keyboard with web_app button).
    pub reply_markup: Option<String>,
}

#[pymethods]
impl TelegramReply {
    /// Create a simple text reply.
    #[staticmethod]
    #[pyo3(signature = (chat_id, text, parse_mode=None))]
    pub fn text(chat_id: i64, text: String, parse_mode: Option<String>) -> Self {
        Self {
            method: "sendMessage".to_string(),
            chat_id,
            text,
            parse_mode,
            reply_markup: None,
        }
    }

    /// Create a reply with a Mini App inline button.
    #[staticmethod]
    pub fn with_webapp(
        chat_id: i64,
        text: String,
        button_text: String,
        webapp_url: String,
    ) -> Self {
        let markup = serde_json::json!({
            "inline_keyboard": [[{
                "text": button_text,
                "web_app": {"url": webapp_url}
            }]]
        });

        Self {
            method: "sendMessage".to_string(),
            chat_id,
            text,
            parse_mode: None,
            reply_markup: Some(markup.to_string()),
        }
    }

    /// Serialize to JSON for sending.
    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}

// ─── Bot Config ─────────────────────────────────────────────────────────────

/// Telegram bot configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all, set_all)]
pub struct TelegramBotConfig {
    pub token: String,
    pub username: String,
    pub webhook_secret: String,
    pub mini_app_url: String,
}

#[pymethods]
impl TelegramBotConfig {
    #[new]
    #[pyo3(signature = (token="".to_string(), username="".to_string(), webhook_secret="".to_string(), mini_app_url="https://qbc.network".to_string()))]
    pub fn new(
        token: String,
        username: String,
        webhook_secret: String,
        mini_app_url: String,
    ) -> Self {
        Self {
            token,
            username,
            webhook_secret,
            mini_app_url,
        }
    }

    /// Check if the bot is properly configured.
    pub fn is_configured(&self) -> bool {
        !self.token.is_empty() && !self.webhook_secret.is_empty()
    }

    /// Verify a webhook secret token (constant-time comparison).
    pub fn verify_webhook(&self, signature: &str) -> bool {
        // Constant-time comparison
        if signature.len() != self.webhook_secret.len() {
            return false;
        }
        let mut diff = 0u8;
        for (a, b) in signature.bytes().zip(self.webhook_secret.bytes()) {
            diff |= a ^ b;
        }
        diff == 0
    }

    /// Build the referral deep link URL.
    pub fn referral_link(&self, referral_code: &str) -> String {
        format!("https://t.me/{}?start={}", self.username, referral_code)
    }
}

// ─── Command Parser / Response Builder ──────────────────────────────────────

/// Bot statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct TelegramBotStats {
    pub messages_processed: u64,
    pub commands_processed: u64,
    pub linked_wallets: usize,
    pub active_sessions: usize,
}

/// Stateful command parser and response builder.
/// Manages wallet links, session tracking, and message counting.
#[pyclass]
pub struct TelegramCommandParser {
    config: TelegramBotConfig,
    /// telegram_user_id -> QBC wallet address
    user_wallets: HashMap<i64, String>,
    /// telegram_user_id -> session_id
    user_sessions: HashMap<i64, String>,
    messages_processed: u64,
    commands_processed: u64,
}

#[pymethods]
impl TelegramCommandParser {
    #[new]
    pub fn new(config: TelegramBotConfig) -> Self {
        Self {
            config,
            user_wallets: HashMap::new(),
            user_sessions: HashMap::new(),
            messages_processed: 0,
            commands_processed: 0,
        }
    }

    /// Link a Telegram user to a QBC wallet address.
    pub fn link_wallet(&mut self, telegram_user_id: i64, qbc_address: String) -> bool {
        if qbc_address.is_empty() {
            return false;
        }
        self.user_wallets.insert(telegram_user_id, qbc_address);
        true
    }

    /// Get linked wallet for a Telegram user.
    pub fn get_wallet(&self, telegram_user_id: i64) -> Option<String> {
        self.user_wallets.get(&telegram_user_id).cloned()
    }

    /// Get or create a chat session ID for a Telegram user.
    pub fn get_session(&mut self, telegram_user_id: i64) -> String {
        self.user_sessions
            .entry(telegram_user_id)
            .or_insert_with(|| format!("tg-{}", telegram_user_id))
            .clone()
    }

    /// Increment message counter.
    pub fn record_message(&mut self) {
        self.messages_processed += 1;
    }

    /// Increment command counter.
    pub fn record_command(&mut self) {
        self.commands_processed += 1;
    }

    /// Build the /start welcome reply.
    pub fn build_start_reply(&self, chat_id: i64, display_name: &str) -> TelegramReply {
        let welcome = format!(
            "Welcome to Aether Tree, {}!\n\n\
             I'm the AGI reasoning engine of the Qubitcoin blockchain. \
             Contribute knowledge, earn QBC rewards, and help build humanity's first on-chain AGI.\n\n\
             Quick Start:\n\
             /chat \u{2014} Open the Aether Chat\n\
             /earn \u{2014} Start earning QBC\n\
             /wallet \u{2014} Link your wallet\n\
             /refer \u{2014} Get your referral link\n\
             /stats \u{2014} View your stats\n\n",
            display_name
        );
        TelegramReply::with_webapp(
            chat_id,
            welcome,
            "Open Aether Tree".to_string(),
            self.config.mini_app_url.clone(),
        )
    }

    /// Build the /chat reply with Mini App button.
    pub fn build_chat_reply(&self, chat_id: i64) -> TelegramReply {
        TelegramReply::with_webapp(
            chat_id,
            "Open the Aether Chat to talk with the AGI and contribute knowledge.".into(),
            "Open Chat".into(),
            format!("{}/chat", self.config.mini_app_url),
        )
    }

    /// Build the /earn reply.
    pub fn build_earn_reply(&self, chat_id: i64) -> TelegramReply {
        let text = "\
            How to Earn QBC with AIKGS:\n\n\
            1. Chat with Aether \u{2014} every quality message earns rewards\n\
            2. Upload knowledge \u{2014} contribute to the knowledge graph\n\
            3. Complete bounties \u{2014} fill knowledge gaps for bonus QBC\n\
            4. Refer friends \u{2014} earn 10% L1 + 5% L2 commissions\n\
            5. Maintain streaks \u{2014} daily contributions boost rewards up to 2x\n\n\
            Quality tiers determine your multiplier:\n\
              Bronze (0.5x) \u{2192} Silver (1.0x) \u{2192} Gold (2.0x) \u{2192} Diamond (5.0x)\n"
            .to_string();
        TelegramReply::with_webapp(
            chat_id,
            text,
            "Start Earning".into(),
            format!("{}/earn", self.config.mini_app_url),
        )
    }

    /// Build the /wallet reply.
    pub fn build_wallet_reply(&self, chat_id: i64, telegram_user_id: i64) -> TelegramReply {
        let text = if let Some(wallet) = self.user_wallets.get(&telegram_user_id) {
            format!(
                "Linked wallet: `{}...{}`\n\nUse the Mini App to manage your wallet.",
                &wallet[..wallet.len().min(12)],
                &wallet[wallet.len().saturating_sub(8)..]
            )
        } else {
            "No wallet linked yet. Open the Mini App to connect your QBC wallet.".to_string()
        };
        TelegramReply::with_webapp(
            chat_id,
            text,
            "Open Wallet".into(),
            format!("{}/wallet", self.config.mini_app_url),
        )
    }

    /// Build the /help reply.
    pub fn build_help_reply(&self, chat_id: i64) -> TelegramReply {
        let text = format!(
            "Aether Tree Bot Commands:\n\n\
             /start \u{2014} Welcome & onboarding\n\
             /chat \u{2014} Open the Aether Chat\n\
             /earn \u{2014} How to earn QBC\n\
             /wallet \u{2014} Link/view your wallet\n\
             /refer \u{2014} Get your referral link\n\
             /stats \u{2014} View your stats\n\
             /help \u{2014} This help message\n\n\
             Mini App: {}\n\
             Website: https://qbc.network",
            self.config.mini_app_url
        );
        TelegramReply::text(chat_id, text, None)
    }

    /// Build a "wallet needed" reply.
    pub fn build_wallet_needed_reply(&self, chat_id: i64) -> TelegramReply {
        TelegramReply::text(
            chat_id,
            "Link your wallet first to use this feature. Use /wallet to connect.".into(),
            None,
        )
    }

    /// Build an "unknown command" reply.
    pub fn build_unknown_command_reply(&self, chat_id: i64) -> TelegramReply {
        TelegramReply::text(
            chat_id,
            "Unknown command. Use /help to see available commands.".into(),
            None,
        )
    }

    /// Build an Aether chat response reply.
    #[pyo3(signature = (chat_id, response_text, phi=None, pot_hash=None))]
    pub fn build_aether_response(
        &self,
        chat_id: i64,
        response_text: &str,
        phi: Option<f64>,
        pot_hash: Option<&str>,
    ) -> TelegramReply {
        let mut parts = vec![response_text.to_string()];
        if let Some(phi_val) = phi {
            parts.push(format!("\n\n\u{03a6} = {:.4}", phi_val));
        }
        if let Some(hash) = pot_hash {
            if hash.len() >= 16 {
                parts.push(format!("PoT: {}...", &hash[..16]));
            }
        }
        TelegramReply::text(chat_id, parts.join("\n"), None)
    }

    /// Get bot statistics.
    pub fn get_stats(&self) -> TelegramBotStats {
        TelegramBotStats {
            messages_processed: self.messages_processed,
            commands_processed: self.commands_processed,
            linked_wallets: self.user_wallets.len(),
            active_sessions: self.user_sessions.len(),
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_telegram_user_display_name() {
        let u = TelegramUser::new(1, "Alice".into(), "".into(), "".into(), "en".into(), false);
        assert_eq!(u.display_name(), "Alice");

        let u2 = TelegramUser::new(2, "Bob".into(), "Smith".into(), "".into(), "en".into(), false);
        assert_eq!(u2.display_name(), "Bob Smith");
    }

    #[test]
    fn test_telegram_user_from_json() {
        let json = r#"{"id": 12345, "first_name": "Alice", "last_name": "B", "username": "alice_b", "language_code": "en", "is_premium": true}"#;
        let user = TelegramUser::from_json(json).unwrap();
        assert_eq!(user.id, 12345);
        assert_eq!(user.first_name, "Alice");
        assert!(user.is_premium);
    }

    #[test]
    fn test_telegram_message_from_json() {
        let json = r#"{
            "message_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "chat": {"id": 99},
            "text": "hello world",
            "date": 1234567890
        }"#;
        let msg = TelegramMessage::from_json(json).unwrap().unwrap();
        assert_eq!(msg.message_id, 100);
        assert_eq!(msg.chat_id, 99);
        assert_eq!(msg.user.id, 42);
        assert_eq!(msg.text, "hello world");
    }

    #[test]
    fn test_telegram_message_no_from() {
        let json = r#"{"message_id": 1, "chat": {"id": 1}, "text": "hi"}"#;
        let msg = TelegramMessage::from_json(json).unwrap();
        assert!(msg.is_none());
    }

    #[test]
    fn test_command_parse_start() {
        let (cmd, args) = TelegramCommand::parse("/start REF-123");
        assert_eq!(cmd, TelegramCommand::Start);
        assert_eq!(args, vec!["REF-123"]);
    }

    #[test]
    fn test_command_parse_with_bot_suffix() {
        let (cmd, _) = TelegramCommand::parse("/help@AetherTreeBot");
        assert_eq!(cmd, TelegramCommand::Help);
    }

    #[test]
    fn test_command_parse_all_commands() {
        for (input, expected) in [
            ("/start", TelegramCommand::Start),
            ("/chat", TelegramCommand::Chat),
            ("/earn", TelegramCommand::Earn),
            ("/wallet", TelegramCommand::Wallet),
            ("/refer", TelegramCommand::Refer),
            ("/stats", TelegramCommand::Stats),
            ("/help", TelegramCommand::Help),
            ("/unknown_cmd", TelegramCommand::Unknown),
        ] {
            let (cmd, _) = TelegramCommand::parse(input);
            assert_eq!(cmd, expected, "Failed for input: {}", input);
        }
    }

    #[test]
    fn test_command_parse_not_command() {
        let (cmd, _) = TelegramCommand::parse("hello world");
        assert_eq!(cmd, TelegramCommand::Unknown);
    }

    #[test]
    fn test_reply_text() {
        let reply = TelegramReply::text(42, "Hello".into(), None);
        assert_eq!(reply.method, "sendMessage");
        assert_eq!(reply.chat_id, 42);
        assert_eq!(reply.text, "Hello");
        assert!(reply.reply_markup.is_none());
    }

    #[test]
    fn test_reply_with_webapp() {
        let reply = TelegramReply::with_webapp(
            42,
            "Click below".into(),
            "Open".into(),
            "https://qbc.network".into(),
        );
        assert!(reply.reply_markup.is_some());
        let markup = reply.reply_markup.unwrap();
        assert!(markup.contains("inline_keyboard"));
        assert!(markup.contains("qbc.network"));
    }

    #[test]
    fn test_bot_config_is_configured() {
        let config = TelegramBotConfig::new(
            "token".into(),
            "bot".into(),
            "secret".into(),
            "https://qbc.network".into(),
        );
        assert!(config.is_configured());

        let empty = TelegramBotConfig::new("".into(), "".into(), "".into(), "".into());
        assert!(!empty.is_configured());
    }

    #[test]
    fn test_bot_config_verify_webhook() {
        let config = TelegramBotConfig::new(
            "token".into(),
            "bot".into(),
            "my-secret".into(),
            "".into(),
        );
        assert!(config.verify_webhook("my-secret"));
        assert!(!config.verify_webhook("wrong-secret"));
        assert!(!config.verify_webhook(""));
    }

    #[test]
    fn test_bot_config_referral_link() {
        let config = TelegramBotConfig::new(
            "".into(),
            "AetherTreeBot".into(),
            "".into(),
            "".into(),
        );
        let link = config.referral_link("REF-ABC");
        assert_eq!(link, "https://t.me/AetherTreeBot?start=REF-ABC");
    }

    #[test]
    fn test_command_parser_wallet() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let mut parser = TelegramCommandParser::new(config);

        assert!(parser.get_wallet(1).is_none());
        assert!(parser.link_wallet(1, "qbc1abc123def456".into()));
        assert_eq!(parser.get_wallet(1).unwrap(), "qbc1abc123def456");

        // Empty address rejected
        assert!(!parser.link_wallet(2, "".into()));
    }

    #[test]
    fn test_command_parser_session() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let mut parser = TelegramCommandParser::new(config);

        let session = parser.get_session(42);
        assert_eq!(session, "tg-42");

        // Same user gets same session
        let session2 = parser.get_session(42);
        assert_eq!(session, session2);
    }

    #[test]
    fn test_command_parser_stats() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let mut parser = TelegramCommandParser::new(config);

        parser.record_message();
        parser.record_message();
        parser.record_command();
        parser.link_wallet(1, "addr1".into());

        let stats = parser.get_stats();
        assert_eq!(stats.messages_processed, 2);
        assert_eq!(stats.commands_processed, 1);
        assert_eq!(stats.linked_wallets, 1);
    }

    #[test]
    fn test_command_parser_build_start() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let parser = TelegramCommandParser::new(config);
        let reply = parser.build_start_reply(42, "Alice");
        assert!(reply.text.contains("Welcome to Aether Tree, Alice"));
        assert!(reply.reply_markup.is_some());
    }

    #[test]
    fn test_command_parser_build_help() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let parser = TelegramCommandParser::new(config);
        let reply = parser.build_help_reply(42);
        assert!(reply.text.contains("/start"));
        assert!(reply.text.contains("/help"));
        assert!(reply.reply_markup.is_none());
    }

    #[test]
    fn test_command_parser_build_aether_response() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let parser = TelegramCommandParser::new(config);
        let reply = parser.build_aether_response(
            42,
            "Hello from Aether!",
            Some(1.5),
            Some("abcdef1234567890extra"),
        );
        assert!(reply.text.contains("Hello from Aether!"));
        assert!(reply.text.contains("\u{03a6} = 1.5000"));
        assert!(reply.text.contains("PoT: abcdef1234567890..."));
    }

    #[test]
    fn test_command_parser_build_wallet_linked() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let mut parser = TelegramCommandParser::new(config);
        parser.link_wallet(1, "qbc1abcdef123456789012".into());

        let reply = parser.build_wallet_reply(42, 1);
        assert!(reply.text.contains("Linked wallet:"));
    }

    #[test]
    fn test_command_parser_build_wallet_not_linked() {
        let config = TelegramBotConfig::new(
            "t".into(), "b".into(), "s".into(), "https://app.qbc.network".into(),
        );
        let parser = TelegramCommandParser::new(config);
        let reply = parser.build_wallet_reply(42, 999);
        assert!(reply.text.contains("No wallet linked"));
    }
}
