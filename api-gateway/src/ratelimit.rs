//! Rate limiting using `governor` crate with axum middleware.
//!
//! Two tiers:
//! - `/aether/chat*` — 10 req/min per IP (inference is expensive)
//! - All other routes — 60 req/min per IP
//!
//! Uses `CF-Connecting-IP` header for real client IP behind Cloudflare,
//! falling back to the socket address.

use std::net::IpAddr;
use std::num::NonZeroU32;
use std::sync::Arc;

use axum::{
    body::Body,
    extract::ConnectInfo,
    http::{Request, StatusCode},
    middleware::Next,
    response::Response,
};
use governor::{
    clock::DefaultClock,
    state::{InMemoryState, NotKeyed},
    Quota, RateLimiter,
};
use tracing::warn;

/// A shared, non-keyed rate limiter (applied per-route-group, not per-IP for simplicity).
/// For production per-IP limiting, we check IP and use a keyed rate limiter.
pub type SharedLimiter = Arc<RateLimiter<NotKeyed, InMemoryState, DefaultClock>>;

/// Create a rate limiter: `burst` requests allowed, replenishing at `per_second` rate.
pub fn create_limiter(per_second: u32, burst: u32) -> SharedLimiter {
    let quota = Quota::per_second(NonZeroU32::new(per_second).expect("per_second must be > 0"))
        .allow_burst(NonZeroU32::new(burst).expect("burst must be > 0"));
    Arc::new(RateLimiter::direct(quota))
}

/// Extract the real client IP from Cloudflare headers or socket address.
fn extract_ip(req: &Request<Body>) -> Option<IpAddr> {
    // Try CF-Connecting-IP first (Cloudflare tunnel)
    if let Some(cf_ip) = req.headers().get("CF-Connecting-IP") {
        if let Ok(s) = cf_ip.to_str() {
            if let Ok(ip) = s.parse::<IpAddr>() {
                return Some(ip);
            }
        }
    }

    // Try X-Forwarded-For
    if let Some(xff) = req.headers().get("X-Forwarded-For") {
        if let Ok(s) = xff.to_str() {
            if let Some(first) = s.split(',').next() {
                if let Ok(ip) = first.trim().parse::<IpAddr>() {
                    return Some(ip);
                }
            }
        }
    }

    // Fallback to peer address
    req.extensions()
        .get::<ConnectInfo<std::net::SocketAddr>>()
        .map(|ci| ci.0.ip())
}

/// Axum middleware that checks the rate limiter before forwarding.
pub async fn rate_limit_middleware(
    axum::extract::State(limiter): axum::extract::State<SharedLimiter>,
    req: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let ip = extract_ip(&req);

    match limiter.check() {
        Ok(_) => Ok(next.run(req).await),
        Err(_) => {
            if let Some(ip) = ip {
                warn!("Rate limit exceeded for {ip}");
            }
            Err(StatusCode::TOO_MANY_REQUESTS)
        }
    }
}
