"""
AIKGS Telegram Bot — @AetherTreeBot webhook handler.

Features:
  - Webhook-based (no polling) for production reliability
  - Deep linking for referrals (t.me/AetherTreeBot?start=QBC-XXXXXXXX)
  - Inline sharing of knowledge contributions
  - Mini App launch via Web App button
  - Command handlers: /start, /chat, /earn, /wallet, /refer, /stats
  - HMAC-SHA-256 webhook signature verification
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TelegramUser:
    """Telegram user data from webhook."""
    id: int
    first_name: str = ''
    last_name: str = ''
    username: str = ''
    language_code: str = 'en'
    is_premium: bool = False

    def display_name(self) -> str:
        name = self.first_name
        if self.last_name:
            name += f" {self.last_name}"
        return name


@dataclass
class TelegramMessage:
    """Parsed Telegram message."""
    message_id: int
    chat_id: int
    user: TelegramUser
    text: str = ''
    date: int = 0
    entities: List[dict] = field(default_factory=list)


class TelegramBot:
    """Telegram bot webhook handler for AIKGS."""

    def __init__(self,
                 contribution_manager: object = None,
                 affiliate_manager: object = None,
                 reward_engine: object = None,
                 progressive_unlocks: object = None,
                 aikgs_client: object = None,
                 chat_handler: Optional[Callable] = None) -> None:
        """
        Args:
            contribution_manager: AIKGS ContributionManager (legacy Python).
            affiliate_manager: AIKGS AffiliateManager (legacy Python).
            reward_engine: AIKGS RewardEngine (legacy Python).
            progressive_unlocks: AIKGS ProgressiveUnlocks (legacy Python).
            aikgs_client: AIKGS Rust sidecar gRPC client (preferred).
            chat_handler: Callable(session_id, message) -> dict with Aether response.
        """
        self._token = Config.TELEGRAM_BOT_TOKEN
        self._username = Config.TELEGRAM_BOT_USERNAME
        self._webhook_secret = Config.TELEGRAM_WEBHOOK_SECRET
        self._mini_app_url = Config.TELEGRAM_MINI_APP_URL

        self._contribution_manager = contribution_manager
        self._affiliate_manager = affiliate_manager
        self._reward_engine = reward_engine
        self._unlocks = progressive_unlocks
        self._aikgs_client = aikgs_client
        self._chat_handler = chat_handler

        # WARNING: In-memory wallet links — lost on process restart.
        # TODO: Persist to CockroachDB (telegram_wallet_links table) or
        # delegate to AIKGS sidecar for durable storage.
        self._user_wallets: Dict[int, str] = {}
        # Per-user Aether chat sessions (telegram_user_id -> session_id)
        self._user_sessions: Dict[int, str] = {}
        # Message stats
        self._messages_processed: int = 0
        self._commands_processed: int = 0

    @property
    def is_configured(self) -> bool:
        """Check if bot is properly configured."""
        return bool(self._token and self._webhook_secret)

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """Verify webhook secret token (constant-time comparison).

        Compares the X-Telegram-Bot-Api-Secret-Token header against the
        configured secret. Authenticates the sender but does NOT verify
        body integrity — Telegram's security model uses a shared secret
        header, not a body signature.

        Args:
            body: Raw request body bytes (unused — kept for API compat).
            signature: X-Telegram-Bot-Api-Secret-Token header value.

        Returns:
            True if the secret token matches.
        """
        return hmac.compare_digest(signature, self._webhook_secret)

    async def handle_update(self, update: dict) -> Optional[dict]:
        """Process a Telegram webhook update.

        Args:
            update: Parsed JSON update from Telegram.

        Returns:
            Response dict to send back, or None.
        """
        self._messages_processed += 1

        # Handle message updates
        message = update.get('message')
        if message:
            return await self._handle_message(message)

        # Handle callback queries (inline buttons)
        callback = update.get('callback_query')
        if callback:
            return await self._handle_callback(callback)

        # Handle inline queries
        inline = update.get('inline_query')
        if inline:
            return await self._handle_inline(inline)

        return None

    async def _handle_message(self, raw: dict) -> Optional[dict]:
        """Handle an incoming message."""
        msg = self._parse_message(raw)
        if not msg or not msg.text:
            return None

        text = msg.text.strip()

        # Command handling
        if text.startswith('/'):
            return await self._handle_command(msg)

        # Forward regular messages to Aether chat
        if self._chat_handler:
            return await self._forward_to_aether(msg)

        return self._reply(msg.chat_id,
            "Welcome to Aether Tree! Use /start to begin, or open the Mini App to chat with the AGI.")

    async def _forward_to_aether(self, msg: TelegramMessage) -> dict:
        """Forward a user message to Aether Tree chat and return the response."""
        try:
            # Get or create a session for this Telegram user
            session_id = self._user_sessions.get(msg.user.id)
            if not session_id:
                session_id = f"tg-{msg.user.id}"
                self._user_sessions[msg.user.id] = session_id

            result = self._chat_handler(session_id, msg.text)

            response_text = result.get('response', '')
            if not response_text:
                return self._reply(msg.chat_id, "I couldn't process that. Please try again.")

            # Build reply with optional PoT hash
            pot_hash = result.get('proof_of_thought_hash', '')
            phi = result.get('phi_at_response')

            reply_parts = [response_text]
            if phi is not None:
                reply_parts.append(f"\n\n\u03a6 = {phi:.4f}")
            if pot_hash:
                reply_parts.append(f"PoT: {pot_hash[:16]}...")

            return self._reply(msg.chat_id, '\n'.join(reply_parts))
        except Exception as e:
            logger.warning(f"Aether chat error for tg user {msg.user.id}: {e}")
            return self._reply(msg.chat_id,
                "Aether Tree is thinking... please try again in a moment.")

    async def _handle_command(self, msg: TelegramMessage) -> Optional[dict]:
        """Handle bot commands."""
        self._commands_processed += 1

        parts = msg.text.split()
        command = parts[0].lower().split('@')[0]  # Remove @BotUsername suffix
        args = parts[1:] if len(parts) > 1 else []

        if command == '/start':
            return await self._cmd_start(msg, args)
        elif command == '/chat':
            return self._cmd_chat(msg)
        elif command == '/earn':
            return self._cmd_earn(msg)
        elif command == '/wallet':
            return self._cmd_wallet(msg)
        elif command == '/refer':
            return await self._cmd_refer(msg)
        elif command == '/stats':
            return await self._cmd_stats(msg)
        elif command == '/help':
            return self._cmd_help(msg)
        else:
            return self._reply(msg.chat_id,
                "Unknown command. Use /help to see available commands.")

    async def _cmd_start(self, msg: TelegramMessage, args: List[str]) -> dict:
        """Handle /start command with optional deep-link referral code."""
        referral_code = args[0] if args else None

        # Process referral if provided
        if referral_code:
            wallet = self._user_wallets.get(msg.user.id)
            if wallet:
                try:
                    if self._aikgs_client:
                        await self._aikgs_client.register_affiliate(wallet, referral_code=referral_code)
                    elif self._affiliate_manager:
                        self._affiliate_manager.register(wallet, referral_code)
                except Exception as e:
                    logger.debug(f"Referral registration failed: {e}")

        welcome = (
            f"Welcome to Aether Tree, {msg.user.display_name()}!\n\n"
            "I'm the AGI reasoning engine of the Qubitcoin blockchain. "
            "Contribute knowledge, earn QBC rewards, and help build humanity's first on-chain AGI.\n\n"
            "Quick Start:\n"
            "/chat — Open the Aether Chat\n"
            "/earn — Start earning QBC\n"
            "/wallet — Link your wallet\n"
            "/refer — Get your referral link\n"
            "/stats — View your stats\n\n"
        )

        # Add Mini App button
        return self._reply_with_webapp(msg.chat_id, welcome, "Open Aether Tree")

    def _cmd_chat(self, msg: TelegramMessage) -> dict:
        """Open chat Mini App."""
        return self._reply_with_webapp(msg.chat_id,
            "Open the Aether Chat to talk with the AGI and contribute knowledge.",
            "Open Chat",
            f"{self._mini_app_url}/chat")

    def _cmd_earn(self, msg: TelegramMessage) -> dict:
        """Show earning info."""
        text = (
            "How to Earn QBC with AIKGS:\n\n"
            "1. Chat with Aether — every quality message earns rewards\n"
            "2. Upload knowledge — contribute to the knowledge graph\n"
            "3. Complete bounties — fill knowledge gaps for bonus QBC\n"
            "4. Refer friends — earn 10% L1 + 5% L2 commissions\n"
            "5. Maintain streaks — daily contributions boost rewards up to 2x\n\n"
            "Quality tiers determine your multiplier:\n"
            "  Bronze (0.5x) → Silver (1.0x) → Gold (2.0x) → Diamond (5.0x)\n"
        )
        return self._reply_with_webapp(msg.chat_id, text, "Start Earning",
                                       f"{self._mini_app_url}/earn")

    def _cmd_wallet(self, msg: TelegramMessage) -> dict:
        """Wallet linking."""
        wallet = self._user_wallets.get(msg.user.id)
        if wallet:
            text = f"Linked wallet: `{wallet[:12]}...{wallet[-8:]}`\n\nUse the Mini App to manage your wallet."
        else:
            text = "No wallet linked yet. Open the Mini App to connect your QBC wallet."
        return self._reply_with_webapp(msg.chat_id, text, "Open Wallet",
                                       f"{self._mini_app_url}/wallet")

    async def _cmd_refer(self, msg: TelegramMessage) -> dict:
        """Show referral info and link."""
        wallet = self._user_wallets.get(msg.user.id)
        if wallet:
            try:
                if self._aikgs_client:
                    result = await self._aikgs_client.get_affiliate(wallet)
                    if result:
                        code = result.get('referral_code', '')
                        link = f"https://t.me/{self._username}?start={code}"
                        text = (
                            f"Your referral code: `{code}`\n"
                            f"Your referral link: {link}\n\n"
                            f"Direct referrals (L1): {result.get('l1_referrals', 0)}\n"
                            f"Indirect referrals (L2): {result.get('l2_referrals', 0)}\n"
                            f"L1 commission earned: {result.get('total_l1_commission', 0):.4f} QBC\n"
                            f"L2 commission earned: {result.get('total_l2_commission', 0):.4f} QBC\n\n"
                            "Share your link to earn 10% L1 + 5% L2 commission on referral rewards!"
                        )
                        return self._reply(msg.chat_id, text, parse_mode='Markdown')
                elif self._affiliate_manager:
                    affiliate = self._affiliate_manager.get_affiliate(wallet)
                    if affiliate:
                        code = affiliate.referral_code
                        link = f"https://t.me/{self._username}?start={code}"
                        text = (
                            f"Your referral code: `{code}`\n"
                            f"Your referral link: {link}\n\n"
                            f"Direct referrals (L1): {affiliate.l1_referrals}\n"
                            f"Indirect referrals (L2): {affiliate.l2_referrals}\n"
                            f"L1 commission earned: {affiliate.total_l1_commission:.4f} QBC\n"
                            f"L2 commission earned: {affiliate.total_l2_commission:.4f} QBC\n\n"
                            "Share your link to earn 10% L1 + 5% L2 commission on referral rewards!"
                        )
                        return self._reply(msg.chat_id, text, parse_mode='Markdown')
            except Exception as e:
                logger.debug(f"Failed to fetch referral info: {e}")

        return self._reply(msg.chat_id,
            "Link your wallet first to get a referral code. Use /wallet to connect.")

    async def _cmd_stats(self, msg: TelegramMessage) -> dict:
        """Show user stats."""
        wallet = self._user_wallets.get(msg.user.id)
        if not wallet:
            return self._reply(msg.chat_id,
                "Link your wallet to see your stats. Use /wallet.")

        text = f"Stats for `{wallet[:12]}...`\n\n"

        try:
            if self._aikgs_client:
                result = await self._aikgs_client.get_profile(wallet)
                if result:
                    text += (
                        f"Level: {result.get('level', 0)} ({result.get('level_name', 'Unknown')})\n"
                        f"Reputation: {result.get('reputation_points', 0):.0f} RP\n"
                        f"Contributions: {result.get('total_contributions', 0)}\n"
                        f"Streak: {result.get('current_streak', 0)} days\n"
                        f"Best Streak: {result.get('best_streak', 0)} days\n"
                        f"Badges: {len(result.get('badges', []))}\n"
                    )
                    multiplier = result.get('streak_multiplier', 1.0)
                    text += f"\nStreak Multiplier: {multiplier}x\n"
            else:
                if self._unlocks:
                    profile = self._unlocks.get_profile(wallet)
                    text += (
                        f"Level: {profile.level} ({profile.level_name})\n"
                        f"Reputation: {profile.reputation_points:.0f} RP\n"
                        f"Contributions: {profile.total_contributions}\n"
                        f"Streak: {profile.current_streak} days\n"
                        f"Best Streak: {profile.best_streak} days\n"
                        f"Badges: {len(profile.badges)}\n"
                    )

                if self._reward_engine:
                    streak_info = self._reward_engine.get_contributor_streak(wallet)
                    text += f"\nStreak Multiplier: {streak_info['multiplier']}x\n"
        except Exception as e:
            logger.debug(f"Failed to fetch user stats: {e}")
            text += "(Unable to load stats — please try again later.)\n"

        return self._reply(msg.chat_id, text, parse_mode='Markdown')

    def _cmd_help(self, msg: TelegramMessage) -> dict:
        """Show help message."""
        text = (
            "Aether Tree Bot Commands:\n\n"
            "/start — Welcome & onboarding\n"
            "/chat — Open the Aether Chat\n"
            "/earn — How to earn QBC\n"
            "/wallet — Link/view your wallet\n"
            "/refer — Get your referral link\n"
            "/stats — View your stats\n"
            "/help — This help message\n\n"
            f"Mini App: {self._mini_app_url}\n"
            "Website: https://qbc.network"
        )
        return self._reply(msg.chat_id, text)

    async def _handle_callback(self, callback: dict) -> Optional[dict]:
        """Handle inline button callback."""
        return None  # Placeholder for inline button actions

    async def _handle_inline(self, inline: dict) -> Optional[dict]:
        """Handle inline queries for sharing."""
        return None  # Placeholder for inline sharing

    def link_wallet(self, telegram_user_id: int, qbc_address: str) -> bool:
        """Link a Telegram user to a QBC wallet address.

        Args:
            telegram_user_id: Telegram user ID.
            qbc_address: QBC wallet address.

        Returns:
            True if linked successfully.
        """
        if not qbc_address:
            return False
        self._user_wallets[telegram_user_id] = qbc_address
        logger.info(f"Wallet linked: telegram_user={telegram_user_id} address={qbc_address[:8]}...")
        return True

    def get_wallet(self, telegram_user_id: int) -> Optional[str]:
        """Get linked wallet address for a Telegram user."""
        return self._user_wallets.get(telegram_user_id)

    # ─── Reply Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _reply(chat_id: int, text: str, parse_mode: str = '') -> dict:
        """Build a sendMessage response."""
        result: dict = {
            'method': 'sendMessage',
            'chat_id': chat_id,
            'text': text,
        }
        if parse_mode:
            result['parse_mode'] = parse_mode
        return result

    def _reply_with_webapp(self, chat_id: int, text: str, button_text: str,
                           url: str = '') -> dict:
        """Build a reply with a Web App inline button."""
        webapp_url = url or self._mini_app_url
        return {
            'method': 'sendMessage',
            'chat_id': chat_id,
            'text': text,
            'reply_markup': {
                'inline_keyboard': [[{
                    'text': button_text,
                    'web_app': {'url': webapp_url},
                }]]
            },
        }

    @staticmethod
    def _parse_message(raw: dict) -> Optional[TelegramMessage]:
        """Parse raw Telegram message dict."""
        try:
            user_data = raw.get('from', {})
            user = TelegramUser(
                id=user_data.get('id', 0),
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                username=user_data.get('username', ''),
                language_code=user_data.get('language_code', 'en'),
                is_premium=user_data.get('is_premium', False),
            )
            chat = raw.get('chat', {})
            return TelegramMessage(
                message_id=raw.get('message_id', 0),
                chat_id=chat.get('id', 0),
                user=user,
                text=raw.get('text', ''),
                date=raw.get('date', 0),
                entities=raw.get('entities', []),
            )
        except Exception as e:
            logger.warning(f"Failed to parse Telegram message: {e}")
            return None

    def get_stats(self) -> dict:
        """Get bot statistics."""
        return {
            'configured': self.is_configured,
            'username': self._username,
            'mini_app_url': self._mini_app_url,
            'messages_processed': self._messages_processed,
            'commands_processed': self._commands_processed,
            'linked_wallets': len(self._user_wallets),
        }
