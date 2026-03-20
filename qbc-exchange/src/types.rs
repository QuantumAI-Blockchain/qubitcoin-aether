use ordered_float::OrderedFloat;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

impl Side {
    pub fn as_str(&self) -> &'static str {
        match self {
            Side::Buy => "buy",
            Side::Sell => "sell",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderType {
    Limit,
    Market,
}

impl OrderType {
    pub fn as_str(&self) -> &'static str {
        match self {
            OrderType::Limit => "limit",
            OrderType::Market => "market",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderStatus {
    Open,
    Partial,
    Filled,
    Cancelled,
}

impl OrderStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            OrderStatus::Open => "open",
            OrderStatus::Partial => "partial",
            OrderStatus::Filled => "filled",
            OrderStatus::Cancelled => "cancelled",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Order {
    pub id: String,
    pub pair: String,
    pub side: Side,
    pub order_type: OrderType,
    pub price: OrderedFloat<f64>,
    pub size: f64,
    pub filled: f64,
    pub address: String,
    pub timestamp: u64,
    pub status: OrderStatus,
}

impl Order {
    pub fn remaining(&self) -> f64 {
        self.size - self.filled
    }
}

#[derive(Debug, Clone)]
pub struct Trade {
    pub id: String,
    pub pair: String,
    pub price: f64,
    pub size: f64,
    pub side: Side,
    pub maker_order_id: String,
    pub taker_order_id: String,
    pub timestamp: u64,
}

#[derive(Debug, Clone)]
pub struct MarketConfig {
    pub pair: String,
    pub base: String,
    pub quote: String,
    pub tick_size: f64,
    pub min_order: f64,
    pub maker_fee: f64,
    pub taker_fee: f64,
}

#[derive(Debug, Clone)]
pub struct SyntheticAsset {
    pub symbol: String,
    pub name: String,
    pub coingecko_id: String,
    pub decimals: u8,
}

#[derive(Debug, Clone)]
pub struct CollateralPosition {
    pub address: String,
    pub symbol: String,
    pub synthetic_amount: f64,
    pub collateral_locked: f64,
}

impl CollateralPosition {
    pub fn collateral_ratio(&self, oracle_price: f64) -> f64 {
        if self.synthetic_amount <= 0.0 || oracle_price <= 0.0 {
            return f64::MAX;
        }
        self.collateral_locked / (self.synthetic_amount * oracle_price)
    }

    pub fn liquidation_price(&self, min_ratio: f64) -> f64 {
        if self.synthetic_amount <= 0.0 {
            return 0.0;
        }
        self.collateral_locked / (self.synthetic_amount * min_ratio)
    }
}

pub fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
