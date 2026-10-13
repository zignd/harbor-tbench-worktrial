'use strict';

/**
 * seed.js - Pre-populate /app/data/records.db with 48 hours of
 * historical eval records for 20 synthetic users.
 * Runs once at container start before the HTTP service launches.
 */

const Database = require('/app/policy/node_modules/better-sqlite3');
const fs = require('fs');
const path = require('path');

const DB_PATH = '/app/data/records.db';
const USERS = 20;
const HOURS = 48;
const RECORDS_PER_USER_PER_HOUR = 8;

fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = DELETE');
db.pragma('synchronous = FULL');

db.exec(`
  CREATE TABLE IF NOT EXISTS eval_records (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  TEXT    NOT NULL,
    ts       INTEGER NOT NULL,
    cpu_ms   REAL    NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 1
  );
  CREATE INDEX IF NOT EXISTS idx_user_ts ON eval_records(user_id, ts);
`);

const insert = db.prepare(
  'INSERT INTO eval_records (user_id, ts, cpu_ms, accepted) VALUES (?, ?, ?, ?)'
);

const now = Date.now();
const TWO_DAYS_AGO = now - HOURS * 3600 * 1000;

const seed = db.transaction(() => {
  for (let u = 1; u <= USERS; u++) {
    const userId = `hist_user_${u}`;
    for (let h = 0; h < HOURS; h++) {
      for (let r = 0; r < RECORDS_PER_USER_PER_HOUR; r++) {
        const ts = TWO_DAYS_AGO + h * 3600_000 + r * (3600_000 / RECORDS_PER_USER_PER_HOUR);
        // Spread cpu_ms so no single window exceeds 400 ms
        const cpu_ms = 10 + Math.random() * 30;
        insert.run(userId, Math.floor(ts), parseFloat(cpu_ms.toFixed(3)), 1);
      }
    }
  }
});

seed();
db.close();

console.log(`[seed] seeded ${USERS} users x ${HOURS} hours x ${RECORDS_PER_USER_PER_HOUR} records`);
