#!/usr/bin/env python3
"""
Telegram FAQ Bot — CLI Utilities For Database Management
"""

import argparse
import os
from db import connect, init_db
from seed import migrate_qa

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Telegram FAQ Bot — Setup Utilities")
    p.add_argument("--db", default="faq.db", help="Path to SQLite database file (default: faq.db)")
    p.add_argument("--init", action="store_true", help="Create tables/indexes if missing and exit")
    p.add_argument("--migrate", metavar="JSON", help="Seed Q&A from JSON file")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    db_path = args.db
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = connect(db_path)
    init_db(conn)

    if args.init and not args.migrate:
        print(f"Initialized schema in {db_path}.")
        return

    if args.migrate:
        if not os.path.isfile(args.migrate):
            raise FileNotFoundError(f"Seed file {args.migrate} does not exist.")
        inserted = migrate_qa(conn, args.migrate)
        print(f"Migration complete. Inserted/updated records from {args.migrate}: {inserted} new rows.")


if __name__ == "__main__":
    main()

