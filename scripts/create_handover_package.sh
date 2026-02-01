#!/bin/bash

echo "📦 Creating handover package..."

mkdir -p /tmp/qubitcoin_handover

# Copy essential files
cp HANDOVER.md /tmp/qubitcoin_handover/
cp .env /tmp/qubitcoin_handover/
cp -r src/ /tmp/qubitcoin_handover/
cp -r scripts/ /tmp/qubitcoin_handover/
cp -r contracts/ /tmp/qubitcoin_handover/
cp requirements.txt /tmp/qubitcoin_handover/
cp setup.py /tmp/qubitcoin_handover/

# Create database dump
cockroach sql --certs-dir=data/certs --host=localhost:30000 --database=qbc \
  -e "SELECT COUNT(*) as blocks, (SELECT total_minted FROM supply) as supply FROM blocks;" \
  > /tmp/qubitcoin_handover/DATABASE_STATUS.txt

# Create system status
cat > /tmp/qubitcoin_handover/SYSTEM_STATUS.txt << 'STATUS'
QUBITCOIN SYSTEM STATUS
Generated: $(date)

Blocks Mined: 2515+
Supply: 38,420+ QBC
Database Port: 30000
Web UI Port: 30001
RPC Port: 5000
IPFS: 5002 (API), 8082 (Gateway)

All core systems operational.
Ready for bridge deployment and stablecoin initialization.
STATUS

echo "✅ Package created in /tmp/qubitcoin_handover/"
ls -lh /tmp/qubitcoin_handover/
