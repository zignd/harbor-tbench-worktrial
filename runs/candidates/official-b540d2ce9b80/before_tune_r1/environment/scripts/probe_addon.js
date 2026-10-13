
#!/usr/bin/env node
// Helper script to explore the optimizer addon API.
// Run: node scripts/probe_addon.js

const addonPath = "/opt/native/optimizer.node";
let addon;
try {
  addon = require(addonPath);
} catch (e) {
  console.error("Failed to load addon:", e.message);
  process.exit(1);
}

console.log("Addon exports:", Object.keys(addon));

// Try configuring with various settings
const testDescriptors = [
  { id: "probe-1", type: "util", complexity_score: 10, has_side_effects: false },
  { id: "probe-2", type: "util", complexity_score: 25, has_side_effects: false },
  { id: "probe-3", type: "lib", complexity_score: 30, has_side_effects: false },
  { id: "probe-4", type: "lib", complexity_score: 50, has_side_effects: true },
  { id: "probe-5", type: "app", complexity_score: 10, has_side_effects: false },
  { id: "probe-6", type: "vendor", complexity_score: 10, has_side_effects: false },
];

const configs = [
  { elimination_gate: false, folding_threshold: 40, hoist_namespace: "lib" },
  { elimination_gate: true,  folding_threshold: 40, hoist_namespace: "lib" },
  { elimination_gate: true,  folding_threshold: 40, hoist_namespace: "lib+util" },
  { elimination_gate: true,  folding_threshold: 20, hoist_namespace: "lib" },
];

for (const cfg of configs) {
  console.log("
--- Config:", JSON.stringify(cfg));
  const opt = addon.configure(cfg);
  for (const desc of testDescriptors) {
    const result = opt.process(desc);
    console.log(`  ${desc.id} (${desc.type}/${desc.complexity_score}/${desc.has_side_effects}):`, result.passes.join(", ") || "(none)");
  }
}
