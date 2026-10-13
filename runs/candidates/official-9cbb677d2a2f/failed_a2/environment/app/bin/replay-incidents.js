#!/usr/bin/env node
const cp=require('child_process');
const a=process.argv.slice(2); const i=a.indexOf('--input'),o=a.indexOf('--output');
if(i<0||o<0||!a[i+1]||!a[o+1]){console.error('usage: replay-incidents.js --input INPUT --output OUTPUT');process.exit(2)}
const r=cp.spawnSync('python3',['/opt/incident-replay/lib/replay.py','--input',a[i+1],'--output',a[o+1]],{stdio:'inherit'}); process.exit(r.status===null?1:r.status);
