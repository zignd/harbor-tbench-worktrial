'use strict';

const path = require('path');

const DEFAULT_INPUT_DIR = '/app/logs';
const DEFAULT_OUTPUT_FILE = '/app/output/clean.ndjson';
const DEFAULT_SCHEMA_PATH = '/app/schema.json';
const DEFAULT_BATCH_SIZE = 500;
const DEFAULT_LOG_LEVEL = 'info';
const DEFAULT_MAX_LINE_LENGTH = 1024 * 1024; // 1MB

function parseArgs(argv) {
  const args = argv.slice(2);
  const config = {
    input: null,
    output: DEFAULT_OUTPUT_FILE,
    schema: DEFAULT_SCHEMA_PATH,
    batchSize: DEFAULT_BATCH_SIZE,
    logLevel: DEFAULT_LOG_LEVEL,
    maxLineLength: DEFAULT_MAX_LINE_LENGTH,
    dryRun: false,
    verbose: false,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--input':
      case '-i':
        config.input = args[++i];
        break;
      case '--output':
      case '-o':
        config.output = args[++i];
        break;
      case '--schema':
      case '-s':
        config.schema = args[++i];
        break;
      case '--batch-size':
        config.batchSize = parseInt(args[++i], 10);
        break;
      case '--log-level':
        config.logLevel = args[++i];
        break;
      case '--dry-run':
        config.dryRun = true;
        break;
      case '--verbose':
      case '-v':
        config.verbose = true;
        break;
      default:
        // ignore unknown flags
        break;
    }
  }

  return config;
}

function validateConfig(config) {
  if (!config.input) {
    throw new Error('--input <file> is required');
  }
  if (isNaN(config.batchSize) || config.batchSize < 1) {
    throw new Error('--batch-size must be a positive integer');
  }
  return config;
}

module.exports = { parseArgs, validateConfig, DEFAULT_SCHEMA_PATH };
