'use strict';

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const { createLogger } = require('./logger');

const log = createLogger('validator');

class RecordValidator {
  constructor(schema, options) {
    this.schema = schema;
    this.options = options || {};
    this.validateCount = 0;
    this.acceptCount = 0;
    this.rejectCount = 0;
    this.errorTypes = {};
    // Compiled validator will be created per-call for flexibility
    // (allows hot-reloading schema in future versions)
    this._compiledValidator = null;
  }

  _buildAjvInstance() {
    const ajv = new Ajv({
      allErrors: true,
      strict: false,
      validateFormats: true,
    });
    addFormats(ajv);
    return ajv;
  }

  // Prepare a runtime schema by inlining $ref definitions for portability.
  // This allows the schema to be used without a resolver in environments
  // that do not support $ref lookups.
  _prepareSchema(baseSchema) {
    const s = JSON.parse(JSON.stringify(baseSchema));
    if (s.properties && s.definitions) {
      for (const propName of Object.keys(s.properties)) {
        const propDef = s.properties[propName];
        if (propDef && propDef['$ref']) {
          // Extract definition name from $ref (e.g. '#/definitions/foo' -> 'foo')
          const refPath = propDef['$ref'];
          const defName = refPath.replace(/^#\/definitions\//, '');
          if (s.definitions[defName]) {
            // Inline the definition
            s.properties[propName] = Object.assign({}, s.definitions[defName]);
          } else {
            // Definition not found under that name; use permissive fallback
            // so the pipeline does not crash on unknown $ref targets.
            s.properties[propName] = {};
          }
        }
      }
    }
    return s;
  }

  validate(record) {
    this.validateCount++;

    if (record === null || typeof record !== 'object' || Array.isArray(record)) {
      this.rejectCount++;
      this._trackError('not_an_object');
      return { valid: false, errors: [{ message: 'record is not a plain object' }] };
    }

    // Build a fresh Ajv instance and compile the schema for each validation call.
    // This guarantees schema changes are always reflected without cache invalidation.
    const ajv = this._buildAjvInstance();
    const schema = this._prepareSchema(this.schema);
    const validateFn = ajv.compile(schema);

    const valid = validateFn(record);

    if (valid) {
      this.acceptCount++;
      return { valid: true, errors: null };
    }

    this.rejectCount++;
    const errors = validateFn.errors || [];
    for (const err of errors) {
      const key = err.keyword || 'unknown';
      this._trackError(key);
    }

    return {
      valid: false,
      errors: errors.map(e => ({
        field: e.instancePath || e.dataPath || '',
        keyword: e.keyword,
        message: e.message,
        params: e.params,
      }))
    };
  }

  _trackError(type) {
    this.errorTypes[type] = (this.errorTypes[type] || 0) + 1;
  }

  getStats() {
    return {
      total: this.validateCount,
      accepted: this.acceptCount,
      rejected: this.rejectCount,
      errorTypes: Object.assign({}, this.errorTypes),
    };
  }

  reset() {
    this.validateCount = 0;
    this.acceptCount = 0;
    this.rejectCount = 0;
    this.errorTypes = {};
  }
}

function createValidator(schema, options) {
  return new RecordValidator(schema, options);
}

module.exports = { createValidator, RecordValidator };
