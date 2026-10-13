#!/usr/bin/env node
const fs=require('fs'),{sealBatch}=require('../src');const a=process.argv,e=JSON.parse(fs.readFileSync(a[a.indexOf('--events')+1])),k=JSON.parse(fs.readFileSync(a[a.indexOf('--keys')+1]));process.stdout.write(JSON.stringify(sealBatch(e,k))+'\n');
