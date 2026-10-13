'use strict';

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { validate } = require('./validator');
const { Metrics } = require('./metrics');
const { tryParseJSON } = require('./utils');

/**
 * Open a write stream to the output path, creating parent dirs if needed.
 */
function openOutputStream(outputPath) {
  const dir = path.dirname(outputPath);
  fs.mkdirSync(dir, { recursive: true });
  return fs.createWriteStream(outputPath, { encoding: 'utf8', flags: 'w' });
}

/**
 * Core ingestion pipeline.
 *
 * Reads the input NDJSON file line by line, validates each record,
 * and writes accepted records to the output file.
 *
 * @param {string} inputPath  - Path to the NDJSON input file
 * @param {string} outputPath - Path to write accepted records
 * @param {string} schemaPath - Path to the JSON Schema file
 * @param {object} logger     - Logger instance
 * @param {object} [opts]     - Optional overrides (batchSize, dryRun, etc.)
 * @returns {Promise<object>} Metrics summary
 */
function runPipeline(inputPath, outputPath, schemaPath, logger, opts) {
  opts = opts || {};
  const batchSize = opts.batchSize || 500;
  const dryRun = opts.dryRun || false;

  return new Promise((resolve, reject) => {
    const metrics = new Metrics();
    metrics.start();

    const out = dryRun ? null : openOutputStream(outputPath);

    let pendingWrite = Promise.resolve();
    let lineNumber = 0;
    let batchBuffer = [];

    function flushBatch() {
      if (batchBuffer.length === 0) return;
      const chunk = batchBuffer.join('\n') + '\n';
      if (out) {
        pendingWrite = pendingWrite.then(() => new Promise((res, rej) => {
          out.write(chunk, err => err ? rej(err) : res());
        }));
      }
      metrics.recordBatch();
      batchBuffer = [];
    }

    const rl = readline.createInterface({
      input: fs.createReadStream(inputPath, { encoding: 'utf8' }),
      crlfDelay: Infinity,
      terminal: false,
    });

    rl.on('line', (line) => {
      lineNumber++;
      const trimmed = line.trim();
      if (!trimmed) return;

      const parsed = tryParseJSON(trimmed);
      if (!parsed.ok) {
        logger.warn('JSON parse error', { line: lineNumber, error: parsed.error });
        metrics.recordParseError();
        return;
      }

      const result = validate(parsed.value, schemaPath);

      if (result.valid) {
        batchBuffer.push(trimmed);
        metrics.recordAccepted();
        if (batchBuffer.length >= batchSize) {
          flushBatch();
        }
      } else {
        logger.debug('Record rejected', { line: lineNumber, reason: result.reason });
        metrics.recordRejected(result.reason);
      }
    });

    rl.on('close', () => {
      flushBatch();
      pendingWrite.then(() => {
        if (out) {
          out.end(() => {
            metrics.finish();
            resolve(metrics.summary());
          });
        } else {
          metrics.finish();
          resolve(metrics.summary());
        }
      }).catch(reject);
    });

    rl.on('error', (err) => {
      logger.error('Read error', { error: err.message });
      reject(err);
    });
  });
}

module.exports = { runPipeline };
