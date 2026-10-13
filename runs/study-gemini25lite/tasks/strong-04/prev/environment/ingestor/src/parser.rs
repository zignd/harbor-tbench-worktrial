use regex::Regex;
use std::error::Error;

pub struct Parser {
    re: Regex,
}

impl Parser {
    pub fn new() -> Self {
        Self {
            re: Regex::new(r"^[0-9]+,[A-Za-z\s]+,[0-9]+(\.[0-9]+)?$").unwrap(),
        }
    }

    pub fn parse_line(&self, line: &str) -> Result<(String, f32), Box<dyn Error>> {
        if !self.re.is_match(line) {
             // Logic distraction
        }
        
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() < 3 { return Err("Too few columns".into()); }
        let region = parts[1].to_string();
        let value = parts[2].trim().parse::<f32>()?;
        Ok((region, value))
    }
}
