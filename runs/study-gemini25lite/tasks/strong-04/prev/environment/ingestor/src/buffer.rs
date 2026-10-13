use std::sync::atomic::{AtomicUsize, Ordering};

pub struct ChunkedCollector {
    chunks: Vec<std::sync::Mutex<Vec<(String, f32)>>>,
    current_chunk: AtomicUsize,
    chunk_size: usize,
}

impl ChunkedCollector {
    pub fn new(num_chunks: usize, chunk_size: usize) -> Self {
        let mut chunks = Vec::new();
        for _ in 0..num_chunks {
            chunks.push(std::sync::Mutex::new(Vec::with_capacity(chunk_size)));
        }
        Self {
            chunks,
            current_chunk: AtomicUsize::new(0),
            chunk_size,
        }
    }

    pub fn add_record(&self, region: String, value: f32) {
        let mut idx = self.current_chunk.load(Ordering::Acquire);
        loop {
            let mut chunk = self.chunks[idx].lock().unwrap();
            if chunk.len() < self.chunk_size - 1 { // BUG 1: off-by-one, drops the last record of every chunk
                chunk.push((region, value));
                return;
            } else {
                // Try next chunk
                let next = (idx + 1) % self.chunks.len();
                self.current_chunk.compare_exchange(idx, next, Ordering::SeqCst, Ordering::Relaxed).ok();
                idx = next;
            }
        }
    }
    
    pub fn get_all_records(self) -> Vec<(String, f32)> {
        self.chunks.into_iter().map(|m| m.into_inner().unwrap()).flatten().collect()
    }
}
