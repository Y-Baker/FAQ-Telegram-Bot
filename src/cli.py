#!/usr/bin/env python3
"""
Telegram FAQ Bot — CLI Utilities For Database Management
"""

import argparse
import os
from db import connect, init_db
from seed import migrate_qa, migrate_variants

from sentence_transformers import SentenceTransformer

def download_model(model_name: str = "all-MiniLM-L6-v2") -> None:
    """
    Download and save the SentenceTransformer model to a local directory.
    This is useful for offline usage or to avoid downloading it every time.
    """
    if not os.path.exists("./models"):
        os.makedirs("./models")
    
    # Ensure the model directory exists
    if not os.path.exists("./models/" + model_name):
        print(f"Downloading model '{model_name}'...")

    # Download and save locally
    model = SentenceTransformer("sentence-transformers/" + model_name)
    path = "./models/" + model_name
    model.save(path)
    print("Model downloaded and saved to ", path)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Telegram FAQ Bot — Setup Utilities")
    p.add_argument("--db", default="faq.db", help="Path to SQLite database file (default: faq.db)")
    p.add_argument("--init", action="store_true", help="Create tables/indexes if missing and exit")
    p.add_argument(
        "--migrate",
        metavar=("QA_JSON", "PARAPHRASES_JSON"),
        nargs=2,
        help="Seed Q&A and paraphrases from two JSON files: <qa.json> <paraphrases.json>"
    )
    p.add_argument("--nlp", metavar="MODEL", nargs="?", const="all-MiniLM-L6-v2", help="Download and initialize NLP model (default: all-MiniLM-L6-v2)")
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
        if len(args.migrate) != 2:
            print("Error: --migrate requires two arguments: <qa.json> <paraphrases.json>")
            return
        qa_json, paraphrases_json = args.migrate
        if not os.path.exists(qa_json) or not os.path.exists(paraphrases_json):
            print(f"Error: One or both files do not exist: {qa_json}, {paraphrases_json}")
            return
        
        inserted = migrate_qa(conn, qa_json)
        print(f"Inserted/updated records from {qa_json}: {inserted} new rows.")
        inserted = migrate_variants(conn, paraphrases_json)
        print(f"Inserted/updated paraphrases from {paraphrases_json}: {inserted} new rows.")
        print("Migration completed successfully.")


    if args.nlp:
        download_model(args.nlp)
        print(f"NLP model '{args.nlp}' initialized.")

    # If neither --init nor --migrate nor --nlp is specified, show help
    if not args.init and not args.migrate and not args.nlp:
        print("No action specified. Use --init or --migrate or --nlp. See --help for options.")


if __name__ == "__main__":
    main()

