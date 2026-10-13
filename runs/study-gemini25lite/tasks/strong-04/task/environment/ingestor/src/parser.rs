use regex::Regex;
use std::sync::OnceLock;

static REGION_REGEX: OnceLock<Regex> = OnceLock::new();

pub fn validate_region(region: &str) -> bool {
    let re = REGION_REGEX.get_or_init(|| Regex::new(r"^[a-zA-Z\s]+$").unwrap());
    re.is_match(region)
}

pub fn parse_line(line: &str) -> Option<(String, f32)> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() != 2 { return None; }
    let region = parts[0].trim();
    if !validate_region(region) { return None; }
    let value = parts[1].trim().parse::<f32>().ok()?;
    Some((region.to_string(), value))
}
