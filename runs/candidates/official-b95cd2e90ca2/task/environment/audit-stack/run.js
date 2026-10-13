'use strict';
// CLI entry point for the encrypted audit log stack.
// Generates metric records, rotates them into encrypted log windows,
// and optionally verifies the produced log files.
//
// Usage:
//   node run.js [options]
//
// Options:
//   --count N          Total metric records to generate (default: 200)
//   --start-index I    First window index (default: 0)
//   --start-ts T       Window 0 start timestamp in ms (default: 1700000010000)
//   --log-dir DIR      Output directory for log files
//   --verify           Verify logs after generation; exit 1 if any fail
//   --dashboard FILE   Write JSON verification dashboard to FILE

const fs = require('fs');
const path = require('path');
const { generateBatch } = require('./metrics_collector');
const { encryptWindow } = require('./encryptor');
const { verifyLogFile } = require('./verifier');
const skm = require('./session_key_manager');

const CONFIG_PATH = path.join(__dirname, 'config.json');

function parseArgs(argv) {
  const args = {
    count: 200,
    startIndex: 0,
    startTs: 1700000010000,
    logDir: null,
    verify: false,
    dashboardOut: null,
  };
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--count') args.count = parseInt(argv[++i], 10);
    else if (arg === '--start-index') args.startIndex = parseInt(argv[++i], 10);
    else if (arg === '--start-ts') args.startTs = parseInt(argv[++i], 10);
    else if (arg === '--log-dir') args.logDir = argv[++i];
    else if (arg === '--verify') args.verify = true;
    else if (arg === '--dashboard') args.dashboardOut = argv[++i];
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv);
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));

  const logDir = args.logDir || config.logging.logDir;
  fs.mkdirSync(logDir, { recursive: true });

  const { recordsPerWindow, windowDurationMs } = config.rotation;
  const { sampleIntervalMs, dbQueryLatencyBaseMs } = config.metrics;

  const windowStartTimes = {};
  const windowFiles = {};

  let seq = 0;
  let currentWindowIndex = args.startIndex;
  // Window starts are aligned to windowDurationMs boundaries to ensure
  // the sample logs do not exercise the salt boundary edge case.
  let windowStartMs = args.startTs;
  let batchRecords = [];

  for (let rec = 0; rec < args.count; rec++) {
    // Accumulate records into current window batch
    const recTs = windowStartMs + (batchRecords.length * sampleIntervalMs);
    const metric = generateBatch(1, seq, dbQueryLatencyBaseMs, recTs, sampleIntervalMs)[0];
    batchRecords.push(metric);
    seq++;

    // Flush window when batch is full
    if (batchRecords.length >= recordsPerWindow) {
      windowStartTimes[currentWindowIndex] = windowStartMs;
      const logFile = encryptWindow(logDir, currentWindowIndex, windowStartMs, batchRecords, config);
      windowFiles[currentWindowIndex] = logFile;

      // Advance to next window; start time aligned to next boundary
      currentWindowIndex++;
      windowStartMs = windowStartMs + windowDurationMs;
      batchRecords = [];
    }
  }

  // Flush any remaining records as the last partial window
  if (batchRecords.length > 0) {
    windowStartTimes[currentWindowIndex] = windowStartMs;
    const logFile = encryptWindow(logDir, currentWindowIndex, windowStartMs, batchRecords, config);
    windowFiles[currentWindowIndex] = logFile;
  }

  const finalWindowIndex = currentWindowIndex;

  // Persist state
  const stateFile = config.logging.stateFile;
  fs.mkdirSync(path.dirname(stateFile), { recursive: true });
  fs.writeFileSync(stateFile, JSON.stringify({
    lastWindowIndex: finalWindowIndex,
    lastWindowStartMs: windowStartMs,
    windowStartMap: windowStartTimes,
  }, null, 2));

  if (args.verify) {
    const results = [];
    for (const [widxStr, logFile] of Object.entries(windowFiles)) {
      const widx = parseInt(widxStr, 10);
      const wstart = windowStartTimes[widx] || 0;
      const r = verifyLogFile(logFile, wstart, config);
      results.push(r);
    }

    const dashboard = {
      generatedAt: new Date(args.startTs).toISOString(),
      totalWindows: results.length,
      passed: results.filter(r => r.ok).length,
      failed: results.filter(r => !r.ok).length,
      windows: results.map(r => ({
        windowIndex: r.windowIndex,
        status: r.ok ? 'pass' : 'fail',
        error: r.error || null,
        recordCount: r.records ? r.records.length : 0,
      })).sort((a, b) => a.windowIndex - b.windowIndex),
    };

    if (args.dashboardOut) {
      fs.writeFileSync(args.dashboardOut, JSON.stringify(dashboard, null, 2));
    } else {
      process.stdout.write(JSON.stringify(dashboard, null, 2) + '\n');
    }

    const allPassed = results.every(r => r.ok);
    process.exit(allPassed ? 0 : 1);
  } else {
    const lastIdx = finalWindowIndex;
    process.stdout.write(
      `Generated ${args.count} records across ${args.startIndex}-${lastIdx} (${lastIdx - args.startIndex + 1} windows)\n`
    );
  }
}

main();
