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


class InheritancePlanModel(Base):
    """Persisted inheritance plan."""
    __tablename__ = 'inheritance_plans'

    owner_address = Column(String, primary_key=True)
    beneficiary_address = Column(String, nullable=False, index=True)
    inactivity_blocks = Column(BigInteger, nullable=False, default=2618200)
    last_heartbeat_block = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True, index=True)


class InheritanceClaimModel(Base):
    """Persisted inheritance claim."""
    __tablename__ = 'inheritance_claims'

    claim_id = Column(String, primary_key=True)
    owner_address = Column(String, nullable=False, index=True)
    beneficiary_address = Column(String, nullable=False, index=True)
    initiated_at_block = Column(BigInteger, nullable=False)
    grace_expires_block = Column(BigInteger, nullable=False)
    status = Column(String, default='pending', index=True)
    executed_at = Column(DateTime, nullable=True)
    execution_txid = Column(String, nullable=True)


class SecurityPolicyModel(Base):
    """Persisted high-security account policy."""
    __tablename__ = 'security_policies'

    address = Column(String, primary_key=True)
    daily_limit_qbc = Column(BigInteger, nullable=False, default=0)
    require_whitelist = Column(Boolean, default=False)
    whitelist = Column(ARRAY(String), default=[])
    time_lock_blocks = Column(Integer, default=0)
    time_lock_threshold_qbc = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True, index=True)


class SecuritySpendingLogModel(Base):
    """Persisted spending log for daily limit tracking."""
    __tablename__ = 'security_spending_log'

    id = Column(String, primary_key=True)
    address = Column(String, nullable=False, index=True)
    amount_qbc = Column(BigInteger, nullable=False)
    recipient = Column(String, nullable=False)
    block_height = Column(BigInteger, nullable=False, index=True)
