//! SQLite result storage.

use rusqlite::{Connection, params};
use std::path::Path;

use crate::stats::ResultRow;

/// Database handle for the results store.
pub struct ResultsDb {
    conn: Connection,
}

impl ResultsDb {
    /// Open (or create) the results database at the given path.
    pub fn open(path: &Path) -> rusqlite::Result<Self> {
        let conn = Connection::open(path)?;
        // Enable WAL mode for better concurrent write performance.
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")?;
        Ok(ResultsDb { conn })
    }

    /// Open an in-memory database (useful for testing).
    pub fn open_in_memory() -> rusqlite::Result<Self> {
        let conn = Connection::open_in_memory()?;
        Ok(ResultsDb { conn })
    }

    /// Create the results table if it does not exist, then clear it.
    pub fn init_schema(&mut self) -> rusqlite::Result<()> {
        self.conn.execute_batch("
            CREATE TABLE IF NOT EXISTS results (
                batch_id      INTEGER,
                sample_count  INTEGER,
                fixed_mean    INTEGER,
                fixed_variance INTEGER,
                checksum      INTEGER
            );
            DELETE FROM results;
        ")
    }

    /// Insert a single result row.
    pub fn insert_row(&mut self, row: &ResultRow) -> rusqlite::Result<()> {
        self.conn.execute(
            "INSERT INTO results (batch_id, sample_count, fixed_mean, fixed_variance, checksum) \
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                row.batch_id,
                row.sample_count,
                row.fixed_mean,
                row.fixed_variance,
                row.checksum,
            ],
        )?;
        Ok(())
    }

    /// Insert multiple rows in a single transaction.
    pub fn insert_rows(&mut self, rows: &[ResultRow]) -> rusqlite::Result<()> {
        let tx = self.conn.transaction()?;
        for row in rows {
            tx.execute(
                "INSERT INTO results (batch_id, sample_count, fixed_mean, fixed_variance, checksum) \
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                params![
                    row.batch_id,
                    row.sample_count,
                    row.fixed_mean,
                    row.fixed_variance,
                    row.checksum,
                ],
            )?;
        }
        tx.commit()
    }

    /// Query all rows ordered by batch_id.
    pub fn query_all(&mut self) -> rusqlite::Result<Vec<ResultRow>> {
        let mut stmt = self.conn.prepare(
            "SELECT batch_id, sample_count, fixed_mean, fixed_variance, checksum \
             FROM results ORDER BY batch_id",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(ResultRow {
                batch_id: row.get(0)?,
                sample_count: row.get(1)?,
                fixed_mean: row.get(2)?,
                fixed_variance: row.get(3)?,
                checksum: row.get(4)?,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }

    /// Return the number of rows in results.
    pub fn row_count(&mut self) -> rusqlite::Result<i64> {
        self.conn
            .query_row("SELECT COUNT(*) FROM results", [], |row| row.get(0))
    }

    /// Return a row for the given batch_id, or None.
    pub fn get_row(&mut self, batch_id: i64) -> rusqlite::Result<Option<ResultRow>> {
        let mut stmt = self.conn.prepare(
            "SELECT batch_id, sample_count, fixed_mean, fixed_variance, checksum \
             FROM results WHERE batch_id = ?1",
        )?;
        let mut rows = stmt.query_map([batch_id], |row| {
            Ok(ResultRow {
                batch_id: row.get(0)?,
                sample_count: row.get(1)?,
                fixed_mean: row.get(2)?,
                fixed_variance: row.get(3)?,
                checksum: row.get(4)?,
            })
        })?;
        match rows.next() {
            Some(r) => Ok(Some(r?)),
            None => Ok(None),
        }
    }

    /// Delete all rows.
    pub fn clear(&mut self) -> rusqlite::Result<()> {
        self.conn.execute("DELETE FROM results", [])?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_row(batch_id: i64) -> ResultRow {
        ResultRow {
            batch_id,
            sample_count: 100,
            fixed_mean: 32768,
            fixed_variance: 65536,
            checksum: 0xDEADBEEF_u32 as i64,
        }
    }

    #[test]
    fn insert_and_query() {
        let mut db = ResultsDb::open_in_memory().unwrap();
        db.init_schema().unwrap();
        let row = sample_row(1);
        db.insert_row(&row).unwrap();
        let all = db.query_all().unwrap();
        assert_eq!(all.len(), 1);
        assert_eq!(all[0].batch_id, 1);
        assert_eq!(all[0].fixed_mean, 32768);
    }

    #[test]
    fn insert_multiple_rows() {
        let mut db = ResultsDb::open_in_memory().unwrap();
        db.init_schema().unwrap();
        let rows = vec![sample_row(1), sample_row(2), sample_row(3)];
        db.insert_rows(&rows).unwrap();
        assert_eq!(db.row_count().unwrap(), 3);
    }

    #[test]
    fn get_row_by_id() {
        let mut db = ResultsDb::open_in_memory().unwrap();
        db.init_schema().unwrap();
        db.insert_row(&sample_row(42)).unwrap();
        let r = db.get_row(42).unwrap();
        assert!(r.is_some());
        assert_eq!(r.unwrap().batch_id, 42);
        let missing = db.get_row(99).unwrap();
        assert!(missing.is_none());
    }

    #[test]
    fn clear_removes_all_rows() {
        let mut db = ResultsDb::open_in_memory().unwrap();
        db.init_schema().unwrap();
        db.insert_row(&sample_row(1)).unwrap();
        db.clear().unwrap();
        assert_eq!(db.row_count().unwrap(), 0);
    }
}
