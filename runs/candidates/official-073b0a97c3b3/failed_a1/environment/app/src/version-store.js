'use strict';
const logger = require('./logger');

class VersionStore {
  constructor() {
    this.stableVersion = 'payments-v1';
    this.canaryVersion = 'payments-v2';
    this.canaryWeight = 0.2;
    logger.info({ event: 'version-store-init', stableVersion: this.stableVersion, canaryVersion: this.canaryVersion });
  }

  getStableVersion() {
    return this.stableVersion;
  }

  getCanaryVersion() {
    return this.canaryVersion;
  }

  getCanaryWeight() {
    return this.canaryWeight;
  }

  setCanaryWeight(w) {
    this.canaryWeight = w;
    logger.info({ event: 'canary-weight-updated', weight: w });
  }

  promote() {
    logger.info({ event: 'version-promoted', from: this.canaryVersion, to: 'stable' });
    this.stableVersion = this.canaryVersion;
    this.canaryVersion = null;
    this.canaryWeight = 0;
  }

  rollback() {
    logger.info({ event: 'version-rolledback', canary: this.canaryVersion });
    this.canaryWeight = 0;
  }
}

module.exports = new VersionStore();
