'use strict';

const fs = require('fs');
const path = require('path');

/**
 * Load and parse the JSON schema from disk.
 * Validates that it is a valid JSON object before returning.
 */
function loadSchema(schemaPath) {
  const resolved = path.resolve(schemaPath);
  let raw;
  try {
    raw = fs.readFileSync(resolved, 'utf8');
  } catch (e) {
    throw new Error(`Failed to read schema file at ${resolved}: ${e.message}`);
  }

  let schema;
  try {
    schema = JSON.parse(raw);
  } catch (e) {
    throw new Error(`Schema file at ${resolved} is not valid JSON: ${e.message}`);
  }

  if (typeof schema !== 'object' || schema === null || Array.isArray(schema)) {
    throw new Error(`Schema at ${resolved} must be a JSON object`);
  }

  if (!schema.type && !schema.$ref && !schema.anyOf && !schema.oneOf && !schema.allOf) {
    // Lenient: allow schemas without explicit type at root (e.g. pure $ref schemas)
  }

  return schema;
}

/**
 * List all .json files in a directory (non-recursive).
 */
function listSchemaFiles(dir) {
  try {
    return fs.readdirSync(dir)
      .filter(f => f.endsWith('.json'))
      .map(f => path.join(dir, f));
  } catch (e) {
    return [];
  }
}

/**
 * Merge additional definitions into a base schema.
 * Used for composing schemas from multiple fragments.
 */
function mergeDefinitions(baseSchema, extraDefs) {
  const merged = Object.assign({}, baseSchema);
  merged.definitions = Object.assign({}, baseSchema.definitions || {}, extraDefs);
  return merged;
}

module.exports = { loadSchema, listSchemaFiles, mergeDefinitions };
