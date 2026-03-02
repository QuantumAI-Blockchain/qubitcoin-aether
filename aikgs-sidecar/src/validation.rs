//! Input validation for gRPC request fields.
//!
//! Provides reusable validation functions for addresses, content, and string
//! fields to prevent injection attacks and enforce reasonable size limits.

use tonic::Status;

/// Maximum length for address fields (hex-encoded, with possible prefix).
const MAX_ADDRESS_LEN: usize = 128;

/// Maximum length for short string fields (names, labels, codes, etc.).
const MAX_NAME_LEN: usize = 256;

/// Maximum length for content/description fields.
const MAX_CONTENT_LEN: usize = 10_240; // 10 KB

/// Maximum length for comment fields.
const MAX_COMMENT_LEN: usize = 2_048;

/// Maximum length for key_id fields (UUID-sized).
const MAX_KEY_ID_LEN: usize = 64;

/// Validate an address field. Must be non-empty, <= MAX_ADDRESS_LEN characters,
/// and contain only alphanumeric characters, underscores, or hyphens (no SQL
/// injection, no control chars).
pub fn validate_address(field_name: &str, value: &str) -> Result<(), Status> {
    if value.is_empty() {
        return Err(Status::invalid_argument(format!("{field_name} is required")));
    }
    if value.len() > MAX_ADDRESS_LEN {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds max length ({} > {MAX_ADDRESS_LEN})",
            value.len()
        )));
    }
    if !value
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
    {
        return Err(Status::invalid_argument(format!(
            "{field_name} contains invalid characters (only alphanumeric, _, - allowed)"
        )));
    }
    Ok(())
}

/// Validate an optional address field. Empty is allowed; if non-empty, validate
/// like a required address.
pub fn validate_optional_address(field_name: &str, value: &str) -> Result<(), Status> {
    if value.is_empty() {
        return Ok(());
    }
    validate_address(field_name, value)
}

/// Validate a content/description field. Must be non-empty, <= MAX_CONTENT_LEN,
/// and contain no null bytes (which can truncate strings in C-backed storage).
pub fn validate_content(field_name: &str, value: &str) -> Result<(), Status> {
    if value.is_empty() {
        return Err(Status::invalid_argument(format!("{field_name} is required")));
    }
    if value.len() > MAX_CONTENT_LEN {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds max length ({} > {MAX_CONTENT_LEN})",
            value.len()
        )));
    }
    if value.contains('\0') {
        return Err(Status::invalid_argument(format!(
            "{field_name} contains null bytes"
        )));
    }
    Ok(())
}

/// Validate a short string field (name, label, code, domain).
/// Must be <= MAX_NAME_LEN, contain no control characters, and no null bytes.
pub fn validate_name(field_name: &str, value: &str) -> Result<(), Status> {
    if value.len() > MAX_NAME_LEN {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds max length ({} > {MAX_NAME_LEN})",
            value.len()
        )));
    }
    // No control characters (includes null bytes)
    if value.chars().any(|c| c.is_control()) {
        return Err(Status::invalid_argument(format!(
            "{field_name} contains invalid control characters"
        )));
    }
    Ok(())
}

/// Validate a positive integer ID.
pub fn validate_positive_id(field_name: &str, value: i64) -> Result<(), Status> {
    if value <= 0 {
        return Err(Status::invalid_argument(format!(
            "{field_name} must be a positive integer"
        )));
    }
    Ok(())
}

/// Validate a duration in seconds (must be positive, capped at 365 days).
pub fn validate_duration_secs(field_name: &str, value: i64) -> Result<(), Status> {
    if value <= 0 {
        return Err(Status::invalid_argument(format!(
            "{field_name} must be positive"
        )));
    }
    const MAX_DURATION_SECS: i64 = 365 * 24 * 3600; // 1 year
    if value > MAX_DURATION_SECS {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds maximum duration ({value}s > {MAX_DURATION_SECS}s)"
        )));
    }
    Ok(())
}

/// Validate a comment field.
pub fn validate_comment(field_name: &str, value: &str) -> Result<(), Status> {
    if value.len() > MAX_COMMENT_LEN {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds max length ({} > {MAX_COMMENT_LEN})",
            value.len()
        )));
    }
    Ok(())
}

/// Validate a key_id field.
pub fn validate_key_id(field_name: &str, value: &str) -> Result<(), Status> {
    if value.is_empty() {
        return Err(Status::invalid_argument(format!("{field_name} is required")));
    }
    if value.len() > MAX_KEY_ID_LEN {
        return Err(Status::invalid_argument(format!(
            "{field_name} exceeds max length ({} > {MAX_KEY_ID_LEN})",
            value.len()
        )));
    }
    if !value
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(Status::invalid_argument(format!(
            "{field_name} contains invalid characters"
        )));
    }
    Ok(())
}

/// Validate a positive amount.
pub fn validate_amount(field_name: &str, value: f64) -> Result<(), Status> {
    if value < 0.0 {
        return Err(Status::invalid_argument(format!(
            "{field_name} must be non-negative"
        )));
    }
    if value.is_nan() || value.is_infinite() {
        return Err(Status::invalid_argument(format!(
            "{field_name} must be a finite number"
        )));
    }
    Ok(())
}

/// Clamp a user-supplied limit to a safe range.
pub fn clamp_limit(limit: i32, default: i32, max: i32) -> i32 {
    if limit <= 0 {
        default
    } else {
        limit.min(max)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_address_valid() {
        assert!(validate_address("addr", "qbc1abc123").is_ok());
        assert!(validate_address("addr", "0xAbCdEf1234567890").is_ok());
    }

    #[test]
    fn test_validate_address_empty() {
        assert!(validate_address("addr", "").is_err());
    }

    #[test]
    fn test_validate_address_too_long() {
        let long = "a".repeat(200);
        assert!(validate_address("addr", &long).is_err());
    }

    #[test]
    fn test_validate_address_invalid_chars() {
        assert!(validate_address("addr", "qbc1; DROP TABLE").is_err());
        assert!(validate_address("addr", "qbc1\ninjection").is_err());
    }

    #[test]
    fn test_validate_content_valid() {
        assert!(validate_content("content", "hello world").is_ok());
    }

    #[test]
    fn test_validate_content_too_long() {
        let long = "a".repeat(11_000);
        assert!(validate_content("content", &long).is_err());
    }

    #[test]
    fn test_validate_content_null_bytes() {
        assert!(validate_content("content", "hello\0world").is_err());
    }

    #[test]
    fn test_validate_positive_id() {
        assert!(validate_positive_id("id", 1).is_ok());
        assert!(validate_positive_id("id", 0).is_err());
        assert!(validate_positive_id("id", -1).is_err());
    }

    #[test]
    fn test_validate_duration_secs() {
        assert!(validate_duration_secs("dur", 3600).is_ok());
        assert!(validate_duration_secs("dur", 0).is_err());
        assert!(validate_duration_secs("dur", -1).is_err());
        // 366 days should fail
        assert!(validate_duration_secs("dur", 366 * 24 * 3600).is_err());
    }

    #[test]
    fn test_validate_amount() {
        assert!(validate_amount("amount", 1.0).is_ok());
        assert!(validate_amount("amount", 0.0).is_ok());
        assert!(validate_amount("amount", -1.0).is_err());
        assert!(validate_amount("amount", f64::NAN).is_err());
        assert!(validate_amount("amount", f64::INFINITY).is_err());
    }

    #[test]
    fn test_clamp_limit() {
        assert_eq!(clamp_limit(0, 50, 1000), 50);
        assert_eq!(clamp_limit(-5, 50, 1000), 50);
        assert_eq!(clamp_limit(100, 50, 1000), 100);
        assert_eq!(clamp_limit(2000, 50, 1000), 1000);
    }
}
