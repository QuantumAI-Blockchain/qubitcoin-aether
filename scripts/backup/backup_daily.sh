#!/bin/bash
# Daily backup script for Qubitcoin production node
# Dumps CockroachDB + copies RocksDB knowledge fabric
# Run via cron: 0 3 * * * /root/Qubitcoin/scripts/backup/backup_daily.sh

set -euo pipefail

BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting daily backup..."

# 1. CockroachDB dump
echo "  Dumping CockroachDB..."
docker exec qbc-cockroachdb cockroach dump qubitcoin --insecure \
    > "$BACKUP_DIR/cockroachdb_${DATE}.sql" 2>/dev/null || {
    # Fallback: use cockroach sql to export
    docker exec qbc-cockroachdb cockroach sql --insecure -e "BACKUP INTO 'nodelocal://1/backup_${DATE}'" 2>/dev/null || \
    echo "  WARNING: CockroachDB dump failed (container may not be running)"
}

# 2. RocksDB knowledge fabric (aether-mind data)
ROCKSDB_PATH="/root/Qubitcoin/aether_data"
if [ -d "$ROCKSDB_PATH" ]; then
    echo "  Backing up RocksDB knowledge fabric..."
    tar czf "$BACKUP_DIR/rocksdb_knowledge_${DATE}.tar.gz" -C "$(dirname $ROCKSDB_PATH)" "$(basename $ROCKSDB_PATH)" 2>/dev/null || \
    echo "  WARNING: RocksDB backup failed"
fi

# 3. Configuration backup (non-secret)
echo "  Backing up configuration..."
tar czf "$BACKUP_DIR/config_${DATE}.tar.gz" \
    -C /root/Qubitcoin \
    .env \
    docker-compose.yml \
    contract_registry.json \
    config/ \
    2>/dev/null || echo "  WARNING: Config backup failed"

# 4. Prune old backups
echo "  Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "*.sql" -mtime +${RETENTION_DAYS} -delete 2>/dev/null
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null

echo "[$(date)] Backup complete. Files in $BACKUP_DIR:"
ls -lh "$BACKUP_DIR"/*_${DATE}* 2>/dev/null || echo "  (no files created)"
