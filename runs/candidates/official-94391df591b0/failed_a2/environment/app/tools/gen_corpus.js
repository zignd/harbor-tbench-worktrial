#!/usr/bin/env node
'use strict';

// Deterministic NDJSON corpus generator.
// Usage: node gen_corpus.js --seed <n> --count <n> [--invalid-ratio <0-1>] --output <file>
//   or:  node gen_corpus.js --seed <n> --count <n> --mode benign|malicious|mixed --output <file>

const fs = require('fs');
const path = require('path');

// Simple deterministic PRNG (mulberry32)
function makePrng(seed) {
  let s = seed >>> 0;
  return function() {
    s += 0x6D2B79F5;
    let z = s;
    z = Math.imul(z ^ (z >>> 15), z | 1);
    z ^= z + Math.imul(z ^ (z >>> 7), z | 61);
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
}

function randInt(rng, min, max) {
  return min + Math.floor(rng() * (max - min + 1));
}

function randChoice(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

function randString(rng, len) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789-_';
  let s = '';
  for (let i = 0; i < len; i++) s += randChoice(rng, chars);
  return s;
}

function isoTimestamp(rng) {
  // Generate valid ISO8601 timestamps in range 2023-2024
  const year = 2023 + Math.floor(rng() * 2);
  const month = String(randInt(rng, 1, 12)).padStart(2, '0');
  const day = String(randInt(rng, 1, 28)).padStart(2, '0');
  const hour = String(randInt(rng, 0, 23)).padStart(2, '0');
  const min = String(randInt(rng, 0, 59)).padStart(2, '0');
  const sec = String(randInt(rng, 0, 59)).padStart(2, '0');
  const tzChoice = rng();
  if (tzChoice < 0.6) {
    return `${year}-${month}-${day}T${hour}:${min}:${sec}Z`;
  } else if (tzChoice < 0.8) {
    const ms = String(randInt(rng, 0, 999)).padStart(3, '0');
    return `${year}-${month}-${day}T${hour}:${min}:${sec}.${ms}Z`;
  } else {
    const tzH = String(randInt(rng, 0, 14)).padStart(2, '0');
    const tzM = randChoice(rng, ['00', '30']);
    const sign = rng() < 0.5 ? '+' : '-';
    return `${year}-${month}-${day}T${hour}:${min}:${sec}${sign}${tzH}:${tzM}`;
  }
}

const LEVELS = ['debug', 'info', 'warn', 'error'];
const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const SERVICES = ['auth-service', 'api-gateway', 'db-proxy', 'cache-layer', 'queue-worker',
                  'metrics-collector', 'scheduler', 'notifier', 'file-processor', 'audit-log'];

function makeValidRecord(rng, index) {
  const rec = {
    timestamp: isoTimestamp(rng),
    level: randChoice(rng, LEVELS),
    severity: randChoice(rng, SEVERITIES),
    service: randChoice(rng, SERVICES),
    message: `Event ${index}: ${randString(rng, randInt(rng, 8, 40))}`,
  };
  if (rng() < 0.3) {
    rec.metadata = {
      requestId: randString(rng, 16),
      durationMs: randInt(rng, 1, 5000),
    };
  }
  return rec;
}

function makeInvalidRecord(rng, index, invalidType) {
  const type = invalidType || randChoice(rng, [
    'null_severity', 'int_severity', 'missing_level',
    'bad_timestamp', 'missing_service', 'missing_message',
    'bad_level', 'null_timestamp'
  ]);
  const base = makeValidRecord(rng, index);
  switch (type) {
    case 'null_severity':
      base.severity = null;
      break;
    case 'int_severity':
      base.severity = randInt(rng, 1, 100);
      break;
    case 'missing_level':
      delete base.level;
      break;
    case 'bad_timestamp':
      base.timestamp = `${randInt(rng, 2020, 2024)}-${randInt(rng, 1, 12)}-${randInt(rng, 1, 28)}`;
      break;
    case 'missing_service':
      delete base.service;
      break;
    case 'missing_message':
      delete base.message;
      break;
    case 'bad_level':
      base.level = randChoice(rng, ['WARN', 'INFO', 'trace', 'fatal', 'verbose']);
      break;
    case 'null_timestamp':
      base.timestamp = null;
      break;
    default:
      base.severity = null;
  }
  return base;
}

function parseArgs(argv) {
  const args = { seed: 42, count: 200, mode: 'mixed', invalidRatio: 0.2, output: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--seed' && argv[i+1]) args.seed = parseInt(argv[++i], 10);
    else if (argv[i] === '--count' && argv[i+1]) args.count = parseInt(argv[++i], 10);
    else if (argv[i] === '--mode' && argv[i+1]) args.mode = argv[++i];
    else if (argv[i] === '--invalid-ratio' && argv[i+1]) args.invalidRatio = parseFloat(argv[++i]);
    else if (argv[i] === '--output' && argv[i+1]) args.output = argv[++i];
    else if (argv[i] === '--invalid-type' && argv[i+1]) args.invalidType = argv[++i];
  }
  return args;
}

function generate(args) {
  const rng = makePrng(args.seed);
  const records = [];

  if (args.mode === 'benign') {
    for (let i = 0; i < args.count; i++) {
      records.push({ record: makeValidRecord(rng, i), valid: true });
    }
  } else if (args.mode === 'malicious') {
    const types = ['null_severity', 'int_severity', 'missing_level', 'bad_timestamp',
                   'missing_service', 'missing_message', 'bad_level', 'null_timestamp'];
    for (let i = 0; i < args.count; i++) {
      const t = types[i % types.length];
      records.push({ record: makeInvalidRecord(rng, i, t), valid: false });
    }
  } else {
    // mixed: deterministic interleaving
    for (let i = 0; i < args.count; i++) {
      const isInvalid = rng() < args.invalidRatio;
      if (isInvalid) {
        records.push({ record: makeInvalidRecord(rng, i, args.invalidType || null), valid: false });
      } else {
        records.push({ record: makeValidRecord(rng, i), valid: true });
      }
    }
  }
  return records;
}

if (require.main === module) {
  const args = parseArgs(process.argv.slice(2));
  const entries = generate(args);

  const lines = entries.map(e => JSON.stringify(e.record));
  const content = lines.join('\n') + '\n';

  if (args.output) {
    fs.mkdirSync(path.dirname(args.output), { recursive: true });
    fs.writeFileSync(args.output, content, 'utf8');
    process.stderr.write(`Generated ${entries.length} records to ${args.output}\n`);
  } else {
    process.stdout.write(content);
  }
}

module.exports = { generate, makePrng, makeValidRecord, makeInvalidRecord };
