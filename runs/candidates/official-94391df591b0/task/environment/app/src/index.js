'use strict';

const { buildConfig } = require('./config');
const { createLogger } = require('./logger');
const { loadSchema, validateSchemaStructure } = require('./schema_loader');
const { createValidator } = require('./validator');
const { createPipeline } = require('./pipeline');
const { createMetrics } = require('./metrics');

const log = createLogger('index');

async function main() {
  const config = buildConfig();
  log.setLevel(config.logLevel);

  log.info('log ingestion pipeline starting', {
    version: '2.1.0',
    inputFile: config.inputFile,
    outputFile: config.outputFile,
    schemaPath: config.schemaPath,
  });

  // Load and validate schema
  let schema;
  try {
    schema = loadSchema(config.schemaPath);
  } catch (err) {
    log.error('failed to load schema', { error: err.message });
    process.exit(1);
  }

  const schemaWarnings = validateSchemaStructure(schema);
  if (schemaWarnings.length > 0) {
    for (const w of schemaWarnings) {
      log.warn('schema warning', { warning: w });
    }
  }

  // Initialise metrics
  const metrics = createMetrics();
  if (config.metricsEnabled) {
    metrics.startPeriodicReport(config.metricsIntervalMs, log);
  }

  // Build validator
  const validator = createValidator(schema, {
    strictMode: config.strictMode,
  });

  log.info('validator initialised', {
    schemaTitle: schema.title || '(untitled)',
    requiredFields: schema.required || [],
  });

  // Build and run pipeline
  const pipeline = createPipeline(config, validator);

  let summary;
  try {
    summary = await pipeline.run();
  } catch (err) {
    log.error('pipeline failed', { error: err.message, stack: err.stack });
    metrics.stopPeriodicReport();
    process.exit(1);
  }

  metrics.stopPeriodicReport();

  const validatorStats = validator.getStats();
  log.info('validation summary', validatorStats);
  log.info('ingestion complete', {
    accepted: summary.accepted,
    rejected: summary.rejected,
    parseErrors: summary.parseErrors,
    elapsed: summary.elapsed,
    outputFile: config.outputFile,
  });

  const acceptRate = summary.lines > 0
    ? ((summary.accepted / summary.lines) * 100).toFixed(1)
    : '0.0';
  log.info(`acceptance rate: ${acceptRate}%`);

  process.exit(0);
}

main().catch(err => {
  process.stderr.write(`Unhandled error: ${err.message}\n${err.stack}\n`);
  process.exit(1);
});
