'use strict';
const logger = require('./logger');

const PHASES = ['warming', 'canary', 'promoted', 'rolledback'];

class DeploymentStateMachine {
  constructor() {
    this.phase = 'warming';
    this.promotedAt = null;
    this.rolledbackAt = null;
    logger.info({ event: 'deployment-sm-init', phase: this.phase });
  }

  getPhase() {
    return this.phase;
  }

  transition(newPhase) {
    if (!PHASES.includes(newPhase)) {
      throw new Error(`Invalid phase: ${newPhase}`);
    }
    const old = this.phase;
    this.phase = newPhase;
    if (newPhase === 'promoted') this.promotedAt = Date.now();
    if (newPhase === 'rolledback') this.rolledbackAt = Date.now();
    logger.info({ event: 'phase-transition', from: old, to: newPhase });
  }

  canAdvance() {
    return this.phase !== 'promoted' && this.phase !== 'rolledback';
  }

  forceRollback() {
    const old = this.phase;
    this.phase = 'rolledback';
    this.rolledbackAt = Date.now();
    logger.warn({ event: 'forced-rollback', from: old });
  }
}

module.exports = new DeploymentStateMachine();
