SCHEMA_VERSION=3
MIGRATIONS=('events','delivery index','report metadata')
def describe():
    return {'version':SCHEMA_VERSION,'migrations':list(MIGRATIONS)}
