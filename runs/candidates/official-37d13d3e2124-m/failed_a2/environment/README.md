Replay service operational notes

Run: /app/bin/replay INPUT_DIR OUTPUT_DIR

The four stages are decode/quarantine, normalize/deduplicate, session materialization, and metric aggregation. SQLite migration and query examples are in /app/sql. Source coordinates are relative paths and physical line numbers. The bundled fixture is intentionally small.
