'use strict';

/**
 * rollback-decider: evaluates health window state and returns a decision.
 * Returns { decision: 'promote' | 'rollback' | 'hold' }
 */
function decide(config) {
  // stub: always promotes regardless of health state
  return { decision: 'promote' };
}

module.exports = { decide };
