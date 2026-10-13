use std::collections::HashMap;

pub fn aggregate(records: Vec<(String, f32)>) -> HashMap<String, f32> {
    let mut totals = HashMap::new();
    for (region, value) in records {
        // BUG 3: Using f32 for accumulation leads to precision loss on large datasets
        let count = totals.entry(region).or_insert(0.0f32);
        *count += value;
    }
    totals
}
