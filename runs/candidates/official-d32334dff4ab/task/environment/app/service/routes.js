'use strict';

const express = require('express');
const vm = require('vm');

/**
 * createApp - returns an Express application wired to the given policy engine.
 *
 * POST /eval   { user_id: string, code: string } => { accepted: bool, cpu_ms: number, message: string }
 * GET  /stats/:user_id => { user_id: string, total_cpu_ms: number, request_count: number }
 * GET  /health => { status: 'ok' }
 */
function createApp(policy) {
  const app = express();
  app.use(express.json({ limit: '64kb' }));

  // Health check
  app.get('/health', (_req, res) => {
    res.json({ status: 'ok', ts: Date.now() });
  });

  // Evaluate a JavaScript snippet
  app.post('/eval', async (req, res) => {
    const { user_id, code } = req.body || {};

    if (!user_id || typeof user_id !== 'string' || user_id.length > 128) {
      return res.status(400).json({ error: 'user_id must be a non-empty string <= 128 chars' });
    }
    if (!code || typeof code !== 'string') {
      return res.status(400).json({ error: 'code must be a non-empty string' });
    }
    if (code.length > 4096) {
      return res.status(400).json({ error: 'code must be <= 4096 chars' });
    }

    try {
      const result = await policy.evaluate(user_id, code);
      if (!result.accepted) {
        return res.status(429).json({
          accepted: false,
          message: result.message || 'Rate limit exceeded',
          window_total_ms: result.window_total_ms,
        });
      }
      return res.status(200).json({
        accepted: true,
        cpu_ms: result.cpu_ms,
        output: result.output,
      });
    } catch (err) {
      console.error('[routes] /eval error', err);
      return res.status(500).json({ error: 'internal server error' });
    }
  });

  // Get per-user stats
  app.get('/stats/:user_id', async (req, res) => {
    const { user_id } = req.params;
    if (!user_id || user_id.length > 128) {
      return res.status(400).json({ error: 'invalid user_id' });
    }
    try {
      const stats = await policy.getStats(user_id);
      return res.status(200).json(stats);
    } catch (err) {
      console.error('[routes] /stats error', err);
      return res.status(500).json({ error: 'internal server error' });
    }
  });

  // 404 handler
  app.use((_req, res) => {
    res.status(404).json({ error: 'not found' });
  });

  return app;
}

module.exports = { createApp };
