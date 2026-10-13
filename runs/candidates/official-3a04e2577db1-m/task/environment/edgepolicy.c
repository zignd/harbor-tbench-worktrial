#include <sqlite3ext.h>
SQLITE_EXTENSION_INIT1
int edgepolicy_generation(sqlite3 *db) { (void)db; return 1; }
int sqlite3_edgepolicy_init(sqlite3 *db, char **err, const sqlite3_api_routines *api) { SQLITE_EXTENSION_INIT2(api); (void)db; (void)err; return SQLITE_OK; }
