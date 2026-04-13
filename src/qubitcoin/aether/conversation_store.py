"""
Conversation Store — DB-backed persistent conversation memory for the Aether Tree.

Replaces in-memory ChatSession tracking with CockroachDB persistence.
Supports:
  - Per-user conversation threads (wallet address → sessions)
  - Cross-session context (summary of prior conversations)
  - Sliding context window with automatic summary consolidation
  - User memory persistence (replaces JSON-file ChatMemory)
  - Conversation insight extraction for KG integration
"""
import hashlib
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Limits
MAX_CONTEXT_WINDOW: int = 20          # Messages in active context window
MAX_SUMMARY_LENGTH: int = 2000        # Max chars for consolidated summary
MAX_SESSIONS_PER_USER: int = 1000     # Max stored sessions per user
MAX_MESSAGES_PER_SESSION: int = 5000  # Hard cap on messages per session
SUMMARY_TRIGGER: int = 40            # Summarize when messages exceed this
SESSION_EXPIRY_DAYS: int = 30         # Sessions expire after 30 days


class ConversationMessage:
    """A single persisted conversation message."""

    __slots__ = (
        'id', 'session_id', 'role', 'content', 'created_at',
        'reasoning_trace', 'phi_at_response', 'knowledge_nodes_referenced',
        'proof_of_thought_hash', 'quality_score', 'intent', 'entities',
    )

    def __init__(
        self,
        role: str,
        content: str,
        session_id: str = '',
        id: int = 0,
        created_at: Optional[datetime] = None,
        reasoning_trace: Optional[List[dict]] = None,
        phi_at_response: float = 0.0,
        knowledge_nodes_referenced: Optional[List[int]] = None,
        proof_of_thought_hash: str = '',
        quality_score: float = 0.0,
        intent: str = '',
        entities: Optional[Dict] = None,
    ) -> None:
        self.id = id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.created_at = created_at or datetime.now(timezone.utc)
        self.reasoning_trace = reasoning_trace or []
        self.phi_at_response = phi_at_response
        self.knowledge_nodes_referenced = knowledge_nodes_referenced or []
        self.proof_of_thought_hash = proof_of_thought_hash
        self.quality_score = quality_score
        self.intent = intent
        self.entities = entities or {}

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            'reasoning_trace': self.reasoning_trace,
            'phi_at_response': self.phi_at_response,
            'knowledge_nodes_referenced': self.knowledge_nodes_referenced,
            'proof_of_thought_hash': self.proof_of_thought_hash,
            'quality_score': self.quality_score,
            'intent': self.intent,
            'entities': self.entities,
        }


class ConversationSession:
    """A persisted conversation session."""

    __slots__ = (
        'session_id', 'user_id', 'user_address', 'title', 'created_at',
        'last_activity', 'message_count', 'fees_paid_atoms', 'status',
        'context_summary', 'primary_topic', 'topics',
    )

    def __init__(
        self,
        session_id: str = '',
        user_id: str = '',
        user_address: str = '',
        title: str = '',
        created_at: Optional[datetime] = None,
        last_activity: Optional[datetime] = None,
        message_count: int = 0,
        fees_paid_atoms: int = 0,
        status: str = 'active',
        context_summary: str = '',
        primary_topic: str = '',
        topics: Optional[List[str]] = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.user_address = user_address
        self.title = title
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_activity = last_activity or datetime.now(timezone.utc)
        self.message_count = message_count
        self.fees_paid_atoms = fees_paid_atoms
        self.status = status
        self.context_summary = context_summary
        self.primary_topic = primary_topic
        self.topics = topics or []

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'user_address': self.user_address,
            'title': self.title,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            'last_activity': self.last_activity.isoformat() if isinstance(self.last_activity, datetime) else str(self.last_activity),
            'message_count': self.message_count,
            'fees_paid_atoms': self.fees_paid_atoms,
            'status': self.status,
            'context_summary': self.context_summary[:200] + '...' if len(self.context_summary) > 200 else self.context_summary,
            'primary_topic': self.primary_topic,
            'topics': self.topics,
        }


class ConversationStore:
    """DB-backed conversation storage for the Aether Tree.

    Provides persistent conversation history, user memory, and
    cross-session context for institutional-grade chat capabilities.
    """

    def __init__(self, db_manager: Any) -> None:
        self.db = db_manager
        self._ensure_tables()
        logger.info("ConversationStore initialized (DB-backed)")

    def _ensure_tables(self) -> None:
        """Create conversation tables if they don't exist."""
        try:
            with self.db.get_session() as session:
                session.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_sessions (
                        session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(128) NOT NULL,
                        user_address VARCHAR(128) NOT NULL DEFAULT '',
                        title VARCHAR(256) NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        last_activity TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days'),
                        message_count INT NOT NULL DEFAULT 0,
                        fees_paid_atoms BIGINT NOT NULL DEFAULT 0,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        context_summary TEXT NOT NULL DEFAULT '',
                        primary_topic VARCHAR(128) NOT NULL DEFAULT '',
                        topics JSONB NOT NULL DEFAULT '[]'
                    )
                """)
                session.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        id BIGINT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
                        session_id UUID NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        content_hash VARCHAR(64) NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        reasoning_trace JSONB NOT NULL DEFAULT '[]',
                        phi_at_response FLOAT NOT NULL DEFAULT 0.0,
                        knowledge_nodes_referenced JSONB NOT NULL DEFAULT '[]',
                        proof_of_thought_hash VARCHAR(128) NOT NULL DEFAULT '',
                        quality_score FLOAT NOT NULL DEFAULT 0.0,
                        intent VARCHAR(64) NOT NULL DEFAULT '',
                        entities JSONB NOT NULL DEFAULT '{}'
                    )
                """)
                session.execute("""
                    CREATE TABLE IF NOT EXISTS user_memory (
                        id BIGINT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
                        user_id VARCHAR(128) NOT NULL,
                        memory_key VARCHAR(128) NOT NULL,
                        memory_value TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        source VARCHAR(64) NOT NULL DEFAULT 'chat',
                        UNIQUE (user_id, memory_key)
                    )
                """)
                session.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_insights (
                        id BIGINT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
                        session_id UUID NOT NULL,
                        user_id VARCHAR(128) NOT NULL,
                        insight_type VARCHAR(64) NOT NULL,
                        content TEXT NOT NULL,
                        confidence FLOAT NOT NULL DEFAULT 0.5,
                        knowledge_node_id BIGINT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                session.commit()
                logger.info("Conversation tables verified")
        except Exception as e:
            logger.warning(f"Table creation warning (may already exist): {e}")

    # ── Session Management ──────────────────────────────────────

    def create_session(
        self, user_id: str, user_address: str = '',
    ) -> ConversationSession:
        """Create a new conversation session."""
        import json
        session_obj = ConversationSession(
            user_id=user_id,
            user_address=user_address,
        )
        try:
            with self.db.get_session() as session:
                session.execute(
                    """INSERT INTO conversation_sessions
                       (session_id, user_id, user_address, title, created_at, last_activity, message_count, status, topics)
                       VALUES (:sid, :uid, :addr, :title, :created, :activity, 0, 'active', :topics)""",
                    {
                        'sid': session_obj.session_id,
                        'uid': user_id,
                        'addr': user_address,
                        'title': '',
                        'created': session_obj.created_at,
                        'activity': session_obj.last_activity,
                        'topics': json.dumps([]),
                    },
                )
                session.commit()
            logger.debug(f"Created conversation session {session_obj.session_id[:8]} for user {user_id[:16]}")
        except Exception as e:
            logger.error(f"Failed to create conversation session: {e}")
        return session_obj

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Load a conversation session by ID."""
        import json
        try:
            with self.db.get_session() as session:
                row = session.execute(
                    """SELECT session_id, user_id, user_address, title, created_at,
                              last_activity, message_count, fees_paid_atoms, status,
                              context_summary, primary_topic, topics
                       FROM conversation_sessions WHERE session_id = :sid""",
                    {'sid': session_id},
                ).fetchone()
                if not row:
                    return None
                topics = row[11] if row[11] else []
                if isinstance(topics, str):
                    topics = json.loads(topics)
                return ConversationSession(
                    session_id=str(row[0]),
                    user_id=row[1],
                    user_address=row[2] or '',
                    title=row[3] or '',
                    created_at=row[4],
                    last_activity=row[5],
                    message_count=row[6] or 0,
                    fees_paid_atoms=row[7] or 0,
                    status=row[8] or 'active',
                    context_summary=row[9] or '',
                    primary_topic=row[10] or '',
                    topics=topics,
                )
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def get_user_sessions(
        self, user_id: str, limit: int = 20, status: str = 'active',
    ) -> List[ConversationSession]:
        """Get all sessions for a user, ordered by most recent activity."""
        import json
        sessions = []
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    """SELECT session_id, user_id, user_address, title, created_at,
                              last_activity, message_count, fees_paid_atoms, status,
                              context_summary, primary_topic, topics
                       FROM conversation_sessions
                       WHERE user_id = :uid AND status = :status
                       ORDER BY last_activity DESC
                       LIMIT :lim""",
                    {'uid': user_id, 'status': status, 'lim': limit},
                ).fetchall()
                for row in rows:
                    topics = row[11] if row[11] else []
                    if isinstance(topics, str):
                        topics = json.loads(topics)
                    sessions.append(ConversationSession(
                        session_id=str(row[0]),
                        user_id=row[1],
                        user_address=row[2] or '',
                        title=row[3] or '',
                        created_at=row[4],
                        last_activity=row[5],
                        message_count=row[6] or 0,
                        fees_paid_atoms=row[7] or 0,
                        status=row[8] or 'active',
                        context_summary=row[9] or '',
                        primary_topic=row[10] or '',
                        topics=topics,
                    ))
        except Exception as e:
            logger.error(f"Failed to load user sessions: {e}")
        return sessions

    def update_session(
        self, session_id: str, title: str = '', primary_topic: str = '',
        context_summary: str = '', topics: Optional[List[str]] = None,
    ) -> None:
        """Update session metadata."""
        import json
        try:
            with self.db.get_session() as session:
                updates = ["last_activity = now()"]
                params: Dict[str, Any] = {'sid': session_id}
                if title:
                    updates.append("title = :title")
                    params['title'] = title
                if primary_topic:
                    updates.append("primary_topic = :topic")
                    params['topic'] = primary_topic
                if context_summary:
                    updates.append("context_summary = :summary")
                    params['summary'] = context_summary[:MAX_SUMMARY_LENGTH]
                if topics is not None:
                    updates.append("topics = :topics")
                    params['topics'] = json.dumps(topics[-20:])
                session.execute(
                    f"UPDATE conversation_sessions SET {', '.join(updates)} WHERE session_id = :sid",
                    params,
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to update session: {e}")

    def archive_session(self, session_id: str) -> None:
        """Archive a session (soft delete)."""
        try:
            with self.db.get_session() as session:
                session.execute(
                    "UPDATE conversation_sessions SET status = 'archived' WHERE session_id = :sid",
                    {'sid': session_id},
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to archive session: {e}")

    # ── Message Persistence ──────────────────────────────────────

    def save_message(self, msg: ConversationMessage) -> int:
        """Persist a message and return its ID."""
        import json
        content_hash = hashlib.sha256(msg.content.encode()).hexdigest()[:16]
        msg_id = 0
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    """INSERT INTO conversation_messages
                       (session_id, role, content, content_hash, created_at,
                        reasoning_trace, phi_at_response, knowledge_nodes_referenced,
                        proof_of_thought_hash, quality_score, intent, entities)
                       VALUES (:sid, :role, :content, :hash, :created,
                               :trace, :phi, :refs, :pot, :quality, :intent, :entities)
                       RETURNING id""",
                    {
                        'sid': msg.session_id,
                        'role': msg.role,
                        'content': msg.content,
                        'hash': content_hash,
                        'created': msg.created_at,
                        'trace': json.dumps(msg.reasoning_trace),
                        'phi': msg.phi_at_response,
                        'refs': json.dumps(msg.knowledge_nodes_referenced),
                        'pot': msg.proof_of_thought_hash,
                        'quality': msg.quality_score,
                        'intent': msg.intent,
                        'entities': json.dumps(msg.entities),
                    },
                )
                row = result.fetchone()
                if row:
                    msg_id = row[0]
                # Update session message count
                session.execute(
                    """UPDATE conversation_sessions
                       SET message_count = message_count + 1, last_activity = now()
                       WHERE session_id = :sid""",
                    {'sid': msg.session_id},
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
        return msg_id

    def get_messages(
        self, session_id: str, limit: int = MAX_CONTEXT_WINDOW, offset: int = 0,
    ) -> List[ConversationMessage]:
        """Load messages for a session, ordered chronologically."""
        import json
        messages = []
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    """SELECT id, session_id, role, content, created_at,
                              reasoning_trace, phi_at_response, knowledge_nodes_referenced,
                              proof_of_thought_hash, quality_score, intent, entities
                       FROM conversation_messages
                       WHERE session_id = :sid
                       ORDER BY id ASC
                       LIMIT :lim OFFSET :off""",
                    {'sid': session_id, 'lim': limit, 'off': offset},
                ).fetchall()
                for row in rows:
                    trace = row[5] if row[5] else []
                    if isinstance(trace, str):
                        trace = json.loads(trace)
                    refs = row[7] if row[7] else []
                    if isinstance(refs, str):
                        refs = json.loads(refs)
                    ents = row[11] if row[11] else {}
                    if isinstance(ents, str):
                        ents = json.loads(ents)
                    messages.append(ConversationMessage(
                        id=row[0],
                        session_id=str(row[1]),
                        role=row[2],
                        content=row[3],
                        created_at=row[4],
                        reasoning_trace=trace,
                        phi_at_response=row[6] or 0.0,
                        knowledge_nodes_referenced=refs,
                        proof_of_thought_hash=row[8] or '',
                        quality_score=row[9] or 0.0,
                        intent=row[10] or '',
                        entities=ents,
                    ))
        except Exception as e:
            logger.error(f"Failed to load messages: {e}")
        return messages

    def get_recent_messages(self, session_id: str, count: int = MAX_CONTEXT_WINDOW) -> List[ConversationMessage]:
        """Load the most recent N messages for context window."""
        import json
        messages = []
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    """SELECT id, session_id, role, content, created_at,
                              reasoning_trace, phi_at_response, knowledge_nodes_referenced,
                              proof_of_thought_hash, quality_score, intent, entities
                       FROM conversation_messages
                       WHERE session_id = :sid
                       ORDER BY id DESC
                       LIMIT :cnt""",
                    {'sid': session_id, 'cnt': count},
                ).fetchall()
                for row in reversed(rows):  # Reverse to chronological order
                    trace = row[5] if row[5] else []
                    if isinstance(trace, str):
                        trace = json.loads(trace)
                    refs = row[7] if row[7] else []
                    if isinstance(refs, str):
                        refs = json.loads(refs)
                    ents = row[11] if row[11] else {}
                    if isinstance(ents, str):
                        ents = json.loads(ents)
                    messages.append(ConversationMessage(
                        id=row[0],
                        session_id=str(row[1]),
                        role=row[2],
                        content=row[3],
                        created_at=row[4],
                        reasoning_trace=trace,
                        phi_at_response=row[6] or 0.0,
                        knowledge_nodes_referenced=refs,
                        proof_of_thought_hash=row[8] or '',
                        quality_score=row[9] or 0.0,
                        intent=row[10] or '',
                        entities=ents,
                    ))
        except Exception as e:
            logger.error(f"Failed to load recent messages: {e}")
        return messages

    # ── Context Window ──────────────────────────────────────

    def build_context(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Build full conversation context for response generation.

        Returns:
            Dict with:
              - recent_messages: last N messages (role, content pairs)
              - context_summary: summary of older messages
              - user_memories: cross-session user knowledge
              - prior_sessions: summaries from previous sessions
              - total_interactions: lifetime message count for this user
        """
        # Recent messages from current session
        recent = self.get_recent_messages(session_id, MAX_CONTEXT_WINDOW)

        # Current session summary
        conv_session = self.get_session(session_id)
        summary = conv_session.context_summary if conv_session else ''

        # User memories (cross-session)
        memories = self.get_user_memories(user_id)

        # Prior session summaries (last 5 sessions, excluding current)
        prior_summaries = []
        try:
            prior_sessions = self.get_user_sessions(user_id, limit=6)
            for ps in prior_sessions:
                if ps.session_id != session_id and ps.context_summary:
                    prior_summaries.append({
                        'session_id': ps.session_id[:8],
                        'title': ps.title or ps.primary_topic or 'Untitled',
                        'summary': ps.context_summary[:300],
                        'date': ps.last_activity.isoformat() if isinstance(ps.last_activity, datetime) else str(ps.last_activity),
                        'messages': ps.message_count,
                    })
        except Exception as e:
            logger.debug(f"Failed to load prior sessions: {e}")

        # Total lifetime interactions
        total = self._count_user_messages(user_id)

        return {
            'recent_messages': [(m.role, m.content) for m in recent],
            'context_summary': summary,
            'user_memories': memories,
            'prior_sessions': prior_summaries[:5],
            'total_interactions': total,
        }

    def _count_user_messages(self, user_id: str) -> int:
        """Count total messages across all sessions for a user."""
        try:
            with self.db.get_session() as session:
                row = session.execute(
                    """SELECT COALESCE(SUM(message_count), 0)
                       FROM conversation_sessions WHERE user_id = :uid""",
                    {'uid': user_id},
                ).fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.debug(f"Failed to count user messages: {e}")
            return 0

    def consolidate_summary(self, session_id: str, llm_adapter: Any = None) -> str:
        """Consolidate older messages into a summary.

        If an LLM adapter is provided, uses it for intelligent summarization.
        Otherwise, creates a structured extract of key points.
        """
        messages = self.get_messages(session_id, limit=MAX_MESSAGES_PER_SESSION)
        if len(messages) <= SUMMARY_TRIGGER:
            return ''  # Not enough messages to summarize

        # Messages to summarize (everything except the most recent context window)
        to_summarize = messages[:-MAX_CONTEXT_WINDOW]

        # Try LLM-based summarization
        if llm_adapter:
            try:
                text = '\n'.join(f"{m.role}: {m.content[:200]}" for m in to_summarize[-50:])
                prompt = (
                    "Summarize this conversation concisely. Focus on: "
                    "1) Key topics discussed, 2) User preferences/interests learned, "
                    "3) Important questions asked, 4) Key information shared. "
                    "Keep under 500 words.\n\n" + text
                )
                summary = llm_adapter.generate(prompt, max_tokens=600)
                if summary:
                    self.update_session(session_id, context_summary=summary)
                    return summary
            except Exception as e:
                logger.debug(f"LLM summarization failed, using structured extract: {e}")

        # Structured extract fallback
        topics = set()
        user_questions = []
        key_facts = []
        for m in to_summarize:
            if m.role == 'user':
                if '?' in m.content:
                    user_questions.append(m.content[:100])
                if m.intent:
                    topics.add(m.intent)
            elif m.quality_score > 0.7:
                key_facts.append(m.content[:100])

        parts = []
        if topics:
            parts.append(f"Topics: {', '.join(list(topics)[:10])}")
        if user_questions:
            parts.append(f"Questions asked: {len(user_questions)}")
            parts.append(f"Recent questions: {'; '.join(user_questions[-5:])}")
        if key_facts:
            parts.append(f"Key responses: {'; '.join(key_facts[-3:])}")
        parts.append(f"Messages summarized: {len(to_summarize)}")

        summary = ' | '.join(parts)[:MAX_SUMMARY_LENGTH]
        self.update_session(session_id, context_summary=summary)
        return summary

    # ── User Memory (DB-backed) ──────────────────────────────────

    def remember(self, user_id: str, key: str, value: str, source: str = 'chat') -> None:
        """Store a memory for a user (upsert)."""
        try:
            with self.db.get_session() as session:
                session.execute(
                    """INSERT INTO user_memory (user_id, memory_key, memory_value, source, updated_at)
                       VALUES (:uid, :key, :val, :src, now())
                       ON CONFLICT (user_id, memory_key)
                       DO UPDATE SET memory_value = :val, updated_at = now(), source = :src""",
                    {'uid': user_id, 'key': key, 'val': value, 'src': source},
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to remember: {e}")

    def recall(self, user_id: str, key: str) -> Optional[str]:
        """Recall a specific memory for a user."""
        try:
            with self.db.get_session() as session:
                row = session.execute(
                    "SELECT memory_value FROM user_memory WHERE user_id = :uid AND memory_key = :key",
                    {'uid': user_id, 'key': key},
                ).fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.debug(f"Failed to recall: {e}")
            return None

    def get_user_memories(self, user_id: str) -> Dict[str, str]:
        """Get all memories for a user."""
        memories: Dict[str, str] = {}
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    "SELECT memory_key, memory_value FROM user_memory WHERE user_id = :uid ORDER BY updated_at DESC",
                    {'uid': user_id},
                ).fetchall()
                for row in rows:
                    memories[row[0]] = row[1]
        except Exception as e:
            logger.debug(f"Failed to get user memories: {e}")
        return memories

    def forget(self, user_id: str, key: str) -> None:
        """Delete a specific memory for a user."""
        try:
            with self.db.get_session() as session:
                session.execute(
                    "DELETE FROM user_memory WHERE user_id = :uid AND memory_key = :key",
                    {'uid': user_id, 'key': key},
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to forget: {e}")

    def forget_all(self, user_id: str) -> None:
        """Delete all memories for a user."""
        try:
            with self.db.get_session() as session:
                session.execute(
                    "DELETE FROM user_memory WHERE user_id = :uid",
                    {'uid': user_id},
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to forget all: {e}")

    # ── Conversation Insights ──────────────────────────────────

    def save_insight(
        self, session_id: str, user_id: str, insight_type: str,
        content: str, confidence: float = 0.5, knowledge_node_id: Optional[int] = None,
    ) -> None:
        """Save a conversation insight."""
        try:
            with self.db.get_session() as session:
                session.execute(
                    """INSERT INTO conversation_insights
                       (session_id, user_id, insight_type, content, confidence, knowledge_node_id)
                       VALUES (:sid, :uid, :itype, :content, :conf, :knid)""",
                    {
                        'sid': session_id,
                        'uid': user_id,
                        'itype': insight_type,
                        'content': content,
                        'conf': confidence,
                        'knid': knowledge_node_id,
                    },
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save insight: {e}")

    def get_user_insights(
        self, user_id: str, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent insights for a user."""
        insights = []
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    """SELECT insight_type, content, confidence, knowledge_node_id, created_at
                       FROM conversation_insights
                       WHERE user_id = :uid
                       ORDER BY created_at DESC
                       LIMIT :lim""",
                    {'uid': user_id, 'lim': limit},
                ).fetchall()
                for row in rows:
                    insights.append({
                        'type': row[0],
                        'content': row[1],
                        'confidence': row[2],
                        'knowledge_node_id': row[3],
                        'created_at': row[4].isoformat() if isinstance(row[4], datetime) else str(row[4]),
                    })
        except Exception as e:
            logger.debug(f"Failed to get insights: {e}")
        return insights

    # ── Session Title Generation ──────────────────────────────

    def auto_title(self, session_id: str) -> str:
        """Generate a title from the first user message."""
        messages = self.get_messages(session_id, limit=2)
        for m in messages:
            if m.role == 'user':
                # Use first 60 chars of first user message as title
                title = m.content[:60].strip()
                if len(m.content) > 60:
                    title += '...'
                self.update_session(session_id, title=title)
                return title
        return ''

    # ── Cleanup ──────────────────────────────────────

    def expire_old_sessions(self) -> int:
        """Archive sessions past their expiry date. Returns count archived."""
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    """UPDATE conversation_sessions
                       SET status = 'expired'
                       WHERE status = 'active' AND expires_at < now()"""
                )
                session.commit()
                count = result.rowcount or 0
                if count > 0:
                    logger.info(f"Expired {count} old conversation sessions")
                return count
        except Exception as e:
            logger.error(f"Failed to expire sessions: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation store statistics."""
        stats: Dict[str, Any] = {}
        try:
            with self.db.get_session() as session:
                # Total sessions
                row = session.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()
                stats['total_sessions'] = row[0] if row else 0

                # Active sessions
                row = session.execute(
                    "SELECT COUNT(*) FROM conversation_sessions WHERE status = 'active'"
                ).fetchone()
                stats['active_sessions'] = row[0] if row else 0

                # Total messages
                row = session.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()
                stats['total_messages'] = row[0] if row else 0

                # Unique users
                row = session.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM conversation_sessions"
                ).fetchone()
                stats['unique_users'] = row[0] if row else 0

                # User memories
                row = session.execute("SELECT COUNT(*) FROM user_memory").fetchone()
                stats['total_memories'] = row[0] if row else 0

                # Insights
                row = session.execute("SELECT COUNT(*) FROM conversation_insights").fetchone()
                stats['total_insights'] = row[0] if row else 0
        except Exception as e:
            logger.debug(f"Failed to get stats: {e}")
        return stats
