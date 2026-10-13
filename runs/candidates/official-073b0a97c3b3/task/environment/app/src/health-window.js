'use strict';
const logger = require('./logger');

class HealthWindow {
  constructor() {
    this.samples = [];
    this.totalWeight = 0;
    this.errorWeight = 0;
    this.sampleCount = 0;
    logger.info({ event: 'health-window-init' });
  }

  addSample(statusCode, weight, originalStatusCode) {
    const isError = (originalStatusCode !== undefined ? originalStatusCode : statusCode) >= 500;
    this.samples.push({ statusCode, weight, isError, originalStatusCode });
    this.totalWeight += weight;
    if (isError) this.errorWeight += weight;
    this.sampleCount++;
    logger.debug({
      event: 'sample-added',
      statusCode,
      originalStatusCode,
      weight,
      isError,
      sampleCount: this.sampleCount,
      totalWeight: this.totalWeight,
      errorWeight: this.errorWeight
    });
  }

  getSampleCount() {
    return this.sampleCount;
  }

  getSampledErrorRate() {
    if (this.totalWeight === 0) return 0;
    return this.errorWeight / this.totalWeight;
  }

  reset() {
    logger.warn({ event: 'health-window-reset', hadSamples: this.sampleCount });
    this.samples = [];
    this.totalWeight = 0;
    this.errorWeight = 0;
    this.sampleCount = 0;
  }
}

module.exports = HealthWindow;
