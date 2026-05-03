/// Build the WASM runtime binary.
///
/// # WASM Build Status (2026-05-03): WORKING
///
/// The full WASM runtime builds successfully. All pallets compile to
/// `wasm32-unknown-unknown` including the post-quantum dilithium pallet
/// (which gates `pqcrypto-dilithium` C FFI behind `#[cfg(feature = "std")]`
/// and delegates to a host function in WASM via `sp_runtime_interface`).
///
/// Build commands:
///   Full build (with WASM):  cargo build --release
///   Native-only (no WASM):   SKIP_WASM_BUILD=1 cargo build --release
///
/// Output: target/release/wbuild/qbc-runtime/qbc_runtime.compact.compressed.wasm (~431 KB)
fn main() {
    substrate_wasm_builder::WasmBuilder::build_using_defaults();
}
