pub mod bloom;
pub mod finality;

use pyo3::prelude::*;

#[pymodule]
fn security_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    pyo3_log::init();
    m.add_class::<bloom::BloomFilter>()?;
    m.add_class::<finality::FinalityCore>()?;
    Ok(())
}
