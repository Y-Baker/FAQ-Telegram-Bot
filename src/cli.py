#!/usr/bin/env python3
"""
Telegram FAQ Bot — CLI Utilities For Database Management
"""

import argparse
import os
from db import connect, init_db
from seed import migrate_qa

from sentence_transformers import SentenceTransformer

def download_model():
    """
    Download and save the SentenceTransformer model to a local directory.
    This is useful for offline usage or to avoid downloading it every time.
    """
    if not os.path.exists("./models"):
        os.makedirs("./models")
    
    # Ensure the model directory exists
    if not os.path.exists("./models/all-MiniLM-L6-v2"):
        print("Downloading SentenceTransformer model...")

    # Download and save locally
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    model.save("./models/all-MiniLM-L6-v2")
    print("Model downloaded and saved to ./models/all-MiniLM-L6-v2.")

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Telegram FAQ Bot — Setup Utilities")
    p.add_argument("--db", default="faq.db", help="Path to SQLite database file (default: faq.db)")
    p.add_argument("--init", action="store_true", help="Create tables/indexes if missing and exit")
    p.add_argument("--migrate", metavar="JSON", help="Seed Q&A from JSON file")
    p.add_argument("--nlp", action="store_true", help="Initialize NLP model (if needed)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = connect(db_path)

    # Initialize database schema if requested
    if args.init:
        init_db(conn)
        print(f"Initialized schema in {db_path}.")

    # Migrate Q&A data if requested
    if args.migrate:
        if not os.path.isfile(args.migrate):
            raise FileNotFoundError(f"Seed file {args.migrate} does not exist.")
        inserted = migrate_qa(conn, args.migrate)
        print(f"Migration complete. Inserted/updated records from {args.migrate}: {inserted} new rows.")

    if args.nlp:
        download_model()
        print("NLP model initialized.")

    # If neither --init nor --migrate is specified, show help
    if not args.init and not args.migrate and not args.nlp:
        print("No action specified. Use --init or --migrate or --nlp. See --help for options.")


if __name__ == "__main__":
    main()

