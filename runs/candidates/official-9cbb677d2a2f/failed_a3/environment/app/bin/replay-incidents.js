#!/usr/bin/env node
'use strict';
const cp = require('child_process');
const args = process.argv.slice(2);
let input = null, output = null;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--input') input = args[++i];
  else if (args[i] === '--output') output = args[++i];
}
if (!input || !output) { console.error('usage: replay-incidents.js --input INPUT --output OUTPUT'); process.exit(2); }
const r = cp.spawnSync('python3', [__dirname + '/../lib/replay.py', '--input', input, '--output', output], {stdio:'inherit'});
process.exit(r.status === null ? 1 : r.status);
