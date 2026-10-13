const crypto=require('crypto');
function partition(events,size){if(!Number.isInteger(size)||size<1)throw Error('invalid size');const out=[];for(let i=0;i<events.length;i+=size)out.push(events.slice(i,i+size));return out}
function stableId(value){return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0,16)}
module.exports={partition,stableId};
