fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("../../rust-p2p/proto/p2p_service.proto")?;
    Ok(())
}
