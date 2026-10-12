'use strict';

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

class Logger {
  constructor(name, level) {
    this.name = name || 'app';
    this.level = level || 'info';
    this.levelNum = LEVELS[this.level] !== undefined ? LEVELS[this.level] : 1;
  }

  _shouldLog(level) {
    return (LEVELS[level] || 0) >= this.levelNum;
  }

  _format(level, msg, meta) {
    const ts = new Date().toISOString();
    const base = `[${ts}] [${level.toUpperCase()}] [${this.name}] ${msg}`;
    if (meta && Object.keys(meta).length > 0) {
      try {
        return base + ' ' + JSON.stringify(meta);
      } catch (_) {
        return base;
      }
    }
    return base;
  }

  debug(msg, meta) {
    if (this._shouldLog('debug')) {
      process.stderr.write(this._format('debug', msg, meta) + '\n');
    }
  }

  info(msg, meta) {
    if (this._shouldLog('info')) {
      process.stderr.write(this._format('info', msg, meta) + '\n');
    }
  }

  warn(msg, meta) {
    if (this._shouldLog('warn')) {
      process.stderr.write(this._format('warn', msg, meta) + '\n');
    }
  }

  error(msg, meta) {
    if (this._shouldLog('error')) {
      process.stderr.write(this._format('error', msg, meta) + '\n');
    }
  }

  child(name) {
    return new Logger(`${this.name}:${name}`, this.level);
  }

  setLevel(level) {
    this.level = level;
    this.levelNum = LEVELS[level] !== undefined ? LEVELS[level] : 1;
  }
}

function createLogger(name, level) {
  return new Logger(name, level);
}

module.exports = { createLogger, Logger, LEVELS };
