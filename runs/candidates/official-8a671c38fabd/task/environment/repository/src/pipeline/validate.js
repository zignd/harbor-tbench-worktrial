function validateEvent(e){if(!e||typeof e!=='object'||Array.isArray(e))return false;if(!Number.isInteger(e.timestamp))return false;return Object.prototype.hasOwnProperty.call(e,'payload')}
function validateRotation(r){return !!r&&typeof r.id==='string'&&Number.isInteger(r.effectiveAt)&&typeof r.key==='string'}
function validateBatch(events,rotations){if(!Array.isArray(events)||!Array.isArray(rotations)||!rotations.every(validateRotation))return false;return events.every(validateEvent)}
module.exports={validateEvent,validateRotation,validateBatch};
