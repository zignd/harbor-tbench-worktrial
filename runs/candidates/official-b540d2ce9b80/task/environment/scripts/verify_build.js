#!/usr/bin/env node
// Verifies that the configured addon in webpack.config.js matches the Python
// preprocessor output for a generated set of module descriptors.
// Exits 0 on success, non-zero on mismatch.

const path = require("path");
const fs = require("fs");

function makeLCG(seed) {
  let s = seed >>> 0;
  return function() {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0xFFFFFFFF;
  };
}

const now = new Date();
const dateSeed = now.getFullYear() * 10000 + (now.getMonth() + 1) * 100 + now.getDate();
const rng = makeLCG(dateSeed);

const types = ["util", "lib", "app", "vendor"];
const boundaryScores = [0, 5, 15, 19, 20, 25, 35, 39, 40, 45, 55];

const descriptors = [];

const boundaryDescriptors = [
  { id: "verify-boundary-1",  type: "util", complexity_score: 19, has_side_effects: false },
  { id: "verify-boundary-2",  type: "util", complexity_score: 20, has_side_effects: false },
  { id: "verify-boundary-3",  type: "util", complexity_score: 0,  has_side_effects: false },
  { id: "verify-boundary-4",  type: "lib",  complexity_score: 50, has_side_effects: false },
  { id: "verify-boundary-5",  type: "lib",  complexity_score: 39, has_side_effects: true },
  { id: "verify-boundary-6",  type: "util", complexity_score: 39, has_side_effects: false },
  { id: "verify-boundary-7",  type: "util", complexity_score: 40, has_side_effects: false },
  { id: "verify-boundary-8",  type: "app",  complexity_score: 10, has_side_effects: false },
];
descriptors.push(...boundaryDescriptors);

for (let i = 0; i < 42; i++) {
  const typeIdx = Math.floor(rng() * types.length);
  const scoreIdx = Math.floor(rng() * boundaryScores.length);
  const sideEffects = rng() > 0.6;
  descriptors.push({
    id: `verify-gen-${i}`,
    type: types[typeIdx],
    complexity_score: boundaryScores[scoreIdx],
    has_side_effects: sideEffects
  });
}

function referenceProcess(desc) {
  const passes = [];
  const t = desc.type;
  const s = desc.complexity_score;
  const se = desc.has_side_effects;
  if ((t === "util" || t === "lib") && !se) passes.push("dead_code_elimination");
  if (s < 40) passes.push("const_folding");
  if (t === "lib" || (t === "util" && s < 20)) passes.push("scope_hoisting");
  return passes;
}

let optimizerFn;
try {
  const webpackConfig = require(path.join(process.cwd(), "webpack.config.js"));
  if (typeof webpackConfig === "function" && typeof webpackConfig.getOptimizer === "function") {
    optimizerFn = webpackConfig.getOptimizer();
  } else if (typeof webpackConfig.getOptimizer === "function") {
    optimizerFn = webpackConfig.getOptimizer();
  } else {
    throw new Error("webpack.config.js must export getOptimizer() (as function export or object export)");
  }
} catch (e) {
  console.error("Error loading webpack.config.js:", e.message);
  process.exit(1);
}

let failures = 0;
let tested = 0;

for (const desc of descriptors) {
  const expected = referenceProcess(desc);
  let actual;
  try {
    const result = optimizerFn.process(desc);
    actual = result.passes;
  } catch (e) {
    console.error(`Error processing ${desc.id}:`, e.message);
    failures++;
    continue;
  }

  const expectedStr = expected.slice().sort().join(",");
  const actualStr = actual.slice().sort().join(",");

  if (expectedStr !== actualStr) {
    console.error(`MISMATCH for ${desc.id} (type=${desc.type}, complexity=${desc.complexity_score}, side_effects=${desc.has_side_effects})`);
    console.error(`  expected: [${expected.join(", ")}]`);
    console.error(`  actual:   [${actual.join(", ")}]`);
    failures++;
  }
  tested++;
}

console.log(`Tested ${tested} module descriptors.`);
if (failures > 0) {
  console.error(`FAILED: ${failures} mismatches found.`);
  process.exit(1);
} else {
  console.log("All pass assignments match. OK.");
  process.exit(0);
}
