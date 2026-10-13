#!/usr/bin/env node
const fs=require('fs'),rs=JSON.parse(fs.readFileSync(process.argv[2]));let last=-Infinity;for(const r of rs){if(r.effectiveAt<last)process.exit(2);last=r.effectiveAt}process.stdout.write('rotation schedule valid\n');
