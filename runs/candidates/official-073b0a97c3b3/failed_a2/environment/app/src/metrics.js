'use strict';
const deployment = require('./deployment');
const config = require('./config');
const versionStore = require('./version-store');

function formatMetrics() {
  const phase = deployment.getPhase();
  const hw = config.healthWindow;
  const sampleCount = hw.getSampleCount();
  const errorRate = hw.getSampledErrorRate();

  const lines = [];
  lines.push('# HELP canary_phase Current canary phase (0=warming,1=canary,2=promoted,3=rolledback)');
  lines.push('# TYPE canary_phase gauge');
  const phaseMap = { warming: 0, canary: 1, promoted: 2, rolledback: 3 };
  lines.push(`canary_phase ${phaseMap[phase] !== undefined ? phaseMap[phase] : -1}`);

  lines.push('# HELP canary_sample_count Total samples in health window');
  lines.push('# TYPE canary_sample_count counter');
  lines.push(`canary_sample_count ${sampleCount}`);

  lines.push('# HELP canary_error_rate Weighted sampled error rate');
  lines.push('# TYPE canary_error_rate gauge');
  lines.push(`canary_error_rate ${errorRate.toFixed(6)}`);

  lines.push('# HELP canary_error_threshold Configured error threshold');
  lines.push('# TYPE canary_error_threshold gauge');
  lines.push(`canary_error_threshold ${config.errorThreshold}`);

  return lines.join('\n') + '\n';
}

module.exports = { formatMetrics };
