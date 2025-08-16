#!/usr/bin/env bash
set -euo pipefail

# Ensure data dir exists and DB file exists (so volume created with right permissions)
mkdir -p "/app/data"
touch "${DB_PATH:-/app/data/faq.db}"

# run the provided command
exec "$@"
