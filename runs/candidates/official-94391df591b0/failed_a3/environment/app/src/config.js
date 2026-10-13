'use strict';

const path = require('path');

const defaults = {
  inputDir: '/app/logs',
  outputDir: '/app/output',
  schemaPath: '/app/schema.json',
  batchSize: 500,
  logLevel: process.env.LOG_LEVEL || 'info',
  maxLineLength: 65536,
  encoding: 'utf8',
  strictMode: false,
  metricsEnabled: true,
  metricsIntervalMs: 5000,
};

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--input' && argv[i + 1]) {
      args.inputFile = argv[++i];
    } else if (arg === '--output' && argv[i + 1]) {
      args.outputFile = argv[++i];
    } else if (arg === '--schema' && argv[i + 1]) {
      args.schemaPath = argv[++i];
    } else if (arg === '--batch-size' && argv[i + 1]) {
      args.batchSize = parseInt(argv[++i], 10);
    } else if (arg === '--log-level' && argv[i + 1]) {
      args.logLevel = argv[++i];
    } else if (arg === '--strict') {
      args.strictMode = true;
    } else if (arg === '--no-metrics') {
      args.metricsEnabled = false;
    }
  }
  return args;
}

function buildConfig(overrides) {
  const cliArgs = parseArgs(process.argv.slice(2));
  const merged = Object.assign({}, defaults, overrides || {}, cliArgs);
  if (!merged.inputFile) {
    merged.inputFile = path.join(merged.inputDir, 'sample.ndjson');
  }
  if (!merged.outputFile) {
    merged.outputFile = path.join(merged.outputDir, 'clean.ndjson');
  }
  return merged;
}

module.exports = { buildConfig, parseArgs, defaults };
