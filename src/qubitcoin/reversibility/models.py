"""SQLAlchemy models for transaction reversibility."""

from sqlalchemy import Column, String, BigInteger, Integer, Boolean, DateTime, ARRAY, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class ReversalRequestModel(Base):
    """Persisted reversal request."""
    __tablename__ = 'reversal_requests'

    request_id = Column(String, primary_key=True)
    txid = Column(String, nullable=False, index=True)
    requester = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    window_expires_block = Column(BigInteger, nullable=False)
    guardian_approvals = Column(ARRAY(String), default=[])
    status = Column(String, default='pending', index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    reversal_txid = Column(String, nullable=True)


class SecurityGuardianModel(Base):
    """Persisted security guardian."""
    __tablename__ = 'security_guardians'

    address = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    added_at = Column(BigInteger, nullable=False)
    added_by = Column(String, nullable=False)
    removed_at = Column(BigInteger, nullable=True)
    active = Column(Boolean, default=True, index=True)


class TransactionWindowModel(Base):
    """Persisted transaction reversal window."""
    __tablename__ = 'transaction_windows'

    txid = Column(String, primary_key=True)
    window_blocks = Column(Integer, nullable=False, default=0)
    set_by = Column(String, nullable=False, index=True)
    set_at_block = Column(BigInteger, nullable=False)
