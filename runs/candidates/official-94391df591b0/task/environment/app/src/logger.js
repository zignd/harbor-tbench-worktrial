'use strict';

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

class Logger {
  constructor(level) {
    this.level = level || 'info';
    this.levelValue = LEVELS[this.level] !== undefined ? LEVELS[this.level] : 1;
  }

  _log(levelName, message, extra) {
    const levelValue = LEVELS[levelName];
    if (levelValue < this.levelValue) return;
    const ts = new Date().toISOString();
    let line = `[${ts}] [${levelName.toUpperCase()}] ${message}`;
    if (extra && typeof extra === 'object') {
      line += ' ' + JSON.stringify(extra);
    }
    if (levelName === 'error' || levelName === 'warn') {
      process.stderr.write(line + '\n');
    } else {
      process.stdout.write(line + '\n');
    }
  }

  debug(msg, extra) { this._log('debug', msg, extra); }
  info(msg, extra) { this._log('info', msg, extra); }
  warn(msg, extra) { this._log('warn', msg, extra); }
  error(msg, extra) { this._log('error', msg, extra); }

  child(context) {
    const child = new Logger(this.level);
    const parentLog = this._log.bind(this);
    child._log = (levelName, message, extra) => {
      const merged = Object.assign({}, context, extra || {});
      parentLog(levelName, message, Object.keys(merged).length ? merged : undefined);
    };
    return child;
  }
}

module.exports = { Logger };
