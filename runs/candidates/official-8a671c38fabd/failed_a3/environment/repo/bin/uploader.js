#!/usr/bin/env node
const fs=require('fs'),{sealBatch}=require('../src/seal'),a=process.argv,i=a.indexOf('--input'),k=a.indexOf('--keys');let e=fs.readFileSync(a[i+1],'utf8').trim().split('\n').filter(Boolean).map(JSON.parse),r=JSON.parse(fs.readFileSync(a[k+1]));console.log(JSON.stringify(sealBatch(e,r)));
