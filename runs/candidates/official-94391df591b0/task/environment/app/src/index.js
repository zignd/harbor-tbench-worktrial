'use strict';

const path = require('path');
const { parseArgs, validateConfig } = require('./config');
const { Logger } = require('./logger');
const { runPipeline } = require('./pipeline');
const { formatDuration } = require('./utils');

const DEFAULT_SCHEMA = '/app/schema.json';

async function main() {
  const config = validateConfig(parseArgs(process.argv));
  const logger = new Logger(config.logLevel);

  logger.info('Log ingestion pipeline starting', {
    input: config.input,
    output: config.output,
    schema: config.schema,
  });

  const schemaPath = config.schema || DEFAULT_SCHEMA;
  const startMs = Date.now();

  let summary;
  try {
    summary = await runPipeline(
      config.input,
      config.output,
      schemaPath,
      logger,
      {
        batchSize: config.batchSize,
        dryRun: config.dryRun,
      }
    );
  } catch (err) {
    logger.error('Pipeline failed', { error: err.message });
    process.exit(1);
  }

  const elapsed = Date.now() - startMs;
  logger.info('Pipeline complete', {
    accepted: summary.acceptedRecords,
    rejected: summary.rejectedRecords,
    parseErrors: summary.parseErrors,
    total: summary.totalRecords,
    acceptedPct: summary.acceptedRatePct + '%',
    throughput: summary.throughputRps + ' rec/s',
    duration: formatDuration(elapsed),
  });

  if (config.verbose && summary.topValidationErrors.length > 0) {
    logger.info('Top validation error reasons', { errors: summary.topValidationErrors });
  }
}

main().catch(err => {
  process.stderr.write('Fatal: ' + err.message + '\n');
  process.exit(1);
});
