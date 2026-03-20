use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{Request, Response, Status};
use tracing::info;
use ordered_float::OrderedFloat;

use crate::exchange_proto;
use crate::exchange_proto::exchange_server::Exchange;
use crate::oracle::Oracle;
use crate::orderbook::OrderBook;
use crate::synthetic::SyntheticManager;
use crate::types::*;

pub struct ExchangeState {
    pub books: HashMap<String, OrderBook>,
    pub balances: HashMap<String, HashMap<String, f64>>,
    pub synthetic_mgr: SyntheticManager,
    /// symbol -> coingecko_id mapping
    pub symbol_to_cg: HashMap<String, String>,
    pub start_time: u64,
}

pub struct ExchangeService {
    pub state: Arc<RwLock<ExchangeState>>,
    pub oracle: Arc<Oracle>,
}

#[tonic::async_trait]
impl Exchange for ExchangeService {
    // ── Order Management ─────────────────────────────────────────────

    async fn place_order(
        &self,
        request: Request<exchange_proto::PlaceOrderRequest>,
    ) -> Result<Response<exchange_proto::PlaceOrderResponse>, Status> {
        let req = request.into_inner();
        let pair = normalize_pair(&req.pair);

        let mut state = self.state.write().await;

        // Extract config info before mutable borrow
        let (min_order, base, quote) = {
            let book = state.books.get(&pair).ok_or_else(|| {
                Status::not_found(format!("Unknown pair: {}", pair))
            })?;
            (book.config.min_order, book.config.base.clone(), book.config.quote.clone())
        };

        let side = match req.side {
            0 => Side::Buy,
            _ => Side::Sell,
        };
        let order_type = match req.order_type {
            0 => OrderType::Limit,
            _ => OrderType::Market,
        };

        // Check min order size
        if req.size < min_order {
            return Ok(Response::new(exchange_proto::PlaceOrderResponse {
                success: false,
                error: format!("Min order size is {} {}", min_order, base),
                ..Default::default()
            }));
        }

        // Balance check for limit orders
        if !req.address.is_empty() && order_type == OrderType::Limit {
            let user_bals = state.balances.entry(req.address.clone()).or_default();
            let (required_asset, required_amount) = match side {
                Side::Buy => (quote.clone(), req.price * req.size),
                Side::Sell => (base.clone(), req.size),
            };
            let available = user_bals.get(&required_asset).copied().unwrap_or(0.0);
            if available < required_amount {
                return Ok(Response::new(exchange_proto::PlaceOrderResponse {
                    success: false,
                    error: format!(
                        "Insufficient {}: have {}, need {}",
                        required_asset, available, required_amount
                    ),
                    ..Default::default()
                }));
            }
        }

        let book = state.books.get_mut(&pair).unwrap();
        let order_id = book.next_order_id();
        let order = Order {
            id: order_id,
            pair: pair.clone(),
            side,
            order_type,
            price: OrderedFloat(req.price),
            size: req.size,
            filled: 0.0,
            address: req.address.clone(),
            timestamp: now_secs(),
            status: OrderStatus::Open,
        };

        let fills = book.add_order(order.clone());
        let config = book.config.clone();
        let final_order = book.all_orders.get(&order.id).cloned().unwrap_or(order.clone());

        // Settle fills in balances (no longer borrowing book)
        for fill in &fills {
            settle_fill(&mut state.balances, &config, fill);
        }

        let proto_fills: Vec<exchange_proto::TradeInfo> = fills
            .iter()
            .map(|t| exchange_proto::TradeInfo {
                id: t.id.clone(),
                pair: t.pair.clone(),
                price: t.price,
                size: t.size,
                side: t.side.as_str().to_string(),
                maker_order_id: t.maker_order_id.clone(),
                taker_order_id: t.taker_order_id.clone(),
                timestamp: t.timestamp,
            })
            .collect();

        Ok(Response::new(exchange_proto::PlaceOrderResponse {
            success: true,
            error: String::new(),
            order: Some(order_to_proto(&final_order)),
            fills: proto_fills,
            filled_size: final_order.filled,
            remaining_size: final_order.remaining(),
        }))
    }

    async fn cancel_order(
        &self,
        request: Request<exchange_proto::CancelOrderRequest>,
    ) -> Result<Response<exchange_proto::CancelOrderResponse>, Status> {
        let req = request.into_inner();
        let pair = normalize_pair(&req.pair);

        let mut state = self.state.write().await;

        // Try specific pair first, then scan all
        let success = if let Some(book) = state.books.get_mut(&pair) {
            book.cancel_order(&req.order_id, &req.address)
        } else {
            let mut found = false;
            for book in state.books.values_mut() {
                if book.cancel_order(&req.order_id, &req.address) {
                    found = true;
                    break;
                }
            }
            found
        };

        Ok(Response::new(exchange_proto::CancelOrderResponse {
            success,
            error: if success { String::new() } else { "Order not found or not cancellable".to_string() },
        }))
    }

    async fn get_order_book(
        &self,
        request: Request<exchange_proto::GetOrderBookRequest>,
    ) -> Result<Response<exchange_proto::OrderBookResponse>, Status> {
        let req = request.into_inner();
        let pair = normalize_pair(&req.pair);
        let depth = if req.depth == 0 { 20 } else { req.depth as usize };

        let state = self.state.read().await;
        let book = state.books.get(&pair).ok_or_else(|| {
            Status::not_found(format!("Unknown pair: {}", pair))
        })?;

        let snap = book.get_orderbook(depth);

        Ok(Response::new(exchange_proto::OrderBookResponse {
            pair: snap.pair,
            bids: snap.bids.iter().map(|(p, s)| exchange_proto::PriceLevel { price: *p, size: *s }).collect(),
            asks: snap.asks.iter().map(|(p, s)| exchange_proto::PriceLevel { price: *p, size: *s }).collect(),
            spread: snap.spread,
            mid_price: snap.mid_price,
            best_bid: snap.best_bid,
            best_ask: snap.best_ask,
        }))
    }

    async fn get_user_orders(
        &self,
        request: Request<exchange_proto::GetUserOrdersRequest>,
    ) -> Result<Response<exchange_proto::UserOrdersResponse>, Status> {
        let req = request.into_inner();
        let state = self.state.read().await;

        let mut orders = Vec::new();
        for book in state.books.values() {
            for o in book.get_user_orders(&req.address) {
                orders.push(order_to_proto(&o));
            }
        }

        Ok(Response::new(exchange_proto::UserOrdersResponse { orders }))
    }

    // ── Market Data ──────────────────────────────────────────────────

    async fn get_markets(
        &self,
        _request: Request<exchange_proto::GetMarketsRequest>,
    ) -> Result<Response<exchange_proto::MarketsResponse>, Status> {
        let state = self.state.read().await;
        let oracle_prices = self.oracle.get_all_prices().await;

        let mut markets = Vec::new();
        for book in state.books.values() {
            let summary = book.get_market_summary();
            let oracle_price = state
                .symbol_to_cg
                .get(&book.config.base)
                .and_then(|cg| oracle_prices.get(cg))
                .copied()
                .unwrap_or(0.0);

            markets.push(exchange_proto::MarketInfo {
                pair: summary.pair,
                base: summary.base,
                quote: summary.quote,
                last_price: summary.last_price,
                best_bid: summary.best_bid,
                best_ask: summary.best_ask,
                high_24h: summary.high_24h,
                low_24h: summary.low_24h,
                volume_24h: summary.volume_24h,
                change_24h: summary.change_24h,
                trades_24h: summary.trades_24h,
                oracle_price,
            });
        }

        Ok(Response::new(exchange_proto::MarketsResponse { markets }))
    }

    async fn get_recent_trades(
        &self,
        request: Request<exchange_proto::GetRecentTradesRequest>,
    ) -> Result<Response<exchange_proto::RecentTradesResponse>, Status> {
        let req = request.into_inner();
        let pair = normalize_pair(&req.pair);
        let limit = if req.limit == 0 { 50 } else { req.limit as usize };

        let state = self.state.read().await;
        let book = state.books.get(&pair).ok_or_else(|| {
            Status::not_found(format!("Unknown pair: {}", pair))
        })?;

        let trades: Vec<exchange_proto::TradeInfo> = book
            .get_recent_trades(limit)
            .iter()
            .map(|t| exchange_proto::TradeInfo {
                id: t.id.clone(),
                pair: t.pair.clone(),
                price: t.price,
                size: t.size,
                side: t.side.as_str().to_string(),
                maker_order_id: t.maker_order_id.clone(),
                taker_order_id: t.taker_order_id.clone(),
                timestamp: t.timestamp,
            })
            .collect();

        Ok(Response::new(exchange_proto::RecentTradesResponse { trades }))
    }

    async fn get_market_summary(
        &self,
        request: Request<exchange_proto::GetMarketSummaryRequest>,
    ) -> Result<Response<exchange_proto::MarketSummaryResponse>, Status> {
        let req = request.into_inner();
        let pair = normalize_pair(&req.pair);

        let state = self.state.read().await;
        let book = state.books.get(&pair).ok_or_else(|| {
            Status::not_found(format!("Unknown pair: {}", pair))
        })?;
        let summary = book.get_market_summary();
        let oracle_prices = self.oracle.get_all_prices().await;
        let oracle_price = state
            .symbol_to_cg
            .get(&book.config.base)
            .and_then(|cg| oracle_prices.get(cg))
            .copied()
            .unwrap_or(0.0);

        Ok(Response::new(exchange_proto::MarketSummaryResponse {
            market: Some(exchange_proto::MarketInfo {
                pair: summary.pair,
                base: summary.base,
                quote: summary.quote,
                last_price: summary.last_price,
                best_bid: summary.best_bid,
                best_ask: summary.best_ask,
                high_24h: summary.high_24h,
                low_24h: summary.low_24h,
                volume_24h: summary.volume_24h,
                change_24h: summary.change_24h,
                trades_24h: summary.trades_24h,
                oracle_price,
            }),
        }))
    }

    // ── Balance Management ───────────────────────────────────────────

    async fn deposit(
        &self,
        request: Request<exchange_proto::DepositRequest>,
    ) -> Result<Response<exchange_proto::BalanceResponse>, Status> {
        let req = request.into_inner();
        if req.amount <= 0.0 {
            return Ok(Response::new(exchange_proto::BalanceResponse {
                success: false,
                error: "Amount must be positive".to_string(),
                ..Default::default()
            }));
        }

        let mut state = self.state.write().await;
        let bal = state
            .balances
            .entry(req.address.clone())
            .or_default()
            .entry(req.asset.clone())
            .or_insert(0.0);
        *bal += req.amount;

        info!("Deposit: {}... +{} {}", &req.address[..12.min(req.address.len())], req.amount, req.asset);

        Ok(Response::new(exchange_proto::BalanceResponse {
            success: true,
            error: String::new(),
            address: req.address,
            asset: req.asset,
            amount: req.amount,
            balance: *bal,
        }))
    }

    async fn withdraw(
        &self,
        request: Request<exchange_proto::WithdrawRequest>,
    ) -> Result<Response<exchange_proto::BalanceResponse>, Status> {
        let req = request.into_inner();
        if req.amount <= 0.0 {
            return Ok(Response::new(exchange_proto::BalanceResponse {
                success: false,
                error: "Amount must be positive".to_string(),
                ..Default::default()
            }));
        }

        let mut state = self.state.write().await;
        let bal = state
            .balances
            .entry(req.address.clone())
            .or_default()
            .entry(req.asset.clone())
            .or_insert(0.0);

        if *bal < req.amount {
            return Ok(Response::new(exchange_proto::BalanceResponse {
                success: false,
                error: format!("Insufficient {}: have {}, need {}", req.asset, bal, req.amount),
                ..Default::default()
            }));
        }

        *bal -= req.amount;

        Ok(Response::new(exchange_proto::BalanceResponse {
            success: true,
            error: String::new(),
            address: req.address,
            asset: req.asset,
            amount: req.amount,
            balance: *bal,
        }))
    }

    async fn get_balance(
        &self,
        request: Request<exchange_proto::GetBalanceRequest>,
    ) -> Result<Response<exchange_proto::UserBalanceResponse>, Status> {
        let req = request.into_inner();
        let state = self.state.read().await;

        let balances = state
            .balances
            .get(&req.address)
            .map(|bals| {
                bals.iter()
                    .filter(|(_, &v)| v > 0.0)
                    .map(|(k, &v)| (k.clone(), v))
                    .collect()
            })
            .unwrap_or_default();

        Ok(Response::new(exchange_proto::UserBalanceResponse {
            address: req.address,
            balances,
        }))
    }

    // ── Synthetic Assets ─────────────────────────────────────────────

    async fn mint_synthetic(
        &self,
        request: Request<exchange_proto::MintSyntheticRequest>,
    ) -> Result<Response<exchange_proto::MintSyntheticResponse>, Status> {
        let req = request.into_inner();
        let mut state = self.state.write().await;

        // Get oracle price for the synthetic
        let cg_id = state.symbol_to_cg.get(&req.symbol).cloned();
        let oracle_price = if let Some(ref cg) = cg_id {
            self.oracle.get_price(cg).await
        } else {
            0.0
        };

        // Check QUSD balance
        let qusd_bal = state
            .balances
            .entry(req.address.clone())
            .or_default()
            .entry("QUSD".to_string())
            .or_insert(0.0);

        if *qusd_bal < req.qusd_amount {
            return Ok(Response::new(exchange_proto::MintSyntheticResponse {
                success: false,
                error: format!("Insufficient QUSD: have {}, need {}", qusd_bal, req.qusd_amount),
                ..Default::default()
            }));
        }

        match state.synthetic_mgr.mint(&req.address, &req.symbol, req.qusd_amount, oracle_price) {
            Ok((minted, collateral, _fee)) => {
                // Debit QUSD
                *state
                    .balances
                    .get_mut(&req.address)
                    .unwrap()
                    .get_mut("QUSD")
                    .unwrap() -= collateral;

                // Credit synthetic
                *state
                    .balances
                    .entry(req.address.clone())
                    .or_default()
                    .entry(req.symbol.clone())
                    .or_insert(0.0) += minted;

                let ratio = collateral / (minted * oracle_price);

                Ok(Response::new(exchange_proto::MintSyntheticResponse {
                    success: true,
                    error: String::new(),
                    symbol: req.symbol,
                    minted_amount: minted,
                    collateral_locked: collateral,
                    oracle_price,
                    collateral_ratio: ratio,
                }))
            }
            Err(e) => Ok(Response::new(exchange_proto::MintSyntheticResponse {
                success: false,
                error: e,
                ..Default::default()
            })),
        }
    }

    async fn burn_synthetic(
        &self,
        request: Request<exchange_proto::BurnSyntheticRequest>,
    ) -> Result<Response<exchange_proto::BurnSyntheticResponse>, Status> {
        let req = request.into_inner();
        let mut state = self.state.write().await;

        let cg_id = state.symbol_to_cg.get(&req.symbol).cloned();
        let oracle_price = if let Some(ref cg) = cg_id {
            self.oracle.get_price(cg).await
        } else {
            0.0
        };

        // Check synthetic balance
        let syn_bal = state
            .balances
            .entry(req.address.clone())
            .or_default()
            .entry(req.symbol.clone())
            .or_insert(0.0);

        if *syn_bal < req.amount {
            return Ok(Response::new(exchange_proto::BurnSyntheticResponse {
                success: false,
                error: format!("Insufficient {}: have {}, need {}", req.symbol, syn_bal, req.amount),
                ..Default::default()
            }));
        }

        match state.synthetic_mgr.burn(&req.address, &req.symbol, req.amount, oracle_price) {
            Ok((qusd_returned, fee)) => {
                // Debit synthetic
                *state
                    .balances
                    .get_mut(&req.address)
                    .unwrap()
                    .get_mut(&req.symbol)
                    .unwrap() -= req.amount;

                // Credit QUSD
                *state
                    .balances
                    .entry(req.address.clone())
                    .or_default()
                    .entry("QUSD".to_string())
                    .or_insert(0.0) += qusd_returned;

                Ok(Response::new(exchange_proto::BurnSyntheticResponse {
                    success: true,
                    error: String::new(),
                    symbol: req.symbol,
                    burned_amount: req.amount,
                    qusd_returned,
                    fee,
                }))
            }
            Err(e) => Ok(Response::new(exchange_proto::BurnSyntheticResponse {
                success: false,
                error: e,
                ..Default::default()
            })),
        }
    }

    async fn get_synthetic_assets(
        &self,
        _request: Request<exchange_proto::GetSyntheticAssetsRequest>,
    ) -> Result<Response<exchange_proto::SyntheticAssetsResponse>, Status> {
        let state = self.state.read().await;
        let oracle_prices = self.oracle.get_all_prices().await;

        let assets: Vec<exchange_proto::SyntheticAssetInfo> = state
            .synthetic_mgr
            .get_assets()
            .values()
            .map(|a| {
                let oracle_price = oracle_prices.get(&a.coingecko_id).copied().unwrap_or(0.0);
                exchange_proto::SyntheticAssetInfo {
                    symbol: a.symbol.clone(),
                    name: a.name.clone(),
                    coingecko_id: a.coingecko_id.clone(),
                    pair: format!("{}/QUSD", a.symbol),
                    oracle_price,
                    total_supply: state.synthetic_mgr.get_total_supply(&a.symbol),
                    total_collateral: state.synthetic_mgr.get_total_collateral(&a.symbol),
                }
            })
            .collect();

        Ok(Response::new(exchange_proto::SyntheticAssetsResponse { assets }))
    }

    async fn get_collateral_position(
        &self,
        request: Request<exchange_proto::GetCollateralPositionRequest>,
    ) -> Result<Response<exchange_proto::CollateralPositionResponse>, Status> {
        let req = request.into_inner();
        let state = self.state.read().await;
        let oracle_prices = self.oracle.get_all_prices().await;
        let liq_ratio = state.synthetic_mgr.liquidation_ratio();

        let positions: Vec<exchange_proto::CollateralPosition> = if req.symbol.is_empty() {
            state
                .synthetic_mgr
                .get_all_positions(&req.address)
                .iter()
                .map(|p| {
                    let price = state
                        .symbol_to_cg
                        .get(&p.symbol)
                        .and_then(|cg| oracle_prices.get(cg))
                        .copied()
                        .unwrap_or(0.0);
                    pos_to_proto(p, price, liq_ratio)
                })
                .collect()
        } else {
            state
                .synthetic_mgr
                .get_position(&req.address, &req.symbol)
                .into_iter()
                .map(|p| {
                    let price = state
                        .symbol_to_cg
                        .get(&p.symbol)
                        .and_then(|cg| oracle_prices.get(cg))
                        .copied()
                        .unwrap_or(0.0);
                    pos_to_proto(p, price, liq_ratio)
                })
                .collect()
        };

        Ok(Response::new(exchange_proto::CollateralPositionResponse { positions }))
    }

    // ── Oracle ───────────────────────────────────────────────────────

    async fn get_oracle_prices(
        &self,
        _request: Request<exchange_proto::GetOraclePricesRequest>,
    ) -> Result<Response<exchange_proto::OraclePricesResponse>, Status> {
        let prices = self.oracle.get_all_prices().await;
        let last_updated = self.oracle.last_updated().await;

        Ok(Response::new(exchange_proto::OraclePricesResponse {
            prices,
            last_updated,
        }))
    }

    // ── Engine Stats ─────────────────────────────────────────────────

    async fn get_engine_stats(
        &self,
        _request: Request<exchange_proto::GetEngineStatsRequest>,
    ) -> Result<Response<exchange_proto::EngineStatsResponse>, Status> {
        let state = self.state.read().await;

        let total_orders: u64 = state.books.values().map(|b| b.total_orders() as u64).sum();
        let total_trades: u64 = state.books.values().map(|b| b.total_trades() as u64).sum();
        let open_orders: u64 = state.books.values().map(|b| b.open_order_count() as u64).sum();
        let markets: Vec<String> = state.books.keys().cloned().collect();

        Ok(Response::new(exchange_proto::EngineStatsResponse {
            total_pairs: state.books.len() as u64,
            total_orders,
            total_trades,
            open_orders,
            markets,
            synthetic_assets: state.synthetic_mgr.get_assets().len() as u64,
            total_collateral_locked: state.synthetic_mgr.total_collateral_locked(),
        }))
    }

    async fn health_check(
        &self,
        _request: Request<exchange_proto::HealthCheckRequest>,
    ) -> Result<Response<exchange_proto::HealthCheckResponse>, Status> {
        let state = self.state.read().await;
        let oracle_active = self.oracle.last_updated().await > 0;

        Ok(Response::new(exchange_proto::HealthCheckResponse {
            healthy: true,
            version: "1.0.0".to_string(),
            uptime_seconds: now_secs() - state.start_time,
            markets: state.books.len() as u64,
            oracle_active,
        }))
    }
}

// ── Helpers ──────────────────────────────────────────────────────────

fn normalize_pair(pair: &str) -> String {
    if !pair.contains('/') && pair.contains('-') {
        pair.replacen('-', "/", 1)
    } else {
        pair.to_string()
    }
}

fn order_to_proto(o: &Order) -> exchange_proto::OrderInfo {
    exchange_proto::OrderInfo {
        id: o.id.clone(),
        pair: o.pair.clone(),
        side: o.side.as_str().to_string(),
        order_type: o.order_type.as_str().to_string(),
        price: o.price.into_inner(),
        size: o.size,
        filled: o.filled,
        remaining: o.remaining(),
        address: o.address.clone(),
        timestamp: o.timestamp,
        status: o.status.as_str().to_string(),
    }
}

fn pos_to_proto(
    p: &crate::types::CollateralPosition,
    oracle_price: f64,
    liq_ratio: f64,
) -> exchange_proto::CollateralPosition {
    let ratio = p.collateral_ratio(oracle_price);
    exchange_proto::CollateralPosition {
        symbol: p.symbol.clone(),
        address: p.address.clone(),
        synthetic_amount: p.synthetic_amount,
        collateral_locked: p.collateral_locked,
        collateral_ratio: ratio,
        liquidation_price: p.liquidation_price(liq_ratio),
        is_liquidatable: ratio < liq_ratio,
    }
}

fn settle_fill(
    _balances: &mut HashMap<String, HashMap<String, f64>>,
    _config: &MarketConfig,
    _trade: &Trade,
) {
    // Balance settlement is handled at the application layer (Python node)
    // since the exchange engine tracks orders and fills, and the node
    // coordinates actual UTXO/balance movements. The exchange tracks
    // internal exchange balances via deposit/withdraw RPCs.
}
