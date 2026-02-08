#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════"
echo "  GENERATING SSL CERTIFICATES FOR COCKROACHDB"
echo "════════════════════════════════════════════════════════════"

# Cleanup old certs
echo "[1/5] Cleaning old certificates..."
sudo rm -rf certs/ my-safe-directory/ 2>/dev/null || true
mkdir -p certs/{node1,node2,node3,client}
mkdir -p my-safe-directory

# Generate CA
echo "[2/5] Generating Certificate Authority (CA)..."
docker run --rm -v "$PROJECT_ROOT/certs:/certs" \
  -v "$PROJECT_ROOT/my-safe-directory:/safe" \
  cockroachdb/cockroach:v24.2.0 cert create-ca \
  --certs-dir=/certs \
  --ca-key=/safe/ca.key

# Fix CA permissions
sudo chown -R $USER:$USER certs/ my-safe-directory/

# Node 1 certificates
echo "[3/5] Generating Node 1 certificates..."
docker run --rm -v "$PROJECT_ROOT/certs:/certs" \
  -v "$PROJECT_ROOT/my-safe-directory:/safe" \
  cockroachdb/cockroach:v24.2.0 cert create-node \
  cockroach-1 \
  localhost \
  127.0.0.1 \
  --certs-dir=/certs \
  --ca-key=/safe/ca.key

sudo chown -R $USER:$USER certs/
cp certs/node.crt certs/node1/
cp certs/node.key certs/node1/
cp certs/ca.crt certs/node1/
rm certs/node.crt certs/node.key

# Node 2 certificates
echo "[3/5] Generating Node 2 certificates..."
docker run --rm -v "$PROJECT_ROOT/certs:/certs" \
  -v "$PROJECT_ROOT/my-safe-directory:/safe" \
  cockroachdb/cockroach:v24.2.0 cert create-node \
  cockroach-2 \
  localhost \
  127.0.0.1 \
  --certs-dir=/certs \
  --ca-key=/safe/ca.key

sudo chown -R $USER:$USER certs/
cp certs/node.crt certs/node2/
cp certs/node.key certs/node2/
cp certs/ca.crt certs/node2/
rm certs/node.crt certs/node.key

# Node 3 certificates
echo "[4/5] Generating Node 3 certificates..."
docker run --rm -v "$PROJECT_ROOT/certs:/certs" \
  -v "$PROJECT_ROOT/my-safe-directory:/safe" \
  cockroachdb/cockroach:v24.2.0 cert create-node \
  cockroach-3 \
  localhost \
  127.0.0.1 \
  --certs-dir=/certs \
  --ca-key=/safe/ca.key

sudo chown -R $USER:$USER certs/
cp certs/node.crt certs/node3/
cp certs/node.key certs/node3/
cp certs/ca.crt certs/node3/
rm certs/node.crt certs/node.key

# Client certificates
echo "[5/5] Generating client certificates..."
docker run --rm -v "$PROJECT_ROOT/certs:/certs" \
  -v "$PROJECT_ROOT/my-safe-directory:/safe" \
  cockroachdb/cockroach:v24.2.0 cert create-client \
  root \
  --certs-dir=/certs \
  --ca-key=/safe/ca.key

sudo chown -R $USER:$USER certs/
cp certs/client.root.crt certs/client/
cp certs/client.root.key certs/client/
cp certs/ca.crt certs/client/
rm certs/client.root.crt certs/client.root.key

# Final permission fix
sudo chown -R $USER:$USER certs/ my-safe-directory/
chmod 600 certs/*/node.key certs/client/client.root.key 2>/dev/null || true

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ CERTIFICATES GENERATED"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Certificate locations:"
echo "  • Node 1: certs/node1/"
echo "  • Node 2: certs/node2/"
echo "  • Node 3: certs/node3/"
echo "  • Client: certs/client/"
echo "  • CA Key: my-safe-directory/ca.key (BACKUP THIS!)"
echo ""
echo "⚠️  CRITICAL: Backup my-safe-directory/ca.key securely!"
echo ""
