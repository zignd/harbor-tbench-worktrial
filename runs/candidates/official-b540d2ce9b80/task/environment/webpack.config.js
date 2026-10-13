
const path = require("path");
const fs = require("fs");
const { execSync } = require("child_process");

// Module descriptor metadata for entry points
// These are used by the preprocessor to determine optimization passes
const MODULE_DESCRIPTORS = [
  { id: "alpha",   type: "util",   complexity_score: 10, has_side_effects: false },
  { id: "beta",    type: "lib",    complexity_score: 15, has_side_effects: false },
  { id: "gamma",   type: "util",   complexity_score: 5,  has_side_effects: false },
  { id: "delta",   type: "lib",    complexity_score: 30, has_side_effects: false },
  { id: "epsilon", type: "util",   complexity_score: 18, has_side_effects: false },
  { id: "zeta",    type: "lib",    complexity_score: 8,  has_side_effects: true  },
  { id: "eta",     type: "app",    complexity_score: 12, has_side_effects: false },
  { id: "theta",   type: "vendor", complexity_score: 22, has_side_effects: true  },
];

// Run the Python preprocessor to compute optimization passes
// NOTE: This uses subprocess to call preprocess.py
function runPreprocessor(descriptors) {
  const tmpFile = "/tmp/module_descriptors.json";
  fs.writeFileSync(tmpFile, JSON.stringify(descriptors));

  try {
    // Call Python preprocessor
    const output = execSync(
      `python /app/scripts/preprocess.py ${tmpFile}`,
      { encoding: "utf8" }
    );
    return JSON.parse(output);
  } catch (err) {
    throw new Error(`Preprocessor failed: ${err.message}`);
  }
}

class OptimizerPlugin {
  apply(compiler) {
    compiler.hooks.afterEmit.tap("OptimizerPlugin", (compilation) => {
      let passAssignments;
      try {
        passAssignments = runPreprocessor(MODULE_DESCRIPTORS);
      } catch (err) {
        console.error("[OptimizerPlugin] Failed to run preprocessor:", err.message);
        passAssignments = MODULE_DESCRIPTORS.map(d => ({ id: d.id, passes: [] }));
      }

      const manifest = {
        generated: new Date().toISOString(),
        modules: passAssignments
      };

      const distDir = path.join(__dirname, "dist");
      if (!fs.existsSync(distDir)) {
        fs.mkdirSync(distDir, { recursive: true });
      }
      fs.writeFileSync(
        path.join(distDir, "manifest.json"),
        JSON.stringify(manifest, null, 2)
      );
      console.log("[OptimizerPlugin] Manifest written to dist/manifest.json");
    });
  }
}

module.exports = {
  mode: "production",
  entry: {
    alpha:   "./src/alpha.js",
    beta:    "./src/beta.js",
    gamma:   "./src/gamma.js",
    delta:   "./src/delta.js",
    epsilon: "./src/epsilon.js",
    zeta:    "./src/zeta.js",
    eta:     "./src/eta.js",
    theta:   "./src/theta.js",
  },
  output: {
    path: path.join(__dirname, "dist"),
    filename: "[name].bundle.js",
  },
  plugins: [new OptimizerPlugin()],
};
