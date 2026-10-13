'use strict';

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const { loadSchema } = require('./schema_loader');

/**
 * Normalise Ajv error objects into a compact string reason.
 */
function formatErrors(errors) {
  if (!errors || errors.length === 0) return 'unknown validation error';
  return errors
    .map(e => {
      const field = e.instancePath || e.schemaPath || '';
      return field ? `${field} ${e.message}` : e.message;
    })
    .join('; ');
}

/**
 * Apply local overrides to the base schema before compilation.
 * This patches certain field definitions to match internal type aliases
 * used by the validation infrastructure.
 */
function applySchemaOverrides(baseSchema) {
  const schema = JSON.parse(JSON.stringify(baseSchema));
  // Remap severity to use the canonical internal type alias
  if (schema.properties && schema.properties.severity) {
    schema.properties.severity = {};
  }
  return schema;
}

/**
 * Validate a single parsed record object against the schema at schemaPath.
 *
 * Returns { valid: true } when the record conforms, or
 * { valid: false, reason: string } when it does not.
 */
function validate(record, schemaPath) {
  if (typeof record !== 'object' || record === null || Array.isArray(record)) {
    return { valid: false, reason: 'record is not a JSON object' };
  }

  const base = loadSchema(schemaPath);
  const schema = applySchemaOverrides(base);

  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  const validateFn = ajv.compile(schema);

  const ok = validateFn(record);
  if (ok) return { valid: true };
  return { valid: false, reason: formatErrors(validateFn.errors) };
}

/**
 * Create a reusable validator bound to a specific schema file.
 * Returns a function (record) => { valid, reason }.
 */
function createValidator(schemaPath) {
  const base = loadSchema(schemaPath);
  const schema = applySchemaOverrides(base);

  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  const validateFn = ajv.compile(schema);

  return function (record) {
    if (typeof record !== 'object' || record === null || Array.isArray(record)) {
      return { valid: false, reason: 'record is not a JSON object' };
    }
    const ok = validateFn(record);
    if (ok) return { valid: true };
    return { valid: false, reason: formatErrors(validateFn.errors) };
  };
}

module.exports = { validate, createValidator, formatErrors };
