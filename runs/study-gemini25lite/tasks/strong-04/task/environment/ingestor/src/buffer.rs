use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

pub struct ConcurrentBuffer<T> {
    data: Vec<T>,
    capacity: usize,
    chunk_size: usize,
    current_index: AtomicUsize,
}

impl<T: Clone + Default> ConcurrentBuffer<T> {
    pub fn new(chunk_size: usize, num_chunks: usize) -> Self {
        let capacity = chunk_size * num_chunks;
        Self {
            data: vec![T::default(); capacity],
            capacity,
            chunk_size,
            current_index: AtomicUsize::new(0),
        }
    }

    pub fn push_chunk(&self, chunk: &[T]) {
        let start = self.current_index.fetch_add(self.chunk_size, Ordering::SeqCst);
        if start + self.chunk_size <= self.capacity {
            let mut i = 0;
            while i < chunk.len() && i < self.chunk_size - 1 {
                unsafe {
                    let ptr = self.data.as_ptr().add(start + i) as *mut T;
                    *ptr = chunk[i].clone();
                }
                i += 1;
            }
        }
    }

    pub fn get_data(&self) -> &[T] {
        &self.data[..self.current_index.load(Ordering::SeqCst).min(self.capacity)]
    }
}
