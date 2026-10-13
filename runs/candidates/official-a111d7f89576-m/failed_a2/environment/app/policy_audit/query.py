from pathlib import Path
SQL = (Path(__file__).with_name('query.sql')).read_text()
def export_rows(connection, since, until):
    return connection.execute(SQL, (since, until))
