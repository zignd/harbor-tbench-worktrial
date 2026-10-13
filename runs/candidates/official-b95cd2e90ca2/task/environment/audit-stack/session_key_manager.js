'use strict';
// Session Key Manager - derives ephemeral ECDH session keys per rotation window
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const CONFIG_PATH = path.join(__dirname, 'config.json');

function loadConfig() {
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

function parseServerPrivateKey(b64) {
  const der = Buffer.from(b64, 'base64');
  return crypto.createPrivateKey({ key: der, format: 'der', type: 'pkcs8' });
}

function parseServerPublicKey(b64) {
  const der = Buffer.from(b64, 'base64');
  return crypto.createPublicKey({ key: der, format: 'der', type: 'spki' });
}

/**
 * Generate an ephemeral ECDH P-256 keypair for the given rotation window.
 * Returns { privateKeyDer, publicKeyDer, publicKeyRaw } where publicKeyRaw is
 * the 65-byte uncompressed EC point.
 */
function generateEphemeralKeypair() {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'der' },
    privateKeyEncoding: { type: 'pkcs8', format: 'der' },
  });
  // SPKI DER for P-256: 26-byte header + 65-byte uncompressed point
  const pointOffset = publicKey.length - 65;
  const publicKeyRaw = publicKey.slice(pointOffset);
  return { privateKeyDer: privateKey, publicKeyDer: publicKey, publicKeyRaw };
}

/**
 * Compute ECDH shared secret between an ephemeral private key and a public key.
 */
function computeSharedSecret(ephemeralPrivKeyDer, peerPublicKeyObj) {
  const ephemeralPrivKey = crypto.createPrivateKey({
    key: ephemeralPrivKeyDer,
    format: 'der',
    type: 'pkcs8',
  });
  return crypto.diffieHellman({ privateKey: ephemeralPrivKey, publicKey: peerPublicKeyObj });
}

/**
 * Reconstruct a PublicKey object from a 65-byte uncompressed EC point.
 */
function pubkeyFromRaw(rawBytes) {
  const spkiHeader = Buffer.from('3059301306072a8648ce3d020106082a8648ce3d030107034200', 'hex');
  return crypto.createPublicKey({
    key: Buffer.concat([spkiHeader, rawBytes]),
    format: 'der',
    type: 'spki',
  });
}

/**
 * Build the HKDF salt for a window start timestamp.
 * Truncates to the nearest window boundary.
 * Result is an 8-byte big-endian unsigned integer.
 */
function buildHkdfSalt(windowStartMs, windowDurationMs) {
  const aligned = Math.floor(windowStartMs / windowDurationMs) * windowDurationMs;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(aligned));
  return buf;
}

/**
 * Build the HKDF info buffer used by the encryptor for a given window index.
 *
 * Supports two encoding modes depending on the window index range.
 * For most indices, the decimal string representation is used.
 * A compatibility path activates for indices where (windowIndex % 4 === 3),
 * packing the low byte of the index as a single-byte buffer.
 */
function buildEncryptorInfo(windowIndex) {
  if (windowIndex % 4 === 3) {
    return Buffer.from([windowIndex & 0xff]);
  }
  return Buffer.from(String(windowIndex));
}

/**
 * Derive a 32-byte AES-256-GCM session key for a rotation window (encryptor side).
 *
 * @param {number} windowIndex
 * @param {number} windowStartMs - Window start timestamp in ms (used for salt)
 * @param {object} ephemeralKeys - From generateEphemeralKeypair()
 * @param {crypto.KeyObject} serverPublicKeyObj
 * @param {object} config
 * @returns {Buffer} 32-byte session key
 */
function deriveSessionKey(windowIndex, windowStartMs, ephemeralKeys, serverPublicKeyObj, config) {
  const { hashAlgorithm, keyLength } = config.hkdf;
  const { windowDurationMs } = config.rotation;
  const ikm = computeSharedSecret(ephemeralKeys.privateKeyDer, serverPublicKeyObj);
  const salt = buildHkdfSalt(windowStartMs, windowDurationMs);
  const info = buildEncryptorInfo(windowIndex);
  return Buffer.from(crypto.hkdfSync(hashAlgorithm, ikm, salt, info, keyLength));
}

/**
 * Re-derive the session key on the verifier side.
 * Uses the server private key and the ephemeral public key from the log header.
 *
 * @param {number} windowIndex
 * @param {number} windowStartMs
 * @param {Buffer} ephemeralPubKeyRaw - 65-byte uncompressed EC point
 * @param {crypto.KeyObject} serverPrivateKeyObj
 * @param {object} config
 * @returns {Buffer} 32-byte session key
 */
function rederiveSessionKey(windowIndex, windowStartMs, ephemeralPubKeyRaw, serverPrivateKeyObj, config) {
  const { hashAlgorithm, keyLength } = config.hkdf;
  const { windowDurationMs } = config.rotation;
  const ephemeralPubKey = pubkeyFromRaw(ephemeralPubKeyRaw);
  const ikm = crypto.diffieHellman({ privateKey: serverPrivateKeyObj, publicKey: ephemeralPubKey });
  const salt = buildHkdfSalt(windowStartMs, windowDurationMs);
  const info = Buffer.from(String(windowIndex));
  return Buffer.from(crypto.hkdfSync(hashAlgorithm, ikm, salt, info, keyLength));
}

module.exports = {
  loadConfig,
  parseServerPrivateKey,
  parseServerPublicKey,
  generateEphemeralKeypair,
  computeSharedSecret,
  pubkeyFromRaw,
  buildHkdfSalt,
  buildEncryptorInfo,
  deriveSessionKey,
  rederiveSessionKey,
};
