#!/usr/bin/env node
'use strict';

/**
 * Deterministic NDJSON corpus generator.
 * Produces a mix of valid and invalid log records using a seeded PRNG.
 *
 * Usage:
 *   node gen_corpus.js --size <n> --seed <s> --output <file>
 *   node gen_corpus.js --size <n> --seed <s>  (writes to stdout)
 */

const fs = require('fs');
const path = require('path');

function makePrng(seed) {
  let s = seed >>> 0;
  return function () {
    s += 0x6d2b79f5;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const LEVELS = ['debug', 'info', 'warn', 'error'];
const SEVERITIES = ['low', 'medium', 'high', 'critical'];
const SERVICES = [
  'api-gateway', 'auth-service', 'billing-service', 'cache-service',
  'data-pipeline', 'event-bus', 'file-storage', 'health-checker',
  'identity-service', 'job-scheduler', 'kafka-consumer', 'load-balancer',
  'metrics-collector', 'notification-service', 'order-processor',
  'payment-gateway', 'query-engine', 'redis-proxy', 'search-service',
  'trace-collector',
];
const MESSAGES = [
  'Request completed successfully',
  'Connection pool exhausted',
  'Cache miss for key',
  'Retry attempt exceeded',
  'Health check passed',
  'Database query slow',
  'Authentication token expired',
  'Rate limit triggered',
  'Circuit breaker opened',
  'Batch job completed',
  'Disk usage threshold reached',
  'Memory pressure detected',
  'Event published to queue',
  'Subscription acknowledged',
  'Config reload triggered',
];

function pad2(n) { return String(n).padStart(2, '0'); }
function pad3(n) { return String(n).padStart(3, '0'); }

// Bad timestamps that structurally fail the ISO8601 regex pattern
const BAD_TIMESTAMPS = [
  '2024/01/15 12:30:00',
  'January 15 2024',
  '1705320600',
  'not-a-timestamp',
  '2024-01-15',
  '12:30:00Z',
  '2024-01-15 12:30:00',
  '20240115T123000Z',
  'Thu Jan 15 2024',
  '2024-01-15T12:30',
];

function makeTimestamp(rng, valid) {
  if (!valid) {
    return BAD_TIMESTAMPS[Math.floor(rng() * BAD_TIMESTAMPS.length)];
  }
  const year = 2024;
  const month = 1 + Math.floor(rng() * 12);
  const day = 1 + Math.floor(rng() * 28);
  const hour = Math.floor(rng() * 24);
  const min = Math.floor(rng() * 60);
  const sec = Math.floor(rng() * 60);
  const ms = Math.floor(rng() * 1000);
  const tzChoice = Math.floor(rng() * 3);
  let tz;
  if (tzChoice === 0) {
    tz = 'Z';
  } else if (tzChoice === 1) {
    const off = Math.floor(rng() * 12);
    tz = '+' + pad2(off) + ':00';
  } else {
    const off = Math.floor(rng() * 6);
    tz = '-' + pad2(off) + ':00';
  }
  return `${year}-${pad2(month)}-${pad2(day)}T${pad2(hour)}:${pad2(min)}:${pad2(sec)}.${pad3(ms)}${tz}`;
}

/**
 * Generate a single record.
 * faultType:
 *   0 = valid
 *   1 = severity null
 *   2 = severity integer
 *   3 = missing level
 *   4 = bad timestamp (structurally invalid)
 *   5 = missing service
 *   6 = missing message
 *   7 = missing timestamp
 */
function makeRecord(rng, faultType) {
  const level = LEVELS[Math.floor(rng() * LEVELS.length)];
  const severity = SEVERITIES[Math.floor(rng() * SEVERITIES.length)];
  const service = SERVICES[Math.floor(rng() * SERVICES.length)];
  const message = MESSAGES[Math.floor(rng() * MESSAGES.length)] +
    ' [' + Math.floor(rng() * 100000) + ']';
  const ts = makeTimestamp(rng, faultType !== 4 && faultType !== 7);

  switch (faultType) {
    case 0: {
      const rec = { timestamp: ts, level, severity, service, message };
      if (rng() < 0.3) {
        rec.metadata = { requestId: 'req-' + Math.floor(rng() * 1e9), latencyMs: Math.floor(rng() * 5000) };
      }
      return rec;
    }
    case 1:
      return { timestamp: ts, level, severity: null, service, message };
    case 2:
      return { timestamp: ts, level, severity: Math.floor(rng() * 10), service, message };
    case 3:
      return { timestamp: ts, severity, service, message };
    case 4:
      return { timestamp: ts, level, severity, service, message };
    case 5:
      return { timestamp: ts, level, severity, message };
    case 6:
      return { timestamp: ts, level, severity, service };
    case 7:
      return { level, severity, service, message };
    default:
      return { timestamp: ts, level, severity, service, message };
  }
}

function chooseFaultType(rng) {
  const r = rng();
  if (r < 0.80) return 0;
  if (r < 0.84) return 1;
  if (r < 0.88) return 2;
  if (r < 0.92) return 3;
  if (r < 0.96) return 4;
  return 5 + Math.floor(rng() * 3);
}

function generateCorpus(size, seed, writeLine) {
  const rng = makePrng(seed);
  let validCount = 0;
  for (let i = 0; i < size; i++) {
    const faultType = chooseFaultType(rng);
    const record = makeRecord(rng, faultType);
    writeLine(JSON.stringify(record));
    if (faultType === 0) validCount++;
  }
  return { totalRecords: size, validRecords: validCount };
}

function generateBenignCorpus(size, seed, writeLine) {
  const rng = makePrng(seed);
  for (let i = 0; i < size; i++) {
    const record = makeRecord(rng, 0);
    writeLine(JSON.stringify(record));
  }
  return { totalRecords: size, validRecords: size };
}

function generateMaliciousCorpus(size, seed, writeLine) {
  const rng = makePrng(seed);
  // Each record cycles through fault types 1-7 in a shuffled order
  // All records are invalid
  const faultTypes = [
    ...Array(200).fill(1),
    ...Array(200).fill(2),
    ...Array(300).fill(3),
    ...Array(300).fill(4),
    ...Array(500).fill(5),
  ];
  for (let i = faultTypes.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const tmp = faultTypes[i]; faultTypes[i] = faultTypes[j]; faultTypes[j] = tmp;
  }
  for (let i = 0; i < size; i++) {
    const faultType = faultTypes[i % faultTypes.length] || 1;
    const record = makeRecord(rng, faultType);
    writeLine(JSON.stringify(record));
  }
  return { totalRecords: size, validRecords: 0 };
}

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = { size: 200, seed: 42, output: null, mode: 'mixed' };
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--size': opts.size = parseInt(args[++i], 10); break;
      case '--seed': opts.seed = parseInt(args[++i], 10); break;
      case '--output': opts.output = args[++i]; break;
      case '--mode': opts.mode = args[++i]; break;
    }
  }
  return opts;
}

if (require.main === module) {
  const opts = parseArgs(process.argv);
  let out;
  if (opts.output) {
    const dir = path.dirname(opts.output);
    fs.mkdirSync(dir, { recursive: true });
    out = fs.createWriteStream(opts.output, { encoding: 'utf8' });
  } else {
    out = process.stdout;
  }
  const writeLine = (line) => out.write(line + '\n');
  let result;
  if (opts.mode === 'benign') {
    result = generateBenignCorpus(opts.size, opts.seed, writeLine);
  } else if (opts.mode === 'malicious') {
    result = generateMaliciousCorpus(opts.size, opts.seed, writeLine);
  } else {
    result = generateCorpus(opts.size, opts.seed, writeLine);
  }
  if (opts.output) {
    out.end(() => {
      process.stderr.write(`Generated ${result.totalRecords} records (${result.validRecords} valid) -> ${opts.output}\n`);
    });
  } else {
    process.stderr.write(`Generated ${result.totalRecords} records (${result.validRecords} valid)\n`);
  }
}

module.exports = { generateCorpus, generateBenignCorpus, generateMaliciousCorpus, makePrng, makeRecord, chooseFaultType };
