#!/usr/bin/env node
// Initial utility supplied with the deployment.
const fs=require('fs'),path=require('path');
function cfg(){let a=process.argv, c={}; for(let i=2;i<a.length;i++) if(a[i]=='--config') c=JSON.parse(fs.readFileSync(a[++i])); else if(a[i]=='--input') c.input=a[++i]; else if(a[i]=='--output') c.output=a[++i]; return c}
function main(){const c=cfg(); if(!c.input||!c.output) throw Error('config required'); let rows=new Map(), files=fs.readdirSync(c.input).filter(x=>x.startsWith('events-')); for(const f of files){let tx={}; for(const l of fs.readFileSync(path.join(c.input,f),'utf8').split('\n')){let p=l.split('\t'); if(p[0]=='O'){let k=p[3]+'\0'+p[4]; if(p[5]=='delete')rows.delete(k);else rows.set(k,{table:p[3],key:p[4],value:JSON.parse(p[6])})}}} let out=[...rows.values()].sort((a,b)=>a.table.localeCompare(b.table)||a.key.localeCompare(b.key)).map(JSON.stringify).join('\n')+'\n';fs.writeFileSync(c.output,out)}
try{main()}catch(e){console.error(e.message);process.exit(1)}
