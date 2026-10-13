'use strict';

const fs = require('fs');
const path = require('path');
const { createLogger } = require('./logger');

const log = createLogger('schema_loader');

function loadSchema(schemaPath) {
  const resolved = path.resolve(schemaPath);
  log.debug('loading schema', { path: resolved });
  let raw;
  try {
    raw = fs.readFileSync(resolved, 'utf8');
  } catch (err) {
    throw new Error(`Failed to read schema file at ${resolved}: ${err.message}`);
  }
  let schema;
  try {
    schema = JSON.parse(raw);
  } catch (err) {
    throw new Error(`Failed to parse schema JSON at ${resolved}: ${err.message}`);
  }
  if (typeof schema !== 'object' || schema === null) {
    throw new Error(`Schema at ${resolved} is not a JSON object`);
  }
  log.debug('schema loaded', { title: schema.title, required: schema.required });
  return schema;
}

function validateSchemaStructure(schema) {
  const warnings = [];
  if (!schema['$schema']) {
    warnings.push('Schema missing $schema declaration');
  }
  if (!schema.type) {
    warnings.push('Schema missing top-level type');
  }
  if (!schema.required || !Array.isArray(schema.required)) {
    warnings.push('Schema missing required array');
  }
  if (!schema.properties || typeof schema.properties !== 'object') {
    warnings.push('Schema missing properties');
  }
  return warnings;
}

function resolveSchemaRefs(schema) {
  // Walk schema and collect all $ref targets for diagnostic purposes
  const refs = [];
  function walk(node, path) {
    if (typeof node !== 'object' || node === null) return;
    if (Array.isArray(node)) {
      node.forEach((item, i) => walk(item, `${path}[${i}]`));
      return;
    }
    for (const [key, value] of Object.entries(node)) {
      if (key === '$ref' && typeof value === 'string') {
        refs.push({ ref: value, path });
      } else {
        walk(value, `${path}.${key}`);
      }
    }
  }
  walk(schema, '#');
  return refs;
}

module.exports = { loadSchema, validateSchemaStructure, resolveSchemaRefs };
