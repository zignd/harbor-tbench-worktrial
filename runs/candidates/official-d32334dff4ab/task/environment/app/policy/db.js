'use strict';

/**
 * db.js - SQLite persistence layer for eval_records.
 *
 * Schema:
 *   eval_records(
 *     id       INTEGER PRIMARY KEY AUTOINCREMENT,
 *     user_id  TEXT    NOT NULL,
 *     ts       INTEGER NOT NULL,
 *     cpu_ms   REAL    NOT NULL,
 *     accepted INTEGER NOT NULL DEFAULT 1
 *   )
 *
 * Uses better-sqlite3 for synchronous SQLite access from the Node.js
 * event loop. The database file is created at /app/data/records.db.
 */

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DEFAULT_DB_PATH = '/app/data/records.db';

class DB {
  constructor(dbPath) {
    this.dbPath = dbPath || DEFAULT_DB_PATH;
    this.db = null;
    this._insertStmt = null;
    this._sumStmt = null;
    this._windowStmt = null;
    this._allRecordsStmt = null;
  }

  async init() {
    // Ensure data directory exists
    fs.mkdirSync(path.dirname(this.dbPath), { recursive: true });

    this.db = new Database(this.dbPath);

    // Apply recommended pragmas for correctness
    this.db.pragma('journal_mode = DELETE');
    this.db.pragma('synchronous = FULL');
    this.db.pragma('foreign_keys = ON');

    // Create schema
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS eval_records (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  TEXT    NOT NULL,
        ts       INTEGER NOT NULL,
        cpu_ms   REAL    NOT NULL,
        accepted INTEGER NOT NULL DEFAULT 1
      );
      CREATE INDEX IF NOT EXISTS idx_user_ts ON eval_records(user_id, ts);
    `);

    // Prepare reusable statements
    this._insertStmt = this.db.prepare(
      'INSERT INTO eval_records (user_id, ts, cpu_ms, accepted) VALUES (?, ?, ?, ?)'
    );
    this._sumStmt = this.db.prepare(
      'SELECT COALESCE(SUM(cpu_ms), 0) AS total FROM eval_records WHERE user_id = ? AND accepted = 1'
    );
    this._countStmt = this.db.prepare(
      'SELECT COUNT(*) AS cnt FROM eval_records WHERE user_id = ? AND accepted = 1'
    );
    this._windowStmt = this.db.prepare(
      'SELECT COALESCE(SUM(cpu_ms), 0) AS total FROM eval_records WHERE user_id = ? AND ts >= ? AND accepted = 1'
    );
    this._allRecordsStmt = this.db.prepare(
      'SELECT id, user_id, ts, cpu_ms, accepted FROM eval_records WHERE user_id = ? AND accepted = 1 ORDER BY ts ASC'
    );

    console.log(`[db] connected to ${this.dbPath}`);
  }

  /**
   * Insert one eval record.
   */
  record(user_id, ts, cpu_ms, accepted) {
    this._insertStmt.run(user_id, ts, cpu_ms, accepted ? 1 : 0);
    return Promise.resolve();
  }

  /**
   * Return the sum of accepted cpu_ms for a user across all time.
   */
  totalCpuMs(user_id) {
    const row = this._sumStmt.get(user_id);
    return row ? row.total : 0;
  }

  /**
   * Return the count of accepted requests for a user.
   */
  requestCount(user_id) {
    const row = this._countStmt.get(user_id);
    return row ? row.cnt : 0;
  }

  /**
   * Return sum of cpu_ms for a user within a rolling window starting at `since` (ms epoch).
   */
  windowTotal(user_id, since) {
    const row = this._windowStmt.get(user_id, since);
    return row ? row.total : 0;
  }

  /**
   * Return all accepted records for a user.
   */
  getRecords(user_id) {
    return this._allRecordsStmt.all(user_id);
  }

  async close() {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }
}

module.exports = { DB };
