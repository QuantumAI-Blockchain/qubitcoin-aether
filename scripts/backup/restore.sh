#!/bin/bash
# Restore script for Qubitcoin production node
# Usage: ./restore.sh <backup_date>  e.g. ./restore.sh 20260503_030000

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_date>"
    echo "  e.g. $0 20260503_030000"
    echo ""
    echo "Available backups:"
    ls /root/backups/cockroachdb_*.sql 2>/dev/null | sed 's/.*cockroachdb_//;s/.sql//' || echo "  (none found)"
    exit 1
fi

DATE="$1"
BACKUP_DIR="/root/backups"

echo "=== Qubitcoin Restore ==="
echo "Restoring from backup: $DATE"
echo ""

# 1. Restore CockroachDB
DB_BACKUP="$BACKUP_DIR/cockroachdb_${DATE}.sql"
if [ -f "$DB_BACKUP" ]; then
    echo "Restoring CockroachDB..."
    echo "  WARNING: This will DROP and recreate the qubitcoin database!"
    read -p "  Continue? [y/N] " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker exec -i qbc-cockroachdb cockroach sql --insecure -e "DROP DATABASE IF EXISTS qubitcoin CASCADE"
        docker exec -i qbc-cockroachdb cockroach sql --insecure -e "CREATE DATABASE qubitcoin"
        docker exec -i qbc-cockroachdb cockroach sql --insecure -d qubitcoin < "$DB_BACKUP"
        echo "  CockroachDB restored."
    else
        echo "  Skipped CockroachDB restore."
    fi
else
    echo "  No CockroachDB backup found for $DATE"
fi

# 2. Restore RocksDB knowledge fabric
ROCKS_BACKUP="$BACKUP_DIR/rocksdb_knowledge_${DATE}.tar.gz"
if [ -f "$ROCKS_BACKUP" ]; then
    echo "Restoring RocksDB knowledge fabric..."
    echo "  WARNING: This will overwrite the current knowledge fabric!"
    read -p "  Continue? [y/N] " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        systemctl stop aether-mind 2>/dev/null || true
        tar xzf "$ROCKS_BACKUP" -C /root/Qubitcoin/
        systemctl start aether-mind 2>/dev/null || true
        echo "  RocksDB restored."
    else
        echo "  Skipped RocksDB restore."
    fi
else
    echo "  No RocksDB backup found for $DATE"
fi

echo ""
echo "Restore complete. Verify services:"
echo "  systemctl status qbc-substrate aether-mind"
echo "  curl -s localhost:5000/chain/info | python3 -m json.tool"
