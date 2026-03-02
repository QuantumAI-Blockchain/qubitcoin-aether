//! Affiliate Manager — 2-Level referral commission system.
//!
//! Commission structure:
//!   - L1 (direct referrer): `l1_commission_rate` of contributor's reward
//!   - L2 (referrer's referrer): `l2_commission_rate` of contributor's reward
//!
//! Commissions are funded from the reward pool (via RewardEngine), NOT deducted
//! from the contributor's reward. Commission records are persisted in the DB for
//! auditability and treasury disbursement.

use crate::config::AikgsConfig;
use crate::db::{AffiliateRow, AffiliateStatsRow, Db};

/// Errors that can occur during affiliate operations.
#[derive(Debug, thiserror::Error)]
pub enum AikgsError {
    #[error("referral code already taken: {0}")]
    CodeAlreadyTaken(String),

    #[error("self-referral not allowed")]
    SelfReferral,

    #[error("affiliate not found: {0}")]
    NotFound(String),

    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),
}

/// Manages the 2-level referral system for AIKGS.
pub struct AffiliateManager;

impl AffiliateManager {
    /// Register a new affiliate with a referral code.
    ///
    /// If the address is already registered, the existing record is returned
    /// unchanged (upsert with ON CONFLICT DO NOTHING).
    ///
    /// # Errors
    /// - `SelfReferral` if `referrer_address` equals `address`
    /// - `CodeAlreadyTaken` if `referral_code` is already used by another address
    /// - `Database` on DB failures
    pub async fn register(
        db: &Db,
        address: &str,
        referrer_address: &str,
        referral_code: &str,
    ) -> Result<AffiliateInfo, AikgsError> {
        // Anti-abuse: no self-referral
        if !referrer_address.is_empty() && referrer_address == address {
            return Err(AikgsError::SelfReferral);
        }

        // Validate referral code uniqueness: must not belong to a different address
        if !referral_code.is_empty() {
            if let Some(existing) = db.get_affiliate_by_code(referral_code).await? {
                if existing.address != address {
                    return Err(AikgsError::CodeAlreadyTaken(referral_code.to_string()));
                }
            }
        }

        // Insert (ON CONFLICT DO NOTHING — idempotent for re-registration)
        db.upsert_affiliate(address, referrer_address, referral_code)
            .await?;

        // Return the persisted record
        let row = db.get_affiliate(address).await?;
        match row {
            Some(r) => Ok(AffiliateInfo::from_row(&r)),
            None => {
                // Should not happen after upsert, but handle gracefully
                Ok(AffiliateInfo {
                    address: address.to_string(),
                    referrer_address: referrer_address.to_string(),
                    referral_code: referral_code.to_string(),
                    l1_referrals: 0,
                    l2_referrals: 0,
                    total_l1_commission: 0.0,
                    total_l2_commission: 0.0,
                    is_active: true,
                })
            }
        }
    }

    /// Get affiliate info by address.
    pub async fn get_affiliate(
        db: &Db,
        address: &str,
    ) -> Result<Option<AffiliateInfo>, AikgsError> {
        let row = db.get_affiliate(address).await?;
        Ok(row.as_ref().map(AffiliateInfo::from_row))
    }

    /// Get affiliate info by referral code.
    pub async fn get_by_code(
        db: &Db,
        code: &str,
    ) -> Result<Option<AffiliateInfo>, AikgsError> {
        let row = db.get_affiliate_by_code(code).await?;
        Ok(row.as_ref().map(AffiliateInfo::from_row))
    }

    /// Process L1 and L2 affiliate commissions for a contribution reward.
    ///
    /// Looks up the contributor's referral chain in the DB:
    ///   - L1: contributor's direct referrer gets `l1_commission_rate * reward_amount`
    ///   - L2: referrer's referrer gets `l2_commission_rate * reward_amount`
    ///
    /// Commission records are inserted into `aikgs_commissions` and the affiliate's
    /// running totals are incremented in `aikgs_affiliates`.
    ///
    /// Returns `(l1_amount, l2_amount)`.
    pub async fn process_commissions(
        db: &Db,
        contributor_address: &str,
        reward_amount: f64,
        contribution_id: i64,
        cfg: &AikgsConfig,
    ) -> Result<(f64, f64), AikgsError> {
        if reward_amount <= 0.0 {
            return Ok((0.0, 0.0));
        }

        // Look up contributor's affiliate record
        let affiliate = match db.get_affiliate(contributor_address).await? {
            Some(a) => a,
            None => return Ok((0.0, 0.0)),
        };

        let l1_referrer = match &affiliate.referrer_address {
            Some(addr) if !addr.is_empty() => addr.clone(),
            _ => return Ok((0.0, 0.0)),
        };

        let mut l1_amount = 0.0;
        let mut l2_amount = 0.0;

        // L1 commission: direct referrer
        let l1_affiliate = db.get_affiliate(&l1_referrer).await?;
        if let Some(ref _l1_aff) = l1_affiliate {
            l1_amount = round8(reward_amount * cfg.l1_commission_rate);
            if l1_amount > 0.0 {
                // Insert commission record
                db.insert_commission(
                    &l1_referrer,
                    contributor_address,
                    l1_amount,
                    1, // level
                    contribution_id,
                )
                .await?;

                // Increment affiliate running totals
                db.increment_affiliate_commission(&l1_referrer, 1, l1_amount)
                    .await?;
            }

            // L2 commission: referrer's referrer
            if let Some(ref l1_aff) = l1_affiliate {
                let l2_referrer = match &l1_aff.referrer_address {
                    Some(addr) if !addr.is_empty() => addr.clone(),
                    _ => String::new(),
                };

                if !l2_referrer.is_empty() {
                    // Verify L2 referrer exists in affiliates table
                    if db.get_affiliate(&l2_referrer).await?.is_some() {
                        l2_amount = round8(reward_amount * cfg.l2_commission_rate);
                        if l2_amount > 0.0 {
                            db.insert_commission(
                                &l2_referrer,
                                contributor_address,
                                l2_amount,
                                2, // level
                                contribution_id,
                            )
                            .await?;

                            db.increment_affiliate_commission(&l2_referrer, 2, l2_amount)
                                .await?;
                        }
                    }
                }
            }
        }

        if l1_amount > 0.0 || l2_amount > 0.0 {
            log::info!(
                "Affiliate commissions: contributor={}... L1={:.8} L2={:.8}",
                &contributor_address[..contributor_address.len().min(8)],
                l1_amount,
                l2_amount,
            );
        }

        Ok((l1_amount, l2_amount))
    }

    /// Get aggregate affiliate system statistics.
    pub async fn get_stats(db: &Db) -> Result<AffiliateStatsRow, AikgsError> {
        Ok(db.get_affiliate_stats().await?)
    }
}

/// Affiliate info returned to callers, matching the proto AffiliateInfo message.
#[derive(Debug, Clone)]
pub struct AffiliateInfo {
    pub address: String,
    pub referrer_address: String,
    pub referral_code: String,
    pub l1_referrals: i32,
    pub l2_referrals: i32,
    pub total_l1_commission: f64,
    pub total_l2_commission: f64,
    pub is_active: bool,
}

impl AffiliateInfo {
    /// Construct from a database row.
    pub fn from_row(row: &AffiliateRow) -> Self {
        Self {
            address: row.address.clone(),
            referrer_address: row
                .referrer_address
                .clone()
                .unwrap_or_default(),
            referral_code: row.referral_code.clone(),
            l1_referrals: row.l1_referrals,
            l2_referrals: row.l2_referrals,
            total_l1_commission: row.total_l1_commission,
            total_l2_commission: row.total_l2_commission,
            is_active: row.is_active,
        }
    }
}

/// Round to 8 decimal places (satoshi precision).
fn round8(v: f64) -> f64 {
    (v * 1e8).round() / 1e8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_round8_precision() {
        let v = 0.123456789012;
        assert_eq!(round8(v), 0.12345679);
    }

    #[test]
    fn test_round8_zero() {
        assert_eq!(round8(0.0), 0.0);
    }

    #[test]
    fn test_affiliate_info_from_row() {
        let row = AffiliateRow {
            address: "qbc1alice".into(),
            referrer_address: Some("qbc1bob".into()),
            referral_code: "QBC-ABCD1234".into(),
            l1_referrals: 5,
            l2_referrals: 2,
            total_l1_commission: 1.5,
            total_l2_commission: 0.3,
            is_active: true,
        };
        let info = AffiliateInfo::from_row(&row);
        assert_eq!(info.address, "qbc1alice");
        assert_eq!(info.referrer_address, "qbc1bob");
        assert_eq!(info.l1_referrals, 5);
        assert_eq!(info.total_l1_commission, 1.5);
    }

    #[test]
    fn test_affiliate_info_no_referrer() {
        let row = AffiliateRow {
            address: "qbc1alice".into(),
            referrer_address: None,
            referral_code: "QBC-XXXX".into(),
            l1_referrals: 0,
            l2_referrals: 0,
            total_l1_commission: 0.0,
            total_l2_commission: 0.0,
            is_active: true,
        };
        let info = AffiliateInfo::from_row(&row);
        assert_eq!(info.referrer_address, "");
        assert!(info.is_active);
    }

    #[test]
    fn test_commission_calculation() {
        let rate = 0.05;
        let reward = 10.0;
        let commission = round8(reward * rate);
        assert_eq!(commission, 0.5);
    }

    #[test]
    fn test_commission_calculation_small() {
        let rate = 0.02;
        let reward = 0.001;
        let commission = round8(reward * rate);
        assert_eq!(commission, 0.00002);
    }
}
