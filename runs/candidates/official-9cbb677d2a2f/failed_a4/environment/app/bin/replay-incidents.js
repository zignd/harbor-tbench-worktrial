#!/usr/bin/env node
const fs=require('fs'),{spawnSync}=require('child_process');
const [,,input,output]=process.argv;
if(!input||!output){console.error('usage: replay-incidents INPUT OUTPUT');process.exit(2)}
const r=spawnSync('python3',[__dirname+'/../lib/replay.py',input,output],{stdio:'inherit'});process.exit(r.status??1)
