'use strict';

/**
 * policy.js - Per-user rate limiting and CPU-time quota enforcement.
 *
 * Each user is allowed at most CPU_BUDGET_MS milliseconds of evaluation
 * time within any rolling WINDOW_SECS second window.
 *
 * The rolling window is tracked in an in-memory Map for fast lookups.
 * Accepted requests are also persisted to the SQLite database via db.js.
 */

const vm = require('vm');
const path = require('path');
const { DB } = require('./db');

const CPU_BUDGET_MS  = 500;   // max CPU-ms per user per rolling window
const WINDOW_SECS   = 60;    // rolling window length in seconds
const EVAL_TIMEOUT  = 2000;  // vm execution hard timeout (ms)

// In-memory per-user state
// Map<userId, { entries: Array<{ts: number, cpu_ms: number}> }>
const userState = new Map();

let db;

async function init() {
  db = new DB(path.resolve('/app/data/records.db'));
  await db.init();
  console.log('[policy] initialised, db ready');
}

async function close() {
  if (db) await db.close();
}

/**
 * Returns the sum of cpu_ms for entries within the rolling window.
 * Mutates the entries array to drop stale records.
 */
function windowTotal(entries) {
  const cutoff = Date.now() - WINDOW_SECS * 1000;
  // Remove entries older than the window
  while (entries.length > 0 && entries[0].ts < cutoff) {
    entries.shift();
  }
  return entries.reduce((sum, e) => sum + e.cpu_ms, 0);
}

/**
 * Run a JavaScript snippet in an isolated vm context.
 * Returns { cpu_ms, output }.
 */
function runSnippet(code) {
  const sandbox = {
    console: {
      log: (...args) => { sandbox.__output = (sandbox.__output || '') + args.join(' ') + '\n'; },
    },
    __output: '',
    Math, JSON, parseInt, parseFloat, isNaN, isFinite,
    setTimeout: undefined, setInterval: undefined, clearTimeout: undefined,
  };

  vm.createContext(sandbox);

  const start = process.hrtime.bigint();
  try {
    vm.runInContext(code, sandbox, { timeout: EVAL_TIMEOUT });
  } catch (e) {
    // Swallow evaluation errors; we still record the CPU time
  }
  const elapsed = process.hrtime.bigint() - start;
  const cpu_ms = Number(elapsed) / 1_000_000;

  return { cpu_ms, output: sandbox.__output || '' };
}

/**
 * Evaluate a snippet for a user, enforcing the CPU budget.
 *
 * Returns { accepted, cpu_ms, output, message, window_total_ms }
 */
async function evaluate(user_id, code) {
  if (!userState.has(user_id)) {
    userState.set(user_id, { entries: [], total_cpu_ms: 0, request_count: 0 });
  }
  const state = userState.get(user_id);

  // Check the rolling window total BEFORE running the snippet
  const currentTotal = windowTotal(state.entries);

  if (currentTotal >= CPU_BUDGET_MS) {
    return {
      accepted: false,
      message: `CPU budget exhausted: ${currentTotal.toFixed(2)} ms used of ${CPU_BUDGET_MS} ms`,
      window_total_ms: currentTotal,
    };
  }

  // Run the snippet (this takes real time - window is NOT locked during execution)
  const { cpu_ms, output } = runSnippet(code);

  const newTotal = currentTotal + cpu_ms;
  if (newTotal > CPU_BUDGET_MS) {
    // Snippet pushed us over budget - reject after the fact
    return {
      accepted: false,
      message: `Execution exceeded CPU budget: would reach ${newTotal.toFixed(2)} ms`,
      window_total_ms: currentTotal,
    };
  }

  // Record the accepted request in memory
  const ts = Date.now();
  state.entries.push({ ts, cpu_ms });
  state.total_cpu_ms += cpu_ms;
  state.request_count += 1;

  // Persist to database asynchronously
  await db.record(user_id, ts, cpu_ms, 1);

  return { accepted: true, cpu_ms, output };
}

/**
 * Return aggregate stats for a user.
 * Reads from the in-memory state (fast path).
 */
async function getStats(user_id) {
  const state = userState.get(user_id);
  if (!state) {
    return { user_id, total_cpu_ms: 0, request_count: 0 };
  }
  // Refresh the rolling window
  windowTotal(state.entries);
  return {
    user_id,
    total_cpu_ms: state.total_cpu_ms,
    request_count: state.request_count,
  };
}

module.exports = { init, close, evaluate, getStats };
