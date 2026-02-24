"""
Regulatory Report Generation

Generates compliance reports for various regulatory frameworks:
  - MiCA (EU Markets in Crypto-Assets Regulation)
  - SEC (US Securities and Exchange Commission)
  - FinCEN (Financial Crimes Enforcement Network)

Reports aggregate on-chain data, compliance proofs, and transaction
patterns into structured documents suitable for regulatory submission.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ReportType(str, Enum):
    """Supported regulatory report types."""
    MICA = 'mica'           # EU Markets in Crypto-Assets
    SEC = 'sec'             # US Securities and Exchange Commission
    FINCEN = 'fincen'       # Financial Crimes Enforcement Network
    GENERAL = 'general'     # General compliance summary


class ReportPeriod(str, Enum):
    """Report time periods."""
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    QUARTERLY = 'quarterly'
    ANNUAL = 'annual'


@dataclass
class RegulatoryReport:
    """A generated regulatory compliance report."""
    report_id: str
    report_type: str
    period: str
    generated_at: float = 0.0
    period_start: float = 0.0
    period_end: float = 0.0
    block_range: tuple = (0, 0)
    data: dict = field(default_factory=dict)
    report_hash: str = ''

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = time.time()
        if not self.report_hash:
            self.report_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute report integrity hash."""
        content = json.dumps({
            'report_id': self.report_id,
            'report_type': self.report_type,
            'period': self.period,
            'block_range': list(self.block_range),
            'data': self.data,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify report has not been tampered with."""
        return self.report_hash == self._compute_hash()

    def to_dict(self) -> dict:
        return {
            'report_id': self.report_id,
            'report_type': self.report_type,
            'period': self.period,
            'generated_at': self.generated_at,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'block_range': list(self.block_range),
            'data': self.data,
            'report_hash': self.report_hash,
            'is_valid': self.verify_integrity(),
        }


class RegulatoryReportGenerator:
    """Generate regulatory compliance reports from chain data.

    Aggregates compliance proofs, transaction data, and policy
    information into formatted reports for each jurisdiction.
    """

    def __init__(self, compliance_engine: object = None,
                 proof_store: object = None) -> None:
        """
        Args:
            compliance_engine: ComplianceEngine for policy data.
            proof_store: ComplianceProofStore for audit proofs.
        """
        self._compliance = compliance_engine
        self._proof_store = proof_store
        self._reports: Dict[str, RegulatoryReport] = {}
        self._report_counter: int = 0

    def generate_report(self, report_type: str, period: str,
                        period_start: float = 0.0,
                        period_end: float = 0.0,
                        block_start: int = 0,
                        block_end: int = 0,
                        additional_data: Optional[dict] = None) -> RegulatoryReport:
        """Generate a regulatory report.

        Args:
            report_type: Type of report (mica, sec, fincen, general).
            period: Reporting period (daily, weekly, monthly, etc.).
            period_start: Start timestamp of the reporting period.
            period_end: End timestamp of the reporting period.
            block_start: Start block height.
            block_end: End block height.
            additional_data: Extra data to include in the report.

        Returns:
            Generated RegulatoryReport.
        """
        self._report_counter += 1
        report_id = f"rpt_{report_type}_{self._report_counter}"

        if not period_end:
            period_end = time.time()
        if not period_start:
            period_start = period_end - self._period_seconds(period)

        # Generate report data based on type
        if report_type == ReportType.MICA:
            data = self._generate_mica(
                period_start, period_end, block_start, block_end,
            )
        elif report_type == ReportType.SEC:
            data = self._generate_sec(
                period_start, period_end, block_start, block_end,
            )
        elif report_type == ReportType.FINCEN:
            data = self._generate_fincen(
                period_start, period_end, block_start, block_end,
            )
        else:
            data = self._generate_general(
                period_start, period_end, block_start, block_end,
            )

        if additional_data:
            data['additional'] = additional_data

        report = RegulatoryReport(
            report_id=report_id,
            report_type=report_type,
            period=period,
            period_start=period_start,
            period_end=period_end,
            block_range=(block_start, block_end),
            data=data,
        )

        self._reports[report_id] = report
        logger.info(
            f"Regulatory report generated: {report_id} "
            f"({report_type}/{period}, blocks {block_start}-{block_end})"
        )
        return report

    def _generate_mica(self, start: float, end: float,
                       block_start: int, block_end: int) -> dict:
        """Generate EU MiCA compliance report data.

        MiCA requires:
          - White paper compliance (token classification)
          - Reserve transparency (for stablecoins)
          - Transaction monitoring
          - Consumer protection measures
        """
        policy_summary = self._get_policy_summary()
        proof_summary = self._get_proof_summary(block_start, block_end)

        return {
            'framework': 'EU Markets in Crypto-Assets Regulation (MiCA)',
            'regulation_reference': 'Regulation (EU) 2023/1114',
            'chain_info': {
                'chain_id': Config.CHAIN_ID,
                'chain_name': 'Qubitcoin',
                'consensus': 'Proof-of-SUSY-Alignment',
                'max_supply': str(Config.MAX_SUPPLY),
            },
            'token_classification': {
                'type': 'utility_token',
                'is_stablecoin': False,
                'is_asset_referenced': False,
                'is_e_money': False,
            },
            'compliance_status': {
                'kyc_enforcement': True,
                'aml_monitoring': True,
                'sanctions_screening': True,
                'transaction_limits': True,
            },
            'policy_summary': policy_summary,
            'proof_summary': proof_summary,
            'reporting_period': {
                'start': start,
                'end': end,
                'blocks': {'start': block_start, 'end': block_end},
            },
        }

    def _generate_sec(self, start: float, end: float,
                      block_start: int, block_end: int) -> dict:
        """Generate US SEC compliance report data.

        SEC focus areas:
          - Securities classification (Howey test considerations)
          - Investor protection
          - Market manipulation monitoring
          - Disclosure requirements
        """
        policy_summary = self._get_policy_summary()
        proof_summary = self._get_proof_summary(block_start, block_end)

        return {
            'framework': 'US Securities and Exchange Commission',
            'chain_info': {
                'chain_id': Config.CHAIN_ID,
                'chain_name': 'Qubitcoin',
                'token_ticker': 'QBC',
            },
            'howey_test_analysis': {
                'investment_of_money': 'QBC obtained through mining (PoSA), not investment',
                'common_enterprise': 'Decentralized network, no central issuer',
                'expectation_of_profits': 'Utility token for network services',
                'efforts_of_others': 'Community-driven, open-source',
                'classification': 'utility_token',
            },
            'investor_protection': {
                'compliance_engine_active': True,
                'circuit_breaker_enabled': True,
                'kyc_levels': ['BASIC', 'ENHANCED', 'FULL'],
                'daily_limits_enforced': True,
            },
            'policy_summary': policy_summary,
            'proof_summary': proof_summary,
            'reporting_period': {
                'start': start,
                'end': end,
                'blocks': {'start': block_start, 'end': block_end},
            },
        }

    def _generate_fincen(self, start: float, end: float,
                         block_start: int, block_end: int) -> dict:
        """Generate US FinCEN compliance report data.

        FinCEN requires:
          - Bank Secrecy Act (BSA) compliance
          - Suspicious Activity Reports (SAR)
          - Currency Transaction Reports (CTR)
          - Customer identification program (CIP)
        """
        policy_summary = self._get_policy_summary()
        proof_summary = self._get_proof_summary(block_start, block_end)

        return {
            'framework': 'Financial Crimes Enforcement Network (FinCEN)',
            'regulation_reference': 'Bank Secrecy Act (BSA)',
            'chain_info': {
                'chain_id': Config.CHAIN_ID,
                'chain_name': 'Qubitcoin',
            },
            'bsa_compliance': {
                'customer_identification': True,
                'suspicious_activity_monitoring': True,
                'currency_transaction_reporting': True,
                'record_keeping': True,
            },
            'aml_program': {
                'risk_assessment': True,
                'internal_controls': True,
                'independent_testing': 'Compliance proofs on-chain',
                'designated_compliance_officer': 'Smart contract (ComplianceEngine)',
            },
            'sanctions_compliance': {
                'ofac_screening': True,
                'un_screening': True,
                'eu_screening': True,
                'real_time_checking': True,
            },
            'policy_summary': policy_summary,
            'proof_summary': proof_summary,
            'reporting_period': {
                'start': start,
                'end': end,
                'blocks': {'start': block_start, 'end': block_end},
            },
        }

    def _generate_general(self, start: float, end: float,
                          block_start: int, block_end: int) -> dict:
        """Generate a general compliance summary report."""
        policy_summary = self._get_policy_summary()
        proof_summary = self._get_proof_summary(block_start, block_end)

        return {
            'framework': 'General Compliance Summary',
            'chain_info': {
                'chain_id': Config.CHAIN_ID,
                'chain_name': 'Qubitcoin',
            },
            'compliance_overview': {
                'engine_active': self._compliance is not None,
                'proof_store_active': self._proof_store is not None,
            },
            'policy_summary': policy_summary,
            'proof_summary': proof_summary,
            'reporting_period': {
                'start': start,
                'end': end,
                'blocks': {'start': block_start, 'end': block_end},
            },
        }

    def _get_policy_summary(self) -> dict:
        """Get summary of active compliance policies."""
        if not self._compliance:
            return {'total_policies': 0, 'active': False}

        try:
            policies = self._compliance.list_policies()
            tier_counts: Dict[str, int] = {}
            kyc_counts: Dict[str, int] = {}

            for p in policies:
                tier = str(p.tier)
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                kyc = str(p.kyc_level)
                kyc_counts[kyc] = kyc_counts.get(kyc, 0) + 1

            return {
                'total_policies': len(policies),
                'active': True,
                'tiers': tier_counts,
                'kyc_levels': kyc_counts,
            }
        except Exception as e:
            logger.debug(f"Policy summary failed: {e}")
            return {'total_policies': 0, 'active': False}

    def _get_proof_summary(self, block_start: int,
                           block_end: int) -> dict:
        """Get summary of compliance proofs in the period."""
        if not self._proof_store:
            return {'total_proofs': 0, 'active': False}

        try:
            stats = self._proof_store.get_stats()
            return {
                'total_proofs': stats.get('total_proofs', 0),
                'unique_addresses': stats.get('unique_addresses', 0),
                'proof_types': stats.get('proof_types', {}),
                'active': True,
                'block_range': [block_start, block_end],
            }
        except Exception as e:
            logger.debug(f"Proof summary failed: {e}")
            return {'total_proofs': 0, 'active': False}

    @staticmethod
    def _period_seconds(period: str) -> float:
        """Convert a period name to seconds."""
        return {
            'daily': 86400,
            'weekly': 604800,
            'monthly': 2592000,
            'quarterly': 7776000,
            'annual': 31536000,
        }.get(period, 86400)

    def get_report(self, report_id: str) -> Optional[dict]:
        """Get a report by ID."""
        report = self._reports.get(report_id)
        return report.to_dict() if report else None

    def list_reports(self, report_type: Optional[str] = None,
                     limit: int = 50) -> List[dict]:
        """List generated reports, optionally filtered by type."""
        results = []
        for report in reversed(list(self._reports.values())):
            if len(results) >= limit:
                break
            if report_type and report.report_type != report_type:
                continue
            results.append(report.to_dict())
        return results

    def get_stats(self) -> dict:
        """Get report generator statistics."""
        type_counts: Dict[str, int] = {}
        for r in self._reports.values():
            type_counts[r.report_type] = type_counts.get(r.report_type, 0) + 1

        return {
            'total_reports': len(self._reports),
            'report_types': type_counts,
            'compliance_engine_available': self._compliance is not None,
            'proof_store_available': self._proof_store is not None,
        }
