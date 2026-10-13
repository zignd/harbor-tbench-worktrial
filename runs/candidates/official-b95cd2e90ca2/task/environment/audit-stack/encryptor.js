'use strict';
// Log Encryptor - encrypts batches of metric records using AES-256-GCM
// and writes them to rotation window log files with a structured binary header.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const skm = require('./session_key_manager');

// Binary format constants
const MAGIC = Buffer.from([0x41, 0x55, 0x4c, 0x47]); // "AULG"
const FORMAT_VERSION = 0x0001;
const IV_SIZE = 12;
const TAG_SIZE = 16;

/**
 * Compute the HKDF salt on the encryptor side.
 * The window start timestamp is aligned to the nearest window boundary.
 */
function computeEncryptorSalt(windowStartMs, windowDurationMs) {
  const aligned = Math.round(windowStartMs / windowDurationMs) * windowDurationMs;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(aligned));
  return buf;
}

/**
 * Build the HKDF info buffer for a window index (encryptor side).
 */
function buildInfo(windowIndex) {
  if (windowIndex % 4 === 3) {
    return Buffer.from([windowIndex & 0xff]);
  }
  return Buffer.from(String(windowIndex));
}

/**
 * Write an encrypted log file for a single rotation window.
 *
 * Binary layout (see README for field descriptions):
 *   [4]  Magic 0x41554c47
 *   [2]  Version 0x0001
 *   [8]  Window index (big-endian uint64)
 *   [4]  Ephemeral public key length (big-endian uint32)
 *   [N]  Ephemeral public key bytes (uncompressed EC point, N=65)
 *   [4]  Number of records (big-endian uint32)
 *   For each record:
 *     [4]  Ciphertext length (big-endian uint32)
 *     [12] AES-GCM IV
 *     [16] AES-GCM auth tag
 *     [M]  Ciphertext
 *
 * @param {string} logDir
 * @param {number} windowIndex
 * @param {number} windowStartMs
 * @param {Array} records
 * @param {object} config
 * @returns {string} Path to written log file
 */
function encryptWindow(logDir, windowIndex, windowStartMs, records, config) {
  const { windowDurationMs } = config.rotation;
  const { hashAlgorithm, keyLength } = config.hkdf;
  const serverPubKey = skm.parseServerPublicKey(config.server.publicKey);

  const ephemeralKeys = skm.generateEphemeralKeypair();

  // Derive session key
  const ikm = skm.computeSharedSecret(ephemeralKeys.privateKeyDer, serverPubKey);
  const salt = computeEncryptorSalt(windowStartMs, windowDurationMs);
  const info = buildInfo(windowIndex);
  const sessionKey = Buffer.from(crypto.hkdfSync(hashAlgorithm, ikm, salt, info, keyLength));

  // Encrypt each record with AES-256-GCM
  const encryptedRecords = records.map(record => {
    const plaintext = Buffer.from(JSON.stringify(record), 'utf8');
    const iv = crypto.randomBytes(IV_SIZE);
    const cipher = crypto.createCipheriv('aes-256-gcm', sessionKey, iv);
    const ct = Buffer.concat([cipher.update(plaintext), cipher.final()]);
    const tag = cipher.getAuthTag();
    return { iv, tag, ct };
  });

  // Build binary header
  const versionBuf = Buffer.alloc(2);
  versionBuf.writeUInt16BE(FORMAT_VERSION);

  const windowIdxBuf = Buffer.alloc(8);
  windowIdxBuf.writeBigUInt64BE(BigInt(windowIndex));

  const pubkeyRaw = ephemeralKeys.publicKeyRaw;
  const pubkeyLenBuf = Buffer.alloc(4);
  pubkeyLenBuf.writeUInt32BE(pubkeyRaw.length);

  const numRecordsBuf = Buffer.alloc(4);
  numRecordsBuf.writeUInt32BE(encryptedRecords.length);

  const parts = [MAGIC, versionBuf, windowIdxBuf, pubkeyLenBuf, pubkeyRaw, numRecordsBuf];

  for (const { iv, tag, ct } of encryptedRecords) {
    const ctLenBuf = Buffer.alloc(4);
    ctLenBuf.writeUInt32BE(ct.length);
    parts.push(ctLenBuf, iv, tag, ct);
  }

  const filename = `window_${String(windowIndex).padStart(6, '0')}.log`;
  const logFile = path.join(logDir, filename);
  fs.writeFileSync(logFile, Buffer.concat(parts));
  return logFile;
}

module.exports = { encryptWindow, MAGIC, FORMAT_VERSION, IV_SIZE, TAG_SIZE };
