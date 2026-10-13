We're migrating our webpack build to use the new optimizer addon at /opt/native/optimizer.node instead of the old Python preprocessor. Wire up the addon in webpack.config.js so the build pipeline produces correct output bundles.

The old preprocessor in scripts/preprocess.py defines which modules get which optimization passes. The new addon should produce identical pass assignments for each module, but it uses a different configuration system that you will need to figure out by experimenting with it. When the build finishes, /dist/manifest.json must list every entry module with its assigned optimization passes matching what the old preprocessor would have produced.

Configure the addon so that running `node scripts/verify_build.js` exits 0. That script generates fresh module descriptors at verify time and checks that the addon output matches the preprocessor for each one.

Requirements:
- webpack.config.js must load and use the addon at /opt/native/optimizer.node to assign optimization passes; it must not invoke the Python preprocessor via subprocess
- webpack.config.js must export a `getOptimizer()` function that returns the configured optimizer instance (the verify script uses this)
- Running `npx webpack --config webpack.config.js` must succeed and write /dist/manifest.json
- /dist/manifest.json must be valid JSON and contain an entry for each of the 8 entry modules (alpha, beta, gamma, delta, epsilon, zeta, eta, theta) with their assigned passes
- `node scripts/verify_build.js` must exit 0
