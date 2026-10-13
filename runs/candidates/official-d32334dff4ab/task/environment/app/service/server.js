'use strict';

const http = require('http');
const path = require('path');
const { createApp } = require('./routes');

const PORT = parseInt(process.env.PORT || '4000', 10);
const HOST = process.env.HOST || '0.0.0.0';

// Initialise the policy engine before accepting connections
const policyModule = path.resolve('/app/policy/policy.js');
const policy = require(policyModule);

async function main() {
  await policy.init();

  const app = createApp(policy);
  const server = http.createServer(app);

  server.keepAliveTimeout = 65_000;
  server.headersTimeout = 66_000;

  await new Promise((resolve, reject) => {
    server.listen(PORT, HOST, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });

  console.log(`[server] snippet-eval-service listening on ${HOST}:${PORT}`);
  console.log(`[server] policy engine ready`);

  // Graceful shutdown
  const shutdown = async (signal) => {
    console.log(`[server] received ${signal}, shutting down`);
    await new Promise((r) => server.close(r));
    await policy.close();
    process.exit(0);
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT',  () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error('[server] fatal startup error', err);
  process.exit(1);
});
