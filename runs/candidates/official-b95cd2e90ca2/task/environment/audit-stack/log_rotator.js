'use strict';
// Log Rotator - manages rotation window indices and triggers log rotation.
const fs = require('fs');
const path = require('path');

const DEFAULT_STATE = {
  lastWindowIndex: -1,
  lastWindowStartMs: 0,
  windowStartMap: {},
};

class LogRotator {
  constructor(config) {
    this.config = config;
    this.stateFile = config.logging.stateFile;
    this.recordsPerWindow = config.rotation.recordsPerWindow;
    this.windowDurationMs = config.rotation.windowDurationMs;
    this.state = this._loadState();
    this.currentRecordCount = 0;
    this.currentWindowIndex = this.state.lastWindowIndex;
    this.currentWindowStartMs = this.state.lastWindowStartMs;
    this.windowStartMap = this.state.windowStartMap || {};
  }

  _loadState() {
    try {
      const data = fs.readFileSync(this.stateFile, 'utf8');
      return { ...DEFAULT_STATE, ...JSON.parse(data) };
    } catch (e) {
      return { ...DEFAULT_STATE };
    }
  }

  _saveState() {
    const state = {
      lastWindowIndex: this.currentWindowIndex,
      lastWindowStartMs: this.currentWindowStartMs,
      windowStartMap: this.windowStartMap,
    };
    fs.writeFileSync(this.stateFile, JSON.stringify(state, null, 2));
  }

  /**
   * Check if a new rotation window should be started.
   * Returns true if the current batch should be flushed.
   */
  shouldRotate(nowMs) {
    if (this.currentWindowIndex < 0) return true;
    if (this.currentRecordCount >= this.recordsPerWindow) return true;
    if (nowMs - this.currentWindowStartMs >= this.windowDurationMs) return true;
    return false;
  }

  /**
   * Advance to the next rotation window.
   * @param {number} nowMs - Current timestamp
   * @returns {number} The new window index
   */
  advanceWindow(nowMs) {
    this.currentWindowIndex += 1;
    this.currentWindowStartMs = nowMs;
    this.currentRecordCount = 0;
    this.windowStartMap[this.currentWindowIndex] = nowMs;
    this._saveState();
    return this.currentWindowIndex;
  }

  /**
   * Record that a record was added to the current window.
   */
  recordAdded() {
    this.currentRecordCount += 1;
  }

  /**
   * Get the current window index.
   */
  getWindowIndex() {
    return this.currentWindowIndex;
  }

  /**
   * Get the current window start timestamp.
   */
  getWindowStartMs() {
    return this.currentWindowStartMs;
  }

  /**
   * Get the map of all window indices to their start timestamps.
   */
  getWindowStartMap() {
    return { ...this.windowStartMap };
  }

  /**
   * Get the number of records in the current window.
   */
  getCurrentRecordCount() {
    return this.currentRecordCount;
  }

  /**
   * Force-save state (call before exit).
   */
  flush() {
    this._saveState();
  }
}

module.exports = { LogRotator };
