#!/usr/bin/env node
const fs=require('fs'),{summarize}=require('../src/pipeline/metrics');const rows=fs.readFileSync(process.argv[2]||0,'utf8').split(/\n/).filter(Boolean).map(JSON.parse);process.stdout.write(JSON.stringify(summarize(rows))+'\n');
