'use strict';

const { formatDuration, formatBytes } = require('./utils');

class Metrics {
  constructor() {
    this.reset();
  }

  reset() {
    this.startTime = null;
    this.endTime = null;
    this.totalRecords = 0;
    this.acceptedRecords = 0;
    this.rejectedRecords = 0;
    this.parseErrors = 0;
    this.bytesRead = 0;
    this.bytesWritten = 0;
    this.validationErrors = {};
    this.batchCount = 0;
    this.peakMemoryMB = 0;
  }

  start() {
    this.startTime = Date.now();
    this.reset();
    this.startTime = Date.now();
  }

  finish() {
    this.endTime = Date.now();
  }

  recordRead(bytes) {
    this.bytesRead += bytes;
  }

  recordWrite(bytes) {
    this.bytesWritten += bytes;
  }

  recordAccepted() {
    this.totalRecords++;
    this.acceptedRecords++;
  }

  recordRejected(reason) {
    this.totalRecords++;
    this.rejectedRecords++;
    if (reason) {
      this.validationErrors[reason] = (this.validationErrors[reason] || 0) + 1;
    }
  }

  recordParseError() {
    this.totalRecords++;
    this.parseErrors++;
  }

  recordBatch() {
    this.batchCount++;
    const memUsage = process.memoryUsage();
    const memMB = memUsage.heapUsed / (1024 * 1024);
    if (memMB > this.peakMemoryMB) {
      this.peakMemoryMB = memMB;
    }
  }

  elapsed() {
    if (!this.startTime) return 0;
    return (this.endTime || Date.now()) - this.startTime;
  }

  acceptedRate() {
    if (this.totalRecords === 0) return 0;
    return (this.acceptedRecords / this.totalRecords * 100).toFixed(1);
  }

  throughput() {
    const ms = this.elapsed();
    if (ms === 0) return 0;
    return Math.round(this.totalRecords / (ms / 1000));
  }

  summary() {
    return {
      durationMs: this.elapsed(),
      durationHuman: formatDuration(this.elapsed()),
      totalRecords: this.totalRecords,
      acceptedRecords: this.acceptedRecords,
      rejectedRecords: this.rejectedRecords,
      parseErrors: this.parseErrors,
      acceptedRatePct: this.acceptedRate(),
      throughputRps: this.throughput(),
      bytesRead: this.bytesRead,
      bytesReadHuman: formatBytes(this.bytesRead),
      bytesWritten: this.bytesWritten,
      bytesWrittenHuman: formatBytes(this.bytesWritten),
      batchCount: this.batchCount,
      peakMemoryMB: this.peakMemoryMB.toFixed(1),
      topValidationErrors: Object.entries(this.validationErrors)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([k, v]) => ({ reason: k, count: v })),
    };
  }
}

module.exports = { Metrics };
