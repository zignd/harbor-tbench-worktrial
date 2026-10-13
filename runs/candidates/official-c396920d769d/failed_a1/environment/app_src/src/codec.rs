//! Binary batch codec.
//!
//! The input format is a sequence of batches. Each batch starts with
//! an 8-byte header followed by sample data.
//!
//! Header layout (little-endian):
//!   bytes 0-3: batch_id  (i32)
//!   bytes 4-7: sample_count (i32)
//!
//! Sample layout:
//!   4 bytes per sample, i32 little-endian
//!
//! Batches are concatenated with no padding or separator.

use std::fs::File;
use std::io::{self, BufReader, Read};
use std::path::Path;

/// A decoded batch of sensor samples.
#[derive(Debug, Clone)]
pub struct Batch {
    pub batch_id: i64,
    pub samples: Vec<i32>,
}

impl Batch {
    /// Returns the number of samples in this batch.
    pub fn len(&self) -> usize {
        self.samples.len()
    }

    /// Returns true if the batch has no samples.
    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    /// Returns the batch ID.
    pub fn id(&self) -> i64 {
        self.batch_id
    }

    /// Iterate over samples.
    pub fn iter(&self) -> impl Iterator<Item = &i32> {
        self.samples.iter()
    }
}

/// Streaming reader over a binary batch file.
pub struct BatchReader {
    inner: BufReader<File>,
    position: u64,
    exhausted: bool,
}

impl BatchReader {
    /// Open a batch file for reading.
    pub fn open(path: &Path) -> io::Result<Self> {
        let file = File::open(path)?;
        Ok(BatchReader {
            inner: BufReader::with_capacity(1 << 20, file),
            position: 0,
            exhausted: false,
        })
    }

    /// Read the next batch header. Returns None on clean EOF.
    fn read_header(&mut self) -> io::Result<Option<(i64, usize)>> {
        let mut header = [0u8; 8];
        match self.inner.read_exact(&mut header) {
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => {
                return Ok(None);
            }
            Err(e) => return Err(e),
        }
        self.position += 8;
        let batch_id = i32::from_le_bytes([header[0], header[1], header[2], header[3]]) as i64;
        let count = i32::from_le_bytes([header[4], header[5], header[6], header[7]]);
        if count < 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("negative sample count {} at byte offset {}", count, self.position - 8),
            ));
        }
        Ok(Some((batch_id, count as usize)))
    }

    /// Read exactly `count` i32 samples.
    fn read_samples(&mut self, count: usize) -> io::Result<Vec<i32>> {
        let mut samples = Vec::with_capacity(count);
        let mut buf = [0u8; 4];
        for i in 0..count {
            match self.inner.read_exact(&mut buf) {
                Ok(_) => {}
                Err(e) => {
                    return Err(io::Error::new(
                        e.kind(),
                        format!("truncated batch at sample {}: {}", i, e),
                    ));
                }
            }
            self.position += 4;
            samples.push(i32::from_le_bytes(buf));
        }
        Ok(samples)
    }

    /// Try to read the next batch. Returns Ok(None) on clean EOF.
    pub fn next_batch(&mut self) -> io::Result<Option<Batch>> {
        if self.exhausted {
            return Ok(None);
        }
        match self.read_header()? {
            None => {
                self.exhausted = true;
                Ok(None)
            }
            Some((batch_id, count)) => {
                let samples = self.read_samples(count)?;
                Ok(Some(Batch { batch_id, samples }))
            }
        }
    }

    /// Current byte position in the file.
    pub fn position(&self) -> u64 {
        self.position
    }
}

impl Iterator for BatchReader {
    type Item = io::Result<Batch>;

    fn next(&mut self) -> Option<Self::Item> {
        match self.next_batch() {
            Ok(Some(b)) => Some(Ok(b)),
            Ok(None) => None,
            Err(e) => Some(Err(e)),
        }
    }
}

/// Write a sequence of batches to a binary file.
pub fn write_batches(path: &Path, batches: &[Batch]) -> io::Result<()> {
    use std::io::Write;
    let mut file = std::io::BufWriter::new(File::create(path)?);
    for batch in batches {
        let batch_id = batch.batch_id as i32;
        let count = batch.samples.len() as i32;
        file.write_all(&batch_id.to_le_bytes())?;
        file.write_all(&count.to_le_bytes())?;
        for &s in &batch.samples {
            file.write_all(&s.to_le_bytes())?;
        }
    }
    file.flush()?;
    Ok(())
}

/// Parse all batches from a byte slice (useful for testing).
pub fn parse_bytes(data: &[u8]) -> io::Result<Vec<Batch>> {
    use std::io::Cursor;
    let mut reader = BufReader::new(Cursor::new(data));
    let mut batches = Vec::new();
    loop {
        let mut header = [0u8; 8];
        match reader.read_exact(&mut header) {
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => break,
            Err(e) => return Err(e),
        }
        let batch_id = i32::from_le_bytes([header[0], header[1], header[2], header[3]]) as i64;
        let count = i32::from_le_bytes([header[4], header[5], header[6], header[7]]);
        if count < 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "negative count"));
        }
        let mut samples = Vec::with_capacity(count as usize);
        for _ in 0..count {
            let mut buf = [0u8; 4];
            reader.read_exact(&mut buf)?;
            samples.push(i32::from_le_bytes(buf));
        }
        batches.push(Batch { batch_id, samples });
    }
    Ok(batches)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_batch_bytes(batch_id: i32, samples: &[i32]) -> Vec<u8> {
        let mut v = Vec::new();
        v.extend_from_slice(&batch_id.to_le_bytes());
        v.extend_from_slice(&(samples.len() as i32).to_le_bytes());
        for &s in samples {
            v.extend_from_slice(&s.to_le_bytes());
        }
        v
    }

    #[test]
    fn round_trip_single_batch() {
        let samples: Vec<i32> = (0..100).collect();
        let data = make_batch_bytes(42, &samples);
        let batches = parse_bytes(&data).unwrap();
        assert_eq!(batches.len(), 1);
        assert_eq!(batches[0].batch_id, 42);
        assert_eq!(batches[0].samples, samples);
    }

    #[test]
    fn round_trip_multiple_batches() {
        let mut data = Vec::new();
        data.extend(make_batch_bytes(1, &[10, 20, 30]));
        data.extend(make_batch_bytes(2, &[-5, 0, 5]));
        let batches = parse_bytes(&data).unwrap();
        assert_eq!(batches.len(), 2);
        assert_eq!(batches[0].batch_id, 1);
        assert_eq!(batches[1].batch_id, 2);
    }

    #[test]
    fn empty_input() {
        let batches = parse_bytes(&[]).unwrap();
        assert_eq!(batches.len(), 0);
    }
}
