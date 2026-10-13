'use strict';

const crypto = require('crypto');

function parseNDJSON(line) {
  if (!line || !line.trim()) return null;
  try {
    return JSON.parse(line);
  } catch (err) {
    return null;
  }
}

function formatNDJSON(obj) {
  try {
    return JSON.stringify(obj);
  } catch (err) {
    return null;
  }
}

function isNonEmptyString(val) {
  return typeof val === 'string' && val.length > 0;
}

function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  try {
    return JSON.parse(JSON.stringify(obj));
  } catch (_) {
    return obj;
  }
}

function hashRecord(record) {
  try {
    const str = JSON.stringify(record);
    return crypto.createHash('sha256').update(str).digest('hex').slice(0, 16);
  } catch (_) {
    return 'unknown';
  }
}

function truncate(str, maxLen) {
  if (typeof str !== 'string') return str;
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + '...';
}

function safeGet(obj, path, defaultVal) {
  if (!obj || typeof obj !== 'object') return defaultVal;
  const parts = Array.isArray(path) ? path : path.split('.');
  let cur = obj;
  for (const part of parts) {
    if (cur === null || cur === undefined || typeof cur !== 'object') return defaultVal;
    cur = cur[part];
  }
  return cur !== undefined ? cur : defaultVal;
}

function flattenObject(obj, prefix, separator) {
  prefix = prefix || '';
  separator = separator || '.';
  const result = {};
  function recurse(current, p) {
    for (const [key, value] of Object.entries(current)) {
      const newKey = p ? `${p}${separator}${key}` : key;
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        recurse(value, newKey);
      } else {
        result[newKey] = value;
      }
    }
  }
  recurse(obj, prefix);
  return result;
}

function groupBy(arr, keyFn) {
  const groups = {};
  for (const item of arr) {
    const k = keyFn(item);
    if (!groups[k]) groups[k] = [];
    groups[k].push(item);
  }
  return groups;
}

function chunk(arr, size) {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = ((ms % 60000) / 1000).toFixed(1);
  return `${minutes}m${seconds}s`;
}

module.exports = {
  parseNDJSON,
  formatNDJSON,
  isNonEmptyString,
  deepClone,
  hashRecord,
  truncate,
  safeGet,
  flattenObject,
  groupBy,
  chunk,
  sleep,
  formatBytes,
  formatDuration,
};
