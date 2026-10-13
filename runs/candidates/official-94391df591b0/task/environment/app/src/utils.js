'use strict';

const crypto = require('crypto');

/**
 * Split a buffer into lines, returning the lines array and any leftover
 * partial line.
 */
function splitLines(buffer, leftover) {
  const combined = leftover ? leftover + buffer.toString('utf8') : buffer.toString('utf8');
  const lines = combined.split('\n');
  const remainder = lines.pop(); // last element may be incomplete
  return { lines, remainder };
}

/**
 * Attempt to parse a line as JSON. Returns { ok, value, error }.
 */
function tryParseJSON(line) {
  try {
    const value = JSON.parse(line);
    return { ok: true, value };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/**
 * Compute a deterministic hash of a record for deduplication tracking.
 */
function hashRecord(record) {
  const canonical = JSON.stringify(record, Object.keys(record).sort());
  return crypto.createHash('sha256').update(canonical).digest('hex').slice(0, 16);
}

/**
 * Format bytes into a human-readable string.
 */
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

/**
 * Format duration milliseconds into a human-readable string.
 */
function formatDuration(ms) {
  if (ms < 1000) return ms + 'ms';
  return (ms / 1000).toFixed(3) + 's';
}

/**
 * Deep freeze an object (prevent accidental mutation of shared config).
 */
function deepFreeze(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  Object.keys(obj).forEach(key => deepFreeze(obj[key]));
  return Object.freeze(obj);
}

/**
 * Chunk an array into groups of at most `size`.
 */
function chunkArray(arr, size) {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

/**
 * Clamp a number between min and max.
 */
function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Sleep for `ms` milliseconds.
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Strip ANSI color codes from a string.
 */
function stripAnsi(str) {
  return str.replace(/\x1b\[[0-9;]*m/g, '');
}

/**
 * Truncate a string to maxLen, appending '...' if truncated.
 */
function truncate(str, maxLen) {
  if (typeof str !== 'string') return str;
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

module.exports = {
  splitLines,
  tryParseJSON,
  hashRecord,
  formatBytes,
  formatDuration,
  deepFreeze,
  chunkArray,
  clamp,
  sleep,
  stripAnsi,
  truncate,
};
