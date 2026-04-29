//! Subscription-based auth middleware for Aether chat routes.
//!
//! Flow:
//! 1. Extract `X-QBC-Address` header (optional).
//! 2. If no address: free tier — track by IP, 5 chats/day.
//! 3. If address: call aether-mind `/aether/auth/check` to verify subscription.
//! 4. If balance sufficient and call is billable: call `/aether/auth/deduct`.
//! 5. Return 402 if insufficient balance.

use std::collections::HashMap;
use std::net::IpAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::{
    body::Body,
    http::{Request, StatusCode},
    middleware::Next,
    response::Response,
};
use serde_json::json;
use tokio::sync::Mutex;
use tracing::warn;

/// Per-IP free tier tracking.
pub struct FreeTierTracker {
    /// IP -> (count, window_start)
    entries: HashMap<IpAddr, (u32, Instant)>,
    max_free: u32,
    window: Duration,
}

impl FreeTierTracker {
    pub fn new(max_free: u32) -> Self {
        Self {
            entries: HashMap::new(),
            max_free,
            window: Duration::from_secs(86400), // 24 hours
        }
    }

    /// Returns true if the IP is within the free tier limit.
    pub fn check_and_increment(&mut self, ip: IpAddr) -> bool {
        let now = Instant::now();

        // Prune expired entries every 100 checks to prevent unbounded growth
        if self.entries.len() > 100 {
            self.entries.retain(|_, (_, start)| now.duration_since(*start) < self.window);
        }

        let entry = self.entries.entry(ip).or_insert((0, now));

        // Reset window if expired
        if now.duration_since(entry.1) > self.window {
            *entry = (0, now);
        }

        if entry.0 >= self.max_free {
            return false;
        }

        entry.0 += 1;
        true
    }
}

pub type SharedFreeTierTracker = Arc<Mutex<FreeTierTracker>>;

/// Create a free tier tracker with 5 chats/day default.
pub fn create_free_tier_tracker() -> SharedFreeTierTracker {
    Arc::new(Mutex::new(FreeTierTracker::new(5)))
}

/// Extract real client IP from request headers.
fn extract_ip(req: &Request<Body>) -> Option<IpAddr> {
    if let Some(cf_ip) = req.headers().get("CF-Connecting-IP") {
        if let Ok(s) = cf_ip.to_str() {
            if let Ok(ip) = s.parse::<IpAddr>() {
                return Some(ip);
            }
        }
    }
    if let Some(xff) = req.headers().get("X-Forwarded-For") {
        if let Ok(s) = xff.to_str() {
            if let Some(first) = s.split(',').next() {
                if let Ok(ip) = first.trim().parse::<IpAddr>() {
                    return Some(ip);
                }
            }
        }
    }
    None
}

/// Auth middleware for chat routes.
/// Checks X-QBC-Address header for subscription, falls back to free tier by IP.
pub async fn auth_middleware(
    axum::extract::State((aether_url, tracker, http_client)): axum::extract::State<(
        String,
        SharedFreeTierTracker,
        reqwest::Client,
    )>,
    req: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let qbc_address = req
        .headers()
        .get("X-QBC-Address")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    match qbc_address {
        Some(address) if !address.is_empty() => {
            // Wallet-authenticated: check subscription via aether-mind
            let check_url = format!(
                "{}/aether/auth/check?address={}",
                aether_url, address
            );
            match http_client.get(&check_url).send().await {
                Ok(resp) => {
                    if let Ok(data) = resp.json::<serde_json::Value>().await {
                        let has_sub = data["has_subscription"].as_bool().unwrap_or(false);
                        let balance = data["balance"].as_u64().unwrap_or(0);

                        if has_sub && balance > 0 {
                            // Deduct fee (best-effort, don't block on failure)
                            let deduct_url =
                                format!("{}/aether/auth/deduct", aether_url);
                            let _ = http_client
                                .post(&deduct_url)
                                .json(&json!({
                                    "address": address,
                                    "call_type": "chat"
                                }))
                                .send()
                                .await;
                        } else if !has_sub {
                            // No subscription — fall through to free tier by IP
                            let ip = extract_ip(&req).unwrap_or(IpAddr::from([127, 0, 0, 1]));
                            let mut t = tracker.lock().await;
                            if !t.check_and_increment(ip) {
                                warn!("Auth: free tier exhausted for {} (address: {})", ip, address);
                                return Err(StatusCode::PAYMENT_REQUIRED);
                            }
                        }
                    }
                }
                Err(e) => {
                    // Aether-mind unavailable — allow through (free tier)
                    warn!("Auth: aether-mind unreachable: {} — allowing free tier", e);
                }
            }

            Ok(next.run(req).await)
        }
        _ => {
            // No wallet: free tier by IP
            let ip = extract_ip(&req).unwrap_or(IpAddr::from([127, 0, 0, 1]));
            let mut t = tracker.lock().await;
            if !t.check_and_increment(ip) {
                warn!("Auth: free tier exhausted for IP {}", ip);
                return Err(StatusCode::PAYMENT_REQUIRED);
            }
            drop(t);

            Ok(next.run(req).await)
        }
    }
}
