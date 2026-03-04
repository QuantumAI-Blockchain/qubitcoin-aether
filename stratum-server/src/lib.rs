pub mod config;
pub mod worker;
pub mod protocol;
pub mod pool;
pub mod bridge;

pub mod stratum_proto {
    tonic::include_proto!("stratum");
}
