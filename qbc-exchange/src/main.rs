mod types;
mod orderbook;
mod oracle;
mod synthetic;
mod service;

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::transport::Server;
use tracing::info;

use orderbook::OrderBook;
use oracle::Oracle;
use service::{ExchangeService, ExchangeState};
use synthetic::SyntheticManager;
use types::*;

pub mod exchange_proto {
    tonic::include_proto!("exchange");
}

/// Top 48 synthetic asset definitions — oracle-priced, QUSD-collateralized.
fn synthetic_assets() -> Vec<SyntheticAsset> {
    vec![
        SyntheticAsset { symbol: "sBTC".into(),    name: "Synthetic Bitcoin".into(),          coingecko_id: "bitcoin".into(),           decimals: 8 },
        SyntheticAsset { symbol: "sETH".into(),    name: "Synthetic Ethereum".into(),         coingecko_id: "ethereum".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sBNB".into(),    name: "Synthetic BNB".into(),              coingecko_id: "binancecoin".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sSOL".into(),    name: "Synthetic Solana".into(),           coingecko_id: "solana".into(),            decimals: 8 },
        SyntheticAsset { symbol: "sXRP".into(),    name: "Synthetic XRP".into(),              coingecko_id: "ripple".into(),            decimals: 8 },
        SyntheticAsset { symbol: "sADA".into(),    name: "Synthetic Cardano".into(),          coingecko_id: "cardano".into(),           decimals: 8 },
        SyntheticAsset { symbol: "sDOGE".into(),   name: "Synthetic Dogecoin".into(),         coingecko_id: "dogecoin".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sAVAX".into(),   name: "Synthetic Avalanche".into(),        coingecko_id: "avalanche-2".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sDOT".into(),    name: "Synthetic Polkadot".into(),         coingecko_id: "polkadot".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sTRX".into(),    name: "Synthetic Tron".into(),             coingecko_id: "tron".into(),              decimals: 8 },
        SyntheticAsset { symbol: "sLINK".into(),   name: "Synthetic Chainlink".into(),        coingecko_id: "chainlink".into(),         decimals: 8 },
        SyntheticAsset { symbol: "sMATIC".into(),  name: "Synthetic Polygon".into(),          coingecko_id: "matic-network".into(),     decimals: 8 },
        SyntheticAsset { symbol: "sSHIB".into(),   name: "Synthetic Shiba Inu".into(),        coingecko_id: "shiba-inu".into(),         decimals: 8 },
        SyntheticAsset { symbol: "sTON".into(),    name: "Synthetic Toncoin".into(),          coingecko_id: "the-open-network".into(),  decimals: 8 },
        SyntheticAsset { symbol: "sLTC".into(),    name: "Synthetic Litecoin".into(),         coingecko_id: "litecoin".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sBCH".into(),    name: "Synthetic Bitcoin Cash".into(),     coingecko_id: "bitcoin-cash".into(),      decimals: 8 },
        SyntheticAsset { symbol: "sUNI".into(),    name: "Synthetic Uniswap".into(),          coingecko_id: "uniswap".into(),           decimals: 8 },
        SyntheticAsset { symbol: "sATOM".into(),   name: "Synthetic Cosmos".into(),           coingecko_id: "cosmos".into(),            decimals: 8 },
        SyntheticAsset { symbol: "sXLM".into(),    name: "Synthetic Stellar".into(),          coingecko_id: "stellar".into(),           decimals: 8 },
        SyntheticAsset { symbol: "sNEAR".into(),   name: "Synthetic NEAR".into(),             coingecko_id: "near".into(),              decimals: 8 },
        SyntheticAsset { symbol: "sAPT".into(),    name: "Synthetic Aptos".into(),            coingecko_id: "aptos".into(),             decimals: 8 },
        SyntheticAsset { symbol: "sICP".into(),    name: "Synthetic ICP".into(),              coingecko_id: "internet-computer".into(), decimals: 8 },
        SyntheticAsset { symbol: "sFIL".into(),    name: "Synthetic Filecoin".into(),         coingecko_id: "filecoin".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sETC".into(),    name: "Synthetic Ethereum Classic".into(), coingecko_id: "ethereum-classic".into(),  decimals: 8 },
        SyntheticAsset { symbol: "sARB".into(),    name: "Synthetic Arbitrum".into(),         coingecko_id: "arbitrum".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sOP".into(),     name: "Synthetic Optimism".into(),         coingecko_id: "optimism".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sIMX".into(),    name: "Synthetic Immutable X".into(),      coingecko_id: "immutable-x".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sINJ".into(),    name: "Synthetic Injective".into(),        coingecko_id: "injective-protocol".into(),decimals: 8 },
        SyntheticAsset { symbol: "sVET".into(),    name: "Synthetic VeChain".into(),          coingecko_id: "vechain".into(),           decimals: 8 },
        SyntheticAsset { symbol: "sHBAR".into(),   name: "Synthetic Hedera".into(),           coingecko_id: "hedera-hashgraph".into(),  decimals: 8 },
        SyntheticAsset { symbol: "sSUI".into(),    name: "Synthetic Sui".into(),              coingecko_id: "sui".into(),               decimals: 8 },
        SyntheticAsset { symbol: "sMKR".into(),    name: "Synthetic Maker".into(),            coingecko_id: "maker".into(),             decimals: 8 },
        SyntheticAsset { symbol: "sAAVE".into(),   name: "Synthetic Aave".into(),             coingecko_id: "aave".into(),              decimals: 8 },
        SyntheticAsset { symbol: "sRENDER".into(), name: "Synthetic Render".into(),           coingecko_id: "render-token".into(),      decimals: 8 },
        SyntheticAsset { symbol: "sGRT".into(),    name: "Synthetic The Graph".into(),        coingecko_id: "the-graph".into(),         decimals: 8 },
        SyntheticAsset { symbol: "sFTM".into(),    name: "Synthetic Fantom".into(),           coingecko_id: "fantom".into(),            decimals: 8 },
        SyntheticAsset { symbol: "sALGO".into(),   name: "Synthetic Algorand".into(),         coingecko_id: "algorand".into(),          decimals: 8 },
        SyntheticAsset { symbol: "sTHETA".into(),  name: "Synthetic Theta".into(),            coingecko_id: "theta-token".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sFLOW".into(),   name: "Synthetic Flow".into(),             coingecko_id: "flow".into(),              decimals: 8 },
        SyntheticAsset { symbol: "sSAND".into(),   name: "Synthetic Sandbox".into(),          coingecko_id: "the-sandbox".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sAXS".into(),    name: "Synthetic Axie Infinity".into(),    coingecko_id: "axie-infinity".into(),     decimals: 8 },
        SyntheticAsset { symbol: "sMANA".into(),   name: "Synthetic Decentraland".into(),     coingecko_id: "decentraland".into(),      decimals: 8 },
        SyntheticAsset { symbol: "sSEI".into(),    name: "Synthetic Sei".into(),              coingecko_id: "sei-network".into(),       decimals: 8 },
        SyntheticAsset { symbol: "sSTX".into(),    name: "Synthetic Stacks".into(),           coingecko_id: "blockstack".into(),        decimals: 8 },
        SyntheticAsset { symbol: "sEGLD".into(),   name: "Synthetic MultiversX".into(),       coingecko_id: "elrond-erd-2".into(),      decimals: 8 },
        SyntheticAsset { symbol: "sQNT".into(),    name: "Synthetic Quant".into(),            coingecko_id: "quant-network".into(),     decimals: 8 },
        SyntheticAsset { symbol: "sPEPE".into(),   name: "Synthetic Pepe".into(),             coingecko_id: "pepe".into(),              decimals: 8 },
        SyntheticAsset { symbol: "sWLD".into(),    name: "Synthetic Worldcoin".into(),        coingecko_id: "worldcoin-wld".into(),     decimals: 8 },
    ]
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,qbc_exchange=debug")
        .init();

    info!("QBC Exchange Engine v1.0.0");

    let grpc_addr = std::env::var("EXCHANGE_GRPC_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:50053".to_string());
    let oracle_ttl: u64 = std::env::var("ORACLE_TTL")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(60);

    // ── Build synthetic assets + markets ──────────────────────────────
    let assets = synthetic_assets();
    let mut books: HashMap<String, OrderBook> = HashMap::new();
    let mut symbol_to_cg: HashMap<String, String> = HashMap::new();

    // Real markets
    books.insert(
        "QBC/QUSD".to_string(),
        OrderBook::new(MarketConfig {
            pair: "QBC/QUSD".into(),
            base: "QBC".into(),
            quote: "QUSD".into(),
            tick_size: 0.0001,
            min_order: 1.0,
            maker_fee: 0.0002,
            taker_fee: 0.0005,
        }),
    );
    books.insert(
        "wQBC/QUSD".to_string(),
        OrderBook::new(MarketConfig {
            pair: "wQBC/QUSD".into(),
            base: "wQBC".into(),
            quote: "QUSD".into(),
            tick_size: 0.0001,
            min_order: 1.0,
            maker_fee: 0.0002,
            taker_fee: 0.0005,
        }),
    );

    // Synthetic markets
    let mut coingecko_ids = Vec::new();
    for asset in &assets {
        let pair = format!("{}/QUSD", asset.symbol);
        symbol_to_cg.insert(asset.symbol.clone(), asset.coingecko_id.clone());
        coingecko_ids.push(asset.coingecko_id.clone());
        books.insert(
            pair.clone(),
            OrderBook::new(MarketConfig {
                pair,
                base: asset.symbol.clone(),
                quote: "QUSD".into(),
                tick_size: 0.01,
                min_order: 0.001,
                maker_fee: 0.0002,
                taker_fee: 0.0005,
            }),
        );
    }

    info!("Markets: 2 real + {} synthetic = {} total", assets.len(), books.len());

    // ── Oracle ────────────────────────────────────────────────────────
    let oracle = Arc::new(Oracle::new(coingecko_ids, oracle_ttl));
    oracle.start_loop();

    // ── Exchange state ────────────────────────────────────────────────
    let state = Arc::new(RwLock::new(ExchangeState {
        books,
        balances: HashMap::new(),
        synthetic_mgr: SyntheticManager::new(assets),
        symbol_to_cg,
        start_time: now_secs(),
    }));

    // ── gRPC Server ───────────────────────────────────────────────────
    let service = ExchangeService {
        state,
        oracle,
    };

    let addr = grpc_addr.parse()?;
    info!("gRPC server listening on {}", addr);

    Server::builder()
        .add_service(exchange_proto::exchange_server::ExchangeServer::new(service))
        .serve(addr)
        .await?;

    Ok(())
}
