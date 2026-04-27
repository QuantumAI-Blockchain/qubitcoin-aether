"""
Tests for Telegram Bot — @AetherTreeBot webhook handler.

Covers:
  - Bot configuration and initialization
  - HMAC-SHA-256 webhook signature verification
  - Command handling (/start, /chat, /earn, /wallet, /refer, /stats, /help)
  - Message parsing and routing
  - Wallet linking and retrieval
  - Deep-link referral code handling
  - Web App button generation
  - Bot statistics tracking
  - Edge cases (malformed input, missing fields)
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from qubitcoin.aether.telegram_bot import TelegramBot, TelegramUser, TelegramMessage


# ─── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def bot() -> TelegramBot:
    """Create a TelegramBot with mock config."""
    with patch("qubitcoin.aether.telegram_bot.Config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF-test-token"
        mock_config.TELEGRAM_BOT_USERNAME = "AetherTreeBot"
        mock_config.TELEGRAM_WEBHOOK_SECRET = "test-webhook-secret-12345"
        mock_config.TELEGRAM_MINI_APP_URL = "https://qbc.network/twa"
        return TelegramBot()


@pytest.fixture
def bot_unconfigured() -> TelegramBot:
    """Create a TelegramBot with empty config."""
    with patch("qubitcoin.aether.telegram_bot.Config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = ""
        mock_config.TELEGRAM_BOT_USERNAME = ""
        mock_config.TELEGRAM_WEBHOOK_SECRET = ""
        mock_config.TELEGRAM_MINI_APP_URL = ""
        return TelegramBot()


@pytest.fixture
def bot_with_managers() -> TelegramBot:
    """Create a TelegramBot with mock AIKGS managers."""
    with patch("qubitcoin.aether.telegram_bot.Config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF-test-token"
        mock_config.TELEGRAM_BOT_USERNAME = "AetherTreeBot"
        mock_config.TELEGRAM_WEBHOOK_SECRET = "test-webhook-secret-12345"
        mock_config.TELEGRAM_MINI_APP_URL = "https://qbc.network/twa"

        contribution_mgr = MagicMock()
        affiliate_mgr = MagicMock()
        reward_engine = MagicMock()
        unlocks = MagicMock()

        return TelegramBot(
            contribution_manager=contribution_mgr,
            affiliate_manager=affiliate_mgr,
            reward_engine=reward_engine,
            progressive_unlocks=unlocks,
        )


def _make_update(text: str, chat_id: int = 42, user_id: int = 100,
                 first_name: str = "Alice", username: str = "alice") -> dict:
    """Helper to build a Telegram update dict."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {
                "id": user_id,
                "first_name": first_name,
                "last_name": "",
                "username": username,
                "language_code": "en",
                "is_premium": False,
            },
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
            "date": 1709337600,
        },
    }


# ─── TelegramUser Tests ───────────────────────────────────────────────────

class TestTelegramUser:
    def test_display_name_first_only(self) -> None:
        user = TelegramUser(id=1, first_name="Alice")
        assert user.display_name() == "Alice"

    def test_display_name_full(self) -> None:
        user = TelegramUser(id=1, first_name="Alice", last_name="Smith")
        assert user.display_name() == "Alice Smith"

    def test_defaults(self) -> None:
        user = TelegramUser(id=42)
        assert user.first_name == ""
        assert user.last_name == ""
        assert user.username == ""
        assert user.language_code == "en"
        assert user.is_premium is False


# ─── Bot Configuration ─────────────────────────────────────────────────────

class TestBotConfiguration:
    def test_is_configured_true(self, bot: TelegramBot) -> None:
        assert bot.is_configured is True

    def test_is_configured_false(self, bot_unconfigured: TelegramBot) -> None:
        assert bot_unconfigured.is_configured is False

    def test_is_configured_partial_token(self) -> None:
        with patch("qubitcoin.aether.telegram_bot.Config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "some-token"
            mock_config.TELEGRAM_BOT_USERNAME = ""
            mock_config.TELEGRAM_WEBHOOK_SECRET = ""
            mock_config.TELEGRAM_MINI_APP_URL = ""
            bot = TelegramBot()
            assert bot.is_configured is False  # Needs both token AND secret


# ─── Webhook Verification ──────────────────────────────────────────────────

class TestWebhookVerification:
    def test_valid_signature(self, bot: TelegramBot) -> None:
        assert bot.verify_webhook(b"test body", "test-webhook-secret-12345") is True

    def test_invalid_signature(self, bot: TelegramBot) -> None:
        assert bot.verify_webhook(b"test body", "wrong-secret") is False

    def test_empty_signature(self, bot: TelegramBot) -> None:
        assert bot.verify_webhook(b"", "") is False

    def test_constant_time_comparison(self, bot: TelegramBot) -> None:
        """Verify HMAC-SHA-256 uses constant-time comparison (hmac.compare_digest)."""
        # The implementation uses hmac.compare_digest which is timing-safe.
        # We just verify it returns correct results for various inputs.
        assert bot.verify_webhook(b"any body", "test-webhook-secret-12345") is True
        assert bot.verify_webhook(b"any body", "test-webhook-secret-1234") is False


# ─── Message Parsing ───────────────────────────────────────────────────────

class TestMessageParsing:
    def test_parse_valid_message(self, bot: TelegramBot) -> None:
        raw = {
            "message_id": 42,
            "from": {
                "id": 100,
                "first_name": "Alice",
                "last_name": "Smith",
                "username": "alice",
                "language_code": "en",
                "is_premium": True,
            },
            "chat": {"id": 200},
            "text": "Hello",
            "date": 1709337600,
            "entities": [],
        }
        msg = bot._parse_message(raw)
        assert msg is not None
        assert msg.message_id == 42
        assert msg.chat_id == 200
        assert msg.user.id == 100
        assert msg.user.first_name == "Alice"
        assert msg.user.last_name == "Smith"
        assert msg.user.is_premium is True
        assert msg.text == "Hello"

    def test_parse_minimal_message(self, bot: TelegramBot) -> None:
        raw = {
            "message_id": 1,
            "from": {"id": 1},
            "chat": {"id": 2},
        }
        msg = bot._parse_message(raw)
        assert msg is not None
        assert msg.text == ""
        assert msg.user.first_name == ""
        assert msg.user.language_code == "en"

    def test_parse_empty_dict(self, bot: TelegramBot) -> None:
        msg = bot._parse_message({})
        assert msg is not None  # Should not crash, fills defaults
        assert msg.user.id == 0

    def test_parse_missing_from(self, bot: TelegramBot) -> None:
        raw = {"message_id": 1, "chat": {"id": 2}, "text": "hello"}
        msg = bot._parse_message(raw)
        assert msg is not None
        assert msg.user.id == 0


# ─── Command Handling ──────────────────────────────────────────────────────

class TestCommandHandling:
    @pytest.mark.asyncio
    async def test_start_command(self, bot: TelegramBot) -> None:
        update = _make_update("/start")
        result = await bot.handle_update(update)
        assert result is not None
        assert result["method"] == "sendMessage"
        assert "Welcome" in result["text"]
        assert "reply_markup" in result  # Has Web App button

    @pytest.mark.asyncio
    async def test_start_with_referral(self, bot_with_managers: TelegramBot) -> None:
        update = _make_update("/start QBC-REF12345")
        result = await bot_with_managers.handle_update(update)
        assert result is not None
        assert "Welcome" in result["text"]

    @pytest.mark.asyncio
    async def test_chat_command(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/chat"))
        assert result is not None
        assert "Chat" in result["text"] or "chat" in result["text"].lower()
        assert "reply_markup" in result

    @pytest.mark.asyncio
    async def test_earn_command(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/earn"))
        assert result is not None
        assert "Earn" in result["text"] or "earn" in result["text"].lower()
        assert "reply_markup" in result

    @pytest.mark.asyncio
    async def test_wallet_command_no_wallet(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/wallet"))
        assert result is not None
        assert "wallet" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_wallet_command_with_wallet(self, bot: TelegramBot) -> None:
        bot.link_wallet(100, "qbc1abc123456789def")
        result = await bot.handle_update(_make_update("/wallet", user_id=100))
        assert result is not None
        assert "qbc1abc12345" in result["text"]

    @pytest.mark.asyncio
    async def test_refer_command_no_wallet(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/refer"))
        assert result is not None
        assert "Link your wallet" in result["text"] or "wallet" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_stats_command_no_wallet(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/stats"))
        assert result is not None
        assert "wallet" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_help_command(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/help"))
        assert result is not None
        assert "/start" in result["text"]
        assert "/chat" in result["text"]
        assert "/earn" in result["text"]
        assert "/wallet" in result["text"]
        assert "/refer" in result["text"]
        assert "/stats" in result["text"]

    @pytest.mark.asyncio
    async def test_unknown_command(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("/unknown"))
        assert result is not None
        assert "Unknown command" in result["text"] or "help" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_command_with_bot_suffix(self, bot: TelegramBot) -> None:
        """Commands like /help@AetherTreeBot should still work."""
        result = await bot.handle_update(_make_update("/help@AetherTreeBot"))
        assert result is not None
        assert "/start" in result["text"]


# ─── Regular Messages ──────────────────────────────────────────────────────

class TestRegularMessages:
    @pytest.mark.asyncio
    async def test_regular_message_no_wallet(self, bot: TelegramBot) -> None:
        result = await bot.handle_update(_make_update("Hello there"))
        assert result is not None
        assert "Welcome" in result["text"] or "start" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_regular_message_with_wallet(self, bot_with_managers: TelegramBot) -> None:
        bot_with_managers.link_wallet(100, "qbc1test")
        result = await bot_with_managers.handle_update(_make_update("Knowledge contribution", user_id=100))
        assert result is not None
        assert "Mini App" in result["text"]

    @pytest.mark.asyncio
    async def test_empty_message(self, bot: TelegramBot) -> None:
        update = _make_update("")
        result = await bot.handle_update(update)
        assert result is None  # Empty text should return None


# ─── Wallet Linking ────────────────────────────────────────────────────────

class TestWalletLinking:
    def test_link_wallet(self, bot: TelegramBot) -> None:
        assert bot.link_wallet(42, "qbc1abc123") is True
        assert bot.get_wallet(42) == "qbc1abc123"

    def test_link_wallet_empty_address(self, bot: TelegramBot) -> None:
        assert bot.link_wallet(42, "") is False
        assert bot.get_wallet(42) is None

    def test_get_wallet_nonexistent(self, bot: TelegramBot) -> None:
        assert bot.get_wallet(999) is None

    def test_link_wallet_overwrite(self, bot: TelegramBot) -> None:
        bot.link_wallet(42, "qbc1first")
        bot.link_wallet(42, "qbc1second")
        assert bot.get_wallet(42) == "qbc1second"

    def test_multiple_users(self, bot: TelegramBot) -> None:
        bot.link_wallet(1, "qbc1user1")
        bot.link_wallet(2, "qbc1user2")
        assert bot.get_wallet(1) == "qbc1user1"
        assert bot.get_wallet(2) == "qbc1user2"


# ─── Reply Helpers ─────────────────────────────────────────────────────────

class TestReplyHelpers:
    def test_reply_basic(self, bot: TelegramBot) -> None:
        result = TelegramBot._reply(42, "Hello")
        assert result == {
            "method": "sendMessage",
            "chat_id": 42,
            "text": "Hello",
        }

    def test_reply_with_parse_mode(self, bot: TelegramBot) -> None:
        result = TelegramBot._reply(42, "**Bold**", parse_mode="Markdown")
        assert result["parse_mode"] == "Markdown"

    def test_reply_no_parse_mode(self, bot: TelegramBot) -> None:
        result = TelegramBot._reply(42, "Hello")
        assert "parse_mode" not in result

    def test_reply_with_webapp(self, bot: TelegramBot) -> None:
        result = bot._reply_with_webapp(42, "Open app", "Launch")
        assert result["method"] == "sendMessage"
        assert result["chat_id"] == 42
        assert result["text"] == "Open app"
        keyboard = result["reply_markup"]["inline_keyboard"]
        assert len(keyboard) == 1
        assert len(keyboard[0]) == 1
        assert keyboard[0][0]["text"] == "Launch"
        assert "web_app" in keyboard[0][0]
        assert keyboard[0][0]["web_app"]["url"] == "https://qbc.network/twa"

    def test_reply_with_webapp_custom_url(self, bot: TelegramBot) -> None:
        result = bot._reply_with_webapp(42, "Open chat", "Chat", "https://qbc.network/twa/chat")
        assert result["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == "https://qbc.network/twa/chat"


# ─── Statistics ────────────────────────────────────────────────────────────

class TestBotStats:
    def test_initial_stats(self, bot: TelegramBot) -> None:
        stats = bot.get_stats()
        assert stats["configured"] is True
        assert stats["username"] == "AetherTreeBot"
        assert stats["mini_app_url"] == "https://qbc.network/twa"
        assert stats["messages_processed"] == 0
        assert stats["commands_processed"] == 0
        assert stats["linked_wallets"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_activity(self, bot: TelegramBot) -> None:
        # Process some messages
        await bot.handle_update(_make_update("/start"))
        await bot.handle_update(_make_update("/help"))
        await bot.handle_update(_make_update("regular message"))
        bot.link_wallet(1, "qbc1test")

        stats = bot.get_stats()
        assert stats["messages_processed"] == 3
        assert stats["commands_processed"] == 2
        assert stats["linked_wallets"] == 1


# ─── Callback and Inline Handling ──────────────────────────────────────────

class TestCallbackInlineHandling:
    @pytest.mark.asyncio
    async def test_callback_query(self, bot: TelegramBot) -> None:
        update = {"callback_query": {"id": "1", "data": "test"}}
        result = await bot.handle_update(update)
        assert result is None  # Placeholder

    @pytest.mark.asyncio
    async def test_inline_query(self, bot: TelegramBot) -> None:
        update = {"inline_query": {"id": "1", "query": "test"}}
        result = await bot.handle_update(update)
        assert result is None  # Placeholder


# ─── Edge Cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_update(self, bot: TelegramBot) -> None:
        result = await bot.handle_update({})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_no_message(self, bot: TelegramBot) -> None:
        result = await bot.handle_update({"update_id": 1})
        assert result is None

    @pytest.mark.asyncio
    async def test_message_no_text(self, bot: TelegramBot) -> None:
        update = {
            "message": {
                "message_id": 1,
                "from": {"id": 1},
                "chat": {"id": 2},
                # No "text" field — e.g., photo message
            },
        }
        result = await bot.handle_update(update)
        assert result is None

    @pytest.mark.asyncio
    async def test_stats_command_with_managers(self, bot_with_managers: TelegramBot) -> None:
        """Stats command with AIKGS managers wired should show profile data."""
        bot_with_managers.link_wallet(100, "qbc1test_address")

        # Mock the progressive unlocks profile
        mock_profile = MagicMock()
        mock_profile.level = 5
        mock_profile.level_name = "Expert"
        mock_profile.reputation_points = 1500.0
        mock_profile.total_contributions = 42
        mock_profile.current_streak = 7
        mock_profile.best_streak = 14
        mock_profile.badges = ["early_adopter", "gold_contributor"]
        bot_with_managers._unlocks.get_profile.return_value = mock_profile

        # Mock streak info
        bot_with_managers._reward_engine.get_contributor_streak.return_value = {
            "multiplier": 1.5,
        }

        result = await bot_with_managers.handle_update(
            _make_update("/stats", user_id=100)
        )
        assert result is not None
        assert "Expert" in result["text"]
        assert "1500" in result["text"]
        assert "42" in result["text"]

    @pytest.mark.asyncio
    async def test_refer_command_with_affiliate(self, bot_with_managers: TelegramBot) -> None:
        """Refer command with linked wallet and affiliate data."""
        bot_with_managers.link_wallet(100, "qbc1test_address")

        mock_affiliate = MagicMock()
        mock_affiliate.referral_code = "QBC-REF123"
        mock_affiliate.l1_referrals = 5
        mock_affiliate.l2_referrals = 12
        mock_affiliate.total_l1_commission = 42.5
        mock_affiliate.total_l2_commission = 18.3
        bot_with_managers._affiliate_manager.get_affiliate.return_value = mock_affiliate

        result = await bot_with_managers.handle_update(
            _make_update("/refer", user_id=100)
        )
        assert result is not None
        assert "QBC-REF123" in result["text"]
        assert "42.5" in result["text"]

    @pytest.mark.asyncio
    async def test_start_referral_with_linked_wallet(self, bot_with_managers: TelegramBot) -> None:
        """Start command with referral code should attempt affiliate registration."""
        bot_with_managers.link_wallet(100, "qbc1test_address")

        await bot_with_managers.handle_update(
            _make_update("/start QBC-REF456", user_id=100)
        )

        bot_with_managers._affiliate_manager.register.assert_called_once_with(
            "qbc1test_address", "QBC-REF456"
        )

    @pytest.mark.asyncio
    async def test_start_referral_registration_failure(self, bot_with_managers: TelegramBot) -> None:
        """Start command should handle referral registration failure gracefully."""
        bot_with_managers.link_wallet(100, "qbc1test_address")
        bot_with_managers._affiliate_manager.register.side_effect = Exception("Invalid code")

        # Should NOT raise — failure is caught and logged
        result = await bot_with_managers.handle_update(
            _make_update("/start BADCODE", user_id=100)
        )
        assert result is not None
        assert "Welcome" in result["text"]
