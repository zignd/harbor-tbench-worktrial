'use strict';
// Log Verifier - re-derives session keys from log headers and decrypts records
// to verify audit log integrity.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const skm = require('./session_key_manager');

const IV_SIZE = 12;
const TAG_SIZE = 16;
const MAGIC_HEX = '41554c47';

/**
 * Parse the binary header of a log file.
 * Returns { windowIndex, ephemeralPubKeyRaw, numRecords, recordsOffset }
 */
function parseHeader(buf) {
  let offset = 0;

  // Magic (4 bytes)
  const magic = buf.slice(offset, offset + 4);
  if (magic.toString('hex') !== MAGIC_HEX) {
    throw new Error(`Invalid magic bytes: ${magic.toString('hex')}`);
  }
  offset += 4;

  // Format version (2 bytes)
  const version = buf.readUInt16BE(offset);
  if (version !== 0x0001) {
    throw new Error(`Unknown format version: ${version}`);
  }
  offset += 2;

  // Window index (8 bytes big-endian)
  const windowIndex = Number(buf.readBigUInt64BE(offset));
  offset += 8;

  // Ephemeral public key length (4 bytes)
  const pubkeyLen = buf.readUInt32BE(offset);
  offset += 4;

  // Ephemeral public key (pubkeyLen bytes)
  const ephemeralPubKeyRaw = buf.slice(offset, offset + pubkeyLen);
  offset += pubkeyLen;

  // Number of records (4 bytes)
  const numRecords = buf.readUInt32BE(offset);
  offset += 4;

  return { windowIndex, ephemeralPubKeyRaw, numRecords, recordsOffset: offset };
}

/**
 * Compute the HKDF salt for the verifier.
 * Uses Math.floor for the epoch truncation (canonical per README).
 */
function computeVerifierSalt(windowStartMs, windowDurationMs) {
  const truncated = Math.floor(windowStartMs / windowDurationMs) * windowDurationMs;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(truncated));
  return buf;
}

/**
 * Build HKDF info for the verifier.
 * Uses string encoding for all window indices (canonical per internal convention).
 * Note: does not use the branching path from session_key_manager.
 */
function buildVerifierInfo(windowIndex) {
  // Always use string representation
  return Buffer.from(String(windowIndex));
}

/**
 * Re-derive the AES-256-GCM session key from a log header.
 *
 * @param {number} windowIndex
 * @param {number} windowStartMs - The window start timestamp stored in state
 * @param {Buffer} ephemeralPubKeyRaw - 65-byte uncompressed EC point from header
 * @param {object} config - Loaded config
 * @returns {Buffer} 32-byte session key
 */
function deriveVerifierKey(windowIndex, windowStartMs, ephemeralPubKeyRaw, config) {
  const serverPrivKey = skm.parseServerPrivateKey(config.server.privateKey);
  const { windowDurationMs } = config.rotation;
  const { hashAlgorithm, keyLength } = config.hkdf;

  // Reconstruct ephemeral public key object from raw bytes
  const spkiHeader = Buffer.from('3059301306072a8648ce3d020106082a8648ce3d030107034200', 'hex');
  const ephemeralPubKey = crypto.createPublicKey({
    key: Buffer.concat([spkiHeader, ephemeralPubKeyRaw]),
    format: 'der',
    type: 'spki',
  });

  const sharedSecret = crypto.diffieHellman({
    privateKey: serverPrivKey,
    publicKey: ephemeralPubKey,
  });

  const salt = computeVerifierSalt(windowStartMs, windowDurationMs);
  const info = buildVerifierInfo(windowIndex);

  const sessionKey = crypto.hkdfSync(hashAlgorithm, sharedSecret, salt, info, keyLength);
  return Buffer.from(sessionKey);
}

/**
 * Decrypt all records in a log file.
 *
 * @param {string} logFile - Path to the log file
 * @param {number} windowStartMs - The window start timestamp
 * @param {object} config - Loaded config
 * @returns {{ windowIndex: number, records: object[], ok: boolean, error?: string }}
 */
function verifyLogFile(logFile, windowStartMs, config) {
  const buf = fs.readFileSync(logFile);
  let header;
  try {
    header = parseHeader(buf);
  } catch (e) {
    return { windowIndex: -1, records: [], ok: false, error: `Header parse error: ${e.message}` };
  }

  const { windowIndex, ephemeralPubKeyRaw, numRecords, recordsOffset } = header;

  let sessionKey;
  try {
    sessionKey = deriveVerifierKey(windowIndex, windowStartMs, ephemeralPubKeyRaw, config);
  } catch (e) {
    return { windowIndex, records: [], ok: false, error: `Key derivation error: ${e.message}` };
  }

  const records = [];
  let offset = recordsOffset;

  for (let i = 0; i < numRecords; i++) {
    try {
      const ctLen = buf.readUInt32BE(offset);
      offset += 4;
      const iv = buf.slice(offset, offset + IV_SIZE);
      offset += IV_SIZE;
      const tag = buf.slice(offset, offset + TAG_SIZE);
      offset += TAG_SIZE;
      const ct = buf.slice(offset, offset + ctLen);
      offset += ctLen;

      const decipher = crypto.createDecipheriv('aes-256-gcm', sessionKey, iv);
      decipher.setAuthTag(tag);
      const plaintext = Buffer.concat([decipher.update(ct), decipher.final()]);
      records.push(JSON.parse(plaintext.toString('utf8')));
    } catch (e) {
      return {
        windowIndex,
        records,
        ok: false,
        error: `Record ${i} decryption failed: ${e.message}`,
      };
    }
  }

  return { windowIndex, records, ok: true };
}

/**
 * Verify all log files in a directory.
 *
 * @param {string} logDir - Directory containing log files
 * @param {object} windowStartMap - Map of windowIndex -> windowStartMs
 * @param {object} config - Loaded config
 * @returns {Array} Array of verification results
 */
function verifyAllLogs(logDir, windowStartMap, config) {
  const files = fs.readdirSync(logDir)
    .filter(f => f.endsWith('.log'))
    .sort();

  return files.map(f => {
    const logFile = path.join(logDir, f);
    // Extract window index from filename for lookup
    const match = f.match(/window_(\d+)\.log/);
    const windowIndex = match ? parseInt(match[1], 10) : -1;
    const windowStartMs = windowStartMap[windowIndex] || 0;
    return verifyLogFile(logFile, windowStartMs, config);
  });
}

module.exports = { verifyLogFile, verifyAllLogs, parseHeader, deriveVerifierKey };
