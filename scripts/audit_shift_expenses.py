"""Operator-only legacy inventory. Uses SELECTs in a database-enforced read-only transaction.

Run with the bench Python, not as a whitelisted web method. No Frappe page/controller,
setup hook, migration, attribution, posting or commit is invoked. The output contains
record identifiers and belongs in private operator storage, not public assets.
"""

import argparse
import json
from pathlib import Path

import pymysql


SCHEMA = {
    "POS Profile": {"posa_default_source_account", "posa_allow_source_account_override"},
    "POS Allowed Source Account": {"account"},
    "POS Allowed Expense Account": {"account"},
    "Quick Expense": {"entry_context", "client_request_id", "pos_opening_shift"},
    "Money Wallet": {"allow_desk_expenses"},
    "Money Wallet Expense Profile": {"pos_profile"},
    "Quick Expense Company Account": {"company", "expense_account"},
    "POS Closing Shift": {"shift_review", "review_status", "discrepancy_reason"},
    "POS Shift Review": {"snapshot_json", "snapshot_hash", "version"},
    "POS Shift Review Account": {"row_key", "remaining_amount"},
    "POS Shift Review Action": {"client_request_id", "request_fingerprint"},
    "POS Shift Source Claim": {"claim_key", "capacity", "allocated_amount"},
    "POS Shift Review Settings": {"company", "shortage_account", "surplus_account"},
}


def inventory(connection):
    """Read a consistent inventory; always roll back, including on query failure."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")

            def select(sql, args=()):
                cursor.execute(sql, args)
                return cursor.fetchall()

            columns = {}
            for row in select(
                "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()"
            ):
                columns.setdefault(row["TABLE_NAME"], set()).add(row["COLUMN_NAME"])

            def has(doctype, *fields):
                return set(fields).issubset(columns.get("tab" + doctype, set()))

            report = {
                "read_only": True,
                "missing_schema": {
                    dt: sorted(fields - columns.get("tab" + dt, set()))
                    for dt, fields in SCHEMA.items()
                    if not has(dt, *fields)
                },
                "notes": [
                    "Amounts below are stored document amounts, grouped by company and source; not a consolidated currency total.",
                    "No date/account inference assigns a legacy expense to a shift.",
                    "Historical closings without immutable evidence are not silently converted into new reviews.",
                ],
            }
            # A Frappe Table field has metadata and a child table, not a SQL
            # column on its parent. Check its Custom Field separately so a
            # successful source-field migration is not falsely reported missing.
            table_fields = {
                "posa_allowed_source_accounts": "POS Allowed Source Account",
                "posa_allowed_expense_accounts": "POS Allowed Expense Account",
            }
            configured = {}
            if has("Custom Field", "dt", "fieldname", "fieldtype", "options"):
                configured = {row["fieldname"]: row for row in select(
                    "SELECT fieldname, fieldtype, options FROM `tabCustom Field` "
                    "WHERE dt=%s AND fieldname IN (%s,%s)",
                    ("POS Profile", *table_fields),
                )}
            report["missing_table_fields"] = [
                field for field, child in table_fields.items()
                if configured.get(field, {}).get("fieldtype") != "Table"
                or configured.get(field, {}).get("options") != child
            ]
            for dt, account, extra in (
                ("Quick Expense", "paid_from", ""),
                ("POS Cash Movement", "source_account", " AND movement_type='Expense'"),
            ):
                if not has(dt, "pos_opening_shift", account, "company", "amount"):
                    report[dt] = {"unavailable": "Required legacy columns are absent"}
                    continue
                # Names are fixed above, never supplied by the operator.
                where = "docstatus=1 AND COALESCE(pos_opening_shift,'')=''" + extra
                report[dt] = {
                    "unassigned_totals": select(
                        f"SELECT company, `{account}` AS account, COUNT(*) AS records, SUM(amount) AS amount "
                        f"FROM `tab{dt}` WHERE {where} GROUP BY company, `{account}` ORDER BY company, `{account}`"
                    ),
                    "sample_limit": 100,
                    "unassigned_sample": select(
                        f"SELECT name, company, `{account}` AS account, amount FROM `tab{dt}` "
                        f"WHERE {where} ORDER BY creation, name LIMIT 100"
                    ),
                }
            if has("POS Closing Shift", "pos_opening_shift") and has("POS Closing Shift Detail", "difference"):
                no_review = (
                    " AND COALESCE(c.shift_review,'')=''"
                    if has("POS Closing Shift", "shift_review") else ""
                )
                report["historical_discrepancies"] = select(
                    "SELECT c.company, COUNT(DISTINCT c.name) AS closings, COUNT(*) AS method_differences "
                    "FROM `tabPOS Closing Shift` c JOIN `tabPOS Closing Shift Detail` d ON d.parent=c.name "
                    "AND d.parenttype='POS Closing Shift' WHERE c.docstatus=1 AND d.difference<>0"
                    + no_review + " GROUP BY c.company ORDER BY c.company"
                )
            if all(has(dt, *fields) for dt, fields in (
                ("POS Profile", ("disabled", "company")),
                ("POS Payment Method", ("mode_of_payment",)),
                ("Mode of Payment Account", ("company", "default_account")),
            )):
                report["shared_register_accounts"] = select(
                    "SELECT p.company, m.default_account AS account, COUNT(DISTINCT p.name) AS registers, "
                    "GROUP_CONCAT(DISTINCT p.name ORDER BY p.name SEPARATOR ', ') AS profiles "
                    "FROM `tabPOS Profile` p JOIN `tabPOS Payment Method` pm ON pm.parent=p.name "
                    "AND pm.parenttype='POS Profile' JOIN `tabMode of Payment Account` m "
                    "ON m.parent=pm.mode_of_payment AND m.company=p.company "
                    "WHERE p.disabled=0 AND COALESCE(m.default_account,'')<>'' "
                    "GROUP BY p.company, m.default_account HAVING COUNT(DISTINCT p.name)>1 "
                    "ORDER BY p.company, m.default_account"
                )
            if has("Money Wallet", "account", "company", "enabled"):
                report["wallet_aliases"] = select(
                    "SELECT company, account, COUNT(*) AS enabled_wallets FROM `tabMoney Wallet` "
                    "WHERE enabled=1 AND COALESCE(account,'')<>'' GROUP BY company, account "
                    "HAVING COUNT(*)>1 ORDER BY company, account"
                )
            return report
    finally:
        connection.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites-path", type=Path, required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--db-host", help="Optional operator connection address; does not edit site configuration")
    args = parser.parse_args()
    root = args.sites_path.resolve()
    site = (root / args.site).resolve()
    if site.parent != root:
        parser.error("--site must name a direct child of --sites-path")
    config = {}
    for path in (root / "common_site_config.json", site / "site_config.json"):
        if path.exists():
            config.update(json.loads(path.read_text()))
    connection = pymysql.connect(
        host=args.db_host or config.get("db_host") or "127.0.0.1",
        port=int(config.get("db_port") or 3306),
        user=config.get("db_user") or config["db_name"],
        password=config["db_password"], database=config["db_name"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5, read_timeout=30, write_timeout=5, autocommit=False,
    )
    try:
        print(json.dumps(inventory(connection), indent=2, ensure_ascii=False, default=str))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
