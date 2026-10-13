#!/usr/bin/env node
'use strict';
const cp = require('child_process');
if (process.argv.length !== 4) { console.error('usage: replay-incidents.js INPUT OUTPUT'); process.exit(2); }
const r = cp.spawnSync('python3', ['/opt/replay/replay.py', process.argv[2], process.argv[3]], {stdio:'inherit'});
process.exit(r.status === null ? 1 : r.status);
