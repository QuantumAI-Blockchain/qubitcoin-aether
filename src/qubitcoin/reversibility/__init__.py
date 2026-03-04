"""Transaction reversibility module — opt-in reversal windows with guardian approval.

Includes:
- ReversibilityManager: Transaction reversal within configurable windows
- InheritanceManager: Dead-man's switch for asset transfer to beneficiaries
"""
from .inheritance import InheritanceManager, InheritancePlan, InheritanceClaim, ClaimStatus
from .high_security import HighSecurityManager, SecurityPolicy
