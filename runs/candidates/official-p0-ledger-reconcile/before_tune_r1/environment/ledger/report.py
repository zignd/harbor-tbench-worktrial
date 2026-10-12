"""Generate per-merchant balance reports from the ledger."""
from .schema import get_connection, init_db
from .importer import import_exports


def compute_balances(conn):
    """Return a dict of {(merchant_id, currency): balance_minor}."""
    # Sum all charges per merchant/currency
    charge_rows = conn.execute(
        """SELECT merchant_id, currency, SUM(amount_minor) as total
           FROM charges
           GROUP BY merchant_id, currency"""
    ).fetchall()

    balances = {}
    for row in charge_rows:
        key = (row["merchant_id"], row["currency"])
        balances[key] = row["total"]

    # Subtract refunds: attribute each refund to the merchant of the matched charge.
    # Refunds with no matched charge fall back to the refund's own merchant_id.
    refund_rows = conn.execute(
        """SELECT
               COALESCE(c.merchant_id, r.merchant_id) AS eff_merchant,
               COALESCE(c.currency,   r.currency)    AS eff_currency,
               r.amount_minor
           FROM refunds r
           LEFT JOIN charges c ON r.charge_id = c.id"""
    ).fetchall()

    for row in refund_rows:
        key = (row["eff_merchant"], row["eff_currency"])
        balances[key] = balances.get(key, 0) - row["amount_minor"]

    return balances


def format_amount(amount_minor):
    """Format integer minor units as a decimal string."""
    sign = "-" if amount_minor < 0 else ""
    v = abs(amount_minor)
    return f"{sign}{v // 100}.{v % 100:02d}"


def run_report(exports_dir, db_path=None):
    """Import exports and print the per-merchant balance report."""
    import os
    from .schema import DB_PATH
    if db_path is None:
        db_path = os.environ.get("LEDGER_DB", DB_PATH)
    import_exports(exports_dir, db_path=db_path)
    conn = get_connection(db_path)
    init_db(conn)
    balances = compute_balances(conn)
    conn.close()

    if not balances:
        print("No transactions found.")
        return

    print(f"{"MERCHANT":<20} {"CURRENCY":<8} {"BALANCE"}")
    print("-" * 45)
    for (merchant_id, currency), amount_minor in sorted(balances.items()):
        amount_str = format_amount(amount_minor)
        print(f"{merchant_id:<20} {currency:<8} {amount_str}")
