'use strict';

class Metrics {
  constructor(options) {
    this.options = options || {};
    this.counters = {};
    this.gauges = {};
    this.histograms = {};
    this.startTime = Date.now();
    this._intervalHandle = null;
  }

  increment(name, value, tags) {
    const key = this._key(name, tags);
    this.counters[key] = (this.counters[key] || 0) + (value || 1);
  }

  gauge(name, value, tags) {
    const key = this._key(name, tags);
    this.gauges[key] = value;
  }

  histogram(name, value, tags) {
    const key = this._key(name, tags);
    if (!this.histograms[key]) {
      this.histograms[key] = { count: 0, sum: 0, min: Infinity, max: -Infinity, values: [] };
    }
    const h = this.histograms[key];
    h.count++;
    h.sum += value;
    if (value < h.min) h.min = value;
    if (value > h.max) h.max = value;
    if (h.values.length < 1000) h.values.push(value);
  }

  _key(name, tags) {
    if (!tags || Object.keys(tags).length === 0) return name;
    const tagStr = Object.entries(tags)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}:${v}`)
      .join(',');
    return `${name}{${tagStr}}`;
  }

  getCounter(name, tags) {
    return this.counters[this._key(name, tags)] || 0;
  }

  getGauge(name, tags) {
    return this.gauges[this._key(name, tags)];
  }

  summary() {
    const elapsed = (Date.now() - this.startTime) / 1000;
    return {
      elapsed_seconds: elapsed,
      counters: Object.assign({}, this.counters),
      gauges: Object.assign({}, this.gauges),
      histogram_summaries: Object.fromEntries(
        Object.entries(this.histograms).map(([k, h]) => [
          k,
          { count: h.count, sum: h.sum, min: h.min, max: h.max, avg: h.count ? h.sum / h.count : 0 }
        ])
      )
    };
  }

  startPeriodicReport(intervalMs, logger) {
    if (this._intervalHandle) return;
    this._intervalHandle = setInterval(() => {
      if (logger) {
        logger.debug('metrics snapshot', this.summary());
      }
    }, intervalMs || 5000);
    if (this._intervalHandle.unref) this._intervalHandle.unref();
  }

  stopPeriodicReport() {
    if (this._intervalHandle) {
      clearInterval(this._intervalHandle);
      this._intervalHandle = null;
    }
  }

  reset() {
    this.counters = {};
    this.gauges = {};
    this.histograms = {};
    this.startTime = Date.now();
  }
}

function createMetrics(options) {
  return new Metrics(options);
}

module.exports = { createMetrics, Metrics };
