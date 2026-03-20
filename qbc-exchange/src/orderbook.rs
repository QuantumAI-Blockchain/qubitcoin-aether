use ordered_float::OrderedFloat;
use std::collections::HashMap;
use uuid::Uuid;

use crate::types::*;

/// Single-pair order book with price-time priority matching.
pub struct OrderBook {
    pub config: MarketConfig,
    bids: Vec<Order>,  // sorted: price DESC, time ASC
    asks: Vec<Order>,  // sorted: price ASC, time ASC
    trades: Vec<Trade>,
    pub all_orders: HashMap<String, Order>,
    order_counter: u64,
}

impl OrderBook {
    pub fn new(config: MarketConfig) -> Self {
        Self {
            config,
            bids: Vec::new(),
            asks: Vec::new(),
            trades: Vec::new(),
            all_orders: HashMap::new(),
            order_counter: 0,
        }
    }

    pub fn next_order_id(&mut self) -> String {
        self.order_counter += 1;
        format!("ord-{:08}", self.order_counter)
    }

    fn sort_bids(&mut self) {
        self.bids.sort_by(|a, b| {
            b.price.cmp(&a.price).then(a.timestamp.cmp(&b.timestamp))
        });
    }

    fn sort_asks(&mut self) {
        self.asks.sort_by(|a, b| {
            a.price.cmp(&b.price).then(a.timestamp.cmp(&b.timestamp))
        });
    }

    /// Add order, match against resting orders. Returns fills.
    pub fn add_order(&mut self, mut order: Order) -> Vec<Trade> {
        let fills = match order.order_type {
            OrderType::Market => self.match_market(&mut order),
            OrderType::Limit => self.match_limit(&mut order),
        };

        // Rest remaining limit orders on the book
        if order.remaining() > 1e-12 && order.order_type == OrderType::Limit {
            if order.filled > 0.0 {
                order.status = OrderStatus::Partial;
            }
            match order.side {
                Side::Buy => {
                    self.bids.push(order.clone());
                    self.sort_bids();
                }
                Side::Sell => {
                    self.asks.push(order.clone());
                    self.sort_asks();
                }
            }
        }

        self.all_orders.insert(order.id.clone(), order);
        fills
    }

    fn match_limit(&mut self, taker: &mut Order) -> Vec<Trade> {
        let mut fills = Vec::new();
        let book = match taker.side {
            Side::Buy => &mut self.asks,
            Side::Sell => &mut self.bids,
        };

        let mut i = 0;
        while i < book.len() && taker.remaining() > 1e-12 {
            let maker = &mut book[i];

            // Price check
            match taker.side {
                Side::Buy if maker.price > taker.price => break,
                Side::Sell if maker.price < taker.price => break,
                _ => {}
            }

            let fill_size = taker.remaining().min(maker.remaining());
            let fill_price = maker.price.into_inner();

            taker.filled += fill_size;
            maker.filled += fill_size;

            let trade = Trade {
                id: Uuid::new_v4().to_string()[..8].to_string(),
                pair: taker.pair.clone(),
                price: fill_price,
                size: fill_size,
                side: taker.side,
                maker_order_id: maker.id.clone(),
                taker_order_id: taker.id.clone(),
                timestamp: now_secs(),
            };
            fills.push(trade.clone());
            self.trades.push(trade);

            if maker.remaining() <= 1e-12 {
                let maker_id = maker.id.clone();
                book.remove(i);
                // Update stored order
                if let Some(stored) = self.all_orders.get_mut(&maker_id) {
                    stored.filled = stored.size;
                    stored.status = OrderStatus::Filled;
                }
            } else {
                let maker_id = maker.id.clone();
                let maker_filled = maker.filled;
                if let Some(stored) = self.all_orders.get_mut(&maker_id) {
                    stored.filled = maker_filled;
                    stored.status = OrderStatus::Partial;
                }
                i += 1;
            }
        }

        if taker.remaining() <= 1e-12 {
            taker.status = OrderStatus::Filled;
        }

        fills
    }

    fn match_market(&mut self, taker: &mut Order) -> Vec<Trade> {
        let mut fills = Vec::new();
        let book = match taker.side {
            Side::Buy => &mut self.asks,
            Side::Sell => &mut self.bids,
        };

        while !book.is_empty() && taker.remaining() > 1e-12 {
            let maker = &mut book[0];
            let fill_size = taker.remaining().min(maker.remaining());
            let fill_price = maker.price.into_inner();

            taker.filled += fill_size;
            maker.filled += fill_size;

            let trade = Trade {
                id: Uuid::new_v4().to_string()[..8].to_string(),
                pair: taker.pair.clone(),
                price: fill_price,
                size: fill_size,
                side: taker.side,
                maker_order_id: maker.id.clone(),
                taker_order_id: taker.id.clone(),
                timestamp: now_secs(),
            };
            fills.push(trade.clone());
            self.trades.push(trade);

            if maker.remaining() <= 1e-12 {
                let maker_id = maker.id.clone();
                book.remove(0);
                if let Some(stored) = self.all_orders.get_mut(&maker_id) {
                    stored.filled = stored.size;
                    stored.status = OrderStatus::Filled;
                }
            } else {
                let maker_id = maker.id.clone();
                let maker_filled = maker.filled;
                if let Some(stored) = self.all_orders.get_mut(&maker_id) {
                    stored.filled = maker_filled;
                    stored.status = OrderStatus::Partial;
                }
            }
        }

        if taker.remaining() <= 1e-12 {
            taker.status = OrderStatus::Filled;
        }

        fills
    }

    pub fn cancel_order(&mut self, order_id: &str, owner: &str) -> bool {
        let order = match self.all_orders.get(order_id) {
            Some(o) => o,
            None => return false,
        };

        if matches!(order.status, OrderStatus::Filled | OrderStatus::Cancelled) {
            return false;
        }
        if !owner.is_empty() && order.address != owner {
            return false;
        }

        self.bids.retain(|o| o.id != order_id);
        self.asks.retain(|o| o.id != order_id);

        if let Some(o) = self.all_orders.get_mut(order_id) {
            o.status = OrderStatus::Cancelled;
        }
        true
    }

    pub fn get_orderbook(&self, depth: usize) -> OrderBookSnapshot {
        let mut bid_levels: Vec<(f64, f64)> = Vec::new();
        let mut ask_levels: Vec<(f64, f64)> = Vec::new();

        // Aggregate bids by price
        let mut bid_map: HashMap<OrderedFloat<f64>, f64> = HashMap::new();
        for o in self.bids.iter().take(depth * 5) {
            *bid_map.entry(o.price).or_default() += o.remaining();
        }
        let mut bid_prices: Vec<_> = bid_map.into_iter().collect();
        bid_prices.sort_by(|a, b| b.0.cmp(&a.0));
        for (p, s) in bid_prices.into_iter().take(depth) {
            bid_levels.push((p.into_inner(), s));
        }

        // Aggregate asks by price
        let mut ask_map: HashMap<OrderedFloat<f64>, f64> = HashMap::new();
        for o in self.asks.iter().take(depth * 5) {
            *ask_map.entry(o.price).or_default() += o.remaining();
        }
        let mut ask_prices: Vec<_> = ask_map.into_iter().collect();
        ask_prices.sort_by(|a, b| a.0.cmp(&b.0));
        for (p, s) in ask_prices.into_iter().take(depth) {
            ask_levels.push((p.into_inner(), s));
        }

        let best_bid = bid_levels.first().map(|l| l.0).unwrap_or(0.0);
        let best_ask = ask_levels.first().map(|l| l.0).unwrap_or(0.0);
        let spread = if best_bid > 0.0 && best_ask > 0.0 {
            best_ask - best_bid
        } else {
            0.0
        };
        let mid = if best_bid > 0.0 && best_ask > 0.0 {
            (best_bid + best_ask) / 2.0
        } else {
            0.0
        };

        OrderBookSnapshot {
            pair: self.config.pair.clone(),
            bids: bid_levels,
            asks: ask_levels,
            spread,
            mid_price: mid,
            best_bid,
            best_ask,
        }
    }

    pub fn get_recent_trades(&self, limit: usize) -> Vec<Trade> {
        let start = self.trades.len().saturating_sub(limit);
        self.trades[start..].to_vec()
    }

    pub fn get_market_summary(&self) -> MarketSummary {
        let cutoff = now_secs().saturating_sub(86400);
        let trades_24h: Vec<&Trade> = self.trades.iter().filter(|t| t.timestamp > cutoff).collect();

        let volume = trades_24h.iter().map(|t| t.size * t.price).sum::<f64>();
        let last_price = trades_24h.last().map(|t| t.price).unwrap_or(0.0);
        let high = trades_24h.iter().map(|t| t.price).fold(0.0_f64, f64::max);
        let low = trades_24h
            .iter()
            .map(|t| t.price)
            .fold(f64::MAX, f64::min);
        let low = if low == f64::MAX { 0.0 } else { low };

        let ob = self.get_orderbook(1);
        let first_price = trades_24h.first().map(|t| t.price).unwrap_or(last_price);
        let change = if first_price > 0.0 {
            (last_price - first_price) / first_price * 100.0
        } else {
            0.0
        };

        MarketSummary {
            pair: self.config.pair.clone(),
            base: self.config.base.clone(),
            quote: self.config.quote.clone(),
            last_price,
            best_bid: ob.best_bid,
            best_ask: ob.best_ask,
            high_24h: high,
            low_24h: low,
            volume_24h: volume,
            change_24h: change,
            trades_24h: trades_24h.len() as u64,
        }
    }

    pub fn total_orders(&self) -> usize {
        self.all_orders.len()
    }

    pub fn total_trades(&self) -> usize {
        self.trades.len()
    }

    pub fn open_order_count(&self) -> usize {
        self.bids.len() + self.asks.len()
    }

    pub fn get_user_orders(&self, address: &str) -> Vec<Order> {
        let mut orders = Vec::new();
        for o in self.bids.iter().chain(self.asks.iter()) {
            if o.address == address && matches!(o.status, OrderStatus::Open | OrderStatus::Partial) {
                orders.push(o.clone());
            }
        }
        orders
    }
}

#[derive(Debug)]
pub struct OrderBookSnapshot {
    pub pair: String,
    pub bids: Vec<(f64, f64)>,
    pub asks: Vec<(f64, f64)>,
    pub spread: f64,
    pub mid_price: f64,
    pub best_bid: f64,
    pub best_ask: f64,
}

#[derive(Debug)]
pub struct MarketSummary {
    pub pair: String,
    pub base: String,
    pub quote: String,
    pub last_price: f64,
    pub best_bid: f64,
    pub best_ask: f64,
    pub high_24h: f64,
    pub low_24h: f64,
    pub volume_24h: f64,
    pub change_24h: f64,
    pub trades_24h: u64,
}
