function summarize(events){let bytes=0,unicode=0;for(const e of events){const s=JSON.stringify(e);bytes+=Buffer.byteLength(s);for(const ch of s)if(ch.codePointAt(0)>127)unicode++}return {events:events.length,bytes,unicode}}
function histogram(events,key){const h={};for(const e of events){const v=String(e[key]);h[v]=(h[v]||0)+1}return Object.keys(h).sort().map(value=>({value,count:h[value]}))}
module.exports={summarize,histogram};
