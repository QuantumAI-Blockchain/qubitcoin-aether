use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn, error};

use crate::types::now_secs;

/// CoinGecko oracle price feed with TTL caching.
pub struct Oracle {
    prices: Arc<RwLock<HashMap<String, f64>>>,  // coingecko_id -> USD price
    last_updated: Arc<RwLock<u64>>,
    coingecko_ids: Vec<String>,
    cache_ttl: u64,
}

impl Oracle {
    pub fn new(coingecko_ids: Vec<String>, cache_ttl: u64) -> Self {
        Self {
            prices: Arc::new(RwLock::new(HashMap::new())),
            last_updated: Arc::new(RwLock::new(0)),
            coingecko_ids,
            cache_ttl,
        }
    }

    /// Get current price for a coingecko_id. Returns 0.0 if unknown.
    pub async fn get_price(&self, coingecko_id: &str) -> f64 {
        let prices = self.prices.read().await;
        prices.get(coingecko_id).copied().unwrap_or(0.0)
    }

    /// Get all cached prices.
    pub async fn get_all_prices(&self) -> HashMap<String, f64> {
        self.prices.read().await.clone()
    }

    /// Get last update timestamp.
    pub async fn last_updated(&self) -> u64 {
        *self.last_updated.read().await
    }

    /// Fetch prices from CoinGecko. Called periodically.
    pub async fn fetch_prices(&self) -> anyhow::Result<usize> {
        if self.coingecko_ids.is_empty() {
            return Ok(0);
        }

        // CoinGecko free API: /api/v3/simple/price?ids=...&vs_currencies=usd
        // Max ~250 IDs per request, we have 50 so one call suffices.
        let ids = self.coingecko_ids.join(",");
        let url = format!(
            "https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies=usd",
            ids
        );

        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(15))
            .user_agent("QBC-Exchange/1.0.0")
            .build()?;

        let resp = client.get(&url).send().await?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("CoinGecko returned {}: {}", status, &body[..200.min(body.len())]);
        }

        let data: HashMap<String, HashMap<String, f64>> = resp.json().await?;

        let mut prices = self.prices.write().await;
        let mut count = 0;
        for (id, currencies) in &data {
            if let Some(&usd) = currencies.get("usd") {
                prices.insert(id.clone(), usd);
                count += 1;
            }
        }

        *self.last_updated.write().await = now_secs();
        info!("Oracle updated: {} prices fetched from CoinGecko", count);

        Ok(count)
    }

    /// Start a background loop that fetches prices every `cache_ttl` seconds.
    pub fn start_loop(self: &Arc<Self>) -> tokio::task::JoinHandle<()> {
        let oracle = Arc::clone(self);
        tokio::spawn(async move {
            // Initial fetch
            match oracle.fetch_prices().await {
                Ok(n) => info!("Oracle initial fetch: {} prices", n),
                Err(e) => warn!("Oracle initial fetch failed: {}", e),
            }

            let mut interval = tokio::time::interval(
                std::time::Duration::from_secs(oracle.cache_ttl)
            );
            interval.tick().await; // skip the first immediate tick

            loop {
                interval.tick().await;
                match oracle.fetch_prices().await {
                    Ok(n) => info!("Oracle refresh: {} prices", n),
                    Err(e) => error!("Oracle fetch error: {}", e),
                }
            }
        })
    }
}
