'use strict';

const fs = require('fs');
const readline = require('readline');
const path = require('path');
const { createLogger } = require('./logger');
const { parseNDJSON, formatNDJSON, formatBytes, formatDuration } = require('./utils');
const { createMetrics } = require('./metrics');

const log = createLogger('pipeline');

class Pipeline {
  constructor(config, validator) {
    this.config = config;
    this.validator = validator;
    this.metrics = createMetrics();
    this.state = 'idle';
    this._lineCount = 0;
    this._acceptedCount = 0;
    this._rejectedCount = 0;
    this._parseErrorCount = 0;
    this._bytesRead = 0;
    this._startTime = null;
    this._outputStream = null;
  }

  async run() {
    const { inputFile, outputFile } = this.config;
    this._startTime = Date.now();
    this.state = 'running';

    log.info('pipeline starting', { inputFile, outputFile });

    await this._ensureOutputDir(outputFile);

    this._outputStream = fs.createWriteStream(outputFile, { encoding: 'utf8' });

    await new Promise((resolve, reject) => {
      this._outputStream.on('error', reject);
      this._outputStream.on('open', resolve);
    });

    try {
      await this._processFile(inputFile);
    } finally {
      await new Promise((resolve, reject) => {
        this._outputStream.end(err => {
          if (err) reject(err);
          else resolve();
        });
      });
    }

    const elapsed = Date.now() - this._startTime;
    this.state = 'done';

    const summary = {
      lines: this._lineCount,
      accepted: this._acceptedCount,
      rejected: this._rejectedCount,
      parseErrors: this._parseErrorCount,
      bytesRead: this._bytesRead,
      elapsed: formatDuration(elapsed),
    };
    log.info('pipeline complete', summary);
    return summary;
  }

  async _ensureOutputDir(outputFile) {
    const dir = path.dirname(outputFile);
    try {
      fs.mkdirSync(dir, { recursive: true });
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;
    }
  }

  _processFile(inputFile) {
    return new Promise((resolve, reject) => {
      let inputStream;
      try {
        inputStream = fs.createReadStream(inputFile, { encoding: 'utf8' });
      } catch (err) {
        return reject(new Error(`Cannot open input file ${inputFile}: ${err.message}`));
      }

      inputStream.on('error', err => {
        reject(new Error(`Error reading ${inputFile}: ${err.message}`));
      });

      const rl = readline.createInterface({
        input: inputStream,
        crlfDelay: Infinity,
        terminal: false,
      });

      rl.on('line', (line) => {
        this._lineCount++;
        this._bytesRead += Buffer.byteLength(line, 'utf8') + 1;
        this._processLine(line);
      });

      rl.on('close', () => {
        this.metrics.gauge('lines.total', this._lineCount);
        this.metrics.gauge('records.accepted', this._acceptedCount);
        this.metrics.gauge('records.rejected', this._rejectedCount);
        resolve();
      });

      rl.on('error', reject);
    });
  }

  _processLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return;

    const record = parseNDJSON(trimmed);
    if (record === null) {
      this._parseErrorCount++;
      this.metrics.increment('parse.errors');
      log.debug('parse error', { lineNum: this._lineCount, preview: trimmed.slice(0, 80) });
      return;
    }

    const result = this.validator.validate(record);
    if (result.valid) {
      this._acceptedCount++;
      this.metrics.increment('records.accepted');
      const serialized = formatNDJSON(record);
      if (serialized !== null) {
        this._outputStream.write(serialized + '\n');
      }
    } else {
      this._rejectedCount++;
      this.metrics.increment('records.rejected');
      log.debug('record rejected', {
        lineNum: this._lineCount,
        errorCount: result.errors ? result.errors.length : 0,
      });
    }
  }

  getStats() {
    return {
      state: this.state,
      lines: this._lineCount,
      accepted: this._acceptedCount,
      rejected: this._rejectedCount,
      parseErrors: this._parseErrorCount,
      bytesRead: this._bytesRead,
      elapsedMs: this._startTime ? Date.now() - this._startTime : 0,
      validatorStats: this.validator.getStats(),
    };
  }
}

function createPipeline(config, validator) {
  return new Pipeline(config, validator);
}

module.exports = { createPipeline, Pipeline };
