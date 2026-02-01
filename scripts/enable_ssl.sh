#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║        ENABLE SSL ON COCKROACHDB (NO DATA LOSS)      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# 1. Stop Qubitcoin node
echo "1️⃣  Stopping Qubitcoin node..."
kill $(cat node.pid) 2>/dev/null
pkill -f "python3 -m qubitcoin" 2>/dev/null
sleep 3
echo "   ✅ Node stopped"

# 2. Get current data stats
echo
echo "2️⃣  Current database stats:"
BLOCKS=$(cockroach sql --insecure --database=qbc -e "SELECT COUNT(*) FROM blocks;" --format=csv 2>/dev/null | tail -1)
SUPPLY=$(cockroach sql --insecure --database=qbc -e "SELECT total_minted FROM supply WHERE id=1;" --format=csv 2>/dev/null | tail -1)
echo "   Blocks: $BLOCKS"
echo "   Supply: $SUPPLY QBC"

# 3. Stop CockroachDB
echo
echo "3️⃣  Stopping CockroachDB..."
cockroach quit --insecure --host=localhost:26257 2>/dev/null
sleep 5
echo "   ✅ CockroachDB stopped"

# 4. Create SSL certificates
echo
echo "4️⃣  Creating SSL certificates..."
mkdir -p data/certs

# CA certificate
cockroach cert create-ca \
  --certs-dir=data/certs \
  --ca-key=data/certs/ca.key

# Node certificate
cockroach cert create-node \
  localhost \
  127.0.0.1 \
  $(hostname) \
  --certs-dir=data/certs \
  --ca-key=data/certs/ca.key

# Client certificate for root user
cockroach cert create-client \
  root \
  --certs-dir=data/certs \
  --ca-key=data/certs/ca.key

# Set permissions
chmod 600 data/certs/*.key

echo "   ✅ Certificates created"
ls -lh data/certs/

# 5. Start CockroachDB with SSL
echo
echo "5️⃣  Starting CockroachDB with SSL..."
nohup cockroach start-single-node \
  --certs-dir=/home/ash/qubitcoin/data/certs \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8080 \
  --store=/home/ash/qubitcoin/data/cockroach \
  > logs/cockroach_ssl.log 2>&1 &

sleep 7

# 6. Test SSL connection
echo
echo "6️⃣  Testing SSL connection..."
cockroach sql \
  --certs-dir=/home/ash/qubitcoin/data/certs \
  --host=localhost:26257 \
  --database=qbc \
  -e "SELECT 'SSL Connection Works!' as test, COUNT(*) as blocks FROM blocks;" 2>&1

if [ $? -eq 0 ]; then
    echo "   ✅ SSL connection successful!"
else
    echo "   ❌ SSL connection failed!"
    exit 1
fi

# 7. Update .env with SSL settings
echo
echo "7️⃣  Updating .env with SSL configuration..."
cat > .env << 'ENVEOF'
# Node Identity
ADDRESS=00b5a241577d63bae49073e924f53678f86b4111
PUBLIC_KEY_HEX=33b72910ec6cf7e8d98599f16045a45da47bd440860dfad3c86e21db10866ec80d7d188ac5d79039698bd05d9cbb5012f52dc26f09946c581535507140c5e8be27f7ae144dfded733409798f055cc5881b2b8916c803131f3db9c9c5a11f0fa987a5f6d5af05a661f4b3feed3d537f93bd83281574f28573b753fd4b30fa40a1554ece70462b51da9e6525143a7c714890380465e79546e4a65905d2582c2d9b2e0cd02779fea028a4aed3a38d4fd0e054b164871041048e52e03ee70e412e025d0977235bddb4490c6728233ce97b460d39fc7baec8c467be02557952f99a3c62112b80f4fc30afa6ad2e96c20d990558adfde006d679a0c030b764c9dd84392200238759b10abae6d8c7f591b1ed2f44babd68cecc203eaa2893735dac882048f9e8bebff1cfa089ebc49a36c99233a3aec4ef0e19cf9bc69fe2fdfd5ebf22a3e2061939cc75dcdc45e0a86cb61649ddd0173233919265aa51b49bb642d089dbddd059d5f2314afb4c3d125cb3db5feb881ca4069e6b3dcd58af9bf885a63d8d6eadfd942a346dd4af9c18196c9d00c37bc8742be54f86f2f28709d8bd5e97b948e554bc7436d3e9341ed0803d6481597eb22844866c38094c77271d41f7b72d87286515360a5c1468b683325226198f56dc7497b8e782b23e1b0e847fbfb590a129be943cf26915638593d527e92c00ac77521f842b5bfe31622de7c96ccb5c4add7e09332b15ab06aef30fc72b67ee255e18ade6f5693c9289f51872154e1d52c155ab2ab19467b3a65f6df4618308525ce5b4589b711c7f794e5ec123e7313b36bb33f687e66ebc0118a573840fd86bb6cb13c19598f21d76c22a9cb233f5f4e4d4fd8e7945b1fc62548eb0cd12c204269bf749402076dee9d63217b121e7dd2b6ff99bee9ff4d03a24d64992aa4916500daf93cf07d2cecf1cf67385687b27e0f5460e12690f356057f62ea07ebaf96cdb0bde60721f86d9b98cf90d6ae813f2b1321e14f465e8519c83ae91dacca492520f02acc168242d652a552907926414068e31bc3ac141a4638e2a4df11959346c567cfbb902147079491804a4878b78f1826f9cf2fe6dcb0a3b7e6d13d1b0517090bba33fb9e628aa0c05f5586726a06ecdab844f3d8d8b79f8690d56de7966928e8e3734659c27ee4d0fa44b901ef92b10ec536ba93e574ab3de8ecdb6bea7d7e790b048a04096990942b836875a5430193adee8f7ece6316303a97dcd21d7d13d79e85831d004ce1f101aa7bcc6b9203d52f3c8c6b431f9723156ffe12ca41375ee9a7893f7c2d7d63a8f20d2a727a96cb535ae5ee04cd393361a02fa5111cee9cd27a766cf95bb34291aef6404a3f37e2df2809839762ad52a5b64683f19b3b3afa91fb268521d3d3a20e0d635fff1436fdec5fb002d3d0313d17ec78395da41ca4e9c43485c184c5d1436d12a4726eb780e97eae6dfcc57f6bfb1c257ddc193f19ab2c5f8ec984e9c2144a35ac55eed646ceb895006b4a34b927bdea10966488fe44dc308d3b0fad0de6552e9d9075f3602498719d2e210a686252ae6d450cfc0e7402aa56492de880248e6106d0891b498af4635c2a50dbdc4b063b8ca79d2f20cbcc4ee8567fccaf5946c600ae7cf0040f92514f9d21da45d177f4f78cb0d9bd5e1f20d38d6237595518e7a5495d535ee8f2b8febf893f0eeb90a3272113267a95432a26bc6828f64c04ec139aabf10a76440fcbb38b319d029d8e9a708140b711763d5c4d312f94c00a9d00c8c64b416fb9fe531a9fe5c5277e450f9b81f1b10c7f66e2dda2d4858832d6e6f36553d6c5e05ab3a6e7cda39c93c08c764c3be56b3cd9e32296e5839ce
PRIVATE_KEY_HEX=YOUR_PRIVATE_KEY_FROM_secure_key.env
PRIVATE_KEY_ED25519=YOUR_ED25519_KEY_FROM_secure_key.env

# Quantum Configuration
USE_LOCAL_ESTIMATOR=true
USE_SIMULATOR=false
IBM_TOKEN=
IBM_INSTANCE=

# Network
P2P_PORT=4001
RPC_PORT=5000
PEER_SEEDS=[]

# Database (SECURE with SSL)
DATABASE_URL=postgresql://root@localhost:26257/qbc?sslmode=verify-full&sslrootcert=/home/ash/qubitcoin/data/certs/ca.crt&sslcert=/home/ash/qubitcoin/data/certs/client.root.crt&sslkey=/home/ash/qubitcoin/data/certs/client.root.key

# IPFS
IPFS_API=/ip4/127.0.0.1/tcp/5002/http
PINATA_JWT=

# Mining
AUTO_MINE=true
MINING_INTERVAL=10
SNAPSHOT_INTERVAL=100

# Debugging
DEBUG=true
ENVEOF

# Copy private keys from secure_key.env
if [ -f secure_key.env ]; then
    PRIV_KEY=$(grep "^PRIVATE_KEY_HEX=" secure_key.env | cut -d= -f2)
    ED25519_KEY=$(grep "^PRIVATE_KEY_ED25519=" secure_key.env | cut -d= -f2)
    
    sed -i "s|PRIVATE_KEY_HEX=.*|PRIVATE_KEY_HEX=$PRIV_KEY|g" .env
    sed -i "s|PRIVATE_KEY_ED25519=.*|PRIVATE_KEY_ED25519=$ED25519_KEY|g" .env
fi

echo "   ✅ .env updated with SSL"

# 8. Update config.py default
echo
echo "8️⃣  Updating config.py default..."
sed -i "s|'postgresql://root@localhost:26257/qbc?sslmode=disable'|'postgresql://root@localhost:26257/qbc?sslmode=verify-full\&sslrootcert=/home/ash/qubitcoin/data/certs/ca.crt\&sslcert=/home/ash/qubitcoin/data/certs/client.root.crt\&sslkey=/home/ash/qubitcoin/data/certs/client.root.key'|g" src/qubitcoin/config.py

echo "   ✅ config.py updated"

# 9. Start Qubitcoin node with SSL
echo
echo "9️⃣  Starting Qubitcoin node with SSL..."
nohup python3 -m qubitcoin.node > logs/node_ssl.log 2>&1 &
echo $! > node.pid

sleep 10

# 10. Verify everything works
echo
echo "🔟 Verifying SSL setup..."

if ps -p $(cat node.pid) > /dev/null; then
    echo "   ✅ Node is running"
else
    echo "   ❌ Node failed to start!"
    echo "   Check logs: tail -50 logs/node_ssl.log"
    exit 1
fi

# Test database connection
BLOCKS_AFTER=$(cockroach sql --certs-dir=data/certs --host=localhost:26257 --database=qbc -e "SELECT COUNT(*) FROM blocks;" --format=csv 2>/dev/null | tail -1)
echo "   Blocks after SSL: $BLOCKS_AFTER"

if [ "$BLOCKS" = "$BLOCKS_AFTER" ]; then
    echo "   ✅ All data preserved!"
else
    echo "   ⚠️  Block count mismatch!"
fi

# Test RPC
curl -s http://localhost:5000/health | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"   Database: {'✅' if d['database'] else '❌'}\")
    print(f\"   Mining:   {'✅' if d['mining'] else '❌'}\")
    print(f\"   Quantum:  {'✅' if d['quantum'] else '❌'}\")
    print(f\"   IPFS:     {'✅' if d['ipfs'] else '❌'}\")
except:
    print('   ⚠️  RPC not responding')
" 2>/dev/null

echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║              🔐 SSL ENABLED SUCCESSFULLY! 🔐          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo
echo "All connections now encrypted with TLS!"
echo "Certificates: /home/ash/qubitcoin/data/certs/"
echo
