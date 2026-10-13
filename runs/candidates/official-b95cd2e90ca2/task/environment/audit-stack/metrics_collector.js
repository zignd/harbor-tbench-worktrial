'use strict';
// Metrics Collector - samples synthetic DB query latency metrics.
// In production this would attach to a real DB client; here it generates
// realistic-looking latency distributions for testing.

const QUERY_TYPES = [
  'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT', 'ROLLBACK',
];

const TABLE_NAMES = [
  'users', 'sessions', 'audit_events', 'api_keys', 'permissions',
  'organizations', 'billing_records', 'notification_queue',
];

const ENDPOINTS = [
  '/api/v2/users', '/api/v2/sessions', '/api/v2/audit',
  '/api/v2/billing', '/internal/healthcheck', '/api/v2/permissions',
];

/**
 * Seeded pseudo-random number generator (LCG) for deterministic metric generation.
 */
class SeededRNG {
  constructor(seed) {
    this.state = seed >>> 0;
  }

  next() {
    // LCG parameters (Numerical Recipes)
    this.state = (Math.imul(1664525, this.state) + 1013904223) >>> 0;
    return this.state / 0x100000000;
  }

  nextInt(min, max) {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  choice(arr) {
    return arr[this.nextInt(0, arr.length - 1)];
  }
}

/**
 * Generate a single synthetic DB query latency metric record.
 *
 * @param {number} seqNum - Sequence number for determinism
 * @param {number} baseLatencyMs - Base latency from config
 * @param {number} timestamp - Timestamp for the record (ms)
 * @returns {object} Metric record
 */
function sampleMetric(seqNum, baseLatencyMs, timestamp) {
  const rng = new SeededRNG(seqNum * 0x9e3779b9);

  const queryType = rng.choice(QUERY_TYPES);
  const table = rng.choice(TABLE_NAMES);
  const endpoint = rng.choice(ENDPOINTS);

  // Simulate latency with occasional spikes
  const base = baseLatencyMs + rng.next() * baseLatencyMs * 2;
  const spike = rng.next() < 0.05 ? rng.next() * 500 : 0;
  const latencyMs = Math.trunc(base + spike) + 1;

  const rowsAffected = queryType === 'SELECT'
    ? rng.nextInt(0, 1000)
    : rng.nextInt(0, 10);

  return {
    seq: seqNum,
    ts: timestamp,
    queryType,
    table,
    endpoint,
    latencyMs,
    rowsAffected,
    dbHost: 'db-primary-01.internal',
    connectionPool: `pool-${rng.nextInt(0, 7)}`,
    cached: rng.next() < 0.3,
  };
}

/**
 * Generate a batch of metric records.
 *
 * @param {number} count - Number of records to generate
 * @param {number} startSeq - Starting sequence number
 * @param {number} baseLatencyMs - Base latency from config
 * @param {number} startTimestamp - Starting timestamp (ms)
 * @param {number} intervalMs - Interval between records (ms)
 * @returns {Array} Array of metric records
 */
function generateBatch(count, startSeq, baseLatencyMs, startTimestamp, intervalMs) {
  const records = [];
  for (let i = 0; i < count; i++) {
    const ts = startTimestamp + i * intervalMs;
    records.push(sampleMetric(startSeq + i, baseLatencyMs, ts));
  }
  return records;
}

module.exports = { sampleMetric, generateBatch, SeededRNG };
