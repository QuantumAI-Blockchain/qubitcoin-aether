//! aether-infra: Infrastructure modules for the Aether Tree AI engine.
//!
//! Covers WebSocket event streaming types, AIKGS gRPC client types and
//! circuit breaker, API key vault (encryption, rate limiting, tiers),
//! and Telegram bot message parsing / command routing.
//!
//! All network I/O (actual WebSocket frames, gRPC calls, HTTP) is deferred
//! to the aether-engine orchestrator crate. This crate provides the types,
//! configuration, and pure logic.

pub mod ws_streaming;
pub mod aikgs_client;
pub mod api_vault;
pub mod telegram;

pub use ws_streaming::{
    AetherWSClient, AetherWSManager, WSEvent, WSEventType, WSStats,
};
pub use aikgs_client::{
    AikgsClientConfig, AikgsContribution, AikgsAffiliate, AikgsBounty,
    AikgsProfile, AikgsCurationRound, AikgsReview, AikgsKeyInfo,
    AikgsRewardStats, AikgsContributionStats, AikgsBountyStats,
    AikgsCuratorStats, AikgsCurationStats, AikgsAffiliateStats,
    AikgsUnlocksStats, CircuitBreaker, CircuitState,
};
pub use api_vault::{
    StoredKey, APIKeyVault, ApiTier, RateLimitEntry, VaultStats,
};
pub use telegram::{
    TelegramUser, TelegramMessage, TelegramCommand, TelegramReply,
    TelegramBotConfig, TelegramCommandParser, TelegramBotStats,
};
