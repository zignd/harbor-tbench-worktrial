use std::collections::HashMap;

pub struct Aggregator {
    sums: HashMap<String, f32>,
}

impl Aggregator {
    pub fn new() -> Self {
        Self { sums: HashMap::new() }
    }

    pub fn add(&mut self, region: String, value: f32) {
        let entry = self.sums.entry(region).or_insert(0.0);
        *entry += value;
    }

    pub fn get_results(&self) -> HashMap<String, f32> {
        self.sums.clone()
    }
}
