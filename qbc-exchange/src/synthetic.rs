use std::collections::HashMap;
use tracing::{info, warn};

use crate::types::{CollateralPosition, SyntheticAsset};

/// Manages synthetic asset minting, burning, and collateral positions.
pub struct SyntheticManager {
    /// symbol -> asset definition
    assets: HashMap<String, SyntheticAsset>,
    /// (address, symbol) -> collateral position
    positions: HashMap<(String, String), CollateralPosition>,
    /// symbol -> total supply minted
    total_supply: HashMap<String, f64>,
    /// symbol -> total QUSD collateral locked
    total_collateral: HashMap<String, f64>,
    /// Minimum collateral ratio (e.g. 1.5 = 150%)
    min_collateral_ratio: f64,
    /// Liquidation threshold (e.g. 1.1 = 110%)
    liquidation_ratio: f64,
    /// Fee on mint/burn (e.g. 0.003 = 0.3%)
    fee_rate: f64,
}

impl SyntheticManager {
    pub fn new(assets: Vec<SyntheticAsset>) -> Self {
        let mut asset_map = HashMap::new();
        for a in assets {
            asset_map.insert(a.symbol.clone(), a);
        }
        Self {
            assets: asset_map,
            positions: HashMap::new(),
            total_supply: HashMap::new(),
            total_collateral: HashMap::new(),
            min_collateral_ratio: 1.5,
            liquidation_ratio: 1.1,
            fee_rate: 0.003,
        }
    }

    /// Mint synthetic tokens by depositing QUSD collateral.
    /// Returns (minted_amount, collateral_locked, fee).
    pub fn mint(
        &mut self,
        address: &str,
        symbol: &str,
        qusd_amount: f64,
        oracle_price: f64,
    ) -> Result<(f64, f64, f64), String> {
        if !self.assets.contains_key(symbol) {
            return Err(format!("Unknown synthetic: {}", symbol));
        }
        if oracle_price <= 0.0 {
            return Err(format!("No oracle price for {}", symbol));
        }
        if qusd_amount <= 0.0 {
            return Err("Amount must be positive".to_string());
        }

        // With 150% collateralization:
        // qusd_amount = collateral deposited
        // effective_value = qusd_amount / min_collateral_ratio
        // minted_amount = effective_value / oracle_price
        let effective_value = qusd_amount / self.min_collateral_ratio;
        let fee = effective_value * self.fee_rate;
        let minted_amount = (effective_value - fee) / oracle_price;

        if minted_amount <= 0.0 {
            return Err("Mint amount too small after fees".to_string());
        }

        // Update position
        let key = (address.to_string(), symbol.to_string());
        let pos = self.positions.entry(key).or_insert(CollateralPosition {
            address: address.to_string(),
            symbol: symbol.to_string(),
            synthetic_amount: 0.0,
            collateral_locked: 0.0,
        });
        pos.synthetic_amount += minted_amount;
        pos.collateral_locked += qusd_amount;

        *self.total_supply.entry(symbol.to_string()).or_default() += minted_amount;
        *self.total_collateral.entry(symbol.to_string()).or_default() += qusd_amount;

        info!(
            "Mint: {} {} for {} QUSD (addr: {}...)",
            minted_amount,
            symbol,
            qusd_amount,
            &address[..12.min(address.len())]
        );

        Ok((minted_amount, qusd_amount, fee))
    }

    /// Burn synthetic tokens and return QUSD collateral.
    /// Returns (qusd_returned, fee).
    pub fn burn(
        &mut self,
        address: &str,
        symbol: &str,
        amount: f64,
        oracle_price: f64,
    ) -> Result<(f64, f64), String> {
        if !self.assets.contains_key(symbol) {
            return Err(format!("Unknown synthetic: {}", symbol));
        }
        if oracle_price <= 0.0 {
            return Err(format!("No oracle price for {}", symbol));
        }
        if amount <= 0.0 {
            return Err("Amount must be positive".to_string());
        }

        let key = (address.to_string(), symbol.to_string());
        let pos = self.positions.get_mut(&key).ok_or("No position found")?;

        if pos.synthetic_amount < amount - 1e-12 {
            return Err(format!(
                "Insufficient balance: have {}, need {}",
                pos.synthetic_amount, amount
            ));
        }

        // QUSD to return: proportional to position
        let proportion = amount / pos.synthetic_amount;
        let collateral_to_return = pos.collateral_locked * proportion;
        let fee = collateral_to_return * self.fee_rate;
        let qusd_returned = collateral_to_return - fee;

        pos.synthetic_amount -= amount;
        pos.collateral_locked -= collateral_to_return;

        // Clean up empty positions
        if pos.synthetic_amount < 1e-12 {
            self.positions.remove(&key);
        }

        *self.total_supply.entry(symbol.to_string()).or_default() -= amount;
        *self.total_collateral.entry(symbol.to_string()).or_default() -= collateral_to_return;

        info!(
            "Burn: {} {} -> {} QUSD (addr: {}...)",
            amount,
            symbol,
            qusd_returned,
            &address[..12.min(address.len())]
        );

        Ok((qusd_returned, fee))
    }

    /// Check and liquidate undercollateralized positions.
    /// Returns list of (address, symbol, liquidated_amount).
    pub fn check_liquidations(
        &mut self,
        oracle_prices: &HashMap<String, f64>,
    ) -> Vec<(String, String, f64)> {
        let mut liquidated = Vec::new();

        let keys: Vec<_> = self.positions.keys().cloned().collect();
        for key in keys {
            let (ref addr, ref sym) = key;
            let asset = match self.assets.get(sym) {
                Some(a) => a,
                None => continue,
            };
            let price = match oracle_prices.get(&asset.coingecko_id) {
                Some(&p) if p > 0.0 => p,
                _ => continue,
            };

            let pos = match self.positions.get(&key) {
                Some(p) => p,
                None => continue,
            };

            let ratio = pos.collateral_ratio(price);
            if ratio < self.liquidation_ratio {
                warn!(
                    "Liquidating position: {} {} (ratio: {:.2}%, addr: {}...)",
                    pos.synthetic_amount,
                    sym,
                    ratio * 100.0,
                    &addr[..12.min(addr.len())]
                );
                let amount = pos.synthetic_amount;
                liquidated.push((addr.clone(), sym.clone(), amount));

                // Remove supply/collateral tracking
                *self.total_supply.entry(sym.clone()).or_default() -= amount;
                if let Some(pos) = self.positions.get(&key) {
                    *self.total_collateral.entry(sym.clone()).or_default() -=
                        pos.collateral_locked;
                }
                self.positions.remove(&key);
            }
        }

        liquidated
    }

    pub fn get_position(&self, address: &str, symbol: &str) -> Option<&CollateralPosition> {
        self.positions.get(&(address.to_string(), symbol.to_string()))
    }

    pub fn get_all_positions(&self, address: &str) -> Vec<&CollateralPosition> {
        self.positions
            .iter()
            .filter(|((addr, _), _)| addr == address)
            .map(|(_, pos)| pos)
            .collect()
    }

    pub fn get_assets(&self) -> &HashMap<String, SyntheticAsset> {
        &self.assets
    }

    pub fn get_total_supply(&self, symbol: &str) -> f64 {
        self.total_supply.get(symbol).copied().unwrap_or(0.0)
    }

    pub fn get_total_collateral(&self, symbol: &str) -> f64 {
        self.total_collateral.get(symbol).copied().unwrap_or(0.0)
    }

    pub fn total_collateral_locked(&self) -> f64 {
        self.total_collateral.values().sum()
    }

    pub fn liquidation_ratio(&self) -> f64 {
        self.liquidation_ratio
    }
}
